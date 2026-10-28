"""
Base class for comic source providers in wmdl
"""

import abc
from typing import List, Dict, Optional, Tuple
import aiohttp  # type: ignore[import-untyped,import-not-found]


class BaseSource(abc.ABC):
    """Abstract base class for all comic sources"""

    name: str = "Base"
    slug: str = "base"
    base_url: str = ""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    @abc.abstractmethod
    def can_handle_url(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """
        Check if this source can handle the given URL or identifier.

        Returns:
            Tuple of (matches: bool, query_or_id: Optional[str], is_direct_id: bool)
        """
        pass

    @abc.abstractmethod
    async def search(self, query: str) -> List[Dict]:
        """
        Search for comics on this source.

        Returns:
            List of dicts:
            {
                "title": str,
                "manga_id": str,
                "status": str,
                "cover": str,
                "source": str,
                "source_name": str,
                "score": int
            }
        """
        pass

    @abc.abstractmethod
    async def get_manga_info(self, manga_id: str) -> Dict:
        """
        Get details for a comic.

        Returns:
            Dict:
            {
                "title": str,
                "manga_id": str,
                "status": str,
                "cover": str,
                "description": str,
                "source": str
            }
        """
        pass

    @abc.abstractmethod
    async def get_chapter_list(self, manga_id: str) -> List[Dict]:
        """
        Get list of chapters for a comic.

        Returns:
            List of dicts:
            {
                "chapter_id": str,
                "number": str,
                "raw_number": str,
                "title": str,
                "name": str
            }
        """
        pass

    @abc.abstractmethod
    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """
        Get list of image URLs for a chapter.

        Returns:
            List of image URLs
        """
        pass

    def get_image_referer(self, image_url: Optional[str] = None) -> str:
        """Return referer header for image CDN downloads"""
        return f"{self.base_url}/"

    async def _ensure_session(self, headers: Optional[dict] = None):
        """Ensure an aiohttp ClientSession is active"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            default_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": f"{self.base_url}/",
            }
            if headers:
                default_headers.update(headers)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=default_headers)

    async def fetch_html(self, url: str, headers: Optional[dict] = None, allow_cf_bypass: bool = True) -> str:
        """
        Fetch HTML content from a URL with automatic Cloudflare challenge detection and bypass.
        """
        await self._ensure_session(headers)
        if not self.session:
            raise Exception("Session initialization failed")

        from ..bypass import is_cloudflare_challenge, cf_bypasser

        # Apply cached cookies if available
        cached = cf_bypasser.get_cached_cookies(url)
        req_headers = dict(headers or {})
        if cached:
            cookies, ua = cached
            for k, v in cookies.items():
                self.session.cookie_jar.update_cookies({k: v})
            if ua:
                req_headers["User-Agent"] = ua

        async with self.session.get(url, headers=req_headers if req_headers else None) as resp:
            text = await resp.text()
            if resp.status == 200:
                return text

            # Check if blocked by Cloudflare anti-bot challenge
            if allow_cf_bypass and is_cloudflare_challenge(resp.status, text, dict(resp.headers)):
                bypassed_html = await cf_bypasser.fetch_html(url)
                if bypassed_html:
                    cached_fresh = cf_bypasser.get_cached_cookies(url)
                    if cached_fresh:
                        fresh_cookies, _ = cached_fresh
                        for k, v in fresh_cookies.items():
                            self.session.cookie_jar.update_cookies({k: v})
                    return bypassed_html

            raise Exception(f"HTTP {resp.status} fetching {url}")

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
