"""Mixkit built-in stock provider (videos).

Mixkit does not offer a public JSON API. This adapter scrapes their public
search page and extracts direct MP4 CDN URLs from assets.mixkit.co. Any
network/schema issue results in an empty list — the pipeline is unaffected.

No user API key required.
"""
import logging
import re
from typing import List, Dict, Optional

import httpx

from .base import StockProvider

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class MixkitProvider(StockProvider):
    slug = "mixkit"
    display_name = "Mixkit"
    requires_api_key = False
    supports_videos = True
    supports_images = False

    _SEARCH_URL = "https://mixkit.co/free-stock-video/search/{query}/"
    # Mixkit serves MP4 previews from this CDN with predictable filenames.
    _MP4_PATTERN = re.compile(
        r"https://assets\.mixkit\.co/videos/preview/[a-zA-Z0-9\-_]+-(?:small|medium|large|1080)\.mp4"
    )
    _POSTER_PATTERN = re.compile(
        r"https://assets\.mixkit\.co/videos/preview/[a-zA-Z0-9\-_]+-poster\.(?:jpg|webp)"
    )

    async def search_videos(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        try:
            slug = query.strip().lower().replace(" ", "-")
            url = self._SEARCH_URL.format(query=slug)
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": _UA}, timeout=20.0)
            if r.status_code != 200:
                logger.warning(f"[mixkit] search page returned {r.status_code}")
                return []
            mp4_urls = list(dict.fromkeys(self._MP4_PATTERN.findall(r.text)))[: count * 2]
            posters = list(dict.fromkeys(self._POSTER_PATTERN.findall(r.text)))
            out: List[Dict] = []
            for i, mp4 in enumerate(mp4_urls[:count]):
                # Derive a stable id from the CDN filename.
                vid = mp4.rsplit("/", 1)[-1].rsplit("-", 1)[0]
                out.append({
                    "id": f"mixkit_{vid}",
                    "url": mp4,
                    "thumbnail": posters[i] if i < len(posters) else None,
                    "duration": None,
                    "source": "mixkit",
                })
            return out
        except Exception as e:
            logger.error(f"[mixkit] videos fetch error: {e}")
            return []
