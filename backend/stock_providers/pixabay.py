"""Pixabay stock media provider (videos + images).

Requires a per-user API key.
"""
import logging
from typing import List, Dict, Optional

import httpx

from .base import StockProvider

logger = logging.getLogger(__name__)


class PixabayProvider(StockProvider):
    slug = "pixabay"
    display_name = "Pixabay"
    requires_api_key = True
    supports_videos = True
    supports_images = True

    _VIDEOS_URL = "https://pixabay.com/api/videos/"
    _IMAGES_URL = "https://pixabay.com/api/"

    async def search_videos(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    self._VIDEOS_URL,
                    params={
                        "key": api_key, "q": query,
                        "per_page": max(count, 3), "safesearch": "true",
                    },
                    timeout=30.0,
                )
            if r.status_code != 200:
                logger.warning(f"[pixabay] videos API returned {r.status_code}")
                return []
            out: List[Dict] = []
            for hit in r.json().get("hits", [])[:count]:
                sizes = hit.get("videos", {})
                best = sizes.get("large") or sizes.get("medium") or sizes.get("small")
                if best and best.get("url"):
                    out.append({
                        "id": f"pixabay_{hit.get('id')}",
                        "url": best["url"],
                        "thumbnail": best.get("thumbnail") or (sizes.get("tiny") or {}).get("thumbnail"),
                        "duration": hit.get("duration"),
                        "width": best.get("width"),
                        "height": best.get("height"),
                        "source": "pixabay",
                    })
            return out
        except Exception as e:
            logger.error(f"[pixabay] videos fetch error: {e}")
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
                    params={
                        "key": api_key, "q": query,
                        "per_page": max(count, 3),
                        "orientation": "horizontal", "safesearch": "true",
                    },
                    timeout=30.0,
                )
            if r.status_code != 200:
                logger.warning(f"[pixabay] images API returned {r.status_code}")
                return []
            out: List[Dict] = []
            for hit in r.json().get("hits", [])[:count]:
                out.append({
                    "id": f"pixabay_{hit.get('id')}",
                    "url": hit.get("largeImageURL") or hit.get("webformatURL"),
                    "thumbnail": hit.get("previewURL"),
                    "alt": hit.get("tags", ""),
                    "source": "pixabay",
                })
            return out
        except Exception as e:
            logger.error(f"[pixabay] images fetch error: {e}")
            return []

    async def validate_key(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    self._IMAGES_URL,
                    params={"key": api_key, "q": "nature", "per_page": 3},
                    timeout=15.0,
                )
            return r.status_code == 200
        except Exception:
            return False
