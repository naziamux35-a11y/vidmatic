#!/usr/bin/env python3
import requests
import json
import uuid
from datetime import datetime, timezone

# Base URL from environment
BASE_URL = "https://vidmatic-preview.preview.emergentagent.com/api"

class VidmaticBackendTest:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.user_id = None
        self.test_user_email = f"test_composio_{uuid.uuid4().hex[:8]}@example.com"
        self.test_user_password = "TestPassword123"
        self.test_user_name = "Composio Test User"
        self.connection_id = None
        self.channel_id = None
        
        # Test results tracking
        self.results = {
            "auth_register": False,
            "youtube_oauth_start": False,
            "youtube_channels_get": False,
            "youtube_channel_disconnect": False,
            "youtube_oauth_callback": False
        }
        self.errors = []

    def log(self, message):
        print(f"[{datetime.now().isoformat()}] {message}")

    def test_auth_register(self):
        """Test user registration"""
        self.log("Testing user registration...")
        try:
            response = self.session.post(f"{BASE_URL}/auth/signup", json={
                "email": self.test_user_email,
                "password": self.test_user_password,
                "name": self.test_user_name
            })
            
            self.log(f"Registration response status: {response.status_code}")
            self.log(f"Registration response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if "user" in data:
                    self.user_id = data["user"]["user_id"]
                    self.log(f"User registered successfully: {self.user_id}")
                    self.results["auth_register"] = True
                    return True
                else:
                    self.errors.append("Registration response missing user data")
            else:
                self.errors.append(f"Registration failed with status {response.status_code}: {response.text}")
        except Exception as e:
            self.errors.append(f"Registration error: {str(e)}")
        
        return False

    def test_auth_login(self):
        """Test user login and get session token"""
        self.log("Testing user login...")
        try:
            response = self.session.post(f"{BASE_URL}/auth/login", json={
                "email": self.test_user_email,
                "password": self.test_user_password
            })
            
            self.log(f"Login response status: {response.status_code}")
            
            if response.status_code == 200:
                # Check if session cookie was set
                if 'session_token' in response.cookies:
                    self.access_token = response.cookies['session_token']
                    self.log("Login successful - session cookie received")
                    return True
                else:
                    # Try to get session token from response
                    data = response.json()
                    if "session_token" in data:
                        self.access_token = data["session_token"]
                        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
                        self.log("Login successful - session token from response")
                        return True
                    else:
                        self.errors.append("Login successful but no session token received")
            else:
                self.errors.append(f"Login failed with status {response.status_code}: {response.text}")
        except Exception as e:
            self.errors.append(f"Login error: {str(e)}")
        
        return False

    def test_youtube_oauth_start(self):
        """Test YouTube OAuth start endpoint"""
        self.log("Testing YouTube OAuth start...")
        try:
            headers = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            
            response = self.session.post(f"{BASE_URL}/youtube/oauth/start", 
                                       json={}, 
                                       headers=headers)
            
            self.log(f"YouTube OAuth start response status: {response.status_code}")
            self.log(f"YouTube OAuth start response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["authorization_url", "connection_id", "state"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.errors.append(f"OAuth start response missing fields: {missing_fields}")
                    return False
                
                # Validate authorization_url starts with Composio domain
                auth_url = data["authorization_url"]
                if not auth_url.startswith("https://backend.composio.dev"):
                    self.errors.append(f"Invalid authorization URL domain: {auth_url}")
                    return False
                
                self.connection_id = data["connection_id"]
                self.log(f"OAuth start successful. Connection ID: {self.connection_id}")
                self.log(f"Authorization URL: {auth_url}")
                self.results["youtube_oauth_start"] = True
                return True
            else:
                self.errors.append(f"OAuth start failed with status {response.status_code}: {response.text}")
        except Exception as e:
            self.errors.append(f"OAuth start error: {str(e)}")
        
        return False

    def test_youtube_channels_get(self):
        """Test get YouTube channels endpoint"""
        self.log("Testing get YouTube channels...")
        try:
            headers = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            
            response = self.session.get(f"{BASE_URL}/youtube/channels", headers=headers)
            
            self.log(f"Get channels response status: {response.status_code}")
            self.log(f"Get channels response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Should be a list (empty initially since no OAuth flow completed)
                if isinstance(data, list):
                    self.log(f"Channels retrieved successfully: {len(data)} channels")
                    self.results["youtube_channels_get"] = True
                    return True
                else:
                    self.errors.append(f"Expected list response, got: {type(data)}")
            else:
                self.errors.append(f"Get channels failed with status {response.status_code}: {response.text}")
        except Exception as e:
            self.errors.append(f"Get channels error: {str(e)}")
        
        return False

    def test_youtube_channel_disconnect(self):
        """Test disconnect YouTube channel endpoint"""
        self.log("Testing disconnect YouTube channel...")
        
        # Since we don't have a real connected channel, test with a dummy channel_id
        # This should return 404 but verify the endpoint exists and handles it properly
        dummy_channel_id = f"ch_{uuid.uuid4().hex[:12]}"
        
        try:
            headers = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            
            response = self.session.delete(f"{BASE_URL}/youtube/channels/{dummy_channel_id}", 
                                         headers=headers)
            
            self.log(f"Disconnect channel response status: {response.status_code}")
            self.log(f"Disconnect channel response: {response.text}")
            
            # Should return 404 for non-existent channel
            if response.status_code == 404:
                data = response.json()
                if "detail" in data and "not found" in data["detail"].lower():
                    self.log("Disconnect endpoint working correctly (404 for non-existent channel)")
                    self.results["youtube_channel_disconnect"] = True
                    return True
                else:
                    self.errors.append(f"Unexpected 404 response format: {data}")
            else:
                self.errors.append(f"Expected 404 for non-existent channel, got {response.status_code}: {response.text}")
        except Exception as e:
            self.errors.append(f"Disconnect channel error: {str(e)}")
        
        return False

    def test_youtube_oauth_callback(self):
        """Test YouTube OAuth callback endpoint"""
        self.log("Testing YouTube OAuth callback...")
        
        # Test error handling - callback without parameters
        try:
            # Don't allow automatic redirects so we can check the redirect response
            response = self.session.get(f"{BASE_URL}/youtube/oauth/callback", allow_redirects=False)
            
            self.log(f"OAuth callback (no params) response status: {response.status_code}")
            
            # Should redirect to dashboard with error
            if response.status_code in [302, 301, 307, 308]:  # Redirect status codes
                location = response.headers.get('location', '')
                self.log(f"OAuth callback redirect location: {location}")
                if 'youtube_error' in location:
                    self.log("OAuth callback correctly handles missing parameters with error redirect")
                    self.results["youtube_oauth_callback"] = True
                    return True
                else:
                    self.errors.append(f"Callback redirect doesn't contain error parameter: {location}")
            else:
                self.errors.append(f"Expected redirect response for callback, got {response.status_code}")
        except Exception as e:
            self.errors.append(f"OAuth callback error: {str(e)}")
        
        return False

    def run_all_tests(self):
        """Run all backend tests"""
        self.log("Starting Vidmatic YouTube OAuth Backend Tests")
        self.log("=" * 60)
        
        # Step 1: Register user
        if not self.test_auth_register():
            self.log("❌ User registration failed - cannot continue with authenticated tests")
            return self.generate_report()
        
        # Step 2: Login user (get session token)
        if not self.test_auth_login():
            self.log("❌ User login failed - cannot continue with authenticated tests")
            return self.generate_report()
        
        # Step 3: Test YouTube OAuth endpoints
        self.test_youtube_oauth_start()
        self.test_youtube_channels_get()
        self.test_youtube_channel_disconnect()
        self.test_youtube_oauth_callback()
        
        return self.generate_report()

    def generate_report(self):
        """Generate test report"""
        self.log("\n" + "=" * 60)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(self.results.values())
        
        for test_name, passed in self.results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            self.log(f"{test_name}: {status}")
        
        self.log(f"\nTotal: {passed_tests}/{total_tests} tests passed")
        
        if self.errors:
            self.log("\n" + "=" * 60)
            self.log("ERRORS ENCOUNTERED")
            self.log("=" * 60)
            for i, error in enumerate(self.errors, 1):
                self.log(f"{i}. {error}")
        
        # Return results for programmatic use
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "results": self.results,
            "errors": self.errors,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0
        }

if __name__ == "__main__":
    tester = VidmaticBackendTest()
    results = tester.run_all_tests()
    
    # Exit with non-zero code if tests failed
    if results["success_rate"] < 1.0:
        exit(1)
    else:
        print("\n🎉 All tests passed!")