#!/usr/bin/env python3
"""
Quick verification of channels endpoint
"""

import requests
import json

# Test configuration
BACKEND_URL = "https://vidmatic-preview.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test user credentials for authentication
TEST_EMAIL = "testuser_real_composio@test.com"
TEST_PASSWORD = "testpassword123"

session = requests.Session()
session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})

# Login
login_data = {
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD
}

response = session.post(f"{API_BASE}/auth/login", json=login_data)
if response.status_code == 200:
    print("✅ Authenticated successfully")
    
    # Get channels
    channels_response = session.get(f"{API_BASE}/youtube/channels")
    if channels_response.status_code == 200:
        channels = channels_response.json()
        print(f"✅ Retrieved {len(channels)} channels:")
        for channel in channels:
            print(f"   - {channel.get('channel_name', 'Unknown')} (ID: {channel.get('channel_id', 'Unknown')}, Active: {channel.get('is_active', 'Unknown')})")
    else:
        print(f"❌ Failed to get channels: {channels_response.status_code} - {channels_response.text}")
else:
    print(f"❌ Authentication failed: {response.status_code} - {response.text}")