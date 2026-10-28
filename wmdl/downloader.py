"""
Image downloader with retry logic and progress tracking
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional
import aiohttp  # type: ignore[import-untyped,import-not-found]
from tqdm import tqdm  # type: ignore[import-untyped,import-not-found]

from .config import (
    DEFAULT_DOWNLOAD_DIR,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_RETRIES,
    DOWNLOAD_TIMEOUT,
    RETRY_DELAY
)
from .utils import create_directory, format_image_number, get_file_extension

logger = logging.getLogger(__name__)


class ImageDownloader:
    """Download manager for manga images"""
    
    def __init__(self, download_dir: Optional[Path] = None):
        """
        Initialize downloader
        
        Args:
            download_dir: Base directory for downloads
        """
        self.download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
        create_directory(self.download_dir)
        
        # Semaphore for limiting concurrent downloads
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    
    async def download_chapter(
        self,
        manga_id: str,
        chapter_number: str,
        image_urls: List[str],
        chapter_folder: Optional[str] = None
    ) -> bool:
        """
        Download all images for a chapter
        
        Args:
            manga_id: Manga ID
            chapter_number: Chapter number
            image_urls: List of image URLs
            chapter_folder: Optional custom folder name
            
        Returns:
            True if all images downloaded successfully
        """
        if not image_urls:
            logger.warning(f"No images to download for chapter {chapter_number}")
            return False
        
        # Create chapter directory
        folder_name = chapter_folder or f"chapter-{chapter_number}"
        chapter_path = self.download_dir / manga_id / folder_name
        create_directory(chapter_path)
        
        logger.info(f"Downloading chapter {chapter_number} ({len(image_urls)} images) to {chapter_path}")
        
        # Download images
        async with aiohttp.ClientSession() as session:
            tasks = []
            for idx, url in enumerate(image_urls, 1):
                task = self._download_image(
                    session,
                    url,
                    chapter_path,
                    idx,
                    len(image_urls)
                )
                tasks.append(task)
            
            # Download with progress bar
            results = []
            with tqdm(total=len(image_urls), desc=f"Chapter {chapter_number}", unit="img") as pbar:
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    pbar.update(1)
        
        # Check results
        success_count = sum(1 for r in results if r)
        failed_count = len(results) - success_count
        
        if failed_count > 0:
            logger.warning(f"Chapter {chapter_number}: {success_count}/{len(image_urls)} images downloaded, {failed_count} failed")
            return False
        else:
            logger.info(f"Chapter {chapter_number}: All {success_count} images downloaded successfully")
            return True
    
    async def _download_image(
        self,
        session: aiohttp.ClientSession,
        url: str,
        output_dir: Path,
        image_number: int,
        total_images: int
    ) -> bool:
        """
        Download a single image with retry logic
        
        Args:
            session: aiohttp session
            url: Image URL
            output_dir: Output directory
            image_number: Image number (1-indexed)
            total_images: Total number of images
            
        Returns:
            True if downloaded successfully
        """
        async with self.semaphore:
            # Determine filename
            ext = get_file_extension(url)
            filename = f"{format_image_number(image_number, total_images)}{ext}"
            filepath = output_dir / filename
            
            # Skip if already exists
            if filepath.exists():
                logger.debug(f"Skipping {filename} (already exists)")
                return True
            
            # Retry logic
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # Determine referer based on image URL
                    from .sources import registry
                    referer = registry.get_referer_for_url(url)

                    headers = {
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                        "DNT": "1",
                        "Referer": referer,
                        "Sec-Fetch-Dest": "empty",
                        "Sec-GPC": "1",
                    }
                    
                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
                    ) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            # Write to file
                            filepath.write_bytes(content)
                            
                            logger.debug(f"Downloaded {filename}")
                            
                            return True
                        else:
                            logger.warning(f"Failed to download {filename}: HTTP {response.status}")
                
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout downloading {filename} (attempt {attempt}/{MAX_RETRIES})")
                
                except Exception as e:
                    logger.warning(f"Error downloading {filename} (attempt {attempt}/{MAX_RETRIES}): {e}")
                
                # Wait before retry
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)  # Linear backoff
            
            logger.error(f"Failed to download {filename} after {MAX_RETRIES} attempts")
            return False
    
    async def download_batch(
        self,
        manga_info: dict,
        chapters_to_download: List[dict],
        delay_between_chapters: float = 2.0,
        api: Optional[object] = None
    ) -> dict:
        """
        Download multiple chapters
        
        Args:
            manga_info: Manga information dict from API
            chapters_to_download: List of chapter dicts to download
            delay_between_chapters: Delay between chapters in seconds
            api: Optional API client instance
            
        Returns:
            Dict with download statistics
        """
        stats = {
            'total': len(chapters_to_download),
            'success': 0,
            'failed': 0
        }
        
        logger.info(f"Starting batch download: {len(chapters_to_download)} chapters")
        
        # Determine API client dynamically from registry
        if api is not None:
            active_api = api
            owns_session = False
        else:
            from .sources import registry
            source_key = str(manga_info.get('source_key') or manga_info.get('source', '')).lower()
            active_api = registry.get(source_key) or registry.get('shinigami')
            owns_session = True
        
        try:
            for chapter in chapters_to_download:
                try:
                    # Get chapter images from API
                    images = await active_api.get_chapter_pages(chapter['chapter_id'])
                    
                    if not images:
                        logger.error(f"No images found for chapter {chapter['number']}")
                        stats['failed'] += 1
                        continue
                    
                    # Use sanitized title for folder name
                    from .utils import sanitize_filename
                    folder_name = sanitize_filename(manga_info['title'])
                    
                    # Download chapter
                    success = await self.download_chapter(
                        folder_name,
                        chapter['number'],
                        images,
                        f"chapter-{chapter['number']}"
                    )
                    
                    if success:
                        stats['success'] += 1
                    else:
                        stats['failed'] += 1
                    
                    # Delay between chapters
                    if chapter != chapters_to_download[-1]:
                        await asyncio.sleep(delay_between_chapters)
                
                except Exception as e:
                    logger.error(f"Error downloading chapter {chapter['number']}: {e}")
                    stats['failed'] += 1
        finally:
            if owns_session and active_api:
                await active_api.close()
        
        return stats
