"""
ManhwaIndo source provider for wmdl
Scrapes comics from ManhwaIndo (https://www.manhwaindo.my)
"""

import html as html_lib
import json
import logging
import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

from .base import BaseSource

logger = logging.getLogger(__name__)

# Domain patterns for ad/gambling images — NEVER download these
_AD_DOMAINS = (
    "i.88cdn.cloud",            # gambling banner CDN
    "prizefamily.com",          # ad script domain
)

# Gambling/judi/ad keywords that may appear in image paths from ad networks
_GAMBLING_KEYWORDS = (
    "judi", "slot", "casino", "poker", "togel", "gacor", "maxwin",
    "bandar", "sigacor", "pentaslot", "kaikoslot", "hokidewa", "macaudewa",
    "judi89", "indo666", "arab777", "cina777", "ratu89", "gaza88", "rusia777",
    "iklan", "banner", "bm-slot", "728x90", "720x90", "300x250",
    "wongso", "momoplay", "mamba", "zeus",
)


def _is_ad_image(url: str) -> bool:
    """Return True if url looks like an ad/gambling banner."""
    low = url.lower()
    # Ad/gambling banners are commonly animated GIFs; manga pages are jpg/png/webp
    if low.endswith(".gif") or ".gif?" in low:
        return True
    if any(domain in low for domain in _AD_DOMAINS):
        return True
    if any(kw in low for kw in _GAMBLING_KEYWORDS):
        return True
    return False


def _is_manga_page(url: str) -> bool:
    """Return True only if url is a genuine manga page image."""
    low = url.lower()
    if _is_ad_image(url):
        return False
    # Must have an image extension
    if not re.search(r'\.(?:jpe?g|png|webp)(?:\?.*)?$', low):
        return False
    # Exclude site logos, favicons, avatars
    if any(x in low for x in ["logo", "favicon", "cropped-", "avatar"]):
        return False
    return True


class ManhwaIndoSource(BaseSource):
    """Source provider for ManhwaIndo (https://www.manhwaindo.my)"""

    name = "ManhwaIndo"
    slug = "manhwaindo"
    base_url = "https://www.manhwaindo.my"

    def _normalize_slug(self, raw: str) -> str:
        """Extract the series slug from a URL or return raw value."""
        cleaned = raw.strip().rstrip("/")
        m = re.search(r"/series/([^/?#]+)", cleaned)
        if m:
            return m.group(1).rstrip("/")
        m = re.search(r"manhwaindo\.my/([^/?#]+)", cleaned)
        if m and "series" not in cleaned:
            return m.group(1).rstrip("/")
        return cleaned.split("/")[-1]

    def can_handle_url(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """Check if URL or identifier belongs to ManhwaIndo."""
        cleaned = url.strip()
        lower = cleaned.lower()

        if "manhwaindo" not in lower:
            return False, None, False

        # 1. Series detail page: https://www.manhwaindo.my/series/{slug}/
        m = re.search(r"/series/([^/?#]+)", cleaned, re.IGNORECASE)
        if m:
            return True, m.group(1).rstrip("/"), True

        # 2. Chapter read page: https://www.manhwaindo.my/{slug}-chapter-{n}/
        m_ch = re.search(r"manhwaindo\.my/([^/?#]+-chapter-[^/?#]+)/?", cleaned, re.IGNORECASE)
        if m_ch:
            return True, m_ch.group(1).rstrip("/"), True

        # 3. Search URL: https://www.manhwaindo.my/?s={query}
        m_s = re.search(r"[?&]s=([^&#]+)", cleaned, re.IGNORECASE)
        if m_s:
            query = urllib.parse.unquote_plus(m_s.group(1))
            return True, query, False

        return True, cleaned, False

    def get_image_referer(self, image_url: Optional[str] = None) -> str:
        return f"{self.base_url}/"

    def _to_status(self, raw: str) -> str:
        low = raw.lower()
        if "complete" in low or "tamat" in low or "end" in low or "is-completed" in low:
            return "Completed"
        if "ongoing" in low or "berlangsung" in low or "berjalan" in low or "is-ongoing" in low:
            return "Ongoing"
        return "Unknown"

    async def search(self, query: str) -> List[Dict]:
        """Search comics on ManhwaIndo via the native /?s= endpoint."""
        encoded_q = urllib.parse.quote_plus(query.strip())
        url = f"{self.base_url}/?s={encoded_q}"
        logger.debug(f"Searching ManhwaIndo: {url}")

        await self._ensure_session(headers={"Referer": f"{self.base_url}/"})
        if not self.session:
            return []

        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    logger.debug(f"ManhwaIndo search returned status {resp.status}")
                    return []
                html_text = await resp.text()

            # Each search result: <li class="bm-card-wrap">
            #   <a class="bm-card series" href="..."> ... <img src="..."> ... <span class="bm-card__title">...</span>
            items = re.split(r'<li[^>]+class=["\'][^"\']*bm-card-wrap[^"\']*["\']', html_text)[1:]

            keywords = [w.lower() for w in re.split(r"[\s\-_]+", query) if len(w) > 1]
            norm_query = query.lower().replace("-", " ")

            results: List[Dict] = []
            for item in items:
                href_m = re.search(r'href=["\'](https?://www\.manhwaindo\.my/series/([^/"\'#]+)/?)["\']', item, re.I)
                title_m = re.search(r'class=["\'][^"\']*bm-card__title[^"\']*["\'][^>]*>(.*?)</span>', item, re.DOTALL)
                img_m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', item)
                status_m = re.search(r'class=["\'][^"\']*bm-badge[^"\']*is-(?:completed|ongoing)[^"\']*["\']', item, re.I)

                if not href_m or not title_m:
                    continue

                slug = href_m.group(2).rstrip("/")
                title = html_lib.unescape(re.sub(r"<[^>]+>", "", title_m.group(1)).strip())
                cover = img_m.group(1) if img_m else ""
                status_raw = status_m.group(0) if status_m else "ongoing"
                status = self._to_status(status_raw)

                t_lower = title.lower()
                s_lower = slug.lower()

                if not keywords or any(kw in t_lower or kw in s_lower for kw in keywords):
                    if t_lower == norm_query or t_lower == query.lower():
                        score = 100
                    elif keywords and all(kw in t_lower or kw in s_lower for kw in keywords):
                        score = 50
                    else:
                        score = 10

                    results.append({
                        "title": title,
                        "manga_id": slug,
                        "status": status,
                        "cover": cover,
                        "source": self.slug,
                        "source_name": self.name,
                        "score": score,
                    })

            results.sort(key=lambda x: -x["score"])
            return results[:5]

        except Exception as e:
            logger.debug(f"ManhwaIndo search error: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Dict:
        """Fetch comic metadata from its series detail page."""
        await self._ensure_session(headers={"Referer": f"{self.base_url}/"})
        if not self.session:
            raise Exception("Session initialization failed")

        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/series/{slug}/"
        logger.debug(f"Fetching ManhwaIndo manga info: {url}")

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"ManhwaIndo returned status {resp.status} for {url}")
            html_text = await resp.text()

        # Title from <h1>
        title = slug.replace("-", " ").title()
        h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.DOTALL | re.I)
        if h1_m:
            title = html_lib.unescape(re.sub(r"<[^>]+>", "", h1_m.group(1)).strip())

        # Cover from og:image
        og_m = re.search(r'<meta[^>]+property=["\'"]og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']', html_text, re.I)
        if not og_m:
            og_m = re.search(r'content=["\'](https?://[^"\']+)["\'][^>]*property=["\'"]og:image["\']', html_text, re.I)
        cover = og_m.group(1) if og_m else ""

        # Status — ManhwaIndo uses is-completed / is-ongoing CSS class
        status = "Ongoing"
        status_m = re.search(r'class=["\'][^"\']*is-(completed|ongoing)[^"\']*["\'][^>]*>(.*?)</span>', html_text, re.DOTALL | re.I)
        if status_m:
            status = self._to_status(status_m.group(1))

        # Description from <meta name="description"> or bm-description
        desc = ""
        meta_desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html_text, re.I)
        if meta_desc:
            desc = html_lib.unescape(meta_desc.group(1).strip())

        return {
            "title": title,
            "status": status,
            "description": desc,
            "cover": cover,
            "manga_id": slug,
            "source": self.name,
        }

    async def get_chapter_list(self, manga_id: str) -> List[Dict]:
        """
        Get chapter list by reading agcInitialChapters JSON embedded in the series page.
        Each entry: {"id": int, "url": str, "chapter": str, "time": str, "date": int}
        """
        await self._ensure_session(headers={"Referer": f"{self.base_url}/"})
        if not self.session:
            raise Exception("Session initialization failed")

        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/series/{slug}/"
        logger.debug(f"Fetching ManhwaIndo chapter list: {url}")

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"ManhwaIndo returned status {resp.status} for {url}")
            html_text = await resp.text()

        # Extract agcInitialChapters JSON
        ag_m = re.search(r"agcInitialChapters\s*=\s*(\[.*?\]);", html_text, re.DOTALL)
        if not ag_m:
            logger.warning(f"ManhwaIndo: agcInitialChapters not found for {slug}")
            return []

        try:
            raw_json = ag_m.group(1)
            # Unescape forward slashes
            raw_json = raw_json.replace("\\/", "/")
            chapter_data: List[Dict] = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.warning(f"ManhwaIndo: Failed to parse agcInitialChapters JSON for {slug}: {e}")
            return []

        chapters: List[Dict] = []
        for item in chapter_data:
            ch_num = str(item.get("chapter", "")).strip()
            ch_url = str(item.get("url", "")).rstrip("/")
            ch_id = ch_url.rstrip("/").split("/")[-1] if ch_url else ""

            if not ch_num or not ch_url:
                continue

            # Normalize number
            raw_num = ch_num
            clean_num = raw_num.lstrip("0") or "0"
            if clean_num.startswith("."):
                clean_num = "0" + clean_num

            chapters.append({
                "chapter_id": ch_id,
                "number": clean_num,
                "raw_number": raw_num,
                "title": "",
                "name": f"Chapter {raw_num}",
                "url": ch_url,
            })

        logger.info(f"Found {len(chapters)} chapters on ManhwaIndo")
        return chapters

    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """
        Fetch image URLs for a chapter.
        Images sit inside the reader-area paragraph tags within bm-reader__stage.
        Ad/gambling images (from upload.gmbr.pro, i.88cdn.cloud, etc.) are excluded.
        Only genuine manga-page images (from imgx-id.gmbr.pro/uploads/manga-images/) are returned.
        """
        await self._ensure_session(headers={"Referer": f"{self.base_url}/"})
        if not self.session:
            raise Exception("Session initialization failed")

        # chapter_id may be a full URL or just a slug like "solo-leveling-side-story-chapter-1"
        if chapter_id.startswith("http"):
            url = chapter_id
        else:
            url = f"{self.base_url}/{chapter_id.strip('/')}/"

        logger.debug(f"Fetching ManhwaIndo chapter pages: {url}")

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"ManhwaIndo chapter returned status {resp.status} for {url}")
            html_text = await resp.text()

        # Isolate the reader-area inside bm-reader__stage — ignore everything outside it
        stage_m = re.search(r'class=["\']bm-reader__stage["\'][^>]*>(.*?)</main>', html_text, re.DOTALL | re.I)
        if not stage_m:
            stage_m = re.search(r'class=["\']reader-area["\'][^>]*>(.*?)(?:</div>\s*</div>|<footer)', html_text, re.DOTALL | re.I)
        reader_html = stage_m.group(1) if stage_m else html_text

        # Find all <img ...> tags in the reader area
        img_tags = re.findall(r'<img[^>]+>', reader_html, re.I)

        # Filter: keep only genuine manga page images; skip ads/gambling
        image_urls: List[str] = []
        seen: set = set()
        for tag in img_tags:
            # Skip tags with ad indicators in alt or class
            alt_m = re.search(r'alt=["\'](.*?)["\']', tag, re.I)
            if alt_m and any(kw in alt_m.group(1).lower() for kw in ("iklan", "advertisement", "slot", "judi", "banner")):
                continue

            # Extract src or fallback to data-src / data-lazy-src
            src = None
            for attr in ("src", "data-src", "data-lazy-src"):
                m = re.search(rf'{attr}=["\'](https?://[^"\']+)["\']', tag, re.I)
                if m:
                    src = m.group(1).strip()
                    break

            if not src or src in seen:
                continue

            if not _is_manga_page(src):
                logger.debug(f"Skipping non-manga image: {src}")
                continue

            seen.add(src)
            image_urls.append(src)

        logger.info(f"Found {len(image_urls)} pages on ManhwaIndo")
        return image_urls
