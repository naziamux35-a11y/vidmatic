"""Stock media engine.

The engine talks to providers through the uniform StockProvider interface —
it has no provider-specific code. Adding a new provider is a matter of:
    1. Write a class inheriting StockProvider.
    2. Import + append it to PROVIDERS_ORDERED.

Search order (as specified):
    Pexels -> Pixabay -> Videvo -> Mixkit -> Coverr

API-key providers are skipped when the user hasn't supplied their key.
Built-in providers (no key required) always participate.
Every provider is fully isolated via try/except; a failure in one never
prevents the others from returning results.
"""
import logging
from typing import List, Dict, Optional

from .base import StockProvider
from .pexels import PexelsProvider
from .pixabay import PixabayProvider
from .videvo import VidevoProvider
from .mixkit import MixkitProvider
from .coverr import CoverrProvider

logger = logging.getLogger(__name__)

# Canonical provider chain — order matters for search precedence.
PROVIDERS_ORDERED: List[StockProvider] = [
    PexelsProvider(),
    PixabayProvider(),
    VidevoProvider(),
    MixkitProvider(),
    CoverrProvider(),
]

_PROVIDER_MAP = {p.slug: p for p in PROVIDERS_ORDERED}


def get_provider(slug: str) -> Optional[StockProvider]:
    return _PROVIDER_MAP.get(slug)


def list_providers() -> List[Dict]:
    """Introspection helper — used by settings/admin UIs to render provider chips."""
    return [
        {
            "slug": p.slug,
            "display_name": p.display_name,
            "requires_api_key": p.requires_api_key,
            "supports_videos": p.supports_videos,
            "supports_images": p.supports_images,
        }
        for p in PROVIDERS_ORDERED
    ]


def _resolve_key(provider: StockProvider, user_keys: Optional[Dict]) -> Optional[str]:
    if not provider.requires_api_key:
        return None
    return (user_keys or {}).get(provider.slug)


async def search_videos(query: str, count: int, user_keys: Optional[Dict]) -> List[Dict]:
    """Aggregate video results from every eligible provider, in order."""
    aggregated: List[Dict] = []
    for provider in PROVIDERS_ORDERED:
        if not provider.supports_videos:
            continue
        key = _resolve_key(provider, user_keys)
        if provider.requires_api_key and not key:
            continue
        try:
            results = await provider.search_videos(query, count, key)
            if results:
                aggregated.extend(results)
        except Exception as e:  # defensive: provider must never crash the engine
            logger.warning(f"[stock-engine] {provider.slug} search_videos failed: {e}")
    return aggregated


async def search_images(query: str, count: int, user_keys: Optional[Dict]) -> List[Dict]:
    """Aggregate image results from every eligible provider, in order."""
    aggregated: List[Dict] = []
    for provider in PROVIDERS_ORDERED:
        if not provider.supports_images:
            continue
        key = _resolve_key(provider, user_keys)
        if provider.requires_api_key and not key:
            continue
        try:
            results = await provider.search_images(query, count, key)
            if results:
                aggregated.extend(results)
        except Exception as e:
            logger.warning(f"[stock-engine] {provider.slug} search_images failed: {e}")
    return aggregated


async def validate_key(provider_slug: str, api_key: str) -> bool:
    """Verify an API key against its provider — used by settings save flow."""
    provider = get_provider(provider_slug)
    if not provider:
        return False
    if not provider.requires_api_key:
        return True
    try:
        return await provider.validate_key(api_key)
    except Exception as e:
        logger.warning(f"[stock-engine] {provider_slug} validate_key failed: {e}")
        return False
