"""Base contract every stock media provider must implement.

Each provider is an independent adapter. The engine orchestrates them via this
uniform interface, so adding a new provider is a matter of writing one class
and registering it in engine.PROVIDERS_ORDERED.
"""
from abc import ABC
from typing import List, Dict, Optional


class StockProvider(ABC):
    # --- Provider metadata (subclasses override) ---
    slug: str = ""              # e.g. "pexels" — used as key in user_keys / DB
    display_name: str = ""      # e.g. "Pexels"
    requires_api_key: bool = False   # True => needs a user-supplied key
    supports_videos: bool = True
    supports_images: bool = False

    # --- Provider capabilities (subclasses override the ones they support) ---
    async def search_videos(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        """Return a list of normalized video dicts.

        Each dict must include at minimum: id, url, source.
        Optional fields: thumbnail, duration, width, height.
        """
        return []

    async def search_images(
        self, query: str, count: int, api_key: Optional[str] = None
    ) -> List[Dict]:
        """Return a list of normalized image dicts.

        Each dict must include at minimum: id, url, source.
        Optional fields: thumbnail, alt.
        """
        return []

    async def validate_key(self, api_key: str) -> bool:
        """API-key providers override this to verify the credential.

        Built-in providers (no key) can leave the default True.
        """
        return True
