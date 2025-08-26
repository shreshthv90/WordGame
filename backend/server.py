from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
import random
import time
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Set, Optional
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Scrabble tile distribution
SCRABBLE_TILES = {
    'A': 9, 'B': 2, 'C': 2, 'D': 4, 'E': 12, 'F': 2, 'G': 3, 'H': 2,
    'I': 9, 'J': 1, 'K': 1, 'L': 4, 'M': 2, 'N': 6, 'O': 8, 'P': 2,
    'Q': 1, 'R': 6, 'S': 4, 'T': 6, 'U': 4, 'V': 2, 'W': 2, 'X': 1, 'Y': 2, 'Z': 1
}

# Scrabble tile scores
SCRABBLE_SCORES = {
    'A': 1, 'E': 1, 'I': 1, 'O': 1, 'U': 1, 'L': 1, 'N': 1, 'S': 1, 'T': 1, 'R': 1,
    'D': 2, 'G': 2,
    'B': 3, 'C': 3, 'M': 3, 'P': 3,
    'F': 4, 'H': 4, 'V': 4, 'W': 4, 'Y': 4,
    'K': 5,
    'J': 8, 'X': 8,
    'Q': 10, 'Z': 10
}

# Basic word dictionary (simplified for MVP)
VALID_WORDS = {
    'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'HAD', 'BY', 'WORD',
    'WHAT', 'SAID', 'EACH', 'WHICH', 'SHE', 'DO', 'HOW', 'THEIR', 'IF', 'WILL', 'UP', 'OTHER', 'ABOUT', 'OUT',
    'MANY', 'THEN', 'THEM', 'THESE', 'SO', 'SOME', 'HER', 'WOULD', 'MAKE', 'LIKE', 'INTO', 'TIME', 'HAS', 'TWO',
    'MORE', 'VERY', 'AFTER', 'WORDS', 'LONG', 'JUST', 'WHERE', 'THROUGH', 'MUCH', 'BEFORE', 'LINE', 'RIGHT',
    'TOO', 'MEANS', 'OLD', 'ANY', 'SAME', 'TELL', 'BOY', 'FOLLOW', 'CAME', 'WANT', 'SHOW', 'ALSO', 'AROUND',
    'FARM', 'THREE', 'SMALL', 'SET', 'PUT', 'END', 'WHY', 'AGAIN', 'TURN', 'HERE', 'OFF', 'WENT', 'OLD', 'NUMBER',
    'GREAT', 'TELL', 'MEN', 'SAY', 'SMALL', 'EVERY', 'FOUND', 'STILL', 'BETWEEN', 'NAME', 'SHOULD', 'HOME',
    'BIG', 'GIVE', 'AIR', 'LINE', 'SET', 'OWN', 'UNDER', 'READ', 'LAST', 'NEVER', 'US', 'LEFT', 'END', 'ALONG',
    'WHILE', 'MIGHT', 'NEXT', 'SOUND', 'BELOW', 'SAW', 'SOMETHING', 'THOUGHT', 'BOTH', 'FEW', 'THOSE', 'ALWAYS',
    'LOOKED', 'SHOW', 'LARGE', 'OFTEN', 'TOGETHER', 'ASKED', 'HOUSE', 'WORLD', 'GOING', 'WANT', 'SCHOOL',
    'IMPORTANT', 'UNTIL', 'FORM', 'FOOD', 'KEEP', 'CHILDREN', 'FEET', 'LAND', 'SIDE', 'WITHOUT', 'BOY', 'ONCE',
    'ANIMAL', 'LIFE', 'ENOUGH', 'TOOK', 'FOUR', 'HEAD', 'ABOVE', 'KIND', 'BEGAN', 'ALMOST', 'LIVE', 'PAGE',
    'GOT', 'EARTH', 'NEED', 'FAR', 'HAND', 'HIGH', 'YEAR', 'MOTHER', 'LIGHT', 'COUNTRY', 'FATHER', 'LET', 'NIGHT',
    'PICTURE', 'BEING', 'STUDY', 'SECOND', 'SOON', 'STORY', 'SINCE', 'WHITE', 'EVER', 'PAPER', 'HARD', 'NEAR',
    'SENTENCE', 'BETTER', 'BEST', 'ACROSS', 'DURING', 'TODAY', 'HOWEVER', 'SURE', 'KNEW', 'ITS', 'TRYING', 'HORSE',
    'WATCH', 'TREE', 'LETTER', 'NOW', 'COLOR', 'WOOD', 'MAIN', 'NEAR', 'TOOK', 'SCIENCE', 'EAT', 'ROOM', 'FRIEND',
    'BEGAN', 'IDEA', 'FISH', 'MOUNTAIN', 'STOP', 'ONCE', 'BASE', 'HEAR', 'USUALLY', 'MARK', 'MUSIC', 'THOSE'
}

# Game state storage
games: Dict[str, dict] = {}
connections: Dict[str, List[WebSocket]] = {}

class GameState:
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.players = {}  # {websocket_id: {"name": str, "score": int}}
        self.letters_on_table = []  # List of available letters
        self.deck = self._create_deck()
        self.game_started = False
        self.game_ended = False
        self.last_letter_time = None
        self.last_word_time = None
        self.timer_task = None

    def _create_deck(self) -> List[str]:
        deck = []
        for letter, count in SCRABBLE_TILES.items():
            deck.extend([letter] * count)
        random.shuffle(deck)
        return deck

    def add_letter_to_table(self):
        if self.deck and len(self.letters_on_table) < 26:
            letter = self.deck.pop()
            self.letters_on_table.append({
                'letter': letter,
                'id': str(uuid.uuid4()),
                'timestamp': time.time()
            })
            self.last_letter_time = time.time()
            return letter
        return None

    def can_form_word(self, selected_letters: List[str], word: str) -> bool:
        if len(word) < 3 or len(word) > 6:
            return False
        if word.upper() not in VALID_WORDS:
            return False
        
        word_letters = list(word.upper())
        available_letters = [l['letter'] for l in self.letters_on_table if l['id'] in selected_letters]
        
        for letter in word_letters:
            if letter in available_letters:
                available_letters.remove(letter)
            else:
                return False
        return True

    def remove_letters(self, letter_ids: List[str]):
        self.letters_on_table = [l for l in self.letters_on_table if l['id'] not in letter_ids]
        self.last_word_time = time.time()

    def calculate_word_score(self, word: str) -> int:
        return sum(SCRABBLE_SCORES[letter.upper()] for letter in word)

    def should_end_game(self) -> bool:
        # Game ends if deck is empty or 26 letters on table with 26 seconds timeout
        if not self.deck:
            return True
        if len(self.letters_on_table) >= 26:
            if self.last_word_time:
                return time.time() - self.last_word_time >= 26
            elif self.last_letter_time:
                return time.time() - self.last_letter_time >= 26
        return False

# Connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_code: str):
        await websocket.accept()
        if room_code not in self.active_connections:
            self.active_connections[room_code] = []
        self.active_connections[room_code].append(websocket)

    def disconnect(self, websocket: WebSocket, room_code: str):
        if room_code in self.active_connections:
            self.active_connections[room_code].remove(websocket)

    async def broadcast_to_room(self, message: dict, room_code: str):
        if room_code in self.active_connections:
            for connection in self.active_connections[room_code]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    pass

manager = ConnectionManager()

# Models
class JoinRoomRequest(BaseModel):
    room_code: str
    player_name: str

class WordSubmission(BaseModel):
    word: str
    selected_letter_ids: List[str]

# API Routes
@api_router.get("/")
async def root():
    return {"message": "WordSmith Game Server"}

@api_router.post("/create-room")
async def create_room():
    room_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
    games[room_code] = GameState(room_code)
    return {"room_code": room_code}

# WebSocket endpoint
@api_router.websocket("/ws/{room_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str):
    await manager.connect(websocket, room_code)
    
    if room_code not in games:
        games[room_code] = GameState(room_code)
    
    game = games[room_code]
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "join":
                player_name = message["player_name"]
                websocket_id = str(id(websocket))
                game.players[websocket_id] = {"name": player_name, "score": 0}
                
                await manager.broadcast_to_room({
                    "type": "player_joined",
                    "player_name": player_name,
                    "players": list(game.players.values())
                }, room_code)
                
                # Send current game state to new player
                await websocket.send_text(json.dumps({
                    "type": "game_state",
                    "letters": game.letters_on_table,
                    "players": list(game.players.values()),
                    "game_started": game.game_started
                }))
                
            elif message["type"] == "start_game":
                if not game.game_started:
                    game.game_started = True
                    # Start letter generation timer
                    asyncio.create_task(letter_generation_timer(room_code))
                    
                    await manager.broadcast_to_room({
                        "type": "game_started"
                    }, room_code)
                    
            elif message["type"] == "submit_word":
                word = message["word"]
                selected_ids = message["selected_letter_ids"]
                player_id = str(id(websocket))
                
                if game.can_form_word(selected_ids, word):
                    score = game.calculate_word_score(word)
                    game.players[player_id]["score"] += score
                    game.remove_letters(selected_ids)
                    
                    await manager.broadcast_to_room({
                        "type": "word_accepted",
                        "word": word.upper(),
                        "player": game.players[player_id]["name"],
                        "score": score,
                        "letters": game.letters_on_table,
                        "players": list(game.players.values())
                    }, room_code)
                else:
                    await websocket.send_text(json.dumps({
                        "type": "word_rejected",
                        "word": word,
                        "reason": "Invalid word or letters not available"
                    }))
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        # Remove player from game
        websocket_id = str(id(websocket))
        if websocket_id in game.players:
            player_name = game.players[websocket_id]["name"]
            del game.players[websocket_id]
            await manager.broadcast_to_room({
                "type": "player_left",
                "player_name": player_name,
                "players": list(game.players.values())
            }, room_code)

async def letter_generation_timer(room_code: str):
    """Add letters to table every 4 seconds"""
    game = games.get(room_code)
    if not game:
        return
        
    while game.game_started and not game.should_end_game():
        letter = game.add_letter_to_table()
        if letter:
            await manager.broadcast_to_room({
                "type": "new_letter",
                "letter": letter,
                "letters": game.letters_on_table
            }, room_code)
        
        if game.should_end_game():
            game.game_ended = True
            await manager.broadcast_to_room({
                "type": "game_ended",
                "final_scores": list(game.players.values())
            }, room_code)
            break
            
        await asyncio.sleep(4)

# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()