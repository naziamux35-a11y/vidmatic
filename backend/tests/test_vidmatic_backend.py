"""Vidmatic backend E2E tests: auth, settings, videos (stream/download/voiceover/publish), youtube oauth."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vidmatic-preview.preview.emergentagent.com").rstrip("/")
EMAIL = "e2e_render@test.com"
PASSWORD = "TestPass123"
VIDEO_ID = "vid_3e10b384068f"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


# ---------------- AUTH ----------------
class TestAuth:
    def test_login_and_me(self, client):
        r = client.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("email") == EMAIL


# ---------------- SETTINGS ----------------
class TestSettings:
    def test_get_stock_keys(self, client):
        r = client.get(f"{BASE_URL}/api/settings/stock-keys", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "has_pexels" in data and "has_pixabay" in data

    def test_put_invalid_pexels(self, client):
        r = client.put(f"{BASE_URL}/api/settings/stock-keys",
                       json={"pexels_api_key": "badkey123"}, timeout=30)
        assert r.status_code == 400, f"Expected 400 got {r.status_code}: {r.text}"
        assert "detail" in r.json()


# ---------------- VIDEOS LIST ----------------
class TestVideosList:
    def test_list_contains_ready_video(self, client):
        r = client.get(f"{BASE_URL}/api/videos/", timeout=30)
        assert r.status_code == 200, r.text
        videos = r.json()
        assert isinstance(videos, list)
        match = next((v for v in videos if v.get("video_id") == VIDEO_ID), None)
        assert match is not None, f"video {VIDEO_ID} not found in list"
        assert match.get("status") == "ready"
        assert match.get("video_url") == f"/api/videos/{VIDEO_ID}/stream"
        assert match.get("download_url") == f"/api/videos/{VIDEO_ID}/download"
        assert match.get("rendered_duration") and 60 < match["rendered_duration"] < 80
        assert match.get("file_size_mb") is not None


# ---------------- STREAM / DOWNLOAD / VOICEOVER ----------------
class TestVideoAssets:
    def test_stream_range_206(self, client):
        r = client.get(f"{BASE_URL}/api/videos/{VIDEO_ID}/stream",
                       headers={"Range": "bytes=0-1023"}, timeout=30, stream=True)
        assert r.status_code == 206, f"Expected 206 got {r.status_code}: {r.text[:200]}"
        assert "Content-Range" in r.headers
        r.close()

    def test_stream_no_range_200(self, client):
        r = client.get(f"{BASE_URL}/api/videos/{VIDEO_ID}/stream", timeout=30, stream=True)
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text[:200]}"
        assert "video/mp4" in r.headers.get("content-type", "")
        r.close()

    def test_download(self, client):
        r = client.get(f"{BASE_URL}/api/videos/{VIDEO_ID}/download", timeout=30, stream=True)
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text[:200]}"
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        assert "video/mp4" in r.headers.get("content-type", "")
        r.close()

    def test_voiceover(self, client):
        r = client.get(f"{BASE_URL}/api/videos/{VIDEO_ID}/voiceover", timeout=30, stream=True)
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text[:200]}"
        assert "audio/mpeg" in r.headers.get("content-type", "")
        r.close()


# ---------------- PUBLISH ----------------
class TestPublish:
    def test_publish_fake_channel_404(self, client):
        r = client.post(f"{BASE_URL}/api/videos/{VIDEO_ID}/publish",
                        json={"channel_id": "fake_channel_xxx", "publish_now": True}, timeout=30)
        assert r.status_code == 404, f"Expected 404 got {r.status_code}: {r.text}"
        assert "channel" in r.text.lower()


# ---------------- YOUTUBE OAUTH ----------------
class TestYouTubeOAuth:
    def test_oauth_start_returns_composio_url(self, client):
        r = client.post(f"{BASE_URL}/api/youtube/oauth/start", json={}, timeout=60)
        assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        auth_url = data.get("authorization_url") or data.get("auth_url") or data.get("redirect_url")
        assert auth_url, f"no authorization_url in response: {data}"
        assert auth_url.startswith("https://backend.composio.dev"), f"unexpected: {auth_url}"


# ---------------- CREATE VALIDATION ----------------
class TestCreateValidation:
    def test_invalid_video_length_400(self, client):
        r = client.post(f"{BASE_URL}/api/videos/create",
                        json={"prompt": "test prompt", "video_length": "xxl",
                              "voice_style": "friendly", "visual_style": "cinematic",
                              "language": "en"}, timeout=30)
        # If credits exhausted may return 403; test asserts it's 400 or 403 without starting generation.
        assert r.status_code in (400, 403), f"Expected 400/403 got {r.status_code}: {r.text}"
        if r.status_code == 400:
            assert "video length" in r.text.lower() or "length" in r.text.lower()
