"""Regression tests for the FFMPEG NameError fix in backend/rendering.py."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vidmatic-preview.preview.emergentagent.com").rstrip("/")
EMAIL = "e2e_render@test.com"
PASSWORD = "TestPass123"


# ---- get_ffmpeg_binaries returns two absolute paths ----
def test_ffmpeg_binaries_resolve():
    import sys
    sys.path.insert(0, "/app/backend")
    from rendering import get_ffmpeg_binaries
    ffmpeg, ffprobe = get_ffmpeg_binaries()
    assert os.path.isabs(ffmpeg) and os.path.exists(ffmpeg)
    assert os.path.isabs(ffprobe) and os.path.exists(ffprobe)


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


# ---- Pipeline creates and never surfaces a FFMPEG NameError ----
def test_video_pipeline_no_ffmpeg_nameerror(session):
    # Check credits first
    me = session.get(f"{BASE_URL}/api/auth/me", timeout=30).json()
    total = (me.get("video_credits") or 0) + (me.get("free_video_credits") or 0)
    if total <= 0:
        pytest.skip(f"No credits remaining for {EMAIL} (video_credits+free={total}) — cannot exercise pipeline")

    payload = {
        "prompt": "The wonders of nature and wildlife",
        "video_length": "short",
        "voice_style": "professional",
        "visual_style": "cinematic",
        "language": "en",
    }
    r = session.post(f"{BASE_URL}/api/videos/create", json=payload, timeout=60)
    assert r.status_code == 200, f"Create failed: {r.status_code} {r.text}"
    video_id = r.json()["video_id"]
    print(f"Created video_id={video_id}")

    # Poll for up to 8 minutes
    deadline = time.time() + 480
    last = {}
    reached_render_or_ready = False
    while time.time() < deadline:
        pr = session.get(f"{BASE_URL}/api/videos/{video_id}/progress", timeout=30)
        assert pr.status_code == 200
        last = pr.json()
        status = last.get("status")
        progress = last.get("progress") or 0
        err = (last.get("error_message") or "") + " " + (last.get("progress_message") or "")

        # Fail immediately if the NameError regression appears
        assert "FFMPEG" not in (last.get("error_message") or ""), \
            f"REGRESSION: FFMPEG NameError present: {last}"
        assert "name 'FFMPEG' is not defined" not in err, f"REGRESSION: {last}"

        if status in ("rendering", "ready") or progress >= 80:
            reached_render_or_ready = True
            break
        if status == "failed":
            # Acceptable failure only if it's NOT the FFMPEG regression
            msg = last.get("error_message") or ""
            assert "FFMPEG" not in msg and "name 'FFMPEG'" not in msg, \
                f"REGRESSION: pipeline failed with FFMPEG NameError: {msg}"
            print(f"Pipeline failed for a NON-FFMPEG reason (acceptable per review): {msg}")
            return
        time.sleep(10)

    print(f"Final status snapshot: {last}")
    assert reached_render_or_ready, f"Did not reach rendering/ready within timeout. Last: {last}"


# ---- Confirm no static reference to bare FFMPEG identifier ----
def test_rendering_source_has_no_bare_ffmpeg_name():
    src = open("/app/backend/rendering.py").read()
    # Should not contain the offending token as a bare identifier
    # (allowed: _FFMPEG, get_ffmpeg_binaries, "ffmpeg", string literals)
    import re
    # Look for uppercase FFMPEG used as an identifier not prefixed by underscore or quotes
    matches = re.findall(r"(?<![_A-Za-z\"'])FFMPEG(?![_A-Za-z])", src)
    assert not matches, f"Bare FFMPEG identifier still present: {matches}"
