"""
Main CLI entry point for wmdl
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import Optional, Dict

from .api_client import ShinigamiAPI
from .softkomik_client import SoftkomikAPI
from .downloader import ImageDownloader
from .utils import (
    validate_url,
    parse_chapter_range,
    setup_logging,
    sanitize_filename
)
from .config import DEFAULT_DOWNLOAD_DIR

logger = logging.getLogger(__name__)


class WMDLApp:
    """Main application class"""
    
    def __init__(self, download_dir: Optional[Path] = None, verbose: bool = False):
        """
        Initialize application
        
        Args:
            download_dir: Custom download directory
            verbose: Enable verbose logging
        """
        setup_logging(verbose)
        self.download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
        self.downloader = ImageDownloader(self.download_dir)
    
    async def _resolve_manga(self, api, query: str, interactive: bool = False) -> Optional[Dict]:
        """
        Resolve manga by ID or search
        
        Args:
            api: API instance (ShinigamiAPI or SoftkomikAPI)
            query: Manga ID or search query
            interactive: Whether to ask user for selection
            
        Returns:
            Manga info dict or None
        """
        # 1. Try direct ID fetch
        try:
            manga_info = await api.get_manga_info(query)
            return manga_info
        except:
            # Not a valid ID, try search
            logger.debug(f"ID fetch failed for '{query}', trying search...")
        
        # 2. Search
        try:
            raw_results = await api.search_manga(query)
            
            if not raw_results:
                return None
            
            # Filter results so that at least one significant keyword appears in title or manga_id
            import re
            keywords = [w.lower() for w in re.split(r'[\s\-_]+', query) if len(w) > 1]
            results = []
            for manga in raw_results:
                title_lower = manga.get('title', '').lower()
                manga_id_lower = manga.get('manga_id', '').lower()
                if not keywords or any(kw in title_lower or kw in manga_id_lower for kw in keywords):
                    results.append(manga)
            
            if not results:
                logger.debug(f"No relevant search results for '{query}' after keyword filter")
                return None
            
            if len(results) == 1:
                # Only 1 result, use it
                return await api.get_manga_info(results[0]['manga_id'])
            
            # Multiple results
            if interactive:
                print(f"\nMultiple results found for '{query}':")
                for i, manga in enumerate(results[:5], 1):
                    print(f"  {i}. {manga['title']} ({manga['status']})")
                print()
                
                while True:
                    choice = input(f"Select manga (1-{len(results[:5])}, or 0 to cancel): ").strip()
                    if choice == '0':
                        return None
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(results[:5]):
                            return await api.get_manga_info(results[idx]['manga_id'])
                    except ValueError:
                        pass
                    print("Invalid selection!")
            else:
                # Direct mode: Try exact match or fail
                # Normalize query (replace hyphens with spaces) and lowercase
                norm_query = query.lower().replace('-', ' ')
                
                for manga in results:
                    norm_title = manga['title'].lower()
                    # Check for exact match, slug match, or query contained in title
                    if norm_title == norm_query or norm_title == query.lower() or norm_query in norm_title:
                         return await api.get_manga_info(manga['manga_id'])
                
                return None
                
        except Exception as e:
            logger.error(f"Error resolving manga: {e}")
            return None

    async def _fetch_manga_and_chapters(self, query: str, is_softkomik_hint: bool, interactive: bool) -> Optional[Dict]:
        """Resolve manga and fetch chapters from Softkomik or Shinigami"""
        if is_softkomik_hint:
            try:
                async with SoftkomikAPI() as api:
                    info = await self._resolve_manga(api, query, interactive=interactive)
                    if info:
                        chapters = await api.get_chapter_list(info['manga_id'])
                        info['chapters'] = chapters
                        info['source'] = 'softkomik'
                        return info
            except Exception as e:
                logger.debug(f"Softkomik fetch error: {e}")
            return None

        # Try Shinigami first
        try:
            async with ShinigamiAPI() as api:
                info = await self._resolve_manga(api, query, interactive=interactive)
                if info:
                    chapters = await api.get_chapter_list(info['manga_id'])
                    info['chapters'] = chapters
                    info['source'] = 'shinigami'
                    return info
        except Exception as e:
            logger.debug(f"Shinigami fetch error: {e}")

        # Fallback to Softkomik if Shinigami not found
        try:
            async with SoftkomikAPI() as api:
                info = await self._resolve_manga(api, query, interactive=interactive)
                if info:
                    chapters = await api.get_chapter_list(info['manga_id'])
                    info['chapters'] = chapters
                    info['source'] = 'softkomik'
                    return info
        except Exception as e:
            logger.debug(f"Softkomik fallback error: {e}")

        return None

    async def run_interactive(self):
        """Run in interactive mode"""
        print("=" * 60)
        print("Manga Downloader (Shinigami.id & Softkomik.co)")
        print("=" * 60)
        print()
        
        # Get comic URL/ID
        while True:
            url = input("Paste manga URL, ID, or Title (e.g., 'solo-leveling' or 'melting-slowly'): ").strip()
            
            if not url:
                print("Input cannot be empty!")
                continue
            
            is_valid, result = validate_url(url)
            
            if is_valid:
                query = result
                break
            else:
                print(f"Error: {result}")
                print()
        
        print()
        print("Fetching manga information...")
        
        # Get manga info
        is_softkomik = 'softkomik' in url.lower() or query.endswith('-bahasa-indonesia')
        manga_info = await self._fetch_manga_and_chapters(query, is_softkomik, interactive=True)
        
        if not manga_info:
            print(f"Error: Manga '{query}' not found!")
            return
        
        if not manga_info.get('chapters'):
            print("Error: No chapters found for this manga!")
            return
        
        print()
        print(f"Title: {manga_info['title']}")
        print(f"Status: {manga_info['status']}")
        print(f"Available chapters: {len(manga_info['chapters'])}")
        print(f"Latest chapter: {manga_info['chapters'][0]['name']}")
        print()
        
        # Get download choice
        while True:
            print("Download options:")
            print("  1. Single chapter")
            print("  2. Chapter range (e.g., 1-10)")
            print("  3. All chapters")
            print("  4. Exit")
            print()
            
            choice = input("Select option (1-4): ").strip()
            
            if choice == '4':
                print("Goodbye!")
                return
            
            if choice == '1':
                # Single chapter
                print(f"Enter chapter number (Available: {manga_info['chapters'][-1]['name']} - {manga_info['chapters'][0]['name']})")
                chapter_input = input("Chapter number (or range like 1-10): ").strip()
                if '-' in chapter_input or ',' in chapter_input:
                    try:
                        target_nums = parse_chapter_range(chapter_input)
                        target_strs = [str(n) for n in target_nums]
                        chapters_to_process = [
                            ch for ch in manga_info['chapters'] 
                            if ch['number'] in target_strs 
                            or ch.get('raw_number') in target_strs
                            or (ch['number'].isdigit() and int(ch['number']) in target_nums)
                        ]
                        if not chapters_to_process:
                            print(f"No matching chapters found for {chapter_input}!")
                            continue
                        break
                    except ValueError:
                        print("Invalid chapter range format!")
                        print()
                        continue
                
                try:
                    target_chapter = str(chapter_input).strip()
                    target_int = int(target_chapter) if target_chapter.isdigit() else None
                    chapter_to_download = next((
                        ch for ch in manga_info['chapters'] 
                        if ch['number'] == target_chapter 
                        or ch.get('raw_number') == target_chapter
                        or (target_int is not None and ch['number'].isdigit() and int(ch['number']) == target_int)
                    ), None)
                    
                    if not chapter_to_download:
                        print(f"Chapter {chapter_input} not found!")
                        continue
                        
                    chapters_to_process = [chapter_to_download]
                    break
                except ValueError:
                    print("Invalid chapter number!")
                    print()
            
            elif choice == '2':
                # Chapter range
                range_input = input("Enter chapter range (e.g., 1-10 or 1,3,5): ").strip()
                try:
                    target_nums = parse_chapter_range(range_input)
                    target_strs = [str(n) for n in target_nums]
                    
                    chapters_to_process = [
                        ch for ch in manga_info['chapters'] 
                        if ch['number'] in target_strs 
                        or ch.get('raw_number') in target_strs
                        or (ch['number'].isdigit() and int(ch['number']) in target_nums)
                    ]
                    
                    if not chapters_to_process:
                        print("No matching chapters found!")
                        continue
                        
                    break
                except ValueError as e:
                    print(f"Invalid range format: {e}")
                    print()
            
            elif choice == '3':
                # All chapters
                chapters_to_process = manga_info['chapters']
                break
            
            else:
                print("Invalid option!")
                print()
        
        # Sort chapters
        try:
            chapters_to_process.sort(key=lambda x: float(x['number']) if x['number'].replace('.', '', 1).isdigit() else 999999)
        except:
            pass
            
        print()
        print(f"Will download {len(chapters_to_process)} chapter(s)")
        folder_name = sanitize_filename(manga_info.get('title') or manga_info['manga_id'])
        print(f"Download location: {self.download_dir / folder_name}")
        print()
        
        confirm = input("Start download? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Download cancelled")
            return
        
        print()
        print("Starting download...")
        print()
        
        # Download
        stats = await self.downloader.download_batch(
            manga_info,
            chapters_to_process,
            delay_between_chapters=1.0
        )
        
        # Show results
        print()
        print("=" * 60)
        print("Download Complete!")
        print("=" * 60)
        print(f"Total chapters: {stats['total']}")
        print(f"Success: {stats['success']}")
        print(f"Failed: {stats['failed']}")
        print()
        folder_name = sanitize_filename(manga_info.get('title') or manga_info['manga_id'])
        print(f"Files saved to: {self.download_dir / folder_name}")
        print()
    
    async def run_direct(
        self,
        url: str,
        chapter: Optional[str] = None,
        chapters: Optional[str] = None,
        all_chapters: bool = False
    ):
        """
        Run in direct mode with command arguments
        
        Args:
            url: Manga URL, ID, or Title
            chapter: Single chapter number
            chapters: Chapter range string
            all_chapters: Download all chapters
        """
        # Validate URL/ID
        is_valid, result = validate_url(url)
        if not is_valid:
            print(f"Error: {result}")
            return
        
        query = result
        
        print("Fetching manga information...")
        
        # Get manga info
        is_softkomik = 'softkomik' in url.lower() or query.endswith('-bahasa-indonesia')
        manga_info = await self._fetch_manga_and_chapters(query, is_softkomik, interactive=False)
        
        if not manga_info:
            print(f"Error: Manga '{query}' not found! Try using the exact ID or URL.")
            return

        if not manga_info.get('chapters'):
            print("Error: No chapters found for this manga!")
            return
        
        print(f"Title: {manga_info['title']}")
        print(f"Available chapters: {len(manga_info['chapters'])}")
        print()
        
        # Determine chapters to download
        chapters_to_process = []
        
        # Merge chapter and chapters arguments so user can use either --chapter or --chapters
        chapter_arg = chapters or chapter

        if all_chapters:
            chapters_to_process = manga_info['chapters']
        elif chapter_arg:
            chapter_str = str(chapter_arg).strip()
            # If range format (contains '-' or ',')
            if '-' in chapter_str or ',' in chapter_str:
                try:
                    target_nums = parse_chapter_range(chapter_str)
                    target_strs = [str(n) for n in target_nums]
                    
                    chapters_to_process = [
                        ch for ch in manga_info['chapters'] 
                        if ch['number'] in target_strs 
                        or ch.get('raw_number') in target_strs
                        or (ch['number'].isdigit() and int(ch['number']) in target_nums)
                    ]
                except ValueError as e:
                    print(f"Error: Invalid chapter range - {e}")
                    return
            else:
                # Single chapter
                target_chapter = chapter_str
                target_int = int(target_chapter) if target_chapter.isdigit() else None
                chapter_data = next((
                    ch for ch in manga_info['chapters'] 
                    if ch['number'] == target_chapter 
                    or ch.get('raw_number') == target_chapter
                    or (target_int is not None and ch['number'].isdigit() and int(ch['number']) == target_int)
                ), None)
                if chapter_data:
                    chapters_to_process = [chapter_data]
                else:
                    print(f"Error: Chapter {chapter_str} not found")
                    return
        else:
            print("Error: Must specify --chapter, --chapters, or --all")
            return
        
        if not chapters_to_process:
            print("No matching chapters found to download.")
            return

        # Sort chapters
        try:
            chapters_to_process.sort(key=lambda x: float(x['number']) if x['number'].replace('.', '', 1).isdigit() else 999999)
        except:
            pass

        print(f"Downloading {len(chapters_to_process)} chapter(s)...")
        print()
        
        # Download
        stats = await self.downloader.download_batch(
            manga_info,
            chapters_to_process,
            delay_between_chapters=1.0
        )
        
        # Show results
        print()
        print("=" * 60)
        print("Download Complete!")
        print("=" * 60)
        print(f"Success: {stats['success']}/{stats['total']}")
        if stats['failed'] > 0:
            print(f"Failed: {stats['failed']}")
        folder_name = sanitize_filename(manga_info.get('title') or manga_info['manga_id'])
        print(f"Location: {self.download_dir / folder_name}")
        print()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Manga Downloader - Download manga/manhwa from Shinigami.id & Softkomik.co",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python -m wmdl
  
  # Download from Softkomik by URL
  python -m wmdl https://softkomik.co/melting-slowly-bahasa-indonesia --chapter 0
  
  # Download from Softkomik by Title
  python -m wmdl "Melting Slowly" --chapter 0
  
  # Download range from Softkomik
  python -m wmdl "Melting Slowly" --chapters 0-3
  
  # Download from Shinigami
  python -m wmdl "Solo Leveling" --chapter 1
  python -m wmdl solo-leveling --chapters 1-10
        """
    )
    
    parser.add_argument(
        'url',
        nargs='?',
        help='Manga URL, ID, or Title (e.g., solo-leveling or https://softkomik.co/melting-slowly-bahasa-indonesia)'
    )
    
    parser.add_argument(
        '--chapter',
        type=str,
        help='Download single chapter'
    )
    
    parser.add_argument(
        '--chapters',
        type=str,
        help='Download chapter range (e.g., 1-10 or 1,3,5)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Download all chapters'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        type=Path,
        help=f'Output directory (default: {DEFAULT_DOWNLOAD_DIR})'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Create app
    app = WMDLApp(download_dir=args.output, verbose=args.verbose)
    
    # Run
    try:
        if args.url:
            # Direct mode
            asyncio.run(app.run_direct(
                args.url,
                chapter=args.chapter,
                chapters=args.chapters,
                all_chapters=args.all
            ))
        else:
            # Interactive mode
            asyncio.run(app.run_interactive())
    
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user")
        sys.exit(0)
    
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
