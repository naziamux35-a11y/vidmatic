#!/usr/bin/env python3
"""
Backend API Test Suite for Vidmatic Video Generation Workflow
Using requests instead of httpx for better compatibility
"""

import requests
import json
import time
import uuid
from typing import Dict, Any, Optional

# Configuration
BACKEND_URL = "https://vidmatic-preview.preview.emergentagent.com/api"
TIMEOUT = 30.0

class VidmaticTester:
    def __init__(self):
        self.session_token = None
        self.user_info = None
        self.test_results = []
        self.session = requests.Session()
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {test_name}: {details}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
    
    def register_test_user(self) -> bool:
        """Register a test user for video testing"""
        test_email = f"videotest_{uuid.uuid4().hex[:8]}@test.com"
        test_name = f"Video Test User {uuid.uuid4().hex[:6]}"
        
        try:
            # Register user using email signup
            response = self.session.post(f"{BACKEND_URL}/auth/signup", json={
                "name": test_name,
                "email": test_email,
                "password": "TestPass123!"
            }, timeout=TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                self.user_info = data.get("user")
                
                # Try to get session token from response or cookies
                self.session_token = data.get("session_token")
                if not self.session_token and self.session.cookies.get("session_token"):
                    self.session_token = self.session.cookies["session_token"]
                
                self.log_result(
                    "User Registration", 
                    True, 
                    f"User registered: {test_email}, Credits: {self.user_info.get('video_credits', 0)} + {self.user_info.get('free_video_credits', 0)} free"
                )
                return True
            else:
                self.log_result("User Registration", False, f"Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.log_result("User Registration", False, f"Error: {str(e)}")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        if not self.session_token:
            return {}
        return {"Authorization": f"Bearer {self.session_token}"}
    
    def test_create_video(self) -> Optional[str]:
        """Test POST /api/videos/create endpoint"""
        if not self.session_token:
            self.log_result("Create Video", False, "No authentication token")
            return None
        
        try:
            # Test video creation
            video_data = {
                "prompt": "How to build a sustainable garden at home",
                "video_length": "medium",
                "voice_style": "professional", 
                "visual_style": "cinematic"
            }
            
            response = self.session.post(
                f"{BACKEND_URL}/videos/create",
                json=video_data,
                headers=self.get_auth_headers(),
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                video_id = data.get("video_id")
                status = data.get("status")
                progress = data.get("progress")
                
                if video_id and status == "pending":
                    self.log_result(
                        "Create Video", 
                        True, 
                        f"Video created: {video_id}, Status: {status}, Progress: {progress}%"
                    )
                    return video_id
                else:
                    self.log_result("Create Video", False, f"Invalid response format: {data}")
                    return None
            else:
                self.log_result("Create Video", False, f"Failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.log_result("Create Video", False, f"Error: {str(e)}")
            return None
    
    def test_video_progress(self, video_id: str) -> Dict[str, Any]:
        """Test GET /api/videos/{video_id}/progress endpoint and track status changes"""
        if not video_id:
            self.log_result("Video Progress", False, "No video ID provided")
            return {}
        
        try:
            statuses_seen = set()
            max_checks = 20  # Limit polling to avoid infinite loops
            check_count = 0
            
            while check_count < max_checks:
                response = self.session.get(
                    f"{BACKEND_URL}/videos/{video_id}/progress",
                    headers=self.get_auth_headers(),
                    timeout=TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    progress = data.get("progress", 0)
                    message = data.get("progress_message", "")
                    
                    statuses_seen.add(status)
                    
                    print(f"   Progress Check {check_count + 1}: Status={status}, Progress={progress}%, Message={message}")
                    
                    # Check if video is in a final state
                    if status in ["ready", "failed"]:
                        break
                    
                    # Wait before next check
                    time.sleep(3)
                    check_count += 1
                else:
                    self.log_result("Video Progress", False, f"Progress check failed: {response.status_code}")
                    return {}
            
            # Analyze the progression
            expected_statuses = ["pending", "generating_script", "generating_video", "generating_voiceover", "generating_thumbnail", "ready"]
            progression_analysis = f"Statuses seen: {list(statuses_seen)} (Expected: {expected_statuses})"
            
            final_response = self.session.get(
                f"{BACKEND_URL}/videos/{video_id}/progress",
                headers=self.get_auth_headers(),
                timeout=TIMEOUT
            )
            
            if final_response.status_code == 200:
                final_data = final_response.json()
                final_status = final_data.get("status")
                final_progress = final_data.get("progress", 0)
                
                success = len(statuses_seen) >= 2  # Should see at least 2 different statuses
                self.log_result(
                    "Video Progress", 
                    success, 
                    f"Final: {final_status} ({final_progress}%). {progression_analysis}"
                )
                return final_data
            else:
                self.log_result("Video Progress", False, "Failed to get final status")
                return {}
                
        except Exception as e:
            self.log_result("Video Progress", False, f"Error: {str(e)}")
            return {}
    
    def test_list_videos(self) -> bool:
        """Test GET /api/videos/ endpoint"""
        if not self.session_token:
            self.log_result("List Videos", False, "No authentication token")
            return False
        
        try:
            response = self.session.get(
                f"{BACKEND_URL}/videos/",
                headers=self.get_auth_headers(),
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                videos = response.json()
                if isinstance(videos, list):
                    video_count = len(videos)
                    self.log_result(
                        "List Videos", 
                        True, 
                        f"Retrieved {video_count} videos. Sample fields: {list(videos[0].keys()) if videos else 'N/A'}"
                    )
                    return True
                else:
                    self.log_result("List Videos", False, "Response is not a list")
                    return False
            else:
                self.log_result("List Videos", False, f"Failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.log_result("List Videos", False, f"Error: {str(e)}")
            return False
    
    def test_update_video(self, video_id: str) -> bool:
        """Test PATCH /api/videos/{video_id} endpoint"""
        if not video_id:
            self.log_result("Update Video", False, "No video ID provided")
            return False
        
        try:
            # Test updating video metadata
            update_data = {
                "title": "Updated: Sustainable Home Gardening Guide",
                "description": "Learn how to create an eco-friendly garden at home with sustainable practices",
                "tags": ["gardening", "sustainability", "home", "eco-friendly"],
                "selected_thumbnail_url": "https://example.com/new-thumbnail.jpg"
            }
            
            response = self.session.patch(
                f"{BACKEND_URL}/videos/{video_id}",
                json=update_data,
                headers=self.get_auth_headers(),
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                message = data.get("message", "")
                self.log_result("Update Video", True, f"Video updated successfully: {message}")
                return True
            else:
                self.log_result("Update Video", False, f"Failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Update Video", False, f"Error: {str(e)}")
            return False
    
    def test_get_video_details(self, video_id: str) -> bool:
        """Test GET /api/videos/{video_id} endpoint"""
        if not video_id:
            self.log_result("Get Video Details", False, "No video ID provided")
            return False
        
        try:
            response = self.session.get(
                f"{BACKEND_URL}/videos/{video_id}",
                headers=self.get_auth_headers(),
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                video = response.json()
                # Check for key fields
                required_fields = ["video_id", "status", "prompt", "created_at"]
                missing_fields = [field for field in required_fields if field not in video]
                
                if not missing_fields:
                    self.log_result(
                        "Get Video Details", 
                        True, 
                        f"Video details retrieved: Status={video.get('status')}, Title={video.get('title', 'None')}"
                    )
                    return True
                else:
                    self.log_result("Get Video Details", False, f"Missing fields: {missing_fields}")
                    return False
            else:
                self.log_result("Get Video Details", False, f"Failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Get Video Details", False, f"Error: {str(e)}")
            return False
    
    def test_publish_video(self, video_id: str) -> bool:
        """Test POST /api/videos/{video_id}/publish endpoint"""
        if not video_id:
            self.log_result("Publish Video", False, "No video ID provided")
            return False
        
        try:
            # First, check if user has any YouTube channels
            channels_response = self.session.get(
                f"{BACKEND_URL}/youtube/channels",
                headers=self.get_auth_headers(),
                timeout=TIMEOUT
            )
            
            if channels_response.status_code != 200:
                self.log_result("Publish Video", False, "Could not retrieve YouTube channels")
                return False
            
            channels = channels_response.json()
            if not channels:
                # No channels available - test with a fake channel_id to check error handling
                publish_data = {
                    "channel_id": "fake_channel_id",
                    "publish_now": False
                }
                
                response = self.session.post(
                    f"{BACKEND_URL}/videos/{video_id}/publish",
                    json=publish_data,
                    headers=self.get_auth_headers(),
                    timeout=TIMEOUT
                )
                
                if response.status_code == 404:
                    self.log_result("Publish Video", True, "Properly returns 404 for invalid channel (no channels available)")
                    return True
                else:
                    self.log_result("Publish Video", False, f"Expected 404 for invalid channel, got {response.status_code}")
                    return False
            else:
                # Use first available channel
                channel_id = channels[0]["channel_id"]
                publish_data = {
                    "channel_id": channel_id,
                    "publish_now": False
                }
                
                response = self.session.post(
                    f"{BACKEND_URL}/videos/{video_id}/publish",
                    json=publish_data,
                    headers=self.get_auth_headers(),
                    timeout=TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    message = data.get("message", "")
                    status = data.get("status", "")
                    self.log_result("Publish Video", True, f"Video scheduled: {message}, Status: {status}")
                    return True
                elif response.status_code == 400:
                    # Video might not be ready for publishing
                    error_detail = response.json().get("detail", "")
                    if "not ready" in error_detail.lower():
                        self.log_result("Publish Video", True, f"Proper error handling: {error_detail}")
                        return True
                    else:
                        self.log_result("Publish Video", False, f"Unexpected 400 error: {error_detail}")
                        return False
                else:
                    self.log_result("Publish Video", False, f"Failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            self.log_result("Publish Video", False, f"Error: {str(e)}")
            return False
    
    def run_workflow_test(self) -> None:
        """Test the complete video generation workflow"""
        print("=== VIDMATIC VIDEO GENERATION WORKFLOW TESTING ===\n")
        
        # Step 1: Register test user
        if not self.register_test_user():
            print("❌ Cannot proceed without authentication")
            return
        
        print(f"\n=== Testing Video Endpoints with User: {self.user_info.get('email')} ===\n")
        
        # Step 2: Create video
        video_id = self.test_create_video()
        if not video_id:
            print("❌ Cannot proceed without video creation")
            return
        
        print(f"\n=== Tracking Video Generation Progress for {video_id} ===")
        
        # Step 3: Track progress (this will poll until completion or timeout)
        final_video_status = self.test_video_progress(video_id)
        
        print(f"\n=== Testing Other Video Endpoints ===")
        
        # Step 4: List videos
        self.test_list_videos()
        
        # Step 5: Get video details
        self.test_get_video_details(video_id)
        
        # Step 6: Update video metadata  
        self.test_update_video(video_id)
        
        # Step 7: Test publish endpoint
        self.test_publish_video(video_id)
        
        # Summary
        print(f"\n=== TEST SUMMARY ===")
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   • {result['test']}: {result['details']}")
        
        if passed_tests == total_tests:
            print(f"\n🎉 ALL TESTS PASSED! Video workflow is working correctly.")
        else:
            print(f"\n⚠️  {failed_tests} tests failed. See details above.")

def main():
    """Main test execution"""
    tester = VidmaticTester()
    tester.run_workflow_test()

if __name__ == "__main__":
    main()