from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from motor.motor_asyncio import AsyncIOMotorClient
from auth import get_current_user
from models import User, VideoStatus
import os
import uuid
import base64
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech
from stock import fetch_stock_videos, fetch_stock_images
from rendering import render_video_file, probe_duration, MEDIA_ROOT
import logging

load_dotenv()

logger = logging.getLogger(__name__)

videos_router = APIRouter()

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")


class CreateVideoRequest(BaseModel):
    prompt: str
    video_length: str = "medium"
    voice_style: str = "professional"
    visual_style: str = "cinematic"
    language: str = "en"
    channel_id: Optional[str] = None


class UpdateVideoRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    selected_thumbnail_url: Optional[str] = None


class ScheduleVideoRequest(BaseModel):
    channel_id: str
    scheduled_at: Optional[str] = None
    publish_now: bool = False


class RegenerateRequest(BaseModel):
    regenerate_script: bool = False
    regenerate_voiceover: bool = False
    regenerate_thumbnails: bool = False
    regenerate_seo: bool = False


VOICE_MAP = {
    "professional": "onyx",
    "engaging": "nova",
    "energetic": "shimmer",
    "authoritative": "echo",
    "friendly": "coral",
    "calm": "alloy",
}

DURATION_MAP = {
    "short": {"words": 160, "duration": "about 1 minute", "scenes": 4, "target_seconds": 70, "clips": 8},
    "medium": {"words": 500, "duration": "2-5 minutes", "scenes": 6, "target_seconds": 210, "clips": 20},
    "long": {"words": 975, "duration": "5-8 minutes", "scenes": 10, "target_seconds": 390, "clips": 32},
    "extended": {"words": 1800, "duration": "10-15 minutes", "scenes": 14, "target_seconds": 750, "clips": 40},
}

FALLBACK_THUMBNAILS = [
    "https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg?auto=compress&cs=tinysrgb&w=1280",
    "https://images.pexels.com/photos/546819/pexels-photo-546819.jpeg?auto=compress&cs=tinysrgb&w=1280",
    "https://images.pexels.com/photos/1181671/pexels-photo-1181671.jpeg?auto=compress&cs=tinysrgb&w=1280",
]


def _parse_json_response(response: str) -> Optional[Dict]:
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        return json.loads(response)
    except Exception:
        return None


def _fallback_script(prompt: str, duration_info: Dict) -> Dict:
    intro = f"Welcome! Today we're diving into {prompt}. Stay with us until the end, because we've packed this video with everything you need to know."
    body = (
        f"Let's start with the essentials. {prompt} is a topic that touches many aspects of our daily lives, "
        f"and understanding it can make a real difference. First, consider the background and the key ideas behind it. "
        f"Then, look at how it applies in practice, with real examples you can relate to. "
        f"Finally, keep in mind the most important takeaways as we walk through each point step by step."
    )
    outro = "Thanks for watching! If you found this valuable, like the video and subscribe for more content like this."
    full = f"{intro} {body} {outro}"
    keywords = [w for w in prompt.split() if len(w) > 3][:4] or ["nature"]
    return {
        "title": f"{prompt[:80]}",
        "hook": intro,
        "scenes": [{
            "scene_number": 1, "scene_title": "Main Content",
            "narration": full, "visual_description": prompt,
            "search_keywords": keywords,
        }],
        "outro": outro,
        "full_script": full,
    }


async def generate_script_with_scenes(prompt: str, video_length: str, language: str = "en") -> Dict:
    duration_info = DURATION_MAP.get(video_length, DURATION_MAP["medium"])
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"script_{uuid.uuid4().hex[:8]}",
            system_message="You are an expert YouTube video script writer. Create engaging, well-structured scripts with clear scene breakdowns.",
        )
        chat.with_model("openai", "gpt-5.2")

        prompt_text = f"""Create a complete YouTube video script about: {prompt}

Target duration: {duration_info['duration']}
Target word count: approximately {duration_info['words']} words
Number of scenes: {duration_info['scenes']}
Language: {language}

Output format (JSON):
{{
    "title": "Compelling video title",
    "hook": "First 10-second hook to grab attention",
    "scenes": [
        {{
            "scene_number": 1,
            "scene_title": "Scene title",
            "narration": "Full narration for this scene",
            "visual_description": "What visuals/b-roll to show",
            "search_keywords": ["keyword1", "keyword2"]
        }}
    ],
    "outro": "Call to action and ending",
    "full_script": "Complete narration script without breaks"
}}

Make sure the script is engaging, informative, and optimized for YouTube audience retention."""

        response = await chat.send_message(UserMessage(text=prompt_text))
        parsed = _parse_json_response(response)
        if parsed and parsed.get("full_script"):
            return parsed
        if response and len(response) > 100:
            return {
                "title": f"Video: {prompt[:50]}",
                "hook": response[:200],
                "scenes": [{"scene_number": 1, "scene_title": "Main Content", "narration": response,
                            "visual_description": prompt, "search_keywords": prompt.split()[:3]}],
                "outro": "Thanks for watching!",
                "full_script": response,
            }
    except Exception as e:
        logger.error(f"Script generation failed, using fallback: {e}")
    return _fallback_script(prompt, duration_info)


async def generate_voiceover(script: str, voice_style: str) -> bytes:
    voice = VOICE_MAP.get(voice_style, "alloy")
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)

    max_chars = 4000
    if len(script) <= max_chars:
        return await tts.generate_speech(text=script, model="tts-1-hd", voice=voice, speed=1.0)

    chunks, current, length = [], [], 0
    for word in script.split():
        if length + len(word) + 1 > max_chars:
            chunks.append(' '.join(current))
            current, length = [word], len(word)
        else:
            current.append(word)
            length += len(word) + 1
    if current:
        chunks.append(' '.join(current))

    all_audio = b''
    for chunk in chunks:
        all_audio += await tts.generate_speech(text=chunk, model="tts-1-hd", voice=voice, speed=1.0)
    return all_audio


async def generate_seo_metadata(script_data: Dict, topic: str) -> Dict:
    fallback = {
        "titles": [script_data.get("title", f"Amazing Video: {topic[:60]}")],
        "description": f"{script_data.get('hook', '')}\n\nIn this video we cover: {topic}\n\nDon't forget to like and subscribe for more!",
        "tags": list({w.lower().strip(',.') for w in topic.split() if len(w) > 3})[:10] + ["youtube", "video"],
        "hashtags": ["#youtube", "#video"],
        "seo_score": 70,
        "suggested_category": "Education",
    }
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"seo_{uuid.uuid4().hex[:8]}",
            system_message="You are a YouTube SEO expert. Create metadata that ranks well and drives clicks.",
        )
        chat.with_model("openai", "gpt-5.2")
        full_script = script_data.get("full_script", str(script_data))[:1000]
        prompt_text = f"""Based on this video about '{topic}':

Script excerpt: {full_script}

Generate SEO-optimized metadata:
1. 5 compelling video titles (max 100 chars each, include power words)
2. Full video description (500+ words) with hook paragraph, keywords, and call to action
3. 20 relevant tags (mix of broad and specific)
4. SEO score estimation

Output as JSON:
{{
    "titles": ["title1", "title2", "title3", "title4", "title5"],
    "description": "Full YouTube description",
    "tags": ["tag1", "tag2"],
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
    "seo_score": 85,
    "suggested_category": "Education"
}}"""
        response = await chat.send_message(UserMessage(text=prompt_text))
        parsed = _parse_json_response(response)
        if parsed and parsed.get("description"):
            return parsed
    except Exception as e:
        logger.error(f"SEO generation failed, using fallback: {e}")
    return fallback


async def generate_ai_thumbnails(title: str, topic: str, count: int = 2) -> List[str]:
    thumbnail_urls = []
    styles = [
        "Bold dramatic style with high contrast colors and cinematic lighting",
        "Clean minimalist modern design with subtle gradients",
        "Energetic dynamic style with bright colors and action elements",
    ]
    for i in range(count):
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"thumb_{uuid.uuid4().hex[:8]}",
                system_message="You are a professional YouTube thumbnail designer. Create eye-catching, click-worthy thumbnails.",
            )
            chat.with_model("gemini", "gemini-3-pro-image-preview").with_params(modalities=["image", "text"])
            prompt = f"""Create a professional YouTube thumbnail for a video titled: "{title}"
Topic: {topic}

Style: {styles[i % len(styles)]}

Requirements:
- 16:9 aspect ratio (YouTube thumbnail format)
- Eye-catching and click-worthy
- Professional quality
- NO text in the image
- High visual impact"""
            text_response, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
            if images:
                mime = images[0].get('mime_type', 'image/png')
                thumbnail_urls.append(f"data:{mime};base64,{images[0]['data']}")
        except Exception as e:
            logger.error(f"AI thumbnail {i+1} generation failed: {e}")
            break
    return thumbnail_urls


async def generate_video_pipeline(video_id: str):
    """Complete video generation pipeline: script -> stock -> voiceover -> thumbnails -> SEO -> render."""

    async def update(fields: Dict):
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.videos.update_one({"video_id": video_id}, {"$set": fields})

    try:
        video = await db.videos.find_one({"video_id": video_id})
        if not video:
            return

        duration_info = DURATION_MAP.get(video["video_length"], DURATION_MAP["medium"])
        user_doc = await db.users.find_one({"user_id": video["user_id"]}, {"_id": 0, "stock_api_keys": 1})
        user_keys = (user_doc or {}).get("stock_api_keys") or {}

        # ===== STEP 1: SCRIPT =====
        await update({"status": VideoStatus.GENERATING_SCRIPT.value, "progress": 8,
                      "progress_message": "Writing your video script with AI..."})
        script_data = await generate_script_with_scenes(video["prompt"], video["video_length"], video.get("language", "en"))
        await update({"script": script_data.get("full_script", ""), "script_data": script_data,
                      "title": script_data.get("title", f"Video: {video['prompt'][:50]}"),
                      "progress": 20, "progress_message": "Script ready! Finding copyright-free footage..."})

        # ===== STEP 2: STOCK FOOTAGE =====
        await update({"status": VideoStatus.GENERATING_VIDEO.value, "progress": 24,
                      "progress_message": "Searching HD stock footage (no watermark)..."})

        keywords = []
        for scene in script_data.get("scenes", []):
            keywords.extend(scene.get("search_keywords", []))
        keywords.extend([w for w in video["prompt"].split() if len(w) > 3][:4])
        seen_kw, unique_kw = set(), []
        for kw in keywords:
            k = str(kw).lower().strip()
            if k and k not in seen_kw:
                seen_kw.add(k)
                unique_kw.append(str(kw))
        unique_kw = unique_kw[:12] or [video["prompt"][:40]]

        clips_needed = duration_info["clips"]
        per_kw = max(2, -(-clips_needed // len(unique_kw)))

        stock_media = {"videos": [], "images": []}
        seen_ids = set()
        for kw in unique_kw:
            vids = await fetch_stock_videos(kw, per_kw, user_keys)
            imgs = await fetch_stock_images(kw, 2, user_keys)
            for v in vids:
                if v["id"] not in seen_ids:
                    seen_ids.add(v["id"])
                    stock_media["videos"].append(v)
            for im in imgs:
                if im["id"] not in seen_ids:
                    seen_ids.add(im["id"])
                    stock_media["images"].append(im)
            if len(stock_media["videos"]) >= clips_needed:
                break

        await update({"stock_media": stock_media, "progress": 38,
                      "progress_message": f"Collected {len(stock_media['videos'])} HD clips! Generating voiceover..."})

        # ===== STEP 3: VOICEOVER =====
        await update({"status": VideoStatus.GENERATING_VOICEOVER.value, "progress": 42,
                      "progress_message": "Generating professional AI voiceover..."})

        voiceover_path = None
        full_script = script_data.get("full_script", "")
        if full_script:
            try:
                audio_bytes = await generate_voiceover(full_script, video["voice_style"])
                out_dir = MEDIA_ROOT / video_id
                out_dir.mkdir(parents=True, exist_ok=True)
                voiceover_path = out_dir / "voiceover.mp3"
                voiceover_path.write_bytes(audio_bytes)
                audio_dur = await probe_duration(voiceover_path)
                await update({"voiceover_url": f"/api/videos/{video_id}/voiceover",
                              "voiceover_duration": round((audio_dur or 0) / 60, 2),
                              "progress": 60, "progress_message": "Voiceover ready! Designing thumbnails..."})
            except Exception as e:
                logger.error(f"Voiceover generation failed: {e}")
                await update({"voiceover_url": None, "voiceover_error": str(e)[:200],
                              "progress": 60, "progress_message": "Voiceover skipped, designing thumbnails..."})

        # ===== STEP 4: THUMBNAILS =====
        await update({"status": VideoStatus.GENERATING_THUMBNAIL.value, "progress": 64,
                      "progress_message": "Creating AI thumbnails..."})
        video_title = script_data.get("title", video["prompt"][:50])
        ai_thumbnails = await generate_ai_thumbnails(video_title, video["prompt"], count=2)
        thumbnail_urls = ai_thumbnails.copy()
        for img in stock_media["images"][:3]:
            if img.get("url") and len(thumbnail_urls) < 5:
                thumbnail_urls.append(img["url"])
        for vid in stock_media["videos"][:2]:
            if vid.get("thumbnail") and len(thumbnail_urls) < 5:
                thumbnail_urls.append(vid["thumbnail"])
        if not thumbnail_urls:
            thumbnail_urls = FALLBACK_THUMBNAILS.copy()
        await update({"thumbnail_urls": thumbnail_urls,
                      "selected_thumbnail_url": thumbnail_urls[0],
                      "ai_thumbnails_count": len(ai_thumbnails),
                      "progress": 74, "progress_message": "Thumbnails ready! Optimizing SEO..."})

        # ===== STEP 5: SEO =====
        seo_data = await generate_seo_metadata(script_data, video["prompt"])
        await update({"seo_data": seo_data, "description": seo_data.get("description", ""),
                      "tags": seo_data.get("tags", []), "seo_score": seo_data.get("seo_score", 75),
                      "progress": 80, "progress_message": "SEO optimized! Rendering your video in HD..."})

        # ===== STEP 6: RENDER FINAL MP4 =====
        await update({"status": VideoStatus.RENDERING.value, "progress": 82,
                      "progress_message": "Rendering HD 1080p video (this takes a few minutes)..."})

        async def render_progress(pct: int, msg: str):
            await update({"progress": pct, "progress_message": msg})

        final_path = await render_video_file(
            video_id,
            stock_media["videos"],
            stock_media["images"],
            voiceover_path,
            duration_info["target_seconds"],
            progress_cb=render_progress,
        )
        rendered_duration = await probe_duration(final_path)

        await update({
            "status": VideoStatus.READY.value,
            "video_url": f"/api/videos/{video_id}/stream",
            "download_url": f"/api/videos/{video_id}/download",
            "rendered_duration": round(rendered_duration or 0, 1),
            "file_size_mb": round(final_path.stat().st_size / (1024 * 1024), 1),
            "progress": 100,
            "progress_message": "Your video is ready!",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Video {video_id} generated and rendered successfully")

    except Exception as e:
        logger.error(f"Video generation failed for {video_id}: {e}")
        import traceback
        traceback.print_exc()
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {"status": VideoStatus.FAILED.value, "error_message": str(e)[:300],
                      "progress": 0, "progress_message": f"Generation failed: {str(e)[:100]}",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )


async def publish_pipeline(video_id: str, channel_id: str, publish_now: bool, scheduled_at: Optional[str]):
    """Upload the rendered video to YouTube via Composio. Scheduled videos upload as private."""
    from youtube import upload_video_to_youtube, set_youtube_thumbnail

    async def update(fields: Dict):
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.videos.update_one({"video_id": video_id}, {"$set": fields})

    video = await db.videos.find_one({"video_id": video_id})
    channel = await db.channels.find_one({"channel_id": channel_id})
    if not video or not channel:
        return

    final_path = MEDIA_ROOT / video_id / "final.mp4"
    if not final_path.exists():
        await update({"status": VideoStatus.READY.value, "publish_error": "Rendered video file not found. Please regenerate the video."})
        return

    conn_id = channel.get("composio_connection_id")
    user_id = channel.get("user_id")
    privacy = "public" if publish_now else "private"

    try:
        await update({"status": VideoStatus.PUBLISHING.value,
                      "progress_message": "Uploading video to YouTube..."})
        response = await upload_video_to_youtube(
            user_id, conn_id, str(final_path),
            title=video.get("title") or video["prompt"][:90],
            description=video.get("description") or "",
            tags=video.get("tags") or [],
            privacy_status=privacy,
        )
        yt_id = None
        if isinstance(response, dict):
            yt_id = response.get("id") or (response.get("response_data") or {}).get("id")
        if not yt_id:
            raise RuntimeError(f"YouTube did not return a video ID: {str(response)[:200]}")

        # Best-effort custom thumbnail
        thumb = video.get("selected_thumbnail_url")
        if thumb:
            try:
                await _prepare_public_thumbnail(video_id, thumb)
                await set_youtube_thumbnail(user_id, conn_id, yt_id, f"{FRONTEND_URL}/api/videos/{video_id}/thumbnail")
            except Exception as te:
                logger.warning(f"Thumbnail set failed (non-fatal): {te}")

        if publish_now:
            await update({"status": VideoStatus.PUBLISHED.value, "youtube_video_id": yt_id,
                          "youtube_url": f"https://youtube.com/watch?v={yt_id}",
                          "published_at": datetime.now(timezone.utc).isoformat(),
                          "publish_error": None,
                          "progress_message": "Published to YouTube!"})
        else:
            await update({"status": VideoStatus.SCHEDULED.value, "youtube_video_id": yt_id,
                          "youtube_url": f"https://youtube.com/watch?v={yt_id}",
                          "scheduled_at": scheduled_at,
                          "publish_error": None,
                          "progress_message": "Uploaded as private. Will go public at the scheduled time."})
        logger.info(f"Video {video_id} uploaded to YouTube: {yt_id}")
    except Exception as e:
        logger.error(f"YouTube publish failed for {video_id}: {e}")
        await update({"status": VideoStatus.READY.value, "publish_error": str(e)[:300],
                      "progress_message": "YouTube upload failed. You can retry publishing."})


async def _prepare_public_thumbnail(video_id: str, thumb: str):
    """Save the selected thumbnail as a <2MB JPEG served publicly for YouTube."""
    import httpx
    out_dir = MEDIA_ROOT / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "thumb_raw"
    if thumb.startswith("data:"):
        raw.write_bytes(base64.b64decode(thumb.split(",", 1)[1]))
    else:
        async with httpx.AsyncClient(follow_redirects=True) as c:
            r = await c.get(thumb, timeout=60.0)
            raw.write_bytes(r.content)
    dest = out_dir / "thumb.jpg"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(raw),
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        "-q:v", "3", str(dest),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    raw.unlink(missing_ok=True)


# =============== ENDPOINTS ===============

@videos_router.post("/create")
async def create_video(req: CreateVideoRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    total_credits = user.video_credits + user.free_video_credits
    if total_credits <= 0:
        raise HTTPException(status_code=403, detail="Insufficient video credits. Please upgrade your plan.")

    if req.video_length not in DURATION_MAP:
        raise HTTPException(status_code=400, detail="Invalid video length")

    video_id = f"vid_{uuid.uuid4().hex[:12]}"
    video_doc = {
        "video_id": video_id,
        "user_id": user.user_id,
        "channel_id": req.channel_id,
        "prompt": req.prompt,
        "video_length": req.video_length,
        "voice_style": req.voice_style,
        "visual_style": req.visual_style,
        "language": req.language,
        "status": VideoStatus.PENDING.value,
        "progress": 0,
        "progress_message": "Starting video generation...",
        "script": None, "script_data": None, "stock_media": None,
        "voiceover_url": None, "voiceover_duration": None,
        "video_url": None, "download_url": None, "rendered_duration": None,
        "thumbnail_urls": [], "selected_thumbnail_url": None,
        "title": None, "description": None, "tags": [],
        "seo_data": None, "seo_score": 0,
        "youtube_video_id": None, "youtube_url": None,
        "scheduled_at": None, "published_at": None,
        "error_message": None, "publish_error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.videos.insert_one(video_doc)

    if user.free_video_credits > 0:
        await db.users.update_one({"user_id": user.user_id}, {"$inc": {"free_video_credits": -1}})
    else:
        await db.users.update_one({"user_id": user.user_id}, {"$inc": {"video_credits": -1}})

    background_tasks.add_task(generate_video_pipeline, video_id)
    return {"video_id": video_id, "status": VideoStatus.PENDING.value,
            "message": "Video generation started", "progress": 0}


@videos_router.get("/")
async def list_videos(user: User = Depends(get_current_user)):
    videos = await db.videos.find(
        {"user_id": user.user_id},
        {"_id": 0, "stock_media": 0, "script_data": 0, "seo_data": 0},
    ).sort("created_at", -1).to_list(100)
    for v in videos:
        if v.get("voiceover_url", "") and v["voiceover_url"].startswith("data:"):
            v["voiceover_url"] = f"/api/videos/{v['video_id']}/voiceover"
    return videos


@videos_router.get("/{video_id}")
async def get_video(video_id: str, user: User = Depends(get_current_user)):
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.get("voiceover_url", "") and video["voiceover_url"].startswith("data:"):
        video["voiceover_url"] = f"/api/videos/{video_id}/voiceover"
    return video


@videos_router.get("/{video_id}/progress")
async def get_video_progress(video_id: str, user: User = Depends(get_current_user)):
    video = await db.videos.find_one(
        {"video_id": video_id, "user_id": user.user_id},
        {"_id": 0, "status": 1, "progress": 1, "progress_message": 1, "error_message": 1, "publish_error": 1},
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@videos_router.get("/{video_id}/stream")
async def stream_video(video_id: str, request: Request, user: User = Depends(get_current_user)):
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id}, {"_id": 0, "video_id": 1})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    path = MEDIA_ROOT / video_id / "final.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Rendered video not available yet")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        try:
            range_val = range_header.replace("bytes=", "").split("-")
            start = int(range_val[0]) if range_val[0] else 0
            end = int(range_val[1]) if len(range_val) > 1 and range_val[1] else file_size - 1
        except ValueError:
            start, end = 0, file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_range():
            with path.open("rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(1024 * 512, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(), status_code=206, media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    return FileResponse(path, media_type="video/mp4", filename=f"{video_id}.mp4",
                        content_disposition_type="inline",
                        headers={"Accept-Ranges": "bytes"})


@videos_router.get("/{video_id}/download")
async def download_video(video_id: str, user: User = Depends(get_current_user)):
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id}, {"_id": 0, "title": 1})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    path = MEDIA_ROOT / video_id / "final.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Rendered video not available yet")
    safe_title = "".join(c for c in (video.get("title") or video_id) if c.isalnum() or c in " -_")[:60].strip() or video_id
    return FileResponse(path, media_type="video/mp4", filename=f"{safe_title}.mp4")


@videos_router.get("/{video_id}/thumbnail")
async def get_public_thumbnail(video_id: str):
    """Public thumbnail endpoint (used by YouTube thumbnail update)."""
    path = MEDIA_ROOT / video_id / "thumb.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")


@videos_router.get("/{video_id}/voiceover")
async def get_video_voiceover(video_id: str, user: User = Depends(get_current_user)):
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id}, {"_id": 0, "voiceover_url": 1})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    path = MEDIA_ROOT / video_id / "voiceover.mp3"
    if path.exists():
        return FileResponse(path, media_type="audio/mpeg", content_disposition_type="inline")

    voiceover_url = video.get("voiceover_url")
    if voiceover_url and voiceover_url.startswith("data:audio"):
        audio_bytes = base64.b64decode(voiceover_url.split(",")[1])
        return StreamingResponse(iter([audio_bytes]), media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Voiceover not available")


@videos_router.patch("/{video_id}")
async def update_video(video_id: str, req: UpdateVideoRequest, user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not update_data:
        return {"message": "No updates provided"}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.videos.update_one(
        {"video_id": video_id, "user_id": user.user_id}, {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"message": "Video updated"}


@videos_router.delete("/{video_id}")
async def delete_video(video_id: str, user: User = Depends(get_current_user)):
    result = await db.videos.delete_one({"video_id": video_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    import shutil
    shutil.rmtree(MEDIA_ROOT / video_id, ignore_errors=True)
    return {"message": "Video deleted"}


@videos_router.post("/{video_id}/regenerate")
async def regenerate_video_parts(video_id: str, req: RegenerateRequest, background_tasks: BackgroundTasks,
                                 user: User = Depends(get_current_user)):
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    await db.videos.update_one(
        {"video_id": video_id},
        {"$set": {"status": VideoStatus.PENDING.value, "progress": 0, "error_message": None,
                  "progress_message": "Restarting video generation..."}},
    )
    background_tasks.add_task(generate_video_pipeline, video_id)
    return {"message": "Regeneration started", "video_id": video_id}


@videos_router.post("/{video_id}/publish")
async def publish_video(video_id: str, req: ScheduleVideoRequest, background_tasks: BackgroundTasks,
                        user: User = Depends(get_current_user)):
    """Publish now or schedule the rendered video to YouTube via Composio."""
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["status"] not in (VideoStatus.READY.value, VideoStatus.SCHEDULED.value):
        raise HTTPException(status_code=400, detail="Video is not ready for publishing")

    final_path = MEDIA_ROOT / video_id / "final.mp4"
    if not final_path.exists():
        raise HTTPException(status_code=400, detail="Rendered video file not found. Please regenerate the video first.")

    channel = await db.channels.find_one({"channel_id": req.channel_id, "user_id": user.user_id, "is_active": True})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not channel.get("composio_connection_id"):
        raise HTTPException(status_code=400, detail="Channel has no active YouTube connection. Please reconnect.")

    scheduled_iso = None
    if not req.publish_now:
        if not req.scheduled_at:
            raise HTTPException(status_code=400, detail="scheduled_at is required when not publishing immediately")
        try:
            dt = datetime.fromisoformat(req.scheduled_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            scheduled_iso = dt.isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at datetime")
        if dt <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

    await db.videos.update_one(
        {"video_id": video_id},
        {"$set": {"channel_id": req.channel_id, "status": VideoStatus.PUBLISHING.value,
                  "progress_message": "Uploading to YouTube...",
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    background_tasks.add_task(publish_pipeline, video_id, req.channel_id, req.publish_now, scheduled_iso)

    return {
        "message": "Uploading to YouTube now..." if req.publish_now else "Uploading to YouTube — video will go live at the scheduled time",
        "status": VideoStatus.PUBLISHING.value,
        "channel_name": channel.get("channel_name"),
    }
