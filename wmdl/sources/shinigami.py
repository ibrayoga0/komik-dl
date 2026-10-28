"""
Shinigami source provider for wmdl
"""

import logging
import random
import re
import string
from typing import List, Dict, Optional, Tuple

from .base import BaseSource
from ..config import BASE_URL, API_URL, CDN_URL

logger = logging.getLogger(__name__)

UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


class ShinigamiSource(BaseSource):
    """Source provider for Shinigami (https://app.shinigami.asia)"""

    name = "Shinigami"
    slug = "shinigami"
    base_url = BASE_URL
    api_url = API_URL
    cdn_url = CDN_URL

    def _random_string(self, length: int) -> str:
        chars = string.ascii_letters
        return ''.join(random.choice(chars) for _ in range(length))

    def _get_api_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "DNT": "1",
            "Origin": self.base_url,
            "Sec-GPC": "1",
            "X-Requested-With": self._random_string(random.randint(10, 20))
        }

    def can_handle_url(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """Check if URL or identifier belongs to Shinigami"""
        cleaned = url.strip()
        lower = cleaned.lower()

        # 1. Full Shinigami URL: https://app.shinigami.asia/series/{id}
        if "shinigami" in lower:
            match = re.search(r'/series/([^/?]+)', cleaned)
            if match:
                return True, match.group(1), True
            return True, cleaned, False

        # 2. Direct UUID (Shinigami ID)
        if UUID_REGEX.match(cleaned):
            return True, cleaned, True

        return False, None, False

    def get_image_referer(self, image_url: Optional[str] = None) -> str:
        return f"{self.base_url}/"

    def _to_status(self, val) -> str:
        if val == 1 or str(val).lower() == 'ongoing':
            return 'Ongoing'
        elif val == 2 or str(val).lower() in ('completed', 'end'):
            return 'Completed'
        return 'Unknown'

    async def _ensure_session(self, headers: Optional[dict] = None):
        if self.session is None or self.session.closed:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=30)
            api_headers = self._get_api_headers()
            if headers:
                api_headers.update(headers)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=api_headers)

    async def search(self, query: str) -> List[Dict]:
        """Search manga on Shinigami"""
        await self._ensure_session()
        if not self.session:
            return []

        try:
            url = f"{self.api_url}/v1/manga/list"
            logger.debug(f"Searching Shinigami: {query}")
            params = {
                'page': 1,
                'page_size': 30,
                'search': query
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    return []
                data = await response.json()

            manga_list = []
            if isinstance(data, list):
                manga_list = data
            elif 'manga_list' in data and isinstance(data['manga_list'], list):
                manga_list = data['manga_list']
            elif 'data' in data and isinstance(data['data'], list):
                manga_list = data['data']

            keywords = [w.lower() for w in re.split(r'[\s\-_]+', query) if len(w) > 1]
            norm_query = query.lower().replace('-', ' ')

            results = []
            for item in manga_list:
                title = item.get('title', 'Unknown')
                manga_id = item.get('manga_id', item.get('id', ''))
                cover = item.get('cover_image_url', '')
                status = self._to_status(item.get('status', 0))

                t_lower = title.lower()
                m_lower = manga_id.lower()

                if not keywords or any(kw in t_lower or kw in m_lower for kw in keywords):
                    if t_lower == norm_query or t_lower == query.lower():
                        score = 100
                    elif keywords and all(kw in t_lower or kw in m_lower for kw in keywords):
                        score = 50
                    else:
                        score = 10

                    results.append({
                        'title': title,
                        'manga_id': manga_id,
                        'status': status,
                        'cover': cover,
                        'source': self.slug,
                        'source_name': self.name,
                        'score': score
                    })

            results.sort(key=lambda x: -x['score'])
            return results[:5]

        except Exception as e:
            logger.debug(f"Shinigami search error: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Dict:
        """Get detail of manga on Shinigami"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        url = f"{self.api_url}/v1/manga/detail/{manga_id}"
        logger.debug(f"Fetching Shinigami manga info: {url}")

        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"API returned status {response.status}")
            data = await response.json()

        if not data or 'data' not in data:
            raise Exception("Invalid response from API")

        manga_data = data['data']
        return {
            'title': manga_data.get('title', 'Unknown'),
            'status': self._to_status(manga_data.get('status', 0)),
            'description': manga_data.get('description', ''),
            'cover': manga_data.get('cover_image_url', ''),
            'manga_id': manga_id,
            'source': self.name,
        }

    async def get_chapter_list(self, manga_id: str) -> List[Dict]:
        """Get chapter list for manga on Shinigami"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        url = f"{self.api_url}/v1/chapter/{manga_id}/list"
        logger.debug(f"Fetching Shinigami chapter list: {url}")

        async with self.session.get(url, params={'page_size': 3000}) as response:
            if response.status != 200:
                raise Exception(f"API returned status {response.status}")
            data = await response.json()

        chapter_list = []
        if isinstance(data, list):
            chapter_list = data
        elif 'chapter_list' in data and isinstance(data['chapter_list'], list):
            chapter_list = data['chapter_list']
        elif 'data' in data and isinstance(data['data'], list):
            chapter_list = data['data']

        if not chapter_list:
            return []

        chapters = []
        for item in chapter_list:
            raw_num = str(item.get('chapter_number', item.get('number', ''))).replace('.0', '')
            clean_num = raw_num.lstrip('0') or '0'
            chapter_title = item.get('chapter_title', item.get('title', ''))

            chapters.append({
                'chapter_id': item.get('chapter_id', item.get('id', '')),
                'number': clean_num,
                'raw_number': raw_num,
                'title': chapter_title,
                'name': f"Chapter {raw_num}" + (f" - {chapter_title}" if chapter_title else ""),
                'url': f"{self.base_url}/series/{manga_id}",
            })

        logger.info(f"Found {len(chapters)} chapters on Shinigami")
        return chapters

    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """Get image URLs for chapter on Shinigami"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        url = f"{self.api_url}/v1/chapter/detail/{chapter_id}"
        logger.debug(f"Fetching Shinigami chapter pages: {url}")

        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"API returned status {response.status}")
            data = await response.json()

        if not data or 'data' not in data:
            raise Exception("Invalid response from API")

        chapter_data = data['data']
        chapter_pages = []
        if 'chapter' in chapter_data and 'data' in chapter_data['chapter']:
            chapter_pages = chapter_data['chapter']['data']
        elif 'data' in chapter_data and isinstance(chapter_data['data'], list):
            chapter_pages = chapter_data['data']

        image_urls = []
        for page in chapter_pages:
            image_url = None
            if isinstance(page, str):
                image_url = page
            elif isinstance(page, dict):
                image_url = page.get('image_url') or page.get('url') or page.get('path')

            if image_url:
                if not image_url.startswith('http'):
                    image_url = f"{self.cdn_url}/{image_url.lstrip('/')}"
                image_urls.append(image_url)

        logger.info(f"Found {len(image_urls)} pages on Shinigami")
        return image_urls
