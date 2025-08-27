import asyncio
import websockets
import json
import sys
from datetime import datetime

class WebSocketTester:
    def __init__(self, base_url="wss://wordsmith-24.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    async def test_websocket_connection(self, room_code):
        """Test WebSocket connection to a room"""
        ws_url = f"{self.base_url}/api/ws/{room_code}"
        print(f"\n🔍 Testing WebSocket connection to: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print("✅ WebSocket connection established")
                
                # Test joining the game
                join_message = {
                    "type": "join",
                    "player_name": "TestPlayer"
                }
                
                await websocket.send(json.dumps(join_message))
                print("✅ Sent join message")
                
                # Wait for responses
                response_count = 0
                while response_count < 3:  # Expect multiple responses
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        message = json.loads(response)
                        print(f"📝 Received: {message['type']}")
                        
                        if message['type'] == 'player_joined':
                            print(f"   Player joined: {message.get('player_name')}")
                            print(f"   Total players: {len(message.get('players', []))}")
                        elif message['type'] == 'game_state':
                            print(f"   Game started: {message.get('game_started')}")
                            print(f"   Letters on table: {len(message.get('letters', []))}")
                        
                        response_count += 1
                        
                    except asyncio.TimeoutError:
                        break
                
                self.tests_run += 1
                self.tests_passed += 1
                return True
                
        except Exception as e:
            print(f"❌ WebSocket connection failed: {str(e)}")
            self.tests_run += 1
            return False

    async def test_game_flow(self, room_code):
        """Test complete game flow including starting game and letter generation"""
        ws_url = f"{self.base_url}/api/ws/{room_code}"
        print(f"\n🎮 Testing complete game flow...")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Join game
                await websocket.send(json.dumps({
                    "type": "join",
                    "player_name": "GameTester"
                }))
                
                # Wait for join confirmation
                await asyncio.wait_for(websocket.recv(), timeout=5)
                await asyncio.wait_for(websocket.recv(), timeout=5)
                
                # Start game
                await websocket.send(json.dumps({
                    "type": "start_game"
                }))
                print("✅ Sent start game message")
                
                # Wait for game started confirmation
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                message = json.loads(response)
                
                if message['type'] == 'game_started':
                    print("✅ Game started successfully")
                    
                    # Wait for letters to appear
                    letter_count = 0
                    for _ in range(3):  # Wait for up to 3 letters
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=6)
                            message = json.loads(response)
                            
                            if message['type'] == 'new_letter':
                                letter_count += 1
                                print(f"✅ Letter {letter_count} appeared: {message['letter']}")
                        except asyncio.TimeoutError:
                            break
                    
                    if letter_count > 0:
                        print(f"✅ Letter generation working: {letter_count} letters received")
                        self.tests_run += 1
                        self.tests_passed += 1
                        return True
                    else:
                        print("❌ No letters were generated")
                        self.tests_run += 1
                        return False
                else:
                    print(f"❌ Unexpected response: {message}")
                    self.tests_run += 1
                    return False
                    
        except Exception as e:
            print(f"❌ Game flow test failed: {str(e)}")
            self.tests_run += 1
            return False

    async def test_word_submission(self, room_code):
        """Test word submission and validation"""
        ws_url = f"{self.base_url}/api/ws/{room_code}"
        print(f"\n📝 Testing word submission...")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # Join and start game
                await websocket.send(json.dumps({
                    "type": "join",
                    "player_name": "WordTester"
                }))
                
                # Wait for responses
                await asyncio.wait_for(websocket.recv(), timeout=5)
                await asyncio.wait_for(websocket.recv(), timeout=5)
                
                # Start game
                await websocket.send(json.dumps({
                    "type": "start_game"
                }))
                
                # Wait for game to start and letters to appear
                await asyncio.wait_for(websocket.recv(), timeout=5)  # game_started
                
                # Collect letters
                letters = []
                for _ in range(5):  # Wait for up to 5 letters
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=6)
                        message = json.loads(response)
                        
                        if message['type'] == 'new_letter':
                            letters.extend(message['letters'])
                    except asyncio.TimeoutError:
                        break
                
                if len(letters) >= 3:
                    print(f"✅ Collected {len(letters)} letters for testing")
                    
                    # Test invalid word submission
                    invalid_word = "XYZ"
                    fake_ids = [letters[0]['id'], letters[1]['id'], letters[2]['id']]
                    
                    await websocket.send(json.dumps({
                        "type": "submit_word",
                        "word": invalid_word,
                        "selected_letter_ids": fake_ids
                    }))
                    
                    # Wait for rejection
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    message = json.loads(response)
                    
                    if message['type'] == 'word_rejected':
                        print(f"✅ Invalid word correctly rejected: {message['word']}")
                        self.tests_run += 1
                        self.tests_passed += 1
                        return True
                    else:
                        print(f"❌ Expected rejection but got: {message}")
                        self.tests_run += 1
                        return False
                else:
                    print("❌ Not enough letters collected for testing")
                    self.tests_run += 1
                    return False
                    
        except Exception as e:
            print(f"❌ Word submission test failed: {str(e)}")
            self.tests_run += 1
            return False

async def main():
    print("🎮 WordSmith WebSocket Testing")
    print("=" * 50)
    
    # Create room first using HTTP API
    import requests
    try:
        response = requests.post("https://wordplay-hub-2.preview.emergentagent.com/api/create-room", timeout=10)
        room_data = response.json()
        room_code = room_data['room_code']
        print(f"✅ Created test room: {room_code}")
    except Exception as e:
        print(f"❌ Failed to create room: {str(e)}")
        return 1
    
    # Initialize tester
    tester = WebSocketTester()
    
    # Run tests
    await tester.test_websocket_connection(room_code)
    await tester.test_game_flow(room_code)
    await tester.test_word_submission(room_code)
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 WebSocket Tests: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All WebSocket tests passed!")
        return 0
    else:
        print(f"⚠️ {tester.tests_run - tester.tests_passed} WebSocket tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))