"""Backward-compatible facade over the modular stock media engine.

Existing callers (videos.py, settings_api.py) import from this module. The
real logic now lives in stock_providers/. Do not add provider-specific code
here — add it as a new provider adapter in stock_providers/.
"""
from typing import List, Dict, Optional

from stock_providers import (
    search_videos as _engine_search_videos,
    search_images as _engine_search_images,
    validate_key as _engine_validate_key,
    list_providers as _engine_list_providers,
)


async def fetch_stock_videos(query: str, count: int, user_keys: Optional[Dict]) -> List[Dict]:
    """Aggregate video results across the configured provider chain."""
    return await _engine_search_videos(query, count, user_keys)


async def fetch_stock_images(query: str, count: int, user_keys: Optional[Dict]) -> List[Dict]:
    """Aggregate image results across the configured provider chain."""
    return await _engine_search_images(query, count, user_keys)


async def validate_pexels_key(api_key: str) -> bool:
    return await _engine_validate_key("pexels", api_key)


async def validate_pixabay_key(api_key: str) -> bool:
    return await _engine_validate_key("pixabay", api_key)


async def validate_videvo_key(api_key: str) -> bool:
    return await _engine_validate_key("videvo", api_key)


def list_stock_providers() -> List[Dict]:
    """Return the ordered provider chain (for settings/admin introspection)."""
    return _engine_list_providers()
