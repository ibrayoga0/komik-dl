"""
Softkomik source provider for wmdl
Scrapes metadata and chapters from Softkomik (https://softkomik.app) via Next.js SSR data.
Includes decryption support for encrypted _stk payloads.
"""

import base64
import hashlib
import json
import logging
import re
import importlib
import urllib.parse
from typing import List, Dict, Optional, Tuple

from .base import BaseSource

logger = logging.getLogger(__name__)

SOFTKOMIK_BASE_URL = "https://softkomik.app"
SOFTKOMIK_CDN_URL = "https://psy1.komik.im"
SOFTKOMIK_ENCRYPTION_KEY = "nYTInq9MwR4pWa8yeXtu/2iO3t9nGP65WHpWEvqpEdU="


def _evp_bytes_to_key(password: bytes, salt: bytes, key_len: int = 32, iv_len: int = 16):
    """OpenSSL / CryptoJS EVP_BytesToKey with MD5"""
    dtmp = b""
    d = b""
    while len(d) < (key_len + iv_len):
        dtmp = hashlib.md5(dtmp + password + salt).digest()
        d += dtmp
    return d[:key_len], d[key_len:key_len + iv_len]


def _decrypt_stk(encrypted_b64: str, password: str = SOFTKOMIK_ENCRYPTION_KEY) -> dict:
    """Decrypt CryptoJS AES-encrypted _stk payload"""
    try:
        raw = base64.b64decode(encrypted_b64)
        if not raw.startswith(b"Salted__"):
            return {}

        salt = raw[8:16]
        ciphertext = raw[16:]

        key, iv = _evp_bytes_to_key(password.encode("utf-8"), salt, 32, 16)

        decrypted = None
        # Try PyCryptodome / pycryptodomex first
        try:
            aes_mod = importlib.import_module("Cryptodome.Cipher.AES")
            cipher = aes_mod.new(key, aes_mod.MODE_CBC, iv)
            decrypted = cipher.decrypt(ciphertext)
        except Exception:
            pass

        # Fallback to cryptography package
        if decrypted is None:
            try:
                hazmat = importlib.import_module("cryptography.hazmat.primitives.ciphers")
                cipher = hazmat.Cipher(hazmat.algorithms.AES(key), hazmat.modes.CBC(iv))
                decryptor = cipher.decryptor()
                decrypted = decryptor.update(ciphertext) + decryptor.finalize()
            except Exception:
                pass

        if decrypted is None:
            logger.debug("No AES decryption library available (install cryptography or pycryptodomex)")
            return {}

        pad_len = decrypted[-1]
        if pad_len > 16:
            return {}
        plaintext = decrypted[:-pad_len].decode("utf-8")
        return json.loads(plaintext)
    except Exception as e:
        logger.debug(f"Failed to decrypt _stk: {e}")
        return {}


class SoftkomikSource(BaseSource):
    """Source provider for Softkomik (https://softkomik.app)"""

    name = "Softkomik"
    slug = "softkomik"
    base_url = SOFTKOMIK_BASE_URL
    cdn_url = SOFTKOMIK_CDN_URL

    def can_handle_url(self, url: str) -> Tuple[bool, Optional[str], bool]:
        """
        Check if URL or identifier belongs to Softkomik
        """
        cleaned = url.strip()
        lower = cleaned.lower()

        if "softkomik" in lower:
            # 1. Search page: https://softkomik.app/komik/list?name=...
            if "/komik" in lower:
                name_match = re.search(r'name=([^&#]+)', cleaned)
                if name_match:
                    query = urllib.parse.unquote_plus(name_match.group(1))
                    return True, query, False
                return True, "", False

            # 2. Chapter URL: https://softkomik.app/{slug}/chapter/{ch}
            match_ch = re.search(r'softkomik\.(?:co|app)/([^/?#]+)/chapter/([^/?#]+)', cleaned, re.IGNORECASE)
            if match_ch:
                return True, match_ch.group(1), True

            # 3. Manga detail URL: https://softkomik.app/{slug}
            match = re.search(r'softkomik\.(?:co|app)/([^/?#]+)', cleaned, re.IGNORECASE)
            if match:
                slug_val = match.group(1)
                return True, slug_val, True

        # 4. Direct Softkomik slug (explicitly ends with -bahasa-indonesia)
        if lower.endswith("-bahasa-indonesia"):
            return True, cleaned, True

        return False, None, False

    def get_image_referer(self, image_url: Optional[str] = None) -> str:
        return f"{self.base_url}/"

    def _extract_next_data(self, html: str) -> dict:
        match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
        if not match:
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if not match:
            raise Exception("Gagal mengekstrak __NEXT_DATA__ dari halaman Softkomik")
        try:
            return json.loads(match.group(1))
        except Exception as e:
            raise Exception(f"Gagal mem-parse __NEXT_DATA__ JSON: {e}")

    def _extract_page_props(self, html: str) -> dict:
        next_data = self._extract_next_data(html)
        page_props = next_data.get("props", {}).get("pageProps", {})
        if "_stk" in page_props:
            decrypted = _decrypt_stk(page_props["_stk"])
            if decrypted:
                for k, v in decrypted.items():
                    page_props[k] = v
        return page_props

    def _extract_cdn_token(self, html: str) -> str:
        match = re.search(r'psy\d+\.komik\.im/[^"]+\?id=([^"&\s]+)', html)
        return match.group(1) if match else ""

    def _normalize_slug(self, slug: str) -> str:
        slug = slug.strip().strip("/").lower()
        slug = re.sub(r'[\s_]+', '-', slug)
        if not slug.endswith("-bahasa-indonesia"):
            return f"{slug}-bahasa-indonesia"
        return slug

    def _normalize_chapter_num(self, ch: str) -> str:
        s = str(ch).strip()
        return s.zfill(3) if len(s) < 3 else s

    async def search(self, query: str, page: int = 1) -> List[Dict]:
        """Search manga on Softkomik"""
        await self._ensure_session()
        if not self.session:
            return []

        try:
            url = f"{self.base_url}/komik/list"
            logger.debug(f"Searching Softkomik: {query}")
            async with self.session.get(url, params={"name": query}) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()

            page_props = self._extract_page_props(html)
            items = page_props.get("initialData", {}).get("data", [])

            keywords = [w.lower() for w in re.split(r'[\s\-_]+', query) if len(w) > 1]
            norm_query = query.lower().replace('-', ' ')

            results = []
            for item in items:
                slug = item.get("title_slug", "")
                title = item.get("title", "Unknown")
                gambar = item.get("gambar", "")
                cover = f"{self.cdn_url}/{gambar}" if gambar else ""
                raw_status = str(item.get("status", "Ongoing")).strip()

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
                        "cover": cover,
                        "status": raw_status.capitalize() if raw_status else "Ongoing",
                        "source": self.slug,
                        "source_name": self.name,
                        "score": score,
                    })

            results.sort(key=lambda x: -x["score"])
            return results[:5]

        except Exception as e:
            logger.debug(f"Error searching Softkomik: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Dict:
        """Get detail of manga on Softkomik"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        normalized_slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/{normalized_slug}"
        logger.debug(f"Fetching Softkomik manga info: {url}")

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Softkomik returned status {resp.status} for {url}")
            html = await resp.text()

        page_props = self._extract_page_props(html)
        manga_data = page_props.get("data", {})

        title = manga_data.get("title", normalized_slug.replace("-bahasa-indonesia", "").replace("-", " ").title())
        gambar = manga_data.get("gambar", "")
        cover = f"{self.cdn_url}/{gambar}" if gambar else ""
        raw_status = str(manga_data.get("status", "Ongoing")).strip()

        return {
            "title": title,
            "status": raw_status.capitalize() if raw_status else "Ongoing",
            "description": manga_data.get("sinopsis", ""),
            "cover": cover,
            "manga_id": normalized_slug,
            "source": self.name,
        }

    async def get_chapter_list(self, manga_id: str) -> List[Dict]:
        """Get chapter list for manga on Softkomik"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        normalized_slug = self._normalize_slug(manga_id)
        url = f"{self.base_url}/{normalized_slug}"

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Softkomik returned status {resp.status} for {url}")
            html = await resp.text()

        page_props = self._extract_page_props(html)
        chapter_data = page_props.get("chapterData", {})
        raw_chapters = chapter_data.get("chapter", [])

        chapters = []
        for item in raw_chapters:
            raw_num = str(item.get("chapter", "")).strip()
            clean_num = raw_num.lstrip("0") or "0"

            chapters.append({
                "chapter_id": f"{normalized_slug}::{raw_num}",
                "number": clean_num,
                "raw_number": raw_num,
                "title": "",
                "name": f"Chapter {raw_num}",
                "url": f"{self.base_url}/{normalized_slug}/chapter/{self._normalize_chapter_num(raw_num)}",
            })

        logger.info(f"Found {len(chapters)} chapters on Softkomik")
        return chapters

    async def get_chapter_pages(self, chapter_id: str) -> List[str]:
        """Get image URLs for a chapter on Softkomik (slug::raw_num)"""
        await self._ensure_session()
        if not self.session:
            raise Exception("Session initialization failed")

        if "::" in chapter_id:
            slug, chapter_num = chapter_id.split("::", 1)
        else:
            raise Exception(f"Invalid chapter_id format: {chapter_id}")

        slug = self._normalize_slug(slug)
        formatted_ch = self._normalize_chapter_num(chapter_num)
        url = f"{self.base_url}/{slug}/chapter/{formatted_ch}"
        logger.debug(f"Fetching Softkomik chapter pages: {url}")

        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Softkomik chapter returned status {resp.status} for {url}")
            html = await resp.text()

        token = self._extract_cdn_token(html)
        page_props = self._extract_page_props(html)
        img_list = page_props.get("imgList", [])

        # Filter out promo images
        filtered = [img for img in img_list if not img.startswith("img-file/00-hello/")]

        image_urls = []
        for img_path in filtered:
            full_url = f"{self.cdn_url}/{img_path}"
            if token:
                full_url = f"{full_url}?id={token}"
            image_urls.append(full_url)

        logger.info(f"Found {len(image_urls)} pages on Softkomik")
        return image_urls
