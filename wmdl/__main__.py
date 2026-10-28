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
    parse_target_input,
    parse_chapter_range,
    setup_logging,
    sanitize_filename
)
from .config import DEFAULT_DOWNLOAD_DIR

logger = logging.getLogger(__name__)


class CancelledError(Exception):
    """Raised when user cancels comic selection"""
    pass


def print_banner():
    """Print clean CLI banner"""
    print("+----------------------------------------------------------+")
    print("|                     KOMIK DOWNLOADER                     |")
    print("+----------------------------------------------------------+")
    print()


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

    async def _search_all_sources(self, query: str, source_filter: Optional[str] = None) -> list:
        """
        Search comics across all registered sources concurrently

        Args:
            query: Comic title or search query
            source_filter: Optional source filter ('shinigami' or 'softkomik')

        Returns:
            List of comic search results with source tag and relevance score
        """
        import re
        keywords = [w.lower() for w in re.split(r'[\s\-_]+', query) if len(w) > 1]
        norm_query = query.lower().replace('-', ' ')

        async def _search_shinigami():
            try:
                async with ShinigamiAPI() as api:
                    raw = await api.search_manga(query)
                    filtered = []
                    for item in raw:
                        t_lower = item.get('title', '').lower()
                        m_lower = item.get('manga_id', '').lower()
                        if not keywords or any(kw in t_lower or kw in m_lower for kw in keywords):
                            if t_lower == norm_query or t_lower == query.lower():
                                score = 100
                            elif keywords and all(kw in t_lower or kw in m_lower for kw in keywords):
                                score = 50
                            else:
                                score = 10
                            filtered.append({
                                'title': item.get('title', 'Unknown'),
                                'manga_id': item.get('manga_id', ''),
                                'status': item.get('status', 'Unknown'),
                                'cover': item.get('cover', ''),
                                'source': 'shinigami',
                                'source_name': 'Shinigami',
                                'score': score
                            })
                    filtered.sort(key=lambda x: -x['score'])
                    return filtered[:5]
            except Exception as e:
                logger.debug(f"Shinigami search error: {e}")
                return []

        async def _search_softkomik():
            try:
                async with SoftkomikAPI() as api:
                    raw = await api.search_manga(query)
                    filtered = []
                    for item in raw:
                        t_lower = item.get('title', '').lower()
                        m_lower = item.get('manga_id', '').lower()
                        if not keywords or any(kw in t_lower or kw in m_lower for kw in keywords):
                            if t_lower == norm_query or t_lower == query.lower():
                                score = 100
                            elif keywords and all(kw in t_lower or kw in m_lower for kw in keywords):
                                score = 50
                            else:
                                score = 10
                            filtered.append({
                                'title': item.get('title', 'Unknown'),
                                'manga_id': item.get('manga_id', ''),
                                'status': item.get('status', 'Ongoing'),
                                'cover': item.get('cover', ''),
                                'source': 'softkomik',
                                'source_name': 'Softkomik',
                                'score': score
                            })
                    filtered.sort(key=lambda x: -x['score'])
                    return filtered[:5]
            except Exception as e:
                logger.debug(f"Softkomik search error: {e}")
                return []

        tasks = []
        if source_filter == 'shinigami' or source_filter is None:
            tasks.append(_search_shinigami())
        if source_filter == 'softkomik' or source_filter is None:
            tasks.append(_search_softkomik())

        results_lists = await asyncio.gather(*tasks)
        combined = []
        for items in results_lists:
            combined.extend(items)

        # Stable sort so higher scores come first, keeping relative source order
        combined.sort(key=lambda x: -x['score'])
        return combined

    async def _fetch_comic_and_chapters(self, target_input: str, interactive: bool = False) -> Optional[Dict]:
        """
        Resolve comic and fetch chapters from detected source or multi-source search
        """
        parsed = parse_target_input(target_input)

        # 1. Direct ID / Slug / Detail URL
        if parsed['is_direct_id']:
            source = parsed['source']
            comic_id = parsed['query']
            if source == 'softkomik':
                try:
                    async with SoftkomikAPI() as api:
                        info = await api.get_manga_info(comic_id)
                        chapters = await api.get_chapter_list(info['manga_id'])
                        info['chapters'] = chapters
                        info['source'] = 'Softkomik'
                        return info
                except Exception as e:
                    logger.debug(f"Direct Softkomik fetch failed: {e}")
                    return None
            elif source == 'shinigami':
                try:
                    async with ShinigamiAPI() as api:
                        info = await api.get_manga_info(comic_id)
                        chapters = await api.get_chapter_list(info['manga_id'])
                        info['chapters'] = chapters
                        info['source'] = 'Shinigami'
                        return info
                except Exception as e:
                    logger.debug(f"Direct Shinigami fetch failed: {e}")
                    return None

        # 2. Search across sources
        query = parsed['query']
        source_hint = parsed['source']

        results = await self._search_all_sources(query, source_filter=source_hint)

        if not results:
            return None

        selected = None
        if len(results) == 1:
            selected = results[0]
            if interactive:
                print(f"Found: [{selected['source_name']}] {selected['title']} ({selected['status']})")
        elif interactive:
            print(f"\nMultiple results found for '{query}':")
            for i, comic in enumerate(results, 1):
                print(f"  {i}. [{comic['source_name']}] {comic['title']} ({comic['status']})")
            print()

            while True:
                choice = input(f"Select comic (1-{len(results)}, or 0 to cancel): ").strip()
                if choice == '0':
                    print("Selection cancelled.")
                    raise CancelledError("User cancelled comic selection")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(results):
                        selected = results[idx]
                        break
                except ValueError:
                    pass
                print("Invalid selection!")
        else:
            # Direct / non-interactive mode
            exact_matches = [c for c in results if c['score'] == 100]
            if exact_matches:
                selected = exact_matches[0]
            else:
                selected = results[0]

        # Fetch full comic details and chapters for selected comic
        source = selected['source']
        comic_id = selected['manga_id']

        if source == 'softkomik':
            async with SoftkomikAPI() as api:
                info = await api.get_manga_info(comic_id)
                chapters = await api.get_chapter_list(info['manga_id'])
                info['chapters'] = chapters
                info['source'] = 'Softkomik'
                return info
        elif source == 'shinigami':
            async with ShinigamiAPI() as api:
                info = await api.get_manga_info(comic_id)
                chapters = await api.get_chapter_list(info['manga_id'])
                info['chapters'] = chapters
                info['source'] = 'Shinigami'
                return info

        return None

    async def run_interactive(self):
        """Run in interactive mode"""
        print_banner()
        
        # Get comic URL/ID/Title
        while True:
            raw_input = input("Paste comic URL, ID, or Title (e.g., 'solo-leveling' or 'melting-slowly'): ").strip()
            
            if not raw_input:
                print("Input cannot be empty!")
                continue
            
            is_valid, result = validate_url(raw_input)
            
            if is_valid:
                target = raw_input
                break
            else:
                print(f"Error: {result}")
                print()
        
        print()
        print("Fetching comic information...")
        
        try:
            manga_info = await self._fetch_comic_and_chapters(target, interactive=True)
        except CancelledError:
            return
        
        if not manga_info:
            print(f"Error: Comic '{raw_input}' not found!")
            return
        
        if not manga_info.get('chapters'):
            print("Error: No chapters found for this comic!")
            return
        
        print()
        print(f"Title: {manga_info['title']}")
        if manga_info.get('source'):
            print(f"Source: {manga_info['source']}")
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
        print("-" * 60)
        print("Download Complete!")
        print("-" * 60)
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
            url: Comic URL, ID, or Title
            chapter: Single chapter number
            chapters: Chapter range string
            all_chapters: Download all chapters
        """
        # Validate URL/ID
        is_valid, result = validate_url(url)
        if not is_valid:
            print(f"Error: {result}")
            return
        
        print("Fetching comic information...")
        
        try:
            manga_info = await self._fetch_comic_and_chapters(url, interactive=False)
        except CancelledError:
            return
        
        if not manga_info:
            print(f"Error: Comic '{url}' not found! Try using the exact ID or URL.")
            return

        if not manga_info.get('chapters'):
            print("Error: No chapters found for this comic!")
            return
        
        print(f"Title: {manga_info['title']}")
        if manga_info.get('source'):
            print(f"Source: {manga_info['source']}")
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
        print("-" * 60)
        print("Download Complete!")
        print("-" * 60)
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
        description="Komik Downloader - Fast multi-source comic downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python -m wmdl
  
  # Download by URL
  python -m wmdl https://softkomik.app/melting-slowly-bahasa-indonesia --chapter 0
  
  # Download by Title
  python -m wmdl "Melting Slowly" --chapter 0
  
  # Download chapter range
  python -m wmdl "Solo Leveling" --chapters 1-10
  
  # Download all chapters
  python -m wmdl "Solo Leveling" --all
        """
    )
    
    parser.add_argument(
        'url',
        nargs='?',
        help='Comic URL, ID, or Title (e.g., "Solo Leveling" or "melting-slowly")'
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
