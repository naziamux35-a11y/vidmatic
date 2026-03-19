#!/usr/bin/env python3
"""
Simple debug test for Vidmatic API connectivity
"""

import asyncio
import httpx
import uuid

BACKEND_URL = "https://vidmatic-preview.preview.emergentagent.com/api"

async def simple_test():
    """Simple connectivity test"""
    print("Testing API connectivity...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test API root
            print("1. Testing API root...")
            response = await client.get(f"{BACKEND_URL}/")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
            
            # Test auth signup
            print("\n2. Testing auth signup...")
            test_email = f"simpletest_{uuid.uuid4().hex[:6]}@test.com"
            signup_data = {
                "name": "Simple Test",
                "email": test_email, 
                "password": "TestPass123!"
            }
            
            response = await client.post(f"{BACKEND_URL}/auth/signup", json=signup_data)
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Email: {data.get('user', {}).get('email')}")
            
            if response.status_code == 200:
                # Extract session token
                session_token = response.cookies.get("session_token")
                print(f"   Session Token: {'Found' if session_token else 'Missing'}")
                
                if session_token:
                    # Test video creation
                    print("\n3. Testing video creation...")
                    headers = {"Authorization": f"Bearer {session_token}"}
                    video_data = {
                        "prompt": "Simple test video",
                        "video_length": "short",
                        "voice_style": "professional",
                        "visual_style": "cinematic"
                    }
                    
                    response = await client.post(
                        f"{BACKEND_URL}/videos/create",
                        json=video_data,
                        headers=headers
                    )
                    print(f"   Status: {response.status_code}")
                    if response.status_code == 200:
                        video_data = response.json()
                        print(f"   Video ID: {video_data.get('video_id')}")
                        print(f"   Status: {video_data.get('status')}")
                    else:
                        print(f"   Error: {response.text}")
                        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simple_test())