"""
Cloudflare Protection Bypasser for wmdl
Bypasses Cloudflare challenges (Turnstile / IUAM) using local cf_bypasser or server.
"""

import asyncio
import logging
import os
import sys
import urllib.parse
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Cloudflare challenge indicators in headers/HTML
CF_CHALLENGE_HEADERS = ("cf-mitigated",)
CF_CHALLENGE_TITLE = "just a moment..."
CF_CHALLENGE_MARKERS = (
    "challenges.cloudflare.com",
    "cf-chl-widget",
    "cf-mitigated",
    "_cf_chl_opt",
    "attention required! | cloudflare",
)

# Common Windows browser executables for Brave, Chrome, and Edge
WINDOWS_BROWSER_CANDIDATES = (
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def is_cloudflare_challenge(status: int, text: str, headers: Optional[dict] = None) -> bool:
    """Check if an HTTP response is a Cloudflare anti-bot challenge"""
    if status not in (403, 503):
        return False

    if headers:
        lower_headers = {k.lower(): str(v).lower() for k, v in headers.items()}
        if lower_headers.get("cf-mitigated") == "challenge":
            return True
        if "cloudflare" in lower_headers.get("server", "") and status in (403, 503):
            pass  # Likely cloudflare, check text below

    lower_text = text.lower()
    if CF_CHALLENGE_TITLE in lower_text:
        return True
    return any(marker in lower_text for marker in CF_CHALLENGE_MARKERS)


def _setup_browser_path():
    """Ensure CF_BROWSER_PATH and CF_BROWSERS are set if not already defined"""
    os.environ.setdefault("CF_BROWSERS", "1")
    if "CF_BROWSER_PATH" not in os.environ or not os.path.exists(os.environ["CF_BROWSER_PATH"]):
        for path in WINDOWS_BROWSER_CANDIDATES:
            if os.path.exists(path):
                os.environ["CF_BROWSER_PATH"] = path
                logger.debug(f"Configured CF_BROWSER_PATH={path}")
                break


class CloudflareBypasser:
    """Singleton Cloudflare bypass controller"""

    def __init__(self):
        self._server_url = os.environ.get("CF_BYPASS_URL", "http://localhost:8000")
        self._bypasser = None
        self._lock = asyncio.Lock()
        self._cookie_cache: Dict[str, Dict[str, str]] = {}
        self._ua_cache: Dict[str, str] = {}

    def get_cached_cookies(self, url: str) -> Optional[Tuple[Dict[str, str], str]]:
        """Return cached clearance cookies and user agent for host if available"""
        host = urllib.parse.urlsplit(url).netloc.lower()
        if host in self._cookie_cache and host in self._ua_cache:
            return self._cookie_cache[host], self._ua_cache[host]
        return None

    def store_cookies(self, url: str, cookies: Dict[str, str], user_agent: str):
        """Store clearance cookies and user agent in cache"""
        host = urllib.parse.urlsplit(url).netloc.lower()
        self._cookie_cache[host] = cookies
        self._ua_cache[host] = user_agent

    async def _get_local_bypasser(self):
        """Lazily initialize CFBypasser from clv package"""
        if self._bypasser is None:
            # Prefer embedded wmdl/cf_bypasser, fallback to clv
            wmdl_dir = os.path.dirname(os.path.abspath(__file__))
            if wmdl_dir not in sys.path:
                sys.path.insert(0, wmdl_dir)
            base_dir = os.path.dirname(wmdl_dir)
            clv_dir = os.path.join(base_dir, "clv")
            if clv_dir not in sys.path and os.path.exists(clv_dir):
                sys.path.append(clv_dir)

            _setup_browser_path()

            try:
                try:
                    from .cf_bypasser import CFBypasser  # type: ignore[import-not-found]
                except ImportError:
                    from cf_bypasser import CFBypasser  # type: ignore[import-not-found]
                self._bypasser = CFBypasser(log=False)
                await self._bypasser.start()
            except Exception as e:
                logger.debug(f"Failed to initialize local CFBypasser: {e}")
                self._bypasser = None

        return self._bypasser

    async def fetch_html(self, url: str) -> Optional[str]:
        """
        Bypass Cloudflare and return rendered HTML content.
        Tries local server first, then local embedded CFBypasser.
        """
        async with self._lock:
            # 1. Try local server if running
            try:
                import aiohttp
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    server_endpoint = f"{self._server_url}/html?url={urllib.parse.quote(url)}"
                    async with session.get(server_endpoint) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and "html" in data:
                                if "cookies" in data:
                                    self.store_cookies(url, data["cookies"], data.get("user_agent", ""))
                                return data["html"]
            except Exception:
                pass

            # 2. Try embedded CFBypasser
            bypasser = await self._get_local_bypasser()
            if bypasser:
                try:
                    logger.info(f"Bypassing Cloudflare protection for: {url}...")
                    res = await bypasser.get_or_generate_html(url)
                    if res and "html" in res:
                        if "cookies" in res:
                            self.store_cookies(url, res["cookies"], res.get("user_agent", ""))
                        return res["html"]
                except Exception as e:
                    logger.warning(f"Cloudflare bypass failed: {e}")

            return None

    async def get_cookies(self, url: str) -> Optional[Tuple[Dict[str, str], str]]:
        """Fetch clearance cookies and user-agent for URL"""
        cached = self.get_cached_cookies(url)
        if cached:
            return cached

        async with self._lock:
            bypasser = await self._get_local_bypasser()
            if bypasser:
                try:
                    res = await bypasser.get_or_generate_cookies(url)
                    if res and "cookies" in res:
                        cookies = res["cookies"]
                        ua = res.get("user_agent", "")
                        self.store_cookies(url, cookies, ua)
                        return cookies, ua
                except Exception as e:
                    logger.debug(f"Failed to get CF cookies: {e}")
        return None

    async def cleanup(self):
        """Shutdown bypasser pool"""
        if self._bypasser:
            try:
                await self._bypasser.cleanup()
            except Exception:
                pass
            self._bypasser = None


# Global singleton instance
cf_bypasser = CloudflareBypasser()
