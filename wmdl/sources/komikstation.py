"""
Komik Station source provider for wmdl
Scrapes comics from Komik Station (https://komikstation.org)
Equipped with automatic Cloudflare challenge protection bypass.
"""

import html as html_lib
import logging
import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

from .base import BaseSource

logger = logging.getLogger(__name__)


class KomikStationSource(BaseSource):
    """Source provider for Komik Station (https://komikstation.org)"""

    name = "Komik Station"
    slug = "komikstation"
    base_url = "https://komikstation.org"

    def _normalize_slug(self, raw: str) -> str:
        """Extract clean comic slug from URL or identifier"""
        cleaned = raw.strip()
        match = re.search(r'/manga/([^/?#]+)', cleaned)
        if match:
            return match.group(1).rstrip('/')
        match_ch = re.search(r'komikstation\.org/([^/?#]+-chapter-[^/?#]+)', cleaned)
        if match_ch:
            ch_slug = match_ch.group(1).rstrip('/')
            manga_match = re.search(r'^(.*?)-chapter-', ch_slug)
            if manga_match:
                return manga_match.group(1)
            return ch_slug
        return cleaned.rstrip('/')

    def can_handle_url(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """Check if URL or identifier belongs to Komik Station"""
        cleaned = url.strip()
        lower = cleaned.lower()

        if "komikstation" in lower:
            # 1. Comic detail URL: /manga/{slug}/
            match_manga = re.search(r'/manga/([^/?#]+)', cleaned)
            if match_manga:
                return True, match_manga.group(1), True

            # 2. Chapter URL: /{slug}-chapter-{num}/
            match_ch = re.search(r'komikstation\.org/([^/?#]+-chapter-[^/?#]+)', cleaned)
            if match_ch:
                return True, match_ch.group(1), True

            # 3. Search query from URL: ?s={query}
            match_search = re.search(r'[?&]s=([^&#]+)', cleaned)
            if match_search:
                query = urllib.parse.unquote_plus(match_search.group(1))
                return True, query, False

            return True, cleaned, False

        return False, None, False

    def get_image_referer(self, image_url: Optional[str] = None) -> str:
        """Return referer header for Komik Station image downloads"""
        return f"{self.base_url}/"

    async def search(self, query: str) -> List[Dict]:
        """Search comics on Komik Station using Cloudflare bypass if protected"""
        encoded_query = urllib.parse.quote_plus(query.strip())
        url = f"{self.base_url}/?s={encoded_query}"
        logger.debug(f"Searching Komik Station: {url}")

        try:
            html = await self.fetch_html(url, allow_cf_bypass=True)
            cards = re.findall(r'<div class=["\']bsx["\']>(.*?)</div>\s*</div>', html, re.DOTALL)
            results = []

            keywords = [w.lower() for w in re.split(r'[\s\-_]+', query) if len(w) > 1]
            norm_query = query.lower().replace('-', ' ')

            for card in cards:
                link_m = re.search(r'href=["\'](https?://komikstation\.org/manga/([^"\'/?#]+)/?)["\']', card)
                if not link_m:
                    continue

                slug = link_m.group(2)

                # Title
                title_m = re.search(r'title=["\']([^"\']+)["\']', card)
                if not title_m:
                    title_m = re.search(r'<a[^>]+>([^<]+)</a>', card)
                raw_title = title_m.group(1) if title_m else slug.replace('-', ' ').title()
                title = html_lib.unescape(raw_title).strip()

                # Cover (prefer ts-post-image, skip flag svgs)
                cover_imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', card)
                cover = ""
                for img_url in cover_imgs:
                    if not img_url.endswith(".svg") and "flags" not in img_url:
                        cover = img_url
                        break
                if not cover and cover_imgs:
                    cover = cover_imgs[-1]

                # Status
                status_m = re.search(r'class=["\'][^"\']*(?:status|type)[^"\']*["\'][^>]*>(.*?)<', card)
                status_val = status_m.group(1).strip() if status_m else "Ongoing"
                status = "Completed" if any(w in status_val.lower() for w in ("tamat", "completed", "end")) else "Ongoing"

                # Score
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
            logger.debug(f"Komik Station search error: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Dict:
        """Get detail metadata of a comic from Komik Station"""
        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/manga/{slug}/"
        logger.debug(f"Fetching Komik Station manga info: {url}")

        html = await self.fetch_html(url, allow_cf_bypass=True)

        # Title
        h1_m = re.search(r'<h1[^>]*class=["\'][^"\']*entry-title[^"\']*["\'][^>]*>(.*?)</h1>', html, re.DOTALL)
        if not h1_m:
            h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        raw_title = h1_m.group(1) if h1_m else slug.replace('-', ' ').title()
        title = html_lib.unescape(re.sub(r'<[^>]+>', '', raw_title))
        title = re.sub(r'\s*Bahasa\s*Indonesia\s*$', '', title, flags=re.I).strip()

        # Cover
        cover_m = re.search(r'<div class=["\']thumb["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']', html, re.DOTALL)
        cover = cover_m.group(1) if cover_m else ""

        # Status
        status_m = re.search(r'<div class=["\']imptdt["\'][^>]*>Status\s*<i>(.*?)</i>', html, re.I)
        if not status_m:
            status_m = re.search(r'Status\s*<span>\s*<i>(.*?)</i>', html, re.I)
        status_val = status_m.group(1).strip() if status_m else "Ongoing"
        status = "Completed" if any(w in status_val.lower() for w in ("tamat", "completed", "end")) else "Ongoing"

        # Description
        desc_m = re.search(r'<div class=["\'][^"\']*entry-content-single[^"\']*["\'][^>]*>(.*?)</div>', html, re.DOTALL)
        description = ""
        if desc_m:
            description = html_lib.unescape(re.sub(r'<[^>]+>', ' ', desc_m.group(1))).strip()

        return {
            "title": title,
            "status": status,
            "description": description,
            "cover": cover,
            "manga_id": slug,
            "source": self.name,
        }

    async def get_chapter_list(self, manga_id: str) -> List[Dict]:
        """Get chapter list for a comic on Komik Station"""
        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/manga/{slug}/"
        logger.debug(f"Fetching Komik Station chapter list: {url}")

        html = await self.fetch_html(url, allow_cf_bypass=True)

        items = re.findall(
            r'<li[^>]*data-num=["\']([^"\']+)["\'][^>]*>.*?<a[^>]+href=["\'](https?://komikstation\.org/([^"\'/?#]+)/?)["\'][^>]*>(.*?)</a>',
            html,
            re.DOTALL
        )

        chapters = []
        seen = set()

        for raw_num, full_url, ch_slug, content in items:
            if ch_slug in seen:
                continue
            seen.add(ch_slug)

            clean_num = raw_num.strip()
            name_m = re.search(r'<span class=["\']chapternum["\']>([^<]+)</span>', content)
            name = name_m.group(1).strip() if name_m else f"Chapter {clean_num}"

            chapters.append({
                "chapter_id": ch_slug,
                "number": clean_num,
                "raw_number": raw_num,
                "title": name,
                "name": name,
            })

        # Fallback if no data-num attributes found
        if not chapters:
            ch_links = re.findall(
                r'<a[^>]+href=["\'](https?://komikstation\.org/([^"\'/?#]+-chapter-([0-9]+(?:\.[0-9]+)?)[^"\'/?#]*)/?)["\'][^>]*>(.*?)</a>',
                html,
                re.DOTALL
            )
            for full_url, ch_slug, ch_num, content in ch_links:
                if ch_slug in seen:
                    continue
                seen.add(ch_slug)
                chapters.append({
                    "chapter_id": ch_slug,
                    "number": ch_num,
                    "raw_number": ch_num,
                    "title": f"Chapter {ch_num}",
                    "name": f"Chapter {ch_num}",
                })

        return chapters

    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """Get image URLs for a chapter on Komik Station"""
        slug = chapter_id.strip().rstrip('/')
        url = f"{self.base_url}/{slug}/"
        logger.debug(f"Fetching Komik Station chapter pages: {url}")

        html = await self.fetch_html(url, allow_cf_bypass=True)

        pages = []
        seen = set()

        # Check readerarea
        reader_area = re.search(r'<div[^>]+id=["\']readerarea["\'][^>]*>(.*?)</div>', html, re.DOTALL)
        if reader_area:
            imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', reader_area.group(1))
            for src in imgs:
                clean_src = src.strip()
                if clean_src and clean_src not in seen:
                    seen.add(clean_src)
                    pages.append(clean_src)

        # Fallback if readerarea did not return images
        if not pages:
            ts_images = re.findall(r'"sources":\s*(\[.*?\])', html)
            if ts_images:
                try:
                    import json
                    sources_data = json.loads(ts_images[0])
                    for group in sources_data:
                        for img_url in group.get("images", []):
                            if img_url not in seen:
                                seen.add(img_url)
                                pages.append(img_url)
                except Exception:
                    pass

        logger.info(f"Found {len(pages)} pages on Komik Station for chapter {slug}")
        return pages
