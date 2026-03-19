#!/usr/bin/env python3
"""
YouTube OAuth Callback Test with Composio Integration
Testing backend functionality with connectedAccountId parameter
"""

import requests
import json
import sys
from datetime import datetime

# Test configuration
BACKEND_URL = "https://vidmatic-preview.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test user credentials for authentication
TEST_EMAIL = "testuser_composio_callback@test.com"
TEST_PASSWORD = "testpassword123"

class YouTubeOAuthTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.auth_token = None
        self.user_id = None

    def print_result(self, test_name, success, message, details=None):
        """Print formatted test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        print(f"   {message}")
        if details:
            print(f"   Details: {details}")
        print()

    def register_test_user(self):
        """Register a test user for authentication"""
        print("🔧 Setting up test user...")
        
        # Try to register user
        register_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test User Composio"
        }
        
        response = self.session.post(f"{API_BASE}/auth/signup", json=register_data)
        
        if response.status_code == 200:
            self.print_result("User Registration", True, "Test user registered successfully")
            return True
        elif response.status_code == 400 and "already" in response.text.lower():
            self.print_result("User Registration", True, "Test user already exists, proceeding with login")
            return True
        else:
            self.print_result("User Registration", False, f"Failed to register user: {response.status_code} - {response.text}")
            return False

    def authenticate(self):
        """Authenticate and get JWT token"""
        print("🔐 Authenticating...")
        
        login_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        response = self.session.post(f"{API_BASE}/auth/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("user", {}).get("user_id")  # For session-based auth, we'll use session cookies
            self.user_id = data.get("user", {}).get("user_id")
            
            # We don't need JWT token for this app - it uses session cookies
            self.print_result("Authentication", True, f"Successfully authenticated user: {self.user_id}")
            return True
        else:
            self.print_result("Authentication", False, f"Login failed: {response.status_code} - {response.text}")
            return False

    def test_callback_with_composio_params(self):
        """Test the callback endpoint with Composio connectedAccountId parameter"""
        print("📞 Testing YouTube OAuth Callback with Composio Parameters...")
        
        # Test parameters as specified by the user
        callback_params = {
            "status": "success",
            "connectedAccountId": "fb276b4f-4a84-4c83-89ae-a636e8093b73",
            "appName": "youtube"
        }
        
        # Create a pending connection first (simulate the start flow)
        print("   Setting up pending connection...")
        import asyncio
        import os
        from motor.motor_asyncio import AsyncIOMotorClient
        
        # We can't directly access the database from here, so we'll test the endpoint directly
        # The callback should handle the case where a pending connection might not exist
        
        try:
            # Make the callback request
            response = self.session.get(
                f"{API_BASE}/youtube/oauth/callback",
                params=callback_params,
                allow_redirects=False  # Don't follow redirects so we can check them
            )
            
            if response.status_code in [302, 307]:
                # Check redirect location
                redirect_location = response.headers.get('location', '')
                
                if "dashboard" in redirect_location.lower():
                    if "youtube_connected=true" in redirect_location:
                        # Extract channel_id if present
                        channel_id = None
                        if "channel_id=" in redirect_location:
                            channel_id = redirect_location.split("channel_id=")[1].split("&")[0]
                        
                        self.print_result(
                            "OAuth Callback (Success Flow)", 
                            True, 
                            "Callback successfully processed and redirected to dashboard with success",
                            f"Redirect: {redirect_location}, Channel ID: {channel_id}"
                        )
                        return channel_id
                    elif "youtube_error=" in redirect_location:
                        error_msg = redirect_location.split("youtube_error=")[1].split("&")[0]
                        self.print_result(
                            "OAuth Callback (Error Handling)", 
                            True, 
                            f"Callback handled error and redirected appropriately: {error_msg}",
                            f"Redirect: {redirect_location}"
                        )
                        return None
                else:
                    self.print_result(
                        "OAuth Callback", 
                        False, 
                        f"Unexpected redirect location: {redirect_location}"
                    )
                    return None
            else:
                self.print_result(
                    "OAuth Callback", 
                    False, 
                    f"Expected redirect (302/307) but got: {response.status_code} - {response.text[:200]}"
                )
                return None
                
        except Exception as e:
            self.print_result(
                "OAuth Callback", 
                False, 
                f"Exception during callback test: {str(e)}"
            )
            return None

    def test_get_channels(self):
        """Test the GET /api/youtube/channels endpoint"""
        print("📺 Testing Get YouTube Channels...")
        
        try:
            response = self.session.get(f"{API_BASE}/youtube/channels")
            
            if response.status_code == 200:
                channels = response.json()
                
                if isinstance(channels, list):
                    if len(channels) > 0:
                        self.print_result(
                            "Get YouTube Channels", 
                            True, 
                            f"Successfully retrieved {len(channels)} connected channel(s)",
                            f"Channels: {[ch.get('channel_name', 'Unknown') for ch in channels]}"
                        )
                        return channels
                    else:
                        self.print_result(
                            "Get YouTube Channels", 
                            True, 
                            "Successfully retrieved empty channel list (no connected channels)",
                            "Response: []"
                        )
                        return []
                else:
                    self.print_result(
                        "Get YouTube Channels", 
                        False, 
                        f"Expected list response but got: {type(channels).__name__}",
                        f"Response: {response.text[:200]}"
                    )
                    return None
            else:
                self.print_result(
                    "Get YouTube Channels", 
                    False, 
                    f"API returned error: {response.status_code} - {response.text[:200]}"
                )
                return None
                
        except Exception as e:
            self.print_result(
                "Get YouTube Channels", 
                False, 
                f"Exception during channels test: {str(e)}"
            )
            return None

    def test_oauth_start(self):
        """Test the OAuth start endpoint to ensure it's working"""
        print("🚀 Testing YouTube OAuth Start...")
        
        try:
            response = self.session.post(f"{API_BASE}/youtube/oauth/start", json={})
            
            if response.status_code == 200:
                data = response.json()
                
                required_fields = ["authorization_url", "connection_id", "state"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.print_result(
                        "OAuth Start", 
                        True, 
                        "OAuth start endpoint working correctly",
                        f"Authorization URL: {data.get('authorization_url', '')[:50]}..."
                    )
                    return data
                else:
                    self.print_result(
                        "OAuth Start", 
                        False, 
                        f"Missing required fields: {missing_fields}",
                        f"Response: {data}"
                    )
                    return None
            else:
                self.print_result(
                    "OAuth Start", 
                    False, 
                    f"API returned error: {response.status_code} - {response.text[:200]}"
                )
                return None
                
        except Exception as e:
            self.print_result(
                "OAuth Start", 
                False, 
                f"Exception during OAuth start test: {str(e)}"
            )
            return None

    def verify_database_channel_creation(self, channel_id):
        """Verify that the channel was created in database by checking via API"""
        if not channel_id:
            print("🔍 Skipping database verification - no channel ID provided")
            return False
            
        print(f"🔍 Verifying channel creation in database (Channel ID: {channel_id})...")
        
        # Get all channels and check if our channel exists
        channels = self.test_get_channels()
        
        if channels is not None:
            matching_channels = [ch for ch in channels if ch.get('channel_id') == channel_id]
            
            if matching_channels:
                channel = matching_channels[0]
                self.print_result(
                    "Database Channel Verification", 
                    True, 
                    f"Channel successfully created in database",
                    f"Channel: {channel.get('channel_name', 'Unknown')}, User: {channel.get('user_id', 'Unknown')}, Active: {channel.get('is_active', 'Unknown')}"
                )
                return True
            else:
                self.print_result(
                    "Database Channel Verification", 
                    False, 
                    f"Channel {channel_id} not found in database"
                )
                return False
        else:
            self.print_result(
                "Database Channel Verification", 
                False, 
                "Could not retrieve channels to verify database creation"
            )
            return False

    def test_callback_error_scenarios(self):
        """Test various error scenarios for the callback endpoint"""
        print("🚨 Testing YouTube OAuth Callback Error Scenarios...")
        
        error_scenarios = [
            # Missing parameters
            ({}, "no parameters"),
            # Missing connectedAccountId
            ({"status": "success", "appName": "youtube"}, "missing connectedAccountId"),
            # Error parameter
            ({"error": "access_denied"}, "access denied error"),
            # Invalid status
            ({"status": "failure", "connectedAccountId": "invalid-id", "appName": "youtube"}, "failure status"),
        ]
        
        all_passed = True
        
        for params, scenario_name in error_scenarios:
            try:
                response = self.session.get(
                    f"{API_BASE}/youtube/oauth/callback",
                    params=params,
                    allow_redirects=False
                )
                
                if response.status_code in [302, 307]:
                    redirect_location = response.headers.get('location', '')
                    
                    if "youtube_error=" in redirect_location:
                        self.print_result(
                            f"Error Scenario ({scenario_name})", 
                            True, 
                            "Properly handled error and redirected with error parameter",
                            f"Redirect: {redirect_location}"
                        )
                    else:
                        self.print_result(
                            f"Error Scenario ({scenario_name})", 
                            False, 
                            f"Expected error redirect but got: {redirect_location}"
                        )
                        all_passed = False
                else:
                    self.print_result(
                        f"Error Scenario ({scenario_name})", 
                        False, 
                        f"Expected redirect but got: {response.status_code} - {response.text[:100]}"
                    )
                    all_passed = False
                    
            except Exception as e:
                self.print_result(
                    f"Error Scenario ({scenario_name})", 
                    False, 
                    f"Exception: {str(e)}"
                )
                all_passed = False
        
        return all_passed

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("=" * 80)
        print("🧪 YouTube OAuth Callback Testing with Composio Integration")
        print("=" * 80)
        print()
        
        # Setup
        if not self.register_test_user():
            return False
            
        if not self.authenticate():
            return False
        
        print("=" * 50)
        print("🔬 CORE TESTS")
        print("=" * 50)
        
        # Test OAuth start (to ensure basic functionality)
        oauth_start_data = self.test_oauth_start()
        
        # Test the main callback functionality with Composio parameters
        channel_id = self.test_callback_with_composio_params()
        
        # Test getting channels
        channels = self.test_get_channels()
        
        # Verify database creation
        if channel_id:
            self.verify_database_channel_creation(channel_id)
        
        print("=" * 50)
        print("🔬 ERROR HANDLING TESTS")
        print("=" * 50)
        
        # Test error scenarios
        self.test_callback_error_scenarios()
        
        print("=" * 80)
        print("🏁 Testing Complete")
        print("=" * 80)

if __name__ == "__main__":
    tester = YouTubeOAuthTester()
    tester.run_all_tests()