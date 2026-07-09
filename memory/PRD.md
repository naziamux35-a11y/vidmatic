# Vidmatic — PRD

## Original Problem Statement
Build a production-ready AI YouTube automation SaaS:
1. Replace manual YouTube OAuth with Composio integration (connect channel, fetch stats, store in DB).
2. 4-step video generation workflow: Connect YouTube → Prompt (topic, 2–5 min length, voiceover) → Edit & SEO → Publish/Schedule to YouTube.
3. Production-ready: proper AI voice, no-watermark/copyright stock videos (Pexels + Pixabay).
4. Settings UI for users to input their own stock API keys.
5. Video gallery with playable and downloadable videos.

## Architecture
- Frontend: React + Tailwind (Dashboard 4-step wizard, Library, Settings).
- Backend: FastAPI + Motor (MongoDB async) with HTTP 206 Range video streaming.
- Integrations: Composio v3 SDK (YouTube OAuth + YOUTUBE_UPLOAD_VIDEO), Pexels + Pixabay stock media, LiteLLM/OpenAI for scripts & thumbnails, `static-ffmpeg` for rendering.

## Implemented (Feb 2026)
- Composio v3 migration (SDK 0.17.1); key `ak_NuVubbdFN1Men-ZK4SKN` (no IP write restriction).
- Full AI video pipeline in `backend/videos.py` (script → voiceover → stock media → ffmpeg stitch → thumbnail).
- `backend/youtube.py`: channel connect, channel stats, `YOUTUBE_UPLOAD_VIDEO`, `YOUTUBE_UPDATE_THUMBNAIL`, scheduled publish (upload as private + go public later).
- `backend/rendering.py`: video stitching via `static-ffmpeg` (bypasses missing OS ffmpeg).
- `backend/stock.py`: Pexels + Pixabay stock media fetch.
- `backend/settings_api.py` + `frontend/Settings.js`: per-user Pexels/Pixabay API keys.
- `frontend/Library.js`: streaming playback (Range) + download.
- HTTP 206 Range implementation in `/api/videos/stream/{video_id}`.
- 4-step wizard UI in `Dashboard.js` including edit step (clip swap, text edits).

## Backlog / Next
- P0: E2E user-verified YouTube upload via Composio (rendered mp4 → published).
- P1: E2E manual verification of Edit Step (Step 3) changes propagate to final render.
- P1: Scheduling UX polish (calendar picker) & scheduled → public transition worker.
- P2: Multiple connected YouTube channels; pick target channel at publish time.
- P2: Modularize `videos.py` (routes vs pipeline vs integrations).
- P2: Persistent media storage (currently ephemeral container filesystem).

## Known Constraints
- Container storage is ephemeral — MP4/MP3s from prior sessions disappear (DB row remains).
- OS `ffmpeg`/`ffprobe` unavailable — must use `static-ffmpeg`.
- Composio key must remain `ak_NuVubbdFN1Men-ZK4SKN`.
