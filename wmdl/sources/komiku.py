"""
Komiku source provider for wmdl
Scrapes comics, chapters, and pages from https://komiku.org
"""

import logging
import re
import urllib.parse
from typing import List, Dict, Optional, Tuple

from .base import BaseSource

logger = logging.getLogger(__name__)


class KomikuSource(BaseSource):
    """Source provider for Komiku (https://komiku.org)"""

    name = "Komiku"
    slug = "komiku"
    base_url = "https://komiku.org"
    api_url = "https://api.komiku.org"

    def can_handle_url(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """
        Check if URL or identifier belongs to Komiku
        """
        cleaned = url.strip()
        lower = cleaned.lower()

        if "komiku." in lower or "komiku" in lower:
            # 1. Search page: https://komiku.org/?post_type=manga&s=...
            search_match = re.search(r'komiku\.[^/]+/\?post_type=manga&s=([^&#]+)', cleaned, re.IGNORECASE)
            if search_match:
                query = urllib.parse.unquote_plus(search_match.group(1))
                return True, query, False

            # 2. Reading / chapter page: https://komiku.org/{slug}-chapter-{ch}/
            ch_match = re.search(r'komiku\.[^/]+/([^/?#]+-chapter-[^/?#]+)/?', cleaned, re.IGNORECASE)
            if ch_match:
                return True, ch_match.group(1), True

            # 3. Manga detail page: https://komiku.org/manga/{slug}/
            detail_match = re.search(r'komiku\.[^/]+/manga/([^/?#]+)/?', cleaned, re.IGNORECASE)
            if detail_match:
                return True, detail_match.group(1), True

            # 4. General slug on Komiku domain
            gen_match = re.search(r'komiku\.[^/]+/([^/?#]+)/?', cleaned, re.IGNORECASE)
            if gen_match:
                slug_val = gen_match.group(1)
                if slug_val not in ("manga", "genre", "daftar-komik", "terbaru"):
                    return True, slug_val, True

        return False, None, False

    def get_image_referer(self, image_url: Optional[str] = None) -> str:
        return "https://komiku.org/"

    def _normalize_slug(self, slug: str) -> str:
        s = slug.strip().strip("/").lower()
        if s.startswith("manga/"):
            s = s[6:]
        return s

    async def search(self, query: str) -> List[Dict]:
        """Search manga on Komiku via HTMX search API"""
        await self._ensure_session(headers={"Referer": f"{self.base_url}/"})
        if not self.session:
            return []

        try:
            url = f"{self.api_url}/?post_type=manga&s={urllib.parse.quote_plus(query)}"
            logger.debug(f"Searching Komiku: {url}")
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    logger.debug(f"Komiku search returned status {resp.status}")
                    return []
                html = await resp.text()

            # Split into comic items by <div class="bge">
            items = html.split('<div class="bge">')[1:]
            if not items:
                return []

            keywords = [w.lower() for w in re.split(r'[\s\-_]+', query) if len(w) > 1]
            norm_query = query.lower().replace('-', ' ')

            results = []
            for item in items:
                href_m = re.search(r'href=["\'](?:https://komiku\.org)?/manga/([^/"\'#]+)/?["\']', item)
                title_m = re.search(r'<h3>(.*?)</h3>', item)
                img_m = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\'\s]+)', item)

                if not href_m or not title_m:
                    continue

                slug = href_m.group(1).strip()
                title = re.sub(r'<[^>]+>', ' ', title_m.group(1)).strip()
                cover = img_m.group(1) if img_m else ""

                # Status detection
                status = "Ongoing"
                if "tamat" in item.lower() or "end" in item.lower():
                    status = "Completed"

                # Score calculation
                t_lower = title.lower()
                m_lower = slug.lower()
                if not keywords or any(kw in t_lower or kw in m_lower for kw in keywords):
                    if t_lower == norm_query or t_lower == query.lower():
                        score = 100
                    elif keywords and all(kw in t_lower or kw in m_lower for kw in keywords):
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
            logger.debug(f"Komiku search error: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Dict:
        """Get detail metadata of a comic from Komiku"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/manga/{slug}/"
        logger.debug(f"Fetching Komiku manga info: {url}")

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Komiku returned status {resp.status} for {url}")
            html = await resp.text()

        # Title
        title = ""
        h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if h1_m:
            h1_html = h1_m.group(1)
            span_m = re.search(r'<span[^>]*itemprop=["\']name["\'][^>]*>(.*?)</span>', h1_html, re.DOTALL)
            if span_m:
                title = re.sub(r'<[^>]+>', '', span_m.group(1)).strip()
            else:
                raw_h1 = re.sub(r'<[^>]+>', ' ', h1_html).strip()
                title = re.sub(r'^\s*komik\s+', '', raw_h1, flags=re.I).strip()
        if not title:
            title_tag_m = re.search(r'<title>(.*?)</title>', html, re.I)
            if title_tag_m:
                t = title_tag_m.group(1)
                t = re.sub(r'-\s*komiku.*$', '', t, flags=re.I).strip()
                title = re.sub(r'^\s*komik\s+', '', t, flags=re.I).strip()
        if not title:
            title = slug.replace('-', ' ').title()

        # Cover
        cover_m = re.search(r'<meta itemprop=["\']image["\'] content=["\']([^"\']+)["\']', html)
        if not cover_m:
            cover_m = re.search(r'<div class=["\']ims["\']>\s*<img[^>]+src=["\']([^"\']+)["\']', html)
        cover = cover_m.group(1) if cover_m else ""

        # Status
        status_m = re.search(r'<td>Status:</td>\s*<td>([^<]+)</td>', html, re.I)
        if not status_m:
            status_m = re.search(r'<meta itemprop=["\']creativeWorkStatus["\'] content=["\']([^"\']+)["\']', html)
        status_val = status_m.group(1).strip() if status_m else "Ongoing"
        if status_val.lower() in ("end", "tamat", "completed"):
            status = "Completed"
        else:
            status = "Ongoing"

        # Description
        desc_m = re.search(r'<p class=["\']desc["\'][^>]*>(.*?)</p>', html, re.DOTALL)
        if not desc_m:
            desc_m = re.search(r'<meta itemprop=["\']description["\'] content=["\']([^"\']+)["\']', html)
        raw_desc = desc_m.group(1).strip() if desc_m else ""
        description = re.sub(r'<[^>]+>', ' ', raw_desc).strip()

        return {
            "title": title,
            "status": status,
            "description": description,
            "cover": cover,
            "manga_id": slug,
            "source": self.name,
        }

    async def get_chapter_list(self, manga_id: str) -> List[Dict]:
        """Get chapter list for a comic on Komiku"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/manga/{slug}/"
        logger.debug(f"Fetching Komiku chapter list: {url}")

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Komiku returned status {resp.status} for {url}")
            html = await resp.text()

        # Chapter rows from Daftar_Chapter table
        rows = re.findall(
            r'<td class=["\']judulseries["\'][^>]*>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>.*?<b>(.*?)</b>.*?</a>',
            html,
            re.DOTALL
        )

        chapters = []
        for href, name in rows:
            ch_slug = href.strip("/").split("/")[-1]
            num_m = re.search(r'chapter[\s\-_]*([0-9]+(?:[\.\-][0-9]+)?)', name, re.I)
            if not num_m:
                num_m = re.search(r'chapter[\s\-_]*([0-9]+(?:[\.\-][0-9]+)?)', ch_slug, re.I)

            raw_num = num_m.group(1).replace("-", ".") if num_m else ch_slug
            clean_num = raw_num.lstrip("0")
            if not clean_num or clean_num.startswith("."):
                clean_num = "0" + clean_num

            clean_name = re.sub(r'<[^>]+>', ' ', name).strip()
            chapters.append({
                "chapter_id": ch_slug,
                "number": clean_num,
                "raw_number": raw_num,
                "title": "",
                "name": clean_name or f"Chapter {clean_num}",
                "url": href if href.startswith("http") else f"{self.base_url}{href}",
            })

        logger.info(f"Found {len(chapters)} chapters on Komiku")
        return chapters

    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """Get list of image URLs for a chapter on Komiku"""
        await self._ensure_session(headers={"Referer": f"{self.base_url}/"})
        if not self.session:
            raise Exception("Session initialization failed")

        # chapter_id can be slug or full url
        if chapter_id.startswith("http"):
            url = chapter_id
        else:
            clean_id = chapter_id.strip("/")
            url = f"{self.base_url}/{clean_id}/"

        logger.debug(f"Fetching Komiku chapter pages: {url}")
        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Komiku chapter returned status {resp.status} for {url}")
            html = await resp.text()

        # Extract content inside #Baca_Komik container
        baca_m = re.search(r'<div[^>]+id=["\']Baca_Komik["\'][^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
        if not baca_m:
            baca_m = re.search(r'<div[^>]+id=["\']Baca_Komik["\'][^>]*>(.*?)<footer', html, re.DOTALL)
        if not baca_m:
            baca_m = re.search(r'<div[^>]+id=["\']Baca_Komik["\'][^>]*>(.*)', html, re.DOTALL)

        baca_html = baca_m.group(1) if baca_m else html

        imgs = re.findall(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', baca_html)

        # Filter out promotions and banners
        filtered_imgs = []
        for src in imgs:
            src_clean = src.strip()
            if any(ad in src_clean.lower() for ad in ['promosi', 'iklan', 'banner', 'logo', 'histats', 'komiku-promosi']):
                continue
            if any(ext in src_clean.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                filtered_imgs.append(src_clean)

        logger.info(f"Found {len(filtered_imgs)} pages on Komiku")
        return filtered_imgs
