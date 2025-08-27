from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Cookie, Response
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
import requests
from datetime import datetime, timezone, timedelta
from dictionary import is_valid_word, get_words_by_length, ALL_WORDS

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Database setup
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(MONGO_URL)
db = client.word_rush_db
users_collection = db.users
sessions_collection = db.sessions
game_history_collection = db.game_history

# Authentication Models
class User(BaseModel):
    id: str
    email: str
    name: str
    picture: str
    created_at: datetime
    total_games: int = 0
    total_wins: int = 0
    total_score: int = 0
    elo_rating: int = 1000  # Starting ELO rating

class Session(BaseModel):
    session_token: str
    user_id: str
    expires_at: datetime
    created_at: datetime

class GameHistoryEntry(BaseModel):
    game_id: str
    user_id: str
    room_code: str
    final_score: int
    placement: int  # 1st, 2nd, 3rd, etc.
    word_length: int
    timer_minutes: int
    opponent_count: int
    elo_change: int
    new_elo_rating: int
    played_at: datetime

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Authentication Functions
async def verify_session_token(session_token: Optional[str] = Cookie(None)) -> Optional[User]:
    """Verify session token and return user data"""
    if not session_token:
        return None
    
    # Check if session exists and is valid
    session = await sessions_collection.find_one({
        "session_token": session_token,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not session:
        return None
    
    # Get user data
    user = await users_collection.find_one({"id": session["user_id"]})
    if not user:
        return None
    
    return User(**user)

async def get_current_user(session_token: Optional[str] = Cookie(None)) -> User:
    """Get current authenticated user (raises exception if not authenticated)"""
    user = await verify_session_token(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

async def get_optional_user(session_token: Optional[str] = Cookie(None)) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    return await verify_session_token(session_token)

def calculate_elo_change(winner_elo: int, loser_elo: int, k_factor: int = 32) -> tuple[int, int]:
    """Calculate ELO rating changes for winner and loser"""
    expected_score_winner = 1 / (1 + 10**((loser_elo - winner_elo) / 400))
    expected_score_loser = 1 - expected_score_winner
    
    winner_change = round(k_factor * (1 - expected_score_winner))
    loser_change = round(k_factor * (0 - expected_score_loser))
    
    return winner_change, loser_change

# Authentication API Routes
@api_router.post("/auth/profile")
async def create_profile(session_id: str, response: Response):
    """Handle profile creation after OAuth redirect"""
    try:
        # Call Emergent auth API to get user data
        headers = {"X-Session-ID": session_id}
        auth_response = requests.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers=headers
        )
        
        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        user_data = auth_response.json()
        
        # Check if user already exists
        existing_user = await users_collection.find_one({"email": user_data["email"]})
        
        if not existing_user:
            # Create new user
            new_user = {
                "id": user_data["id"],
                "email": user_data["email"],
                "name": user_data["name"],
                "picture": user_data["picture"],
                "created_at": datetime.utcnow(),
                "total_games": 0,
                "total_wins": 0,
                "total_score": 0,
                "elo_rating": 1000
            }
            await users_collection.insert_one(new_user)
            user_id = user_data["id"]
        else:
            user_id = existing_user["id"]
        
        # Create session
        session_token = user_data["session_token"]
        session_data = {
            "session_token": session_token,
            "user_id": user_id,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "created_at": datetime.utcnow()
        }
        
        # Remove old sessions for this user
        await sessions_collection.delete_many({"user_id": user_id})
        
        # Insert new session
        await sessions_collection.insert_one(session_data)
        
        # Set secure cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=7 * 24 * 60 * 60,  # 7 days
            httponly=True,
            secure=True,
            samesite="none",
            path="/"
        )
        
        return {"success": True, "user": new_user if not existing_user else existing_user}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@api_router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user

@api_router.post("/auth/logout")
async def logout(response: Response, session_token: Optional[str] = Cookie(None)):
    """Logout user by invalidating session"""
    if session_token:
        await sessions_collection.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"success": True}

@api_router.get("/profile/{user_id}")
async def get_user_profile(user_id: str, current_user: Optional[User] = Depends(get_optional_user)):
    """Get user profile by ID"""
    user = await users_collection.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get recent game history
    recent_games = await game_history_collection.find(
        {"user_id": user_id}
    ).sort("played_at", -1).limit(10).to_list(10)
    
    profile_data = {
        "user": User(**user),
        "recent_games": recent_games,
        "is_own_profile": current_user and current_user.id == user_id
    }
    
    return profile_data

@api_router.get("/leaderboard")
async def get_leaderboard(limit: int = 50):
    """Get global leaderboard by ELO rating"""
    leaders = await users_collection.find().sort("elo_rating", -1).limit(limit).to_list(limit)
    
    leaderboard = []
    for i, user in enumerate(leaders):
        leaderboard.append({
            "rank": i + 1,
            "user": User(**user),
            "win_rate": user["total_wins"] / max(user["total_games"], 1) * 100 if user["total_games"] > 0 else 0
        })
    
    return leaderboard

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

# Comprehensive word dictionary with common 3-6 letter words
VALID_WORDS = {
    # 3-letter words
    'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'HAD', 'DAY', 'GET',
    'USE', 'MAN', 'NEW', 'NOW', 'WAY', 'MAY', 'SAY', 'SEE', 'HIM', 'TWO', 'HOW', 'ITS', 'WHO', 'OIL', 'SIT', 'SET',
    'RUN', 'EAT', 'FAR', 'SEA', 'EYE', 'RED', 'TOP', 'ARM', 'TOO', 'OLD', 'ANY', 'APP', 'ART', 'BAD', 'BAG', 'BAR',
    'BAT', 'BED', 'BIG', 'BIT', 'BOX', 'BOY', 'BUS', 'BUY', 'CAR', 'CAT', 'COW', 'CRY', 'CUP', 'CUT', 'DOG', 'DRY',
    'EAR', 'EGG', 'END', 'FAN', 'FEW', 'FIT', 'FIX', 'FLY', 'FOX', 'FUN', 'GAS', 'GOD', 'GOT', 'GUN', 'GUY', 'HAD',
    'HAT', 'HIT', 'HOT', 'JOB', 'KEY', 'KID', 'LAW', 'LAY', 'LEG', 'LET', 'LIE', 'LOT', 'LOW', 'MAP', 'MOM', 'NET',
    'OFF', 'PAY', 'PEN', 'PET', 'PUT', 'RAT', 'RAW', 'ROW', 'SAD', 'SUN', 'TAX', 'TEA', 'TEN', 'TIE', 'TIP', 'TRY',
    'WAR', 'WIN', 'YES', 'YET', 'ZOO', 'ACE', 'ADD', 'AGE', 'AID', 'AIM', 'AIR', 'ASK', 'AXE', 'BAN', 'BEE', 'BET',
    'BIN', 'BOW', 'CAB', 'CAD', 'CAM', 'CAN', 'CAP', 'COB', 'COD', 'COG', 'DIG', 'DIM', 'DIP', 'DOT', 'DUE', 'DUG',
    'ELF', 'ERA', 'EVE', 'FED', 'FIG', 'FIN', 'FOG', 'FUR', 'GAP', 'GEL', 'GEM', 'HAM', 'HEN', 'HEX', 'HID', 'HOP',
    'HUB', 'HUG', 'HUT', 'ICE', 'ILL', 'INK', 'ION', 'JAM', 'JAR', 'JAW', 'JET', 'JOG', 'JOT', 'JOY', 'JUG', 'LAB',
    'LAD', 'LAP', 'LED', 'LID', 'LIP', 'LOG', 'MAD', 'MUD', 'MUG', 'NAP', 'NUT', 'OAK', 'ODD', 'ORB', 'OWL', 'PAD',
    'PAN', 'PAW', 'PEA', 'PIG', 'PIN', 'PIT', 'POD', 'POT', 'PUP', 'RAG', 'RAM', 'RAN', 'RAP', 'RIB', 'RID', 'RIM',
    'RIP', 'ROD', 'RUB', 'RUG', 'RUM', 'SAG', 'SAP', 'SAW', 'SKI', 'SKY', 'SOB', 'SOD', 'SON', 'SPA', 'SPY', 'TAB',
    'TAG', 'TAN', 'TAP', 'TAR', 'TON', 'TOY', 'TUB', 'TUG', 'VAN', 'VAT', 'VET', 'WEB', 'WET', 'WIG', 'ZIP',

    # 4-letter words  
    'WORD', 'WHAT', 'SAID', 'EACH', 'WHICH', 'WILL', 'ABOUT', 'MANY', 'THEN', 'THEM', 'THESE', 'SOME', 'WOULD',
    'MAKE', 'LIKE', 'INTO', 'TIME', 'VERY', 'WHEN', 'COME', 'HERE', 'JUST', 'KNOW', 'TAKE', 'THAN', 'ONLY', 'GOOD',
    'ALSO', 'BACK', 'OVER', 'THINK', 'WHERE', 'BEING', 'WELL', 'LONG', 'LITTLE', 'WORK', 'LIFE', 'STILL', 'SHOULD',
    'AFTER', 'FIRST', 'NEVER', 'THESE', 'GIVE', 'MOST', 'USED', 'MADE', 'OVER', 'NEED', 'CALL', 'FIND', 'TELL',
    'HELP', 'MOVE', 'PART', 'HAND', 'HIGH', 'YEAR', 'CAME', 'SHOW', 'LOOK', 'WANT', 'DOES', 'SEEM', 'FELT', 'KEEP',
    'LEFT', 'TURN', 'SEEN', 'FACT', 'HEAD', 'WEEK', 'CASE', 'LAST', 'SAME', 'BOOK', 'HEAR', 'STOP', 'SIDE', 'BOTH',
    'FACE', 'ONCE', 'OPEN', 'WALK', 'TALK', 'WENT', 'LOOKED', 'EYES', 'DOOR', 'ASKED', 'ROOM', 'WATER', 'AWAY',
    'NIGHT', 'SMALL', 'HOUSE', 'PLACE', 'LARGE', 'SOUND', 'AGAIN', 'UNDER', 'MIGHT', 'WHILE', 'CAME', 'GOING',
    'AREA', 'BEAR', 'BEAT', 'BIRD', 'BLUE', 'BODY', 'BONE', 'BOOK', 'BURN', 'BUSY', 'CAKE', 'CALL', 'CARE', 'CELL',
    'CITY', 'CLUB', 'COAT', 'COLD', 'COOL', 'COPY', 'COST', 'CREW', 'DARK', 'DATA', 'DEAD', 'DEAL', 'DEAR', 'DEEP',
    'DESK', 'DIET', 'DOOR', 'DRAW', 'DRUG', 'DUCK', 'DUTY', 'EACH', 'EARN', 'EAST', 'EASY', 'EDGE', 'ELSE', 'EVEN',
    'EVER', 'EVIL', 'EXIT', 'FACE', 'FAIL', 'FAIR', 'FALL', 'FARM', 'FAST', 'FEAR', 'FEEL', 'FEET', 'FELL', 'FILE',
    'FILM', 'FINE', 'FIRE', 'FISH', 'FIVE', 'FLAT', 'FLOW', 'FOLK', 'FOOD', 'FOOT', 'FORM', 'FREE', 'FROM', 'FULL',
    'FUND', 'GAME', 'GATE', 'GAVE', 'GIFT', 'GIRL', 'GIVE', 'GLAD', 'GOLD', 'GONE', 'GRAB', 'GREW', 'GRIP', 'GROW',
    'HALL', 'HANG', 'HARD', 'HARM', 'HATE', 'HAVE', 'HEAD', 'HEAR', 'HEAT', 'HELD', 'HELL', 'HIDE', 'HILL', 'HIRE',
    'HOLD', 'HOLE', 'HOLY', 'HOME', 'HOPE', 'HOUR', 'HUGE', 'HUNG', 'HUNT', 'HURT', 'IDEA', 'INCH', 'INTO', 'IRON',
    'ITEM', 'JACK', 'JANE', 'JAZZ', 'JOIN', 'JOKE', 'JUMP', 'JUNE', 'JURY', 'JUST', 'KEEP', 'KEPT', 'KICK', 'KILL',
    'KIND', 'KING', 'KNEE', 'KNEW', 'KNOW', 'LACK', 'LADY', 'LAID', 'LAKE', 'LAND', 'LAST', 'LATE', 'LEAD', 'LEAN',
    'LEFT', 'LENS', 'LESS', 'LIES', 'LIFE', 'LIFT', 'LINE', 'LINK', 'LION', 'LIST', 'LIVE', 'LOAN', 'LOCK', 'LONG',
    'LOOK', 'LORD', 'LOSE', 'LOSS', 'LOST', 'LOTS', 'LOUD', 'LOVE', 'LUCK', 'MADE', 'MAIL', 'MAIN', 'MAKE', 'MALE',
    'MALL', 'MANY', 'MARK', 'MASS', 'MATE', 'MATH', 'MEAL', 'MEAN', 'MEAT', 'MEET', 'MELT', 'MENU', 'MESS', 'MICE',
    'MILE', 'MILK', 'MIND', 'MINE', 'MISS', 'MODE', 'MOOD', 'MOON', 'MORE', 'MOST', 'MOVE', 'MUCH', 'MUST', 'NAME',
    'NAVY', 'NEAR', 'NECK', 'NEED', 'NEWS', 'NICE', 'NOON', 'NOTE', 'NUTS', 'ONCE', 'ONLY', 'ONTO', 'OPEN', 'ORAL',
    'OVER', 'PACE', 'PACK', 'PAGE', 'PAID', 'PAIN', 'PAIR', 'PALM', 'PARK', 'PART', 'PASS', 'PAST', 'PATH', 'PEAK',
    'PICK', 'PILE', 'PINK', 'PIPE', 'PLAN', 'PLAY', 'PLOT', 'POEM', 'POET', 'POLL', 'POOL', 'POOR', 'PORT', 'POST',
    'PULL', 'PURE', 'PUSH', 'QUIT', 'RACE', 'RAIN', 'RANK', 'RARE', 'RATE', 'READ', 'REAL', 'REAR', 'RELY', 'RENT',
    'REST', 'RICH', 'RIDE', 'RING', 'RISE', 'RISK', 'ROAD', 'ROCK', 'ROLE', 'ROLL', 'ROOF', 'ROOM', 'ROOT', 'ROPE',
    'ROSE', 'RULE', 'RUSH', 'SAFE', 'SAID', 'SAIL', 'SALE', 'SALT', 'SAME', 'SAND', 'SAVE', 'SEAT', 'SEED', 'SEEK',
    'SEEM', 'SEEN', 'SELL', 'SEND', 'SENT', 'SHIP', 'SHOE', 'SHOP', 'SHOT', 'SHOW', 'SICK', 'SIDE', 'SIGN', 'SING',
    'SINK', 'SITE', 'SIZE', 'SKIN', 'SLIP', 'SLOW', 'SNAP', 'SNOW', 'SOAP', 'SOFT', 'SOIL', 'SOLD', 'SOME', 'SONG',
    'SOON', 'SORT', 'SOUL', 'SOUP', 'SPIN', 'SPOT', 'STAR', 'STAY', 'STEP', 'STOP', 'SUCH', 'SUIT', 'SURE', 'SWIM',
    'TAKE', 'TALK', 'TALL', 'TANK', 'TAPE', 'TASK', 'TEAM', 'TEAR', 'TELL', 'TEND', 'TENT', 'TEST', 'TEXT', 'THAN',
    'THAT', 'THEM', 'THEN', 'THEY', 'THIN', 'THIS', 'THUS', 'TIDE', 'TIED', 'TIES', 'TIME', 'TINY', 'TIPS', 'TIRE',
    'TOLD', 'TONE', 'TOOK', 'TOOL', 'TOPS', 'TORN', 'TOUR', 'TOWN', 'TREE', 'TRIP', 'TRUE', 'TUBE', 'TUNE', 'TURN',
    'TYPE', 'UNIT', 'UPON', 'USED', 'USER', 'VARY', 'VAST', 'VIEW', 'VOTE', 'WAGE', 'WAIT', 'WAKE', 'WALK', 'WALL',
    'WANT', 'WARD', 'WARM', 'WARN', 'WASH', 'WAVE', 'WAYS', 'WEAK', 'WEAR', 'WEEK', 'WELL', 'WENT', 'WERE', 'WEST',
    'WHAT', 'WHEN', 'WHOM', 'WIDE', 'WIFE', 'WILD', 'WILL', 'WIND', 'WINE', 'WING', 'WIRE', 'WISE', 'WISH', 'WITH',
    'WOOD', 'WOOL', 'WORD', 'WORE', 'WORK', 'YARD', 'YEAR', 'YOUR', 'ZERO', 'ZONE',

    # 5-letter words
    'ABOUT', 'OTHER', 'WHICH', 'THEIR', 'WOULD', 'THERE', 'COULD', 'FIRST', 'AFTER', 'THESE', 'THINK', 'WHERE',
    'BEING', 'EVERY', 'GREAT', 'MIGHT', 'SHALL', 'STILL', 'THOSE', 'COME', 'MADE', 'SCHOOL', 'THROUGH', 'JUST',
    'FORM', 'MUCH', 'WATER', 'VERY', 'WHAT', 'KNOW', 'WHILE', 'LAST', 'RIGHT', 'MOVE', 'THING', 'GENERAL', 'WORK',
    'PLACE', 'YEARS', 'LIVE', 'WHERE', 'AFTER', 'BACK', 'LITTLE', 'ONLY', 'WORLD', 'YEAR', 'CAME', 'SHOW', 'EVERY',
    'GOOD', 'GIVE', 'OUR', 'UNDER', 'NAME', 'VERY', 'THROUGH', 'JUST', 'FORM', 'SENTENCE', 'GREAT', 'THINK',
    'APPLE', 'BREAD', 'CHAIR', 'DANCE', 'EAGLE', 'FLAME', 'GLOBE', 'HOUSE', 'IMAGE', 'JUICE', 'KNIFE', 'LEMON',
    'MOUSE', 'NIGHT', 'OCEAN', 'PAPER', 'QUEEN', 'RIVER', 'SMILE', 'TABLE', 'UNCLE', 'VALUE', 'WATER', 'YOUTH',

    # 6-letter words
    'PEOPLE', 'THROUGH', 'BEFORE', 'SHOULD', 'BECAUSE', 'ANOTHER', 'BETWEEN', 'THOUGHT', 'WITHOUT', 'AGAINST',
    'NOTHING', 'SOMEONE', 'AROUND', 'DURING', 'FOLLOW', 'ALWAYS', 'ALMOST', 'ENOUGH', 'SECOND', 'FAMILY',
    'LETTER', 'NEVER', 'STARTED', 'CITY', 'EARTH', 'EYES', 'LIGHT', 'THOUGHT', 'HEAD', 'UNDER', 'STORY', 'SAW',
    'LEFT', 'DONT', 'FEW', 'WHILE', 'ALONG', 'MIGHT', 'CLOSE', 'SOMETHING', 'SEEM', 'NEXT', 'HARD', 'OPEN',
    'EXAMPLE', 'BEGIN', 'LIFE', 'ALWAYS', 'THOSE', 'BOTH', 'PAPER', 'TOGETHER', 'GOT', 'GROUP', 'OFTEN', 'RUN',
    'ANIMAL', 'SYSTEM', 'FRIEND', 'MOTHER', 'FATHER', 'BETTER', 'CHANGE', 'CIRCLE', 'DOLLAR', 'ENERGY', 'FRIEND',
    'GOLDEN', 'HANDLE', 'ISLAND', 'JUNGLE', 'KITTEN', 'LISTEN', 'MASTER', 'NATURE', 'ORANGE', 'PALACE', 'QUIVER',
    'ROCKET', 'SILENT', 'TEMPLE', 'UNIQUE', 'VIOLIN', 'WINDOW'
}

# Game state storage
games: Dict[str, dict] = {}
connections: Dict[str, List[WebSocket]] = {}

class GameState:
    def __init__(self, room_code: str, word_length: int = 3, timer_minutes: int = 4, creator_user: Optional[User] = None):
        self.room_code = room_code
        self.word_length = word_length  # Required word length for this game
        self.timer_minutes = timer_minutes  # Game timer in minutes (2, 4, or 6)
        self.creator_user = creator_user  # User who created the room
        self.game_start_time = None  # When the game actually started
        self.game_id = str(uuid.uuid4())  # Unique game ID for history tracking
        self.players = {}  # {websocket_id: {"name": str, "score": int, "user": Optional[User]}}
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
        if len(word) != self.word_length:  # Must be exactly the required length
            return False
        if not is_valid_word(word, self.word_length):  # Use comprehensive dictionary
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

    def get_time_remaining(self) -> int:
        """Get remaining time in seconds, returns 0 if game not started"""
        if not self.game_started or not self.game_start_time:
            return self.timer_minutes * 60
        
        elapsed_seconds = time.time() - self.game_start_time
        total_seconds = self.timer_minutes * 60
        remaining_seconds = max(0, total_seconds - elapsed_seconds)
        return int(remaining_seconds)

    def calculate_word_score(self, word: str) -> int:
        return sum(SCRABBLE_SCORES[letter.upper()] for letter in word)
    
    async def end_game_and_update_stats(self):
        """End game and update player statistics and ELO ratings"""
        if self.game_ended:
            return
            
        self.game_ended = True
        
        # Sort players by score
        sorted_players = sorted(
            [(ws_id, player) for ws_id, player in self.players.items()],
            key=lambda x: x[1]["score"],
            reverse=True
        )
        
        # Update stats for logged-in players only
        authenticated_players = [
            (ws_id, player) for ws_id, player in sorted_players 
            if player.get("user") is not None
        ]
        
        if len(authenticated_players) < 2:
            # Not enough authenticated players for ELO changes
            return
        
        # Calculate ELO changes for top 2 players
        if len(authenticated_players) >= 2:
            winner_data = authenticated_players[0][1]
            loser_data = authenticated_players[1][1]
            
            winner_user = winner_data["user"]
            loser_user = loser_data["user"]
            
            # Calculate ELO changes
            winner_change, loser_change = calculate_elo_change(
                winner_user.elo_rating, 
                loser_user.elo_rating
            )
            
            # Update ELO ratings in database
            await users_collection.update_one(
                {"id": winner_user.id},
                {
                    "$inc": {
                        "total_games": 1,
                        "total_wins": 1,
                        "total_score": winner_data["score"],
                        "elo_rating": winner_change
                    }
                }
            )
            
            await users_collection.update_one(
                {"id": loser_user.id},
                {
                    "$inc": {
                        "total_games": 1,
                        "total_score": loser_data["score"],
                        "elo_rating": loser_change
                    }
                }
            )
        
        # Save game history for all authenticated players
        for i, (ws_id, player) in enumerate(authenticated_players):
            user = player["user"]
            placement = i + 1
            
            # Calculate ELO change for this specific player
            if i == 0 and len(authenticated_players) >= 2:  # Winner
                elo_change = winner_change
                new_elo = winner_user.elo_rating + winner_change
            elif i == 1 and len(authenticated_players) >= 2:  # Runner-up (loser in 1v1)
                elo_change = loser_change
                new_elo = loser_user.elo_rating + loser_change
            else:  # Other players - smaller ELO changes
                elo_change = 0  # No change for 3rd+ place or insufficient players
                new_elo = user.elo_rating
            
            # Create game history entry
            history_entry = {
                "game_id": self.game_id,
                "user_id": user.id,
                "room_code": self.room_code,
                "final_score": player["score"],
                "placement": placement,
                "word_length": self.word_length,
                "timer_minutes": self.timer_minutes,
                "opponent_count": len(authenticated_players) - 1,
                "elo_change": elo_change,
                "new_elo_rating": new_elo,
                "played_at": datetime.utcnow()
            }
            
            await game_history_collection.insert_one(history_entry)

    def should_end_game(self) -> bool:
        # Game ends if deck is empty, 26 letters on table with 26 seconds timeout, or timer expires
        if not self.deck:
            return True
        if len(self.letters_on_table) >= 26:
            if self.last_word_time:
                return time.time() - self.last_word_time >= 26
            elif self.last_letter_time:
                return time.time() - self.last_letter_time >= 26
        
        # Check if timer has expired
        if self.game_started and self.game_start_time:
            elapsed_minutes = (time.time() - self.game_start_time) / 60
            if elapsed_minutes >= self.timer_minutes:
                return True
                
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
class CreateRoomRequest(BaseModel):
    word_length: int = Field(default=3, ge=3, le=6)
    timer_minutes: int = Field(default=4, ge=2, le=6)  # 2, 4, or 6 minutes

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
async def create_room(request: CreateRoomRequest = None, current_user: Optional[User] = Depends(get_optional_user)):
    if request is None:
        request = CreateRoomRequest()
    
    # Validate timer_minutes - only allow 2, 4, or 6 minutes
    if request.timer_minutes not in [2, 4, 6]:
        request.timer_minutes = 4  # Default to 4 minutes if invalid
    
    room_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
    games[room_code] = GameState(room_code, request.word_length, request.timer_minutes, current_user)
    
    return {
        "room_code": room_code, 
        "word_length": request.word_length, 
        "timer_minutes": request.timer_minutes,
        "creator": current_user.name if current_user else "Anonymous"
    }

# WebSocket endpoint (must be on main app, not router)
@app.websocket("/api/ws/{room_code}")
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
                
                # Try to get user from session token if provided
                session_token = message.get("session_token")
                user = None
                if session_token:
                    try:
                        # Check session validity
                        session = await sessions_collection.find_one({
                            "session_token": session_token,
                            "expires_at": {"$gt": datetime.utcnow()}
                        })
                        if session:
                            user_data = await users_collection.find_one({"id": session["user_id"]})
                            if user_data:
                                user = User(**user_data)
                                player_name = user.name  # Use authenticated name
                    except Exception as e:
                        print(f"Authentication error: {e}")
                
                game.players[websocket_id] = {
                    "name": player_name, 
                    "score": 0,
                    "user": user,  # Store user object for ELO tracking
                    "elo_rating": user.elo_rating if user else None
                }
                
                await manager.broadcast_to_room({
                    "type": "player_joined",
                    "player_name": player_name,
                    "players": [
                        {
                            "name": p["name"],
                            "score": p["score"],
                            "elo_rating": p.get("elo_rating"),
                            "is_authenticated": p.get("user") is not None
                        }
                        for p in game.players.values()
                    ]
                }, room_code)
                
                # Send current game state to new player
                await websocket.send_text(json.dumps({
                    "type": "game_state",
                    "letters": game.letters_on_table,
                    "players": [
                        {
                            "name": p["name"],
                            "score": p["score"],
                            "elo_rating": p.get("elo_rating"),
                            "is_authenticated": p.get("user") is not None
                        }
                        for p in game.players.values()
                    ],
                    "game_started": game.game_started,
                    "word_length": game.word_length,
                    "timer_minutes": game.timer_minutes,
                    "time_remaining": game.get_time_remaining()
                }))
                
            elif message["type"] == "start_game":
                if not game.game_started:
                    game.game_started = True
                    game.game_start_time = time.time()  # Record when game actually started
                    # Start letter generation timer
                    asyncio.create_task(letter_generation_timer(room_code))
                    # Start game timer countdown
                    asyncio.create_task(game_timer_countdown(room_code))
                    
                    await manager.broadcast_to_room({
                        "type": "game_started",
                        "timer_minutes": game.timer_minutes,
                        "time_remaining": game.get_time_remaining()
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
                        "players": [
                            {
                                "name": p["name"],
                                "score": p["score"],
                                "elo_rating": p.get("elo_rating"),
                                "is_authenticated": p.get("user") is not None
                            }
                            for p in game.players.values()
                        ]
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
            await game.end_game_and_update_stats()  # Update stats before ending
            await manager.broadcast_to_room({
                "type": "game_ended",
                "final_scores": [
                    {
                        "name": p["name"],
                        "score": p["score"],
                        "elo_rating": p.get("elo_rating"),
                        "is_authenticated": p.get("user") is not None
                    }
                    for p in game.players.values()
                ]
            }, room_code)
            break
            
        await asyncio.sleep(4)

async def game_timer_countdown(room_code: str):
    """Countdown timer for the game duration"""
    game = games.get(room_code)
    if not game:
        return
    
    while game.game_started and not game.should_end_game():
        time_remaining = game.get_time_remaining()
        
        # Broadcast time remaining every 10 seconds
        await manager.broadcast_to_room({
            "type": "timer_update",
            "time_remaining": time_remaining
        }, room_code)
        
        # Check if time is up
        if time_remaining <= 0:
            await game.end_game_and_update_stats()  # Update stats before ending
            await manager.broadcast_to_room({
                "type": "game_ended",
                "reason": "time_up",
                "final_scores": [
                    {
                        "name": p["name"],
                        "score": p["score"],
                        "elo_rating": p.get("elo_rating"),
                        "is_authenticated": p.get("user") is not None
                    }
                    for p in game.players.values()
                ]
            }, room_code)
            break
            
        await asyncio.sleep(10)  # Update every 10 seconds

async def game_timer_countdown(room_code: str):
    """Countdown timer for the game duration"""
    game = games.get(room_code)
    if not game:
        return
    
    while game.game_started and not game.should_end_game():
        time_remaining = game.get_time_remaining()
        
        # Broadcast time remaining every 10 seconds
        await manager.broadcast_to_room({
            "type": "timer_update",
            "time_remaining": time_remaining
        }, room_code)
        
        # Check if time is up
        if time_remaining <= 0:
            game.game_ended = True
            await manager.broadcast_to_room({
                "type": "game_ended",
                "reason": "time_up",
                "final_scores": list(game.players.values())
            }, room_code)
            break
            
        await asyncio.sleep(10)  # Update every 10 seconds

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