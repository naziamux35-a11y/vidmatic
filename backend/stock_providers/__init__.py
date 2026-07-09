"""Modular stock media provider architecture.

Public API:
    search_videos(query, count, user_keys) -> List[Dict]
    search_images(query, count, user_keys) -> List[Dict]
    validate_key(provider_slug, api_key) -> bool
    list_providers() -> List[Dict]
"""
from .engine import (
    search_videos,
    search_images,
    validate_key,
    list_providers,
    get_provider,
)

__all__ = [
    "search_videos",
    "search_images",
    "validate_key",
    "list_providers",
    "get_provider",
]
