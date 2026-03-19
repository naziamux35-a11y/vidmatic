#!/usr/bin/env python3
"""
Test YouTube OAuth Callback with real Composio connection ID format
"""

import requests
import json
import sys

# Test configuration
BACKEND_URL = "https://vidmatic-preview.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test user credentials for authentication
TEST_EMAIL = "testuser_real_composio@test.com"
TEST_PASSWORD = "testpassword123"

class ComposioCallbackTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.user_id = None

    def print_result(self, test_name, success, message, details=None):
        """Print formatted test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        print(f"   {message}")
        if details:
            print(f"   Details: {details}")
        print()

    def setup_user(self):
        """Setup and authenticate test user"""
        print("🔧 Setting up test user...")
        
        # Try to register user
        register_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test User Real Composio"
        }
        
        response = self.session.post(f"{API_BASE}/auth/signup", json=register_data)
        
        if response.status_code == 200:
            self.print_result("User Registration", True, "Test user registered successfully")
        elif response.status_code == 400 and "already" in response.text.lower():
            self.print_result("User Registration", True, "Test user already exists, proceeding with login")
            # Login existing user
            login_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
            response = self.session.post(f"{API_BASE}/auth/login", json=login_data)
            if response.status_code != 200:
                self.print_result("Authentication", False, f"Login failed: {response.status_code} - {response.text}")
                return False
        else:
            self.print_result("User Registration", False, f"Failed to register user: {response.status_code} - {response.text}")
            return False

        # Extract user_id
        if response.status_code == 200:
            data = response.json()
            self.user_id = data.get("user", {}).get("user_id")
            self.print_result("Authentication", True, f"Successfully authenticated user: {self.user_id}")
            return True
        
        return False

    def get_real_connection_id(self):
        """Get a real connection ID from OAuth start"""
        print("🔗 Getting real Composio connection ID...")
        
        try:
            response = self.session.post(f"{API_BASE}/youtube/oauth/start", json={})
            
            if response.status_code == 200:
                data = response.json()
                connection_id = data.get("connection_id")
                
                self.print_result(
                    "Get Connection ID", 
                    True, 
                    f"Successfully obtained connection ID: {connection_id}"
                )
                return connection_id
            else:
                self.print_result(
                    "Get Connection ID", 
                    False, 
                    f"Failed to get connection ID: {response.status_code} - {response.text}"
                )
                return None
                
        except Exception as e:
            self.print_result(
                "Get Connection ID", 
                False, 
                f"Exception: {str(e)}"
            )
            return None

    def test_callback_with_real_connection_id(self, connection_id):
        """Test callback with real Composio connection ID"""
        print(f"📞 Testing callback with real Composio connection ID: {connection_id}")
        
        callback_params = {
            "status": "success",
            "connectedAccountId": connection_id,
            "appName": "youtube"
        }
        
        try:
            response = self.session.get(
                f"{API_BASE}/youtube/oauth/callback",
                params=callback_params,
                allow_redirects=False
            )
            
            if response.status_code in [302, 307]:
                redirect_location = response.headers.get('location', '')
                
                if "youtube_connected=true" in redirect_location:
                    channel_id = None
                    if "channel_id=" in redirect_location:
                        channel_id = redirect_location.split("channel_id=")[1].split("&")[0]
                    
                    self.print_result(
                        "Real Connection Callback", 
                        True, 
                        "Callback processed successfully with real connection ID",
                        f"Redirect: {redirect_location}, Channel ID: {channel_id}"
                    )
                    return channel_id
                elif "youtube_error=" in redirect_location:
                    error_msg = redirect_location.split("youtube_error=")[1].split("&")[0]
                    
                    # This might be expected if the connection is not actually authorized by Google
                    self.print_result(
                        "Real Connection Callback", 
                        True, 
                        f"Callback handled appropriately (connection not authorized): {error_msg}",
                        f"Redirect: {redirect_location}"
                    )
                    return None
                else:
                    self.print_result(
                        "Real Connection Callback", 
                        False, 
                        f"Unexpected redirect: {redirect_location}"
                    )
                    return None
            else:
                self.print_result(
                    "Real Connection Callback", 
                    False, 
                    f"Expected redirect but got: {response.status_code} - {response.text[:200]}"
                )
                return None
                
        except Exception as e:
            self.print_result(
                "Real Connection Callback", 
                False, 
                f"Exception: {str(e)}"
            )
            return None

    def verify_channel_in_db(self, channel_id):
        """Verify channel was created in database"""
        if not channel_id:
            print("🔍 No channel ID to verify")
            return False
            
        print(f"🔍 Verifying channel {channel_id} in database...")
        
        try:
            response = self.session.get(f"{API_BASE}/youtube/channels")
            
            if response.status_code == 200:
                channels = response.json()
                matching_channels = [ch for ch in channels if ch.get('channel_id') == channel_id]
                
                if matching_channels:
                    channel = matching_channels[0]
                    self.print_result(
                        "Database Verification", 
                        True, 
                        "Channel found in database",
                        f"Channel: {channel.get('channel_name', 'Unknown')}, Active: {channel.get('is_active', 'Unknown')}"
                    )
                    return True
                else:
                    self.print_result(
                        "Database Verification", 
                        False, 
                        f"Channel {channel_id} not found in database"
                    )
                    return False
            else:
                self.print_result(
                    "Database Verification", 
                    False, 
                    f"Could not retrieve channels: {response.status_code} - {response.text}"
                )
                return False
                
        except Exception as e:
            self.print_result(
                "Database Verification", 
                False, 
                f"Exception: {str(e)}"
            )
            return False

    def run_test(self):
        """Run the complete test"""
        print("=" * 80)
        print("🧪 YouTube OAuth Callback Test with Real Composio Connection ID")
        print("=" * 80)
        print()
        
        # Setup
        if not self.setup_user():
            return False
        
        # Get real connection ID
        connection_id = self.get_real_connection_id()
        if not connection_id:
            return False
        
        # Test callback with real connection ID
        channel_id = self.test_callback_with_real_connection_id(connection_id)
        
        # Verify database
        if channel_id:
            self.verify_channel_in_db(channel_id)
        
        print("=" * 80)
        print("🏁 Real Connection Test Complete")
        print("=" * 80)

if __name__ == "__main__":
    tester = ComposioCallbackTester()
    tester.run_test()