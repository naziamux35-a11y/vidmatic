import os
import httpx
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_PEXELS_KEY = os.environ.get("PEXELS_API_KEY")


async def fetch_pexels_videos(query: str, count: int, api_key: Optional[str] = None) -> List[Dict]:
    key = api_key or DEFAULT_PEXELS_KEY
    if not key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.pexels.com/videos/search",
                params={"query": query, "per_page": count, "orientation": "landscape"},
                headers={"Authorization": key},
                timeout=30.0,
            )
        if r.status_code != 200:
            logger.warning(f"Pexels videos API returned {r.status_code}")
            return []
        videos = []
        for video in r.json().get("videos", [])[:count]:
            files = video.get("video_files", [])
            best = None
            for vf in sorted(files, key=lambda f: f.get("width") or 0, reverse=True):
                if (vf.get("width") or 0) <= 1920 and (vf.get("width") or 0) >= 960:
                    best = vf
                    break
            if not best and files:
                best = files[0]
            if best:
                videos.append({
                    "id": f"pexels_{video.get('id')}",
                    "url": best.get("link"),
                    "thumbnail": video.get("image"),
                    "duration": video.get("duration"),
                    "width": best.get("width"),
                    "height": best.get("height"),
                    "source": "pexels",
                })
        return videos
    except Exception as e:
        logger.error(f"Pexels videos fetch error: {e}")
        return []


async def fetch_pexels_images(query: str, count: int, api_key: Optional[str] = None) -> List[Dict]:
    key = api_key or DEFAULT_PEXELS_KEY
    if not key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "per_page": count, "orientation": "landscape"},
                headers={"Authorization": key},
                timeout=30.0,
            )
        if r.status_code != 200:
            logger.warning(f"Pexels images API returned {r.status_code}")
            return []
        images = []
        for photo in r.json().get("photos", [])[:count]:
            src = photo.get("src", {})
            images.append({
                "id": f"pexels_{photo.get('id')}",
                "url": src.get("large2x") or src.get("large"),
                "thumbnail": src.get("medium"),
                "alt": photo.get("alt", ""),
                "source": "pexels",
            })
        return images
    except Exception as e:
        logger.error(f"Pexels images fetch error: {e}")
        return []


async def fetch_pixabay_videos(query: str, count: int, api_key: str) -> List[Dict]:
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://pixabay.com/api/videos/",
                params={"key": api_key, "q": query, "per_page": max(count, 3), "safesearch": "true"},
                timeout=30.0,
            )
        if r.status_code != 200:
            logger.warning(f"Pixabay videos API returned {r.status_code}")
            return []
        videos = []
        for hit in r.json().get("hits", [])[:count]:
            sizes = hit.get("videos", {})
            best = sizes.get("large") or sizes.get("medium") or sizes.get("small")
            if best and best.get("url"):
                videos.append({
                    "id": f"pixabay_{hit.get('id')}",
                    "url": best["url"],
                    "thumbnail": best.get("thumbnail") or (sizes.get("tiny") or {}).get("thumbnail"),
                    "duration": hit.get("duration"),
                    "width": best.get("width"),
                    "height": best.get("height"),
                    "source": "pixabay",
                })
        return videos
    except Exception as e:
        logger.error(f"Pixabay videos fetch error: {e}")
        return []


async def fetch_pixabay_images(query: str, count: int, api_key: str) -> List[Dict]:
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://pixabay.com/api/",
                params={"key": api_key, "q": query, "per_page": max(count, 3), "orientation": "horizontal", "safesearch": "true"},
                timeout=30.0,
            )
        if r.status_code != 200:
            return []
        images = []
        for hit in r.json().get("hits", [])[:count]:
            images.append({
                "id": f"pixabay_{hit.get('id')}",
                "url": hit.get("largeImageURL") or hit.get("webformatURL"),
                "thumbnail": hit.get("previewURL"),
                "alt": hit.get("tags", ""),
                "source": "pixabay",
            })
        return images
    except Exception as e:
        logger.error(f"Pixabay images fetch error: {e}")
        return []


async def fetch_stock_videos(query: str, count: int, user_keys: Dict) -> List[Dict]:
    """Fetch stock videos using user's own API keys when available."""
    user_keys = user_keys or {}
    results = await fetch_pexels_videos(query, count, user_keys.get("pexels"))
    if user_keys.get("pixabay"):
        results.extend(await fetch_pixabay_videos(query, count, user_keys["pixabay"]))
    return results


async def fetch_stock_images(query: str, count: int, user_keys: Dict) -> List[Dict]:
    user_keys = user_keys or {}
    results = await fetch_pexels_images(query, count, user_keys.get("pexels"))
    if user_keys.get("pixabay"):
        results.extend(await fetch_pixabay_images(query, count, user_keys["pixabay"]))
    return results


async def validate_pexels_key(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.pexels.com/v1/search",
                params={"query": "nature", "per_page": 1},
                headers={"Authorization": api_key},
                timeout=15.0,
            )
        return r.status_code == 200
    except Exception:
        return False


async def validate_pixabay_key(api_key: str) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://pixabay.com/api/",
                params={"key": api_key, "q": "nature", "per_page": 3},
                timeout=15.0,
            )
        return r.status_code == 200
    except Exception:
        return False
