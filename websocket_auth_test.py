import asyncio
import websockets
import json
import sys

async def test_websocket_auth():
    """Test WebSocket connection with authentication support"""
    print("🌐 Testing WebSocket Authentication Support...")
    
    # Create a room first
    import requests
    room_response = requests.post(
        "https://wordplay-hub-2.preview.emergentagent.com/api/create-room",
        json={"word_length": 4, "timer_minutes": 4}
    )
    
    if room_response.status_code != 200:
        print("❌ Failed to create room for WebSocket test")
        return False
    
    room_data = room_response.json()
    room_code = room_data.get("room_code")
    
    if not room_code:
        print("❌ No room code returned")
        return False
    
    print(f"✅ Created room {room_code} for WebSocket testing")
    
    # Test WebSocket connection
    ws_url = f"wss://wordplay-hub-2.preview.emergentagent.com/api/ws/{room_code}"
    print(f"🔗 Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connection established")
            
            # Test joining without session token (anonymous)
            join_message = {
                "type": "join",
                "player_name": "TestPlayer"
            }
            
            await websocket.send(json.dumps(join_message))
            print("📤 Sent join message (anonymous)")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            print(f"📥 Received: {response_data.get('type', 'unknown')}")
            
            if response_data.get("type") == "player_joined":
                print("✅ Anonymous player join successful")
                
                # Check if players array includes authentication info
                players = response_data.get("players", [])
                if players and len(players) > 0:
                    player = players[0]
                    if "is_authenticated" in player:
                        print(f"✅ Player authentication status tracked: {player['is_authenticated']}")
                    else:
                        print("❌ Player authentication status not tracked")
                
                return True
            else:
                print(f"❌ Unexpected response type: {response_data.get('type')}")
                return False
                
    except asyncio.TimeoutError:
        print("❌ WebSocket connection timeout")
        return False
    except Exception as e:
        print(f"❌ WebSocket error: {str(e)}")
        return False

async def test_websocket_with_mock_session():
    """Test WebSocket connection with mock session token"""
    print("\n🔐 Testing WebSocket with Mock Session Token...")
    
    # Create a room first
    import requests
    room_response = requests.post(
        "https://wordplay-hub-2.preview.emergentagent.com/api/create-room",
        json={"word_length": 4, "timer_minutes": 4}
    )
    
    if room_response.status_code != 200:
        print("❌ Failed to create room for WebSocket auth test")
        return False
    
    room_data = room_response.json()
    room_code = room_data.get("room_code")
    
    print(f"✅ Created room {room_code} for WebSocket auth testing")
    
    # Test WebSocket connection with mock session
    ws_url = f"wss://wordplay-hub-2.preview.emergentagent.com/api/ws/{room_code}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connection established")
            
            # Test joining with mock session token
            join_message = {
                "type": "join",
                "player_name": "AuthTestPlayer",
                "session_token": "mock_session_token_123"
            }
            
            await websocket.send(json.dumps(join_message))
            print("📤 Sent join message with mock session token")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            print(f"📥 Received: {response_data.get('type', 'unknown')}")
            
            if response_data.get("type") == "player_joined":
                print("✅ Player join with session token handled")
                
                # Check authentication status
                players = response_data.get("players", [])
                if players and len(players) > 0:
                    player = players[0]
                    is_authenticated = player.get("is_authenticated", False)
                    print(f"✅ Authentication status: {is_authenticated} (expected False for mock token)")
                    
                    if not is_authenticated:
                        print("✅ Mock session token correctly rejected")
                        return True
                    else:
                        print("❌ Mock session token incorrectly accepted")
                        return False
                
                return True
            else:
                print(f"❌ Unexpected response type: {response_data.get('type')}")
                return False
                
    except asyncio.TimeoutError:
        print("❌ WebSocket connection timeout")
        return False
    except Exception as e:
        print(f"❌ WebSocket error: {str(e)}")
        return False

async def main():
    print("🌐 WebSocket Authentication Testing")
    print("=" * 40)
    
    # Test basic WebSocket functionality
    test1_result = await test_websocket_auth()
    
    # Test WebSocket with session token
    test2_result = await test_websocket_with_mock_session()
    
    print("\n" + "=" * 40)
    print("📊 WebSocket Authentication Test Results:")
    print(f"   {'✅' if test1_result else '❌'} Anonymous WebSocket Connection")
    print(f"   {'✅' if test2_result else '❌'} WebSocket with Session Token")
    
    if test1_result and test2_result:
        print("\n🎉 WebSocket authentication tests PASSED!")
        return 0
    else:
        print("\n⚠️ WebSocket authentication tests had issues")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))