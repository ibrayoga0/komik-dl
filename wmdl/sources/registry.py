"""
Source registry for wmdl
Manages and dispatches comic sources dynamically
"""

from typing import Dict, List, Optional, Type
from .base import BaseSource
from .shinigami import ShinigamiSource
from .softkomik import SoftkomikSource
from .komiku import KomikuSource
from .mynimeku import MyNimekuSource
from .komikstation import KomikStationSource


class SourceRegistry:
    """Registry for managing all comic sources"""

    def __init__(self):
        self._sources: Dict[str, Type[BaseSource]] = {}
        # Register default sources
        self.register(ShinigamiSource)
        self.register(SoftkomikSource)
        self.register(KomikuSource)
        self.register(MyNimekuSource)
        self.register(KomikStationSource)

    def register(self, source_cls: Type[BaseSource]):
        """Register a new comic source class"""
        self._sources[source_cls.slug.lower()] = source_cls
        self._sources[source_cls.name.lower()] = source_cls

    def get(self, key: Optional[str]) -> Optional[BaseSource]:
        """Get an instance of a source by slug or name"""
        if not key:
            return None
        cls = self._sources.get(key.lower())
        return cls() if cls else None

    def get_all(self) -> List[BaseSource]:
        """Get a list of distinct source instances"""
        seen_slugs = set()
        instances = []
        for cls in self._sources.values():
            if cls.slug not in seen_slugs:
                seen_slugs.add(cls.slug)
                instances.append(cls())
        return instances

    def resolve_input(self, raw_input: str) -> dict:
        """
        Check raw user input against all registered sources to detect source and input type.

        Returns:
            dict with:
                - query: str
                - source: Optional[str] (source slug or None if search all)
                - is_direct_id: bool
        """
        cleaned = raw_input.strip()

        # Check each source
        for source in self.get_all():
            matched, extracted, is_direct = source.can_handle_url(cleaned)
            if matched:
                return {
                    "query": extracted or cleaned,
                    "source": source.slug,
                    "is_direct_id": is_direct,
                }

        # If no specific source matched, treat as search query across all sources
        return {
            "query": cleaned,
            "source": None,
            "is_direct_id": False,
        }

    def get_referer_for_url(self, image_url: str) -> str:
        """Return the appropriate HTTP referer header for a given image CDN URL"""
        low = image_url.lower()
        if "komiku" in low:
            return "https://komiku.org/"
        elif "komik.im" in low or "softkomik" in low:
            return "https://softkomik.app/"
        elif "mynimeku" in low or "mydriveku" in low:
            return "https://www.mynimeku.com/"
        elif "komikstation" in low or "klikcdn" in low:
            return "https://komikstation.org/"
        return "https://app.shinigami.asia/"


# Global registry instance
registry = SourceRegistry()
