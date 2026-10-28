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


def parse_target_input(raw_input: str) -> dict:
    """
    Parse input string to determine query, source hint, and whether it's a direct ID or search query.

    Returns:
        dict with:
            - query: normalized search query or comic ID
            - source: source slug | None (None means search all)
            - is_direct_id: bool (True if explicit ID/URL/slug, False if search query)
    """
    from .sources import registry
    return registry.resolve_input(raw_input)


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if URL is a valid comic URL, ID, or search query
    
    Args:
        url: URL, comic ID, or search query to validate
        
    Returns:
        Tuple of (is_valid, comic_id/slug or error_message)
    """
    cleaned = url.strip()
    if not cleaned:
        return False, "Input cannot be empty!"

    from .sources import registry
    parsed = registry.resolve_input(cleaned)
    if parsed.get("query"):
        return True, parsed["query"]
    
    return False, "Please provide a valid comic URL, ID, or Title"


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
