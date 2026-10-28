"""
MyNimeku source provider for wmdl
Scrapes comics from MyNimeku (https://www.mynimeku.com)
Filters out Anime entries (/series/...) to focus exclusively on Comics (/komik/...)
"""

import html as html_lib
import logging
import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

from .base import BaseSource

logger = logging.getLogger(__name__)


class MyNimekuSource(BaseSource):
    """Source provider for MyNimeku (https://www.mynimeku.com)"""

    name = "MyNimeku"
    slug = "mynimeku"
    base_url = "https://www.mynimeku.com"

    def _normalize_slug(self, raw: str) -> str:
        """Extract clean comic slug from URL or identifier"""
        cleaned = raw.strip()
        match = re.search(r'/komik/([^/?#]+)', cleaned)
        if match:
            return match.group(1).rstrip('/')
        match_ch = re.search(r'/chapter/([^/?#]+)', cleaned)
        if match_ch:
            # e.g. solo-leveling-chapter-1-bahasa-indonesia -> solo-leveling
            ch_slug = match_ch.group(1).rstrip('/')
            manga_match = re.search(r'^(.*?)(?:-chapter-|\b)', ch_slug)
            if manga_match:
                return manga_match.group(1)
            return ch_slug
        return cleaned.rstrip('/')

    def can_handle_url(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """Check if URL or identifier belongs to MyNimeku"""
        cleaned = url.strip()
        lower = cleaned.lower()

        if "mynimeku" in lower:
            # 1. Comic detail URL: /komik/{slug}/
            match_komik = re.search(r'/komik/([^/?#]+)', cleaned)
            if match_komik:
                return True, match_komik.group(1), True

            # 2. Chapter URL: /chapter/{slug}/
            match_ch = re.search(r'/chapter/([^/?#]+)', cleaned)
            if match_ch:
                return True, match_ch.group(1), True

            # 3. Search URL: /search/{query}/
            match_search = re.search(r'/search/([^/?#]+)', cleaned)
            if match_search:
                query = urllib.parse.unquote_plus(match_search.group(1))
                return True, query, False

            return True, cleaned, False

        return False, None, False

    def get_image_referer(self, image_url: Optional[str] = None) -> str:
        """Return referer header for MyNimeku image downloads"""
        return f"{self.base_url}/"

    async def search(self, query: str) -> List[Dict]:
        """
        Search comics on MyNimeku.
        Filters out Anime results (/series/...) to only include Comics (/komik/...).
        """
        encoded_query = urllib.parse.quote(query.strip())
        url = f"{self.base_url}/search/{encoded_query}/"
        logger.debug(f"Searching MyNimeku: {url}")

        try:
            html = await self.fetch_html(url)
            articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
            results = []

            keywords = [w.lower() for w in re.split(r'[\s\-_]+', query) if len(w) > 1]
            norm_query = query.lower().replace('-', ' ')

            for article in articles:
                # FILTER: Only include Comic entries (/komik/...), skip Anime (/series/...)
                link_m = re.search(r'href=["\'](https?://(?:www\.)?mynimeku\.com/komik/([^"\'/?#]+)/?)["\']', article)
                if not link_m:
                    continue

                slug = link_m.group(2)

                # Title extraction
                title_m = re.search(r'<a[^>]+class=["\'][^"\']*series-title[^"\']*["\'][^>]*>(.*?)</a>', article, re.DOTALL)
                if not title_m:
                    title_m = re.search(r'<(?:h2|h3|h4)[^>]*>(.*?)</(?:h2|h3|h4)>', article, re.DOTALL)
                raw_title = title_m.group(1) if title_m else slug.replace('-', ' ').title()
                title = html_lib.unescape(re.sub(r'<[^>]+>', ' ', raw_title)).strip()

                # Cover extraction
                cover_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', article)
                cover = ""
                if cover_m:
                    cover = cover_m.group(1)
                    if cover.startswith("//"):
                        cover = f"https:{cover}"

                # Status extraction
                status_m = re.search(r'class=["\'][^"\']*status[^"\']*["\'][^>]*>(.*?)<', article)
                status_val = status_m.group(1).strip() if status_m else "Ongoing"
                status = "Completed" if any(w in status_val.lower() for w in ("tamat", "completed", "end")) else "Ongoing"

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
            logger.debug(f"MyNimeku search error: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Dict:
        """Get detail metadata of a comic from MyNimeku"""
        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/komik/{slug}/"
        logger.debug(f"Fetching MyNimeku manga info: {url}")

        html = await self.fetch_html(url)

        # Title
        h1_list = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = ""
        for h1 in h1_list:
            clean_h1 = re.sub(r'<[^>]+>', '', h1).strip()
            if clean_h1.lower() != "mynimeku":
                title = clean_h1
                break
        if not title:
            title = slug.replace('-', ' ').title()

        # Cover
        cover_m = re.search(r'<div class=["\'][^"\']*cover[^"\']*["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']', html, re.DOTALL)
        cover = ""
        if cover_m:
            cover = cover_m.group(1)
            if cover.startswith("//"):
                cover = f"https:{cover}"

        # Status
        status_m = re.search(r'<th[^>]*>Status</th>\s*<td>(.*?)</td>', html, re.I)
        status_val = status_m.group(1).strip() if status_m else "Ongoing"
        status = "Completed" if any(w in status_val.lower() for w in ("tamat", "completed", "end")) else "Ongoing"

        # Description
        desc_m = re.search(r'<div class=["\'][^"\']*(?:synopsis|entry)[^"\']*["\'][^>]*>(.*?)</div>', html, re.DOTALL)
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
        """Get chapter list for a comic on MyNimeku"""
        slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/komik/{slug}/"
        logger.debug(f"Fetching MyNimeku chapter list: {url}")

        html = await self.fetch_html(url)

        # Chapter items are formatted as:
        # <a class='komik-series-chapter-item' href='https://www.mynimeku.com/chapter/...'>
        items = re.findall(
            r"<a[^>]+class=['\"][^'\']*komik-series-chapter-item[^'\']*['\'][^>]+href=['\"](https?://(?:www\.)?mynimeku\.com/chapter/([^'\"/?#]+)/?)['\"][^>]*>(.*?)</a>",
            html,
            re.DOTALL
        )

        chapters = []
        for full_url, chapter_slug, content in items:
            # Extract chapter number from num span
            num_m = re.search(r"<span[^>]+class=['\"][^'\']*__num['\"][^>]*>([^<]+)</span>", content)
            if num_m:
                raw_num = num_m.group(1).strip()
            else:
                num_from_slug = re.search(r'chapter[-_ ]*([0-9]+(?:\.[0-9]+)?)', chapter_slug, re.I)
                raw_num = num_from_slug.group(1) if num_from_slug else "0"

            # Clean chapter number
            clean_num = raw_num
            if clean_num.startswith('.'):
                clean_num = '0' + clean_num

            # Chapter name
            name = f"Chapter {clean_num}"

            chapters.append({
                "chapter_id": chapter_slug,
                "number": clean_num,
                "raw_number": raw_num,
                "title": name,
                "name": name,
            })

        return chapters

    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """Get image URLs for a chapter on MyNimeku"""
        slug = chapter_id.strip().rstrip('/')
        url = f"{self.base_url}/chapter/{slug}/"
        logger.debug(f"Fetching MyNimeku chapter pages: {url}")

        html = await self.fetch_html(url)

        # Extract all image tags
        img_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
        pages = []
        seen = set()

        for src in img_srcs:
            clean_src = src.strip()
            if clean_src.startswith("//"):
                clean_src = f"https:{clean_src}"

            # Filter reader images
            if any(marker in clean_src.lower() for marker in ("/api/view-image/", "mydriveku", "/uploads/")):
                if clean_src not in seen:
                    seen.add(clean_src)
                    pages.append(clean_src)

        logger.info(f"Found {len(pages)} pages on MyNimeku for chapter {slug}")
        return pages
