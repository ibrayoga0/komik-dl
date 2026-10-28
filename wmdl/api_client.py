"""
Shinigami API client for wmdl
"""

import asyncio
import logging
import random
import string
from typing import List, Dict, Optional
import aiohttp

from .config import BASE_URL, API_URL, CDN_URL

logger = logging.getLogger(__name__)


class ShinigamiAPI:
    """Client for Shinigami REST API"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.api_url = API_URL
        self.cdn_url = CDN_URL
        self.session: Optional[aiohttp.ClientSession] = None
    
    def _random_string(self, length: int) -> str:
        """Generate random string for headers"""
        chars = string.ascii_letters
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _get_api_headers(self) -> dict:
        """Generate API headers with anti-bot measures"""
        return {
            "Accept": "application/json",
            "DNT": "1",
            "Origin": self.base_url,
            "Sec-GPC": "1",
            "X-Requested-With": self._random_string(random.randint(10, 20))
        }
    
    def _get_image_headers(self) -> dict:
        """Generate headers for image downloads"""
        return {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "DNT": "1",
            "Referer": f"{self.base_url}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-GPC": "1",
            "X-Requested-With": self._random_string(random.randint(10, 20))
        }
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._get_api_headers()
            )
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_manga_info(self, manga_id: str) -> Dict:
        """
        Get manga details
        
        Args:
            manga_id: Manga ID (e.g., 'solo-leveling')
            
        Returns:
            Dict with title and other manga info
        """
        await self._ensure_session()
        
        try:
            url = f"{self.api_url}/v1/manga/detail/{manga_id}"
            logger.debug(f"Fetching manga info from: {url}")
            
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
                    'manga_id': manga_id
                }
        
        except Exception as e:
            logger.debug(f"Shinigami manga info fetch note: {e}")
            raise
    
    async def get_chapter_list(self, manga_id: str) -> List[Dict]:
        """
        Get list of chapters for a manga
        
        Args:
            manga_id: Manga ID
            
        Returns:
            List of chapter dicts with chapter_id, number, and title
        """
        await self._ensure_session()
        
        try:
            url = f"{self.api_url}/v1/chapter/{manga_id}/list"
            logger.debug(f"Fetching chapter list from: {url}")
            
            async with self.session.get(url, params={'page_size': 3000}) as response:
                if response.status != 200:
                    raise Exception(f"API returned status {response.status}")
                
                data = await response.json()
                
                # Handle different response formats
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
                    chapter_num = str(item.get('chapter_number', item.get('number', ''))).replace('.0', '')
                    chapter_title = item.get('chapter_title', item.get('title', ''))
                    
                    chapters.append({
                        'chapter_id': item.get('chapter_id', item.get('id', '')),
                        'number': chapter_num,
                        'title': chapter_title,
                        'name': f"Chapter {chapter_num}" + (f" - {chapter_title}" if chapter_title else "")
                    })
                
                logger.info(f"Found {len(chapters)} chapters")
                return chapters
        
        except Exception as e:
            logger.error(f"Error fetching chapter list: {e}")
            raise
    
    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """
        Get image URLs for a chapter
        
        Args:
            chapter_id: Chapter ID
            
        Returns:
            List of image URLs
        """
        await self._ensure_session()
        
        try:
            url = f"{self.api_url}/v1/chapter/detail/{chapter_id}"
            logger.debug(f"Fetching chapter pages from: {url}")
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"API returned status {response.status}")
                
                data = await response.json()
                
                # Parse response to get image URLs
                pages = []
                base_url = ""
                path = ""
                page_list = []
                
                if 'data' in data and 'chapter' in data['data']:
                    chapter_data = data['data']
                    base_url = chapter_data.get('base_url', chapter_data.get('base_url_low', ''))
                    path = chapter_data['chapter'].get('path', '')
                    page_list = chapter_data['chapter'].get('data', [])
                elif 'page_list' in data and 'chapter_page' in data['page_list']:
                    page_data = data['page_list']['chapter_page']
                    base_url = self.cdn_url
                    path = page_data.get('path', '')
                    page_list = page_data.get('pages', [])
                elif 'pages' in data:
                    page_list = data['pages']
                    base_url = data.get('base_url', self.cdn_url)
                    path = data.get('path', '')
                elif isinstance(data, list):
                    # Direct list of image URLs
                    return [item.get('image_url', item.get('url', item)) for item in data]
                
                if not page_list:
                    raise Exception("No pages found in response")
                
                # Build full image URLs
                image_urls = []
                for page in page_list:
                    if isinstance(page, str):
                        # Page is just filename
                        image_url = f"{base_url}{path}{page}"
                    else:
                        # Page might be an object
                        image_url = page.get('image_url', page.get('url', ''))
                    
                    if image_url:
                        image_urls.append(image_url)
                
                logger.info(f"Found {len(image_urls)} pages")
                return image_urls
        
        except Exception as e:
            logger.error(f"Error fetching chapter pages: {e}")
            raise
    
    async def search_manga(self, query: str, page: int = 1) -> List[Dict]:
        """
        Search for manga
        
        Args:
            query: Search query
            page: Page number
            
        Returns:
            List of manga dicts
        """
        await self._ensure_session()
        
        try:
            url = f"{self.api_url}/v1/manga/list"
            params = {
                'q': query,
                'page': page,
                'page_size': 30
            }
            logger.debug(f"Searching manga: {query}")
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"API returned status {response.status}")
                
                data = await response.json()
                
                if not data or 'data' not in data:
                    return []
                
                manga_list = []
                for item in data['data']:
                    manga_list.append({
                        'title': item.get('title', 'Unknown'),
                        'manga_id': item.get('manga_id', ''),
                        'cover': item.get('cover_image_url', ''),
                        'status': self._to_status(item.get('status', 0))
                    })
                
                return manga_list
        
        except Exception as e:
            logger.error(f"Error searching manga: {e}")
            raise
    
    def _to_status(self, status_code: int) -> str:
        """Convert status code to string"""
        if status_code == 1:
            return "Ongoing"
        elif status_code == 2:
            return "Completed"
        return "Unknown"
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
