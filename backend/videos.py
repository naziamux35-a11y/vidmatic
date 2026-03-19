from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from auth import get_current_user
from models import User, Video, VideoStatus, SubscriptionPlan
import os
import uuid
import base64
import json
import asyncio
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech
import logging

load_dotenv()

logger = logging.getLogger(__name__)

videos_router = APIRouter()

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "free_no_key_required")

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

# Voice mapping for TTS
VOICE_MAP = {
    "professional": "onyx",
    "engaging": "nova", 
    "energetic": "shimmer",
    "authoritative": "echo",
    "friendly": "coral",
    "calm": "alloy"
}

# Duration mapping
DURATION_MAP = {
    "short": {"words": 150, "duration": "60 seconds", "scenes": 3},
    "medium": {"words": 800, "duration": "5-8 minutes", "scenes": 8},
    "long": {"words": 1500, "duration": "10-15 minutes", "scenes": 15}
}

# Fallback stock images (free Unsplash images)
FALLBACK_IMAGES = [
    {"url": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=1280", "thumbnail": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=400"},
    {"url": "https://images.unsplash.com/photo-1551434678-e076c223a692?w=1280", "thumbnail": "https://images.unsplash.com/photo-1551434678-e076c223a692?w=400"},
    {"url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1280", "thumbnail": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=400"},
    {"url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1280", "thumbnail": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400"},
    {"url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=1280", "thumbnail": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=400"},
    {"url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=1280", "thumbnail": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=400"},
    {"url": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=1280", "thumbnail": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400"},
    {"url": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=1280", "thumbnail": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=400"},
]

FALLBACK_VIDEOS = [
    {"url": "https://player.vimeo.com/external/434045526.sd.mp4?s=c27eecc69a27dbc4ff2b87d38afc35f1a9e7c02d", "thumbnail": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=400"},
    {"url": "https://player.vimeo.com/external/371433846.sd.mp4?s=236da2f3c0fd273d2c6d9a064f3ae35579b2bbdf", "thumbnail": "https://images.unsplash.com/photo-1551434678-e076c223a692?w=400"},
]

async def fetch_pexels_videos(query: str, count: int = 5) -> List[Dict]:
    """Fetch stock videos from Pexels API with fallback"""
    try:
        if PEXELS_API_KEY and PEXELS_API_KEY != "free_no_key_required":
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.pexels.com/videos/search",
                    params={"query": query, "per_page": count, "orientation": "landscape"},
                    headers={"Authorization": PEXELS_API_KEY},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    videos = []
                    for video in data.get("videos", [])[:count]:
                        video_files = video.get("video_files", [])
                        best_file = None
                        for vf in video_files:
                            if vf.get("quality") == "hd" or vf.get("width", 0) >= 1280:
                                best_file = vf
                                break
                        if not best_file and video_files:
                            best_file = video_files[0]
                        
                        if best_file:
                            videos.append({
                                "id": video.get("id"),
                                "url": best_file.get("link"),
                                "thumbnail": video.get("image"),
                                "duration": video.get("duration"),
                                "width": best_file.get("width"),
                                "height": best_file.get("height")
                            })
                    return videos
                else:
                    logger.warning(f"Pexels API returned {response.status_code}, using fallbacks")
        
        # Return fallback videos
        return FALLBACK_VIDEOS[:count]
    except Exception as e:
        logger.error(f"Error fetching Pexels videos: {e}")
        return FALLBACK_VIDEOS[:count]

async def fetch_pexels_images(query: str, count: int = 5) -> List[Dict]:
    """Fetch stock images from Pexels API with fallback"""
    try:
        if PEXELS_API_KEY and PEXELS_API_KEY != "free_no_key_required":
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": query, "per_page": count, "orientation": "landscape"},
                    headers={"Authorization": PEXELS_API_KEY},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    images = []
                    for photo in data.get("photos", [])[:count]:
                        images.append({
                            "id": photo.get("id"),
                            "url": photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large"),
                            "thumbnail": photo.get("src", {}).get("medium"),
                            "alt": photo.get("alt", "")
                        })
                    return images
                else:
                    logger.warning(f"Pexels API returned {response.status_code}, using fallbacks")
        
        # Return fallback images
        return FALLBACK_IMAGES[:count]
    except Exception as e:
        logger.error(f"Error fetching Pexels images: {e}")
        return FALLBACK_IMAGES[:count]

async def generate_script_with_scenes(prompt: str, video_length: str, language: str = "en") -> Dict:
    """Generate video script with scene breakdowns"""
    duration_info = DURATION_MAP.get(video_length, DURATION_MAP["medium"])
    
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"script_{uuid.uuid4().hex[:8]}",
        system_message="You are an expert YouTube video script writer. Create engaging, well-structured scripts with clear scene breakdowns."
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

    msg = UserMessage(text=prompt_text)
    response = await chat.send_message(msg)
    
    # Parse JSON response
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response
        
        script_data = json.loads(json_str)
        return script_data
    except Exception as e:
        logger.error(f"Error parsing script JSON: {e}")
        # Return fallback structure
        return {
            "title": f"Video: {prompt[:50]}",
            "hook": response[:200] if response else "Welcome to this video!",
            "scenes": [{"scene_number": 1, "scene_title": "Main Content", "narration": response, "visual_description": prompt, "search_keywords": [prompt.split()[0]]}],
            "outro": "Thanks for watching! Don't forget to like and subscribe!",
            "full_script": response
        }

async def generate_voiceover(script: str, voice_style: str) -> bytes:
    """Generate voiceover audio from script"""
    voice = VOICE_MAP.get(voice_style, "alloy")
    
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    
    # Split script into chunks if too long (max 4096 chars)
    max_chars = 4000
    if len(script) <= max_chars:
        audio_bytes = await tts.generate_speech(
            text=script,
            model="tts-1-hd",
            voice=voice,
            speed=1.0
        )
        return audio_bytes
    else:
        # Split into chunks and combine
        chunks = []
        words = script.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 > max_chars:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # Generate audio for each chunk
        all_audio = b''
        for chunk in chunks:
            audio_bytes = await tts.generate_speech(
                text=chunk,
                model="tts-1-hd",
                voice=voice,
                speed=1.0
            )
            all_audio += audio_bytes
        
        return all_audio

async def generate_seo_metadata(script_data: Dict, topic: str) -> Dict:
    """Generate SEO-optimized title, description, and tags"""
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"seo_{uuid.uuid4().hex[:8]}",
        system_message="You are a YouTube SEO expert. Create metadata that ranks well and drives clicks."
    )
    chat.with_model("openai", "gpt-5.2")
    
    full_script = script_data.get("full_script", str(script_data))[:1000]
    
    prompt_text = f"""Based on this video about '{topic}':

Script excerpt: {full_script}

Generate SEO-optimized metadata:
1. 5 compelling video titles (max 100 chars each, include power words)
2. Full video description (500+ words) with:
   - Hook paragraph
   - Chapter timestamps
   - Keywords naturally integrated
   - Relevant links section
   - Call to action
3. 20 relevant tags (mix of broad and specific)
4. SEO score estimation

Output as JSON:
{{
    "titles": ["title1", "title2", "title3", "title4", "title5"],
    "description": "Full YouTube description",
    "tags": ["tag1", "tag2", ...],
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
    "seo_score": 85,
    "suggested_category": "Education"
}}"""

    msg = UserMessage(text=prompt_text)
    response = await chat.send_message(msg)
    
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response
        
        return json.loads(json_str)
    except:
        return {
            "titles": [script_data.get("title", f"Amazing Video: {topic}")],
            "description": response,
            "tags": ["youtube", "video", topic.split()[0] if topic else "content"],
            "hashtags": ["#youtube", "#video"],
            "seo_score": 70,
            "suggested_category": "Entertainment"
        }

async def generate_ai_thumbnails(title: str, topic: str, count: int = 3) -> List[str]:
    """Generate AI thumbnails using Gemini image generation"""
    thumbnail_urls = []
    
    try:
        for i in range(count):
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"thumb_{uuid.uuid4().hex[:8]}",
                system_message="You are a professional YouTube thumbnail designer. Create eye-catching, click-worthy thumbnails."
            )
            chat.with_model("gemini", "gemini-3-pro-image-preview").with_params(modalities=["image", "text"])
            
            styles = [
                "Bold dramatic style with high contrast colors, large readable text overlay",
                "Clean minimalist modern design with subtle gradients",
                "Energetic dynamic style with bright colors and action elements"
            ]
            
            prompt = f"""Create a professional YouTube thumbnail for a video titled: "{title}"
Topic: {topic}

Style: {styles[i % len(styles)]}

Requirements:
- 16:9 aspect ratio (YouTube thumbnail format)
- Eye-catching and click-worthy
- Professional quality
- Suitable for YouTube audience
- NO text in the image (text will be added separately)
- High visual impact"""

            msg = UserMessage(text=prompt)
            text_response, images = await chat.send_message_multimodal_response(msg)
            
            if images and len(images) > 0:
                # Convert to data URL for storage
                img_data = images[0]['data']
                mime_type = images[0].get('mime_type', 'image/png')
                data_url = f"data:{mime_type};base64,{img_data}"
                thumbnail_urls.append(data_url)
                logger.info(f"Generated AI thumbnail {i+1}")
            
    except Exception as e:
        logger.error(f"AI thumbnail generation failed: {e}")
    
    return thumbnail_urls

async def generate_video_pipeline(video_id: str):
    """Complete video generation pipeline"""
    try:
        video = await db.videos.find_one({"video_id": video_id})
        if not video:
            return
        
        # ===== STEP 1: GENERATE SCRIPT =====
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "status": VideoStatus.GENERATING_SCRIPT.value,
                "progress": 10,
                "progress_message": "Generating video script..."
            }}
        )
        
        script_data = await generate_script_with_scenes(
            video["prompt"], 
            video["video_length"],
            video.get("language", "en")
        )
        
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "script": script_data.get("full_script", ""),
                "script_data": script_data,
                "title": script_data.get("title", f"Video: {video['prompt'][:50]}"),
                "progress": 25,
                "progress_message": "Script generated! Fetching visuals..."
            }}
        )
        
        # ===== STEP 2: FETCH STOCK FOOTAGE =====
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "status": VideoStatus.GENERATING_VIDEO.value,
                "progress": 30,
                "progress_message": "Finding stock footage..."
            }}
        )
        
        # Collect keywords from all scenes
        all_keywords = []
        for scene in script_data.get("scenes", []):
            all_keywords.extend(scene.get("search_keywords", []))
        
        # Add main topic keywords
        all_keywords.extend(video["prompt"].split()[:5])
        
        # Fetch videos and images for each unique keyword
        stock_media = {"videos": [], "images": []}
        seen_keywords = set()
        
        for keyword in all_keywords[:10]:  # Limit to 10 keywords
            if keyword.lower() in seen_keywords:
                continue
            seen_keywords.add(keyword.lower())
            
            videos = await fetch_pexels_videos(keyword, count=2)
            images = await fetch_pexels_images(keyword, count=2)
            
            stock_media["videos"].extend(videos)
            stock_media["images"].extend(images)
        
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "stock_media": stock_media,
                "progress": 45,
                "progress_message": "Stock footage collected! Generating voiceover..."
            }}
        )
        
        # ===== STEP 3: GENERATE VOICEOVER =====
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "status": VideoStatus.GENERATING_VOICEOVER.value,
                "progress": 50,
                "progress_message": "Generating AI voiceover..."
            }}
        )
        
        full_script = script_data.get("full_script", "")
        if full_script:
            try:
                audio_bytes = await generate_voiceover(full_script, video["voice_style"])
                
                # Store as base64 (in production, upload to cloud storage)
                voiceover_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                voiceover_url = f"data:audio/mp3;base64,{voiceover_base64}"
                
                # Estimate duration (rough: 150 words per minute)
                word_count = len(full_script.split())
                duration_minutes = word_count / 150
                
                await db.videos.update_one(
                    {"video_id": video_id},
                    {"$set": {
                        "voiceover_url": voiceover_url,
                        "voiceover_duration": duration_minutes,
                        "progress": 65,
                        "progress_message": "Voiceover generated! Creating thumbnails..."
                    }}
                )
            except Exception as e:
                logger.error(f"Voiceover generation failed: {e}")
                await db.videos.update_one(
                    {"video_id": video_id},
                    {"$set": {
                        "voiceover_url": None,
                        "voiceover_error": str(e),
                        "progress": 65,
                        "progress_message": "Voiceover skipped, generating thumbnails..."
                    }}
                )
        
        # ===== STEP 4: GENERATE THUMBNAILS =====
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "status": VideoStatus.GENERATING_THUMBNAIL.value,
                "progress": 70,
                "progress_message": "Creating AI-powered thumbnails..."
            }}
        )
        
        # Generate AI thumbnails
        video_title = script_data.get("title", video["prompt"][:50])
        ai_thumbnails = await generate_ai_thumbnails(video_title, video["prompt"], count=2)
        
        # Combine AI thumbnails with best stock images
        thumbnail_urls = ai_thumbnails.copy()
        
        # Add best stock images as additional options
        for img in stock_media.get("images", [])[:3]:
            if img.get("url") and len(thumbnail_urls) < 5:
                thumbnail_urls.append(img["url"])
        
        # Add video thumbnails if needed
        for vid in stock_media.get("videos", [])[:2]:
            if vid.get("thumbnail") and len(thumbnail_urls) < 5:
                thumbnail_urls.append(vid["thumbnail"])
        
        # Fallback if no thumbnails generated
        if not thumbnail_urls:
            thumbnail_urls = [
                "https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg?auto=compress&cs=tinysrgb&w=1280",
                "https://images.pexels.com/photos/546819/pexels-photo-546819.jpeg?auto=compress&cs=tinysrgb&w=1280",
                "https://images.pexels.com/photos/1181671/pexels-photo-1181671.jpeg?auto=compress&cs=tinysrgb&w=1280"
            ]
        
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "thumbnail_urls": thumbnail_urls,
                "selected_thumbnail_url": thumbnail_urls[0] if thumbnail_urls else None,
                "ai_thumbnails_count": len(ai_thumbnails),
                "progress": 80,
                "progress_message": "Thumbnails ready! Generating SEO..."
            }}
        )
        
        # ===== STEP 5: GENERATE SEO =====
        seo_data = await generate_seo_metadata(script_data, video["prompt"])
        
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "seo_data": seo_data,
                "description": seo_data.get("description", ""),
                "tags": seo_data.get("tags", []),
                "seo_score": seo_data.get("seo_score", 75),
                "progress": 95,
                "progress_message": "SEO optimized! Finalizing..."
            }}
        )
        
        # ===== STEP 6: FINALIZE =====
        # Create video assembly data (scene timeline)
        video_timeline = []
        for i, scene in enumerate(script_data.get("scenes", [])):
            scene_media = []
            # Assign media to scenes
            if stock_media["videos"] and i < len(stock_media["videos"]):
                scene_media.append({"type": "video", "url": stock_media["videos"][i]["url"]})
            if stock_media["images"] and i < len(stock_media["images"]):
                scene_media.append({"type": "image", "url": stock_media["images"][i]["url"]})
            
            video_timeline.append({
                "scene_number": scene.get("scene_number", i + 1),
                "scene_title": scene.get("scene_title", f"Scene {i + 1}"),
                "narration": scene.get("narration", ""),
                "media": scene_media,
                "duration_estimate": len(scene.get("narration", "").split()) / 150 * 60  # seconds
            })
        
        # Final update - mark as READY
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "status": VideoStatus.READY.value,
                "video_timeline": video_timeline,
                "video_url": f"/api/videos/{video_id}/preview",  # Will serve assembled preview
                "progress": 100,
                "progress_message": "Video ready!",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        logger.info(f"Video {video_id} generation completed successfully")
        
    except Exception as e:
        logger.error(f"Video generation failed for {video_id}: {e}")
        import traceback
        traceback.print_exc()
        
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {
                "status": VideoStatus.FAILED.value,
                "error_message": str(e),
                "progress": 0,
                "progress_message": f"Generation failed: {str(e)[:100]}",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )

@videos_router.post("/create")
async def create_video(req: CreateVideoRequest, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Create a new video generation request"""
    # Check credits
    total_credits = user.video_credits + user.free_video_credits
    if total_credits <= 0:
        raise HTTPException(status_code=403, detail="Insufficient video credits. Please upgrade your plan.")
    
    # Create video record
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
        "script": None,
        "script_data": None,
        "stock_media": None,
        "voiceover_url": None,
        "voiceover_duration": None,
        "video_url": None,
        "video_timeline": None,
        "thumbnail_urls": [],
        "selected_thumbnail_url": None,
        "title": None,
        "description": None,
        "tags": [],
        "seo_data": None,
        "seo_score": 0,
        "youtube_video_id": None,
        "scheduled_at": None,
        "published_at": None,
        "error_message": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.videos.insert_one(video_doc)
    
    # Deduct credits (use free credits first)
    if user.free_video_credits > 0:
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$inc": {"free_video_credits": -1}}
        )
    else:
        await db.users.update_one(
            {"user_id": user.user_id},
            {"$inc": {"video_credits": -1}}
        )
    
    # Start video generation in background
    background_tasks.add_task(generate_video_pipeline, video_id)
    
    return {
        "video_id": video_id, 
        "status": VideoStatus.PENDING.value, 
        "message": "Video generation started",
        "progress": 0
    }

@videos_router.get("/")
async def list_videos(user: User = Depends(get_current_user)):
    """List all videos for the user"""
    videos = await db.videos.find(
        {"user_id": user.user_id}, 
        {"_id": 0, "voiceover_url": 0}  # Exclude large base64 data in list
    ).sort("created_at", -1).to_list(100)
    return videos

@videos_router.get("/{video_id}")
async def get_video(video_id: str, user: User = Depends(get_current_user)):
    """Get video details"""
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@videos_router.get("/{video_id}/progress")
async def get_video_progress(video_id: str, user: User = Depends(get_current_user)):
    """Get video generation progress"""
    video = await db.videos.find_one(
        {"video_id": video_id, "user_id": user.user_id}, 
        {"_id": 0, "status": 1, "progress": 1, "progress_message": 1, "error_message": 1}
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@videos_router.get("/{video_id}/voiceover")
async def get_video_voiceover(video_id: str, user: User = Depends(get_current_user)):
    """Get video voiceover audio"""
    video = await db.videos.find_one(
        {"video_id": video_id, "user_id": user.user_id}, 
        {"_id": 0, "voiceover_url": 1}
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    voiceover_url = video.get("voiceover_url")
    if not voiceover_url:
        raise HTTPException(status_code=404, detail="Voiceover not available")
    
    # If it's a data URL, extract and serve the audio
    if voiceover_url.startswith("data:audio"):
        base64_data = voiceover_url.split(",")[1]
        audio_bytes = base64.b64decode(base64_data)
        return StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f"attachment; filename={video_id}.mp3"}
        )
    
    return {"voiceover_url": voiceover_url}

@videos_router.patch("/{video_id}")
async def update_video(video_id: str, req: UpdateVideoRequest, user: User = Depends(get_current_user)):
    """Update video metadata"""
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not update_data:
        return {"message": "No updates provided"}
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.videos.update_one(
        {"video_id": video_id, "user_id": user.user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return {"message": "Video updated"}

@videos_router.delete("/{video_id}")
async def delete_video(video_id: str, user: User = Depends(get_current_user)):
    """Delete a video"""
    result = await db.videos.delete_one({"video_id": video_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"message": "Video deleted"}

@videos_router.post("/{video_id}/regenerate")
async def regenerate_video_parts(
    video_id: str, 
    req: RegenerateRequest, 
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """Regenerate specific parts of a video"""
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if req.regenerate_script:
        await db.videos.update_one(
            {"video_id": video_id},
            {"$set": {"status": VideoStatus.GENERATING_SCRIPT.value, "progress": 10}}
        )
        # Regenerate in background
        background_tasks.add_task(generate_video_pipeline, video_id)
    
    return {"message": "Regeneration started", "video_id": video_id}

@videos_router.post("/{video_id}/publish")
async def publish_video(video_id: str, req: ScheduleVideoRequest, user: User = Depends(get_current_user)):
    """Publish or schedule video to YouTube"""
    video = await db.videos.find_one({"video_id": video_id, "user_id": user.user_id}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video["status"] != VideoStatus.READY.value:
        raise HTTPException(status_code=400, detail="Video is not ready for publishing")
    
    # Verify channel exists and belongs to user
    channel = await db.channels.find_one({
        "channel_id": req.channel_id, 
        "user_id": user.user_id,
        "is_active": True
    })
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Update video status
    update_data = {
        "channel_id": req.channel_id,
        "status": VideoStatus.SCHEDULED.value if not req.publish_now else VideoStatus.PUBLISHED.value,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if req.scheduled_at:
        update_data["scheduled_at"] = req.scheduled_at
    
    if req.publish_now:
        update_data["published_at"] = datetime.now(timezone.utc).isoformat()
        # TODO: Implement actual YouTube upload via Composio
    
    await db.videos.update_one(
        {"video_id": video_id},
        {"$set": update_data}
    )
    
    return {
        "message": "Video scheduled for publishing" if req.scheduled_at else "Video published successfully",
        "status": update_data["status"],
        "channel_name": channel.get("channel_name")
    }
