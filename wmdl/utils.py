"""
Utility functions for wmdl
"""

import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from .config import BASE_URL, LOG_FORMAT, LOG_DATE_FORMAT


def sanitize_filename(filename: str) -> str:
    """
    Remove or replace characters that are invalid in filenames
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    return filename


def parse_chapter_range(range_str: str) -> List[int]:
    """
    Parse chapter range string like "1-10" into list of chapter numbers
    
    Args:
        range_str: Range string (e.g., "1-10", "5", "1,3,5-7")
        
    Returns:
        List of chapter numbers
    """
    chapters = []
    
    # Split by comma for multiple ranges
    parts = range_str.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range like "1-10"
            start, end = part.split('-')
            start = int(start.strip())
            end = int(end.strip())
            chapters.extend(range(start, end + 1))
        else:
            # Single chapter
            chapters.append(int(part))
    
    return sorted(list(set(chapters)))  # Remove duplicates and sort


def format_chapter_number(chapter_num: int, padding: int = 2) -> str:
    """
    Format chapter number with zero padding
    
    Args:
        chapter_num: Chapter number
        padding: Number of digits to pad to
        
    Returns:
        Formatted chapter number string
    """
    return str(chapter_num).zfill(padding)


def format_image_number(image_num: int, total_images: int) -> str:
    """
    Format image number with appropriate padding based on total
    
    Args:
        image_num: Image number (1-indexed)
        total_images: Total number of images
        
    Returns:
        Formatted image number string
    """
    # Determine padding based on total images
    padding = len(str(total_images))
    return str(image_num).zfill(padding)


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if URL is a valid Shinigami or Softkomik manga URL, or extract ID/slug
    
    Args:
        url: URL, manga ID, or search query to validate
        
    Returns:
        Tuple of (is_valid, manga_id/slug or error_message)
    """
    url = url.strip()
    
    # Check if it's a Softkomik URL
    if 'softkomik' in url.lower():
        # Chapter URL: https://softkomik.co/{slug}/chapter/{ch}
        match_ch = re.search(r'softkomik\.co/([^/?#]+)/chapter/([^/?#]+)', url)
        if match_ch:
            return True, match_ch.group(1)
        # Manga detail URL: https://softkomik.co/{slug}
        match = re.search(r'softkomik\.co/([^/?#]+)', url)
        if match:
            slug = match.group(1)
            if slug == 'komik':
                # e.g. /komik/list?name=...
                name_match = re.search(r'name=([^&#]+)', url)
                if name_match:
                    import urllib.parse
                    return True, urllib.parse.unquote_plus(name_match.group(1))
                return False, "Gunakan link detail komik atau judul pencarian"
            return True, slug
        return False, "Format URL Softkomik tidak valid. Contoh: https://softkomik.co/melting-slowly-bahasa-indonesia"

    # Check if it's a full Shinigami URL
    if 'shinigami' in url.lower():
        # Extract manga ID from URL
        # Format: https://app.shinigami.asia/series/{manga-id}
        match = re.search(r'/series/([^/?]+)', url)
        if match:
            return True, match.group(1)
        return False, "Invalid Shinigami URL format. Expected: https://app.shinigami.asia/series/{manga-id}"
    
    # Check if it's a direct ID, slug, or search query
    if url and not any(char in url for char in ['/', '\\', '?', '#']):
        return True, url
    
    # Allow query with spaces
    if url:
        return True, url
    
    return False, "Please provide a valid manga URL or manga ID/Title"


def setup_logging(verbose: bool = False) -> None:
    """
    Setup logging configuration
    
    Args:
        verbose: Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT
    )


def create_directory(path: Path) -> None:
    """
    Create directory if it doesn't exist
    
    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)


def get_file_extension(url: str) -> str:
    """
    Extract file extension from URL
    
    Args:
        url: Image URL
        
    Returns:
        File extension (e.g., '.jpg', '.png')
    """
    # Remove query parameters
    url = url.split('?')[0]
    
    # Get extension
    ext = Path(url).suffix
    
    # Default to .jpg if no extension found
    if not ext:
        ext = '.jpg'
    
    return ext
