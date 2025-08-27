import requests
import sys
import json
from datetime import datetime

class WordSmithAPITester:
    def __init__(self, base_url="https://wordplay-hub-2.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else self.api_url
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            else:
                response = requests.request(method, url, json=data, headers=headers, timeout=10)

            print(f"   Response Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)}")
                    return True, response_data
                except:
                    print(f"   Response: {response.text}")
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error Response: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"   Error Response: {response.text}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            return False, {}
        except requests.exceptions.ConnectionError:
            print(f"❌ Failed - Connection error")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test("Root API Endpoint", "GET", "", 200)

    def test_create_room(self):
        """Test room creation"""
        success, response = self.run_test("Create Room", "POST", "create-room", 200)
        if success and isinstance(response, dict) and 'room_code' in response:
            room_code = response['room_code']
            if len(room_code) == 6 and room_code.isalnum():
                print(f"   ✅ Room code format valid: {room_code}")
                return room_code
            else:
                print(f"   ❌ Invalid room code format: {room_code}")
                return None
        return None

    def test_multiple_room_creation(self):
        """Test creating multiple rooms to ensure unique codes"""
        print(f"\n🔍 Testing Multiple Room Creation...")
        room_codes = []
        for i in range(3):
            success, response = self.run_test(f"Create Room {i+1}", "POST", "create-room", 200)
            if success and isinstance(response, dict) and 'room_code' in response:
                room_codes.append(response['room_code'])
        
        if len(room_codes) == 3:
            unique_codes = len(set(room_codes)) == len(room_codes)
            if unique_codes:
                print(f"   ✅ All room codes are unique: {room_codes}")
                return True
            else:
                print(f"   ❌ Duplicate room codes found: {room_codes}")
                return False
        return False

    def test_cors_headers(self):
        """Test CORS headers"""
        print(f"\n🔍 Testing CORS Headers...")
        try:
            response = requests.options(f"{self.api_url}/create-room", timeout=10)
            cors_headers = {
                'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
                'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
            }
            print(f"   CORS Headers: {json.dumps(cors_headers, indent=2)}")
            
            if cors_headers['Access-Control-Allow-Origin']:
                print(f"   ✅ CORS configured")
                return True
            else:
                print(f"   ❌ CORS not properly configured")
                return False
        except Exception as e:
            print(f"   ❌ CORS test failed: {str(e)}")
            return False

def main():
    print("🎮 WordSmith Backend API Testing")
    print("=" * 50)
    
    # Setup
    tester = WordSmithAPITester()
    
    # Test basic connectivity
    print("\n📡 Testing Basic Connectivity...")
    success, _ = tester.test_root_endpoint()
    if not success:
        print("❌ Cannot connect to backend API. Stopping tests.")
        return 1

    # Test room creation
    print("\n🏠 Testing Room Management...")
    room_code = tester.test_create_room()
    if not room_code:
        print("❌ Room creation failed. Stopping tests.")
        return 1

    # Test multiple room creation
    tester.test_multiple_room_creation()

    # Test CORS
    print("\n🌐 Testing CORS Configuration...")
    tester.test_cors_headers()

    # Test invalid endpoints
    print("\n🚫 Testing Invalid Endpoints...")
    tester.run_test("Invalid Endpoint", "GET", "invalid-endpoint", 404)
    tester.run_test("Invalid Method", "PUT", "create-room", 405)

    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All backend tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())