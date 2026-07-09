"""Coverr built-in stock provider (videos).

Coverr exposes a public JSON API at api.coverr.co/videos which returns
searchable results without requiring an API key for anonymous access
(rate-limited). This adapter reads that endpoint and falls back to an
empty list on any failure so the pipeline stays healthy.

No user API key required.
"""
import logging
from typing import List, Dict, Optional

import httpx

from .base import StockProvider

logger = logging.getLogger(__name__)


class CoverrProvider(StockProvider):
    slug = "coverr"
    display_name = "Coverr"
    requires_api_key = False
    supports_videos = True
    supports_images = False

    _SEARCH_URL = "https://api.coverr.co/videos"

    async def search_videos(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get(
                    self._SEARCH_URL,
                    params={"query": query, "urls": "true", "page_size": max(count, 3)},
                    timeout=20.0,
                )
            if r.status_code != 200:
                logger.warning(f"[coverr] API returned {r.status_code}")
                return []
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            hits = data.get("hits") or data.get("videos") or data.get("results") or []
            out: List[Dict] = []
            for hit in hits[:count]:
                vid = hit.get("id") or hit.get("_id") or hit.get("slug")
                urls = hit.get("urls") or {}
                mp4 = (
                    urls.get("mp4")
                    or urls.get("mp4_download")
                    or urls.get("preview")
                    or hit.get("mp4_url")
                )
                poster = (
                    urls.get("poster")
                    or hit.get("poster")
                    or hit.get("thumbnail")
                )
                if not mp4 or not vid:
                    continue
                out.append({
                    "id": f"coverr_{vid}",
                    "url": mp4,
                    "thumbnail": poster,
                    "duration": hit.get("max_duration") or hit.get("duration"),
                    "source": "coverr",
                })
            return out
        except Exception as e:
            logger.error(f"[coverr] videos fetch error: {e}")
            return []
