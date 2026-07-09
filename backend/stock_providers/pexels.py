"""Pexels stock media provider (videos + images).

Requires a per-user API key. Default fallback key from env is intentionally
not used here — the provider only fires when a user has supplied their own
key (or the engine passes one explicitly).
"""
import logging
from typing import List, Dict, Optional

import httpx

from .base import StockProvider

logger = logging.getLogger(__name__)


class PexelsProvider(StockProvider):
    slug = "pexels"
    display_name = "Pexels"
    requires_api_key = True
    supports_videos = True
    supports_images = True

    _VIDEOS_URL = "https://api.pexels.com/videos/search"
    _IMAGES_URL = "https://api.pexels.com/v1/search"
    _VALIDATE_URL = "https://api.pexels.com/v1/collections/featured"

    async def search_videos(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    self._VIDEOS_URL,
                    params={"query": query, "per_page": count, "orientation": "landscape"},
                    headers={"Authorization": api_key},
                    timeout=30.0,
                )
            if r.status_code != 200:
                logger.warning(f"[pexels] videos API returned {r.status_code}")
                return []
            out: List[Dict] = []
            for video in r.json().get("videos", [])[:count]:
                files = video.get("video_files", [])
                best = None
                for vf in sorted(files, key=lambda f: f.get("width") or 0, reverse=True):
                    w = vf.get("width") or 0
                    if 960 <= w <= 1920:
                        best = vf
                        break
                if not best and files:
                    best = files[0]
                if best:
                    out.append({
                        "id": f"pexels_{video.get('id')}",
                        "url": best.get("link"),
                        "thumbnail": video.get("image"),
                        "duration": video.get("duration"),
                        "width": best.get("width"),
                        "height": best.get("height"),
                        "source": "pexels",
                    })
            return out
        except Exception as e:
            logger.error(f"[pexels] videos fetch error: {e}")
            return []

    async def search_images(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    self._IMAGES_URL,
                    params={"query": query, "per_page": count, "orientation": "landscape"},
                    headers={"Authorization": api_key},
                    timeout=30.0,
                )
            if r.status_code != 200:
                logger.warning(f"[pexels] images API returned {r.status_code}")
                return []
            out: List[Dict] = []
            for photo in r.json().get("photos", [])[:count]:
                src = photo.get("src", {})
                out.append({
                    "id": f"pexels_{photo.get('id')}",
                    "url": src.get("large2x") or src.get("large"),
                    "thumbnail": src.get("medium"),
                    "alt": photo.get("alt", ""),
                    "source": "pexels",
                })
            return out
        except Exception as e:
            logger.error(f"[pexels] images fetch error: {e}")
            return []

    async def validate_key(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    self._VALIDATE_URL,
                    params={"per_page": 1},
                    headers={"Authorization": api_key},
                    timeout=15.0,
                )
            return r.status_code == 200
        except Exception:
            return False
