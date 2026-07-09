"""Videvo stock media provider (videos).

Requires a per-user API key from https://www.videvo.net/api/ (partner API).
Videvo's public developer API surface is not as standardised as Pexels/Pixabay,
so this adapter is written defensively: any auth/schema issue results in an
empty list, never a raised exception into the pipeline.
"""
import logging
from typing import List, Dict, Optional

import httpx

from .base import StockProvider

logger = logging.getLogger(__name__)


class VidevoProvider(StockProvider):
    slug = "videvo"
    display_name = "Videvo"
    requires_api_key = True
    supports_videos = True
    supports_images = False

    # Videvo's documented partner search endpoint. Some tenants use a slightly
    # different base URL — the adapter accepts either an "Authorization: Bearer"
    # header or a "?api_key=" query param.
    _SEARCH_URL = "https://api.videvo.net/v3/videos/search"

    async def search_videos(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    self._SEARCH_URL,
                    params={
                        "query": query,
                        "per_page": max(count, 3),
                        "api_key": api_key,
                        "orientation": "landscape",
                    },
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=30.0,
                )
            if r.status_code != 200:
                logger.warning(f"[videvo] search API returned {r.status_code}")
                return []
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            hits = data.get("videos") or data.get("results") or data.get("hits") or []
            out: List[Dict] = []
            for hit in hits[:count]:
                # Videvo response shape varies; probe common shapes.
                video_id = hit.get("id") or hit.get("videoId") or hit.get("uuid")
                url = (
                    hit.get("preview_url")
                    or hit.get("previewUrl")
                    or hit.get("download_url")
                    or hit.get("mp4_url")
                    or (hit.get("files") or [{}])[0].get("url")
                )
                if not url or not video_id:
                    continue
                out.append({
                    "id": f"videvo_{video_id}",
                    "url": url,
                    "thumbnail": hit.get("thumbnail") or hit.get("thumb_url"),
                    "duration": hit.get("duration"),
                    "width": hit.get("width"),
                    "height": hit.get("height"),
                    "source": "videvo",
                })
            return out
        except Exception as e:
            logger.error(f"[videvo] videos fetch error: {e}")
            return []

    async def validate_key(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    self._SEARCH_URL,
                    params={"query": "nature", "per_page": 1, "api_key": api_key},
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=15.0,
                )
            # Accept 200 (auth ok) or 400 (schema quirk with a valid key)
            return r.status_code in (200, 400)
        except Exception:
            return False
