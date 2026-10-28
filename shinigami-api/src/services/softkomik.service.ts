import axios, { AxiosInstance } from "axios";
import crypto from "crypto";
import {
  Manga,
  MangaListResponse,
  Chapter,
  Page,
} from "../types/manga.types";

/**
 * SoftkomikService
 *
 * Strategi scraping:
 * 1. Search      → GET /komik/list?name={query}            → parse __NEXT_DATA__ JSON
 * 2. Chapters    → GET /{title_slug}                       → parse __NEXT_DATA__ JSON
 * 3. Page list   → GET /{title_slug}/chapter/{chapterNum}  → parse __NEXT_DATA__ + extract CDN token dari HTML
 *
 * CDN gambar: https://psy1.komik.im/{imgPath}?id={token}
 * Token CDN diambil dari HTML img src pada halaman reading (statik per-chapter).
 */
export class SoftkomikService {
  private baseUrl: string;
  private cdnUrl: string;
  private client: AxiosInstance;

  constructor() {
    this.baseUrl = "https://softkomik.co";
    this.cdnUrl = "https://psy1.komik.im";

    this.client = axios.create({
      timeout: 30000,
      headers: this.getHeaders(),
    });
  }

  private getHeaders(): Record<string, string> {
    return {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      Accept:
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
      Referer: "https://softkomik.co/",
    };
  }

  private getImageHeaders(): Record<string, string> {
    return {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      Accept: "image/webp,image/avif,image/*,*/*;q=0.8",
      Referer: "https://softkomik.co/",
    };
  }

  /**
   * Mengambil dan mem-parse __NEXT_DATA__ JSON dari HTML halaman Next.js SSR
   */
  private extractNextData(html: string): any {
    const marker = "__NEXT_DATA__";
    const markerIdx = html.indexOf(marker);
    if (markerIdx === -1) {
      throw new Error("__NEXT_DATA__ tidak ditemukan di halaman");
    }
    const jsonStart = html.indexOf("{", markerIdx);
    const jsonEnd = html.indexOf("</script>", jsonStart);
    if (jsonStart === -1 || jsonEnd === -1) {
      throw new Error("Gagal mengekstrak __NEXT_DATA__");
    }
    try {
      return JSON.parse(html.substring(jsonStart, jsonEnd));
    } catch {
      throw new Error("Gagal mem-parse __NEXT_DATA__ JSON");
    }
  }

  /**
   * Dekripsi payload _stk yang dienkripsi menggunakan CryptoJS AES
   */
  private decryptStk(encryptedB64: string): any {
    try {
      const password = "nYTInq9MwR4pWa8yeXtu/2iO3t9nGP65WHpWEvqpEdU=";
      const raw = Buffer.from(encryptedB64, "base64");
      if (raw.subarray(0, 8).toString("utf8") !== "Salted__") return null;
      const salt = raw.subarray(8, 16);
      const ciphertext = raw.subarray(16);

      let dtmp = Buffer.alloc(0);
      let d = Buffer.alloc(0);
      const passBuf = Buffer.from(password, "utf8");
      while (d.length < 48) {
        dtmp = crypto.createHash("md5").update(Buffer.concat([dtmp, passBuf, salt])).digest();
        d = Buffer.concat([d, dtmp]);
      }
      const key = d.subarray(0, 32);
      const iv = d.subarray(32, 48);

      const decipher = crypto.createDecipheriv("aes-256-cbc", key, iv);
      let decrypted = decipher.update(ciphertext);
      decrypted = Buffer.concat([decrypted, decipher.final()]);
      return JSON.parse(decrypted.toString("utf8"));
    } catch {
      return null;
    }
  }

  /**
   * Ambil pageProps dan otomatis dekripsi payload _stk jika ada
   */
  private extractPageProps(html: string): any {
    const nextData = this.extractNextData(html);
    const pageProps = nextData?.props?.pageProps;
    if (pageProps?._stk) {
      const decrypted = this.decryptStk(pageProps._stk);
      if (decrypted) {
        Object.assign(pageProps, decrypted);
      }
    }
    return pageProps;
  }

  /**
   * Mengambil CDN token dari HTML halaman reading.
   * Token ini ada pada atribut src img: psy1.komik.im/...?id=TOKEN
   * Token diperlukan agar gambar bisa diakses (tanpa token → redirect ke halaman error).
   */
  private extractCdnToken(html: string): string {
    const match = html.match(/psy\d+\.komik\.im\/[^"]+\?id=([^"&\s]+)/);
    return match ? match[1] : "";
  }

  /**
   * Membangun full URL gambar dari relative path CDN
   */
  private buildImageUrl(relativePath: string, cdnToken?: string): string {
    const base = `${this.cdnUrl}/${relativePath}`;
    return cdnToken ? `${base}?id=${cdnToken}` : base;
  }

  /**
   * Normalisasi chapter number ke string (pertahankan format asli dari website)
   * Website menggunakan format: "000", "001", "076", "0010"
   */
  private normalizeChapterNum(num: string | number): string {
    const s = String(num).trim();
    // Jika kurang dari 3 karakter, pad dengan 0
    return s.length < 3 ? s.padStart(3, "0") : s;
  }


  /**
   * Pastikan title_slug memiliki suffix "-bahasa-indonesia"
   * Jika sudah ada, tidak ditambahkan lagi.
   */
  private normalizeTitleSlug(slug: string): string {
    return slug.endsWith("-bahasa-indonesia")
      ? slug
      : `${slug}-bahasa-indonesia`;
  }

  // ============================================================
  // PUBLIC METHODS
  // ============================================================

  /**
   * Cari komik berdasarkan nama.
   * URL: https://softkomik.co/komik/list?name={query}
   *
   * @param query - Kata kunci pencarian
   * @returns MangaListResponse dengan list komik yang cocok
   */
  async searchManga(query: string): Promise<MangaListResponse> {
    if (!query || query.trim().length === 0) {
      throw new Error("Query pencarian tidak boleh kosong");
    }

    try {
      const response = await this.client.get(`${this.baseUrl}/komik/list`, {
        params: { name: query.trim() },
      });

      const pageProps = this.extractPageProps(response.data as string);

      if (!pageProps) {
        throw new Error("Struktur response tidak valid");
      }

      const items: any[] = pageProps?.initialData?.data || [];

      // CDN token untuk cover image (opsional - cover mungkin tidak perlu token)
      const cdnToken = this.extractCdnToken(response.data as string);

      const mangas: Manga[] = items.map((item: any) => {
        const slug = item.title_slug || "";
        const gambar = item.gambar || "";
        const thumbnailUrl = gambar
          ? this.buildImageUrl(gambar, cdnToken || undefined)
          : "";

        return {
          title: item.title || "Unknown",
          thumbnail: thumbnailUrl,
          url: slug, // title_slug sebagai unique ID
          mangaUrl: `${this.baseUrl}/${slug}`,
        };
      });

      const currentPage = pageProps?.initialData?.page ?? 1;
      const maxPage = pageProps?.initialData?.maxPage ?? 1;

      return {
        mangas,
        hasNextPage: currentPage < maxPage,
      };
    } catch (error: any) {
      if (error.response) {
        throw new Error(
          `Gagal mencari komik: ${error.response.status} - ${
            error.response.data?.message || error.message
          }`
        );
      }
      throw new Error(`Gagal mencari komik: ${error.message}`);
    }
  }

  /**
   * Ambil daftar chapter dari halaman detail komik.
   * URL: https://softkomik.co/{titleSlug}
   *
   * @param titleSlug - Slug komik dari hasil search (field `url`).
   *                    Contoh: "melting-slowly-bahasa-indonesia"
   *                    Suffix "-bahasa-indonesia" akan ditambahkan otomatis jika belum ada.
   * @returns Array Chapter, diurutkan dari terbaru (index 0) ke terlama.
   */
  async getChapterList(titleSlug: string): Promise<Chapter[]> {
    if (!titleSlug) {
      throw new Error("Title slug tidak boleh kosong");
    }

    const slug = this.normalizeTitleSlug(titleSlug);

    try {
      const response = await this.client.get(`${this.baseUrl}/${slug}`);
      const pageProps = this.extractPageProps(response.data as string);

      if (!pageProps) {
        throw new Error("Struktur response tidak valid");
      }

      const chapterData = pageProps?.chapterData;
      if (!chapterData || !Array.isArray(chapterData.chapter)) {
        throw new Error("Data chapter tidak ditemukan");
      }

      const rawChapters: { chapter: string }[] = chapterData.chapter;
      const updatedAt: string | undefined = pageProps?.data?.updated_at;
      const baseTimestamp = updatedAt ? new Date(updatedAt).getTime() : 0;

      // Chapter diurutkan dari terbaru (index 0) ke terlama oleh website
      const chapters: Chapter[] = rawChapters.map((item, index) => {
        const chapterNum = String(item.chapter || "");
        return {
          name: `Chapter ${chapterNum}`,
          // Estimasi: chapter terbaru pakai updated_at, lama dikurangi per index
          dateUpload: Math.max(
            0,
            baseTimestamp - index * 7 * 24 * 60 * 60 * 1000
          ),
          url: `${slug}::${chapterNum}`, // format ID internal: "slug::chapterNum"
          chapterUrl: `${this.baseUrl}/${slug}/chapter/${chapterNum}`,
        };
      });

      return chapters;
    } catch (error: any) {
      if (error.response) {
        throw new Error(
          `Gagal mengambil chapter list: ${error.response.status} - ${
            error.response.data?.message || error.message
          }`
        );
      }
      throw new Error(`Gagal mengambil chapter list: ${error.message}`);
    }
  }

  /**
   * Ambil daftar halaman (gambar) dari sebuah chapter.
   * URL: https://softkomik.co/{titleSlug}/chapter/{chapterNum}
   *
   * @param chapterId - ID chapter dalam format "titleSlug::chapterNum".
   *                    Contoh: "melting-slowly-bahasa-indonesia::001"
   *                    Didapatkan dari field `url` pada hasil getChapterList().
   * @returns Array Page berisi index dan URL gambar lengkap (dengan CDN token)
   */
  async getPageList(chapterId: string): Promise<Page[]> {
    if (!chapterId) {
      throw new Error("Chapter ID tidak boleh kosong");
    }

    // Parse chapterId format "slug::chapterNum"
    const separatorIdx = chapterId.lastIndexOf("::");
    if (separatorIdx === -1) {
      throw new Error(
        'Format chapterId tidak valid. Harus berformat "titleSlug::chapterNum"'
      );
    }

    const titleSlug = chapterId.substring(0, separatorIdx);
    const chapterNum = chapterId.substring(separatorIdx + 2);

    if (!titleSlug || !chapterNum) {
      throw new Error("titleSlug dan chapterNum tidak boleh kosong");
    }

    const slug = this.normalizeTitleSlug(titleSlug);
    const formattedChapter = this.normalizeChapterNum(chapterNum);

    try {
      const url = `${this.baseUrl}/${slug}/chapter/${formattedChapter}`;
      const response = await this.client.get(url);
      const html = response.data as string;

      // Ambil imgList dari pageProps (dengan dekripsi _stk jika ada)
      const pageProps = this.extractPageProps(html);

      if (!pageProps) {
        throw new Error("Struktur response tidak valid");
      }

      const imgList: string[] = pageProps?.imgList || [];

      if (!Array.isArray(imgList) || imgList.length === 0) {
        throw new Error("Daftar gambar tidak ditemukan atau kosong");
      }

      // Ambil CDN token dari HTML (WAJIB untuk akses gambar)
      const cdnToken = this.extractCdnToken(html);

      // Filter gambar promo/hello yang bukan bagian dari chapter
      const filteredImgList = imgList.filter(
        (img) => !img.startsWith("img-file/00-hello/")
      );

      const pages: Page[] = filteredImgList.map(
        (imgPath: string, index: number) => ({
          index,
          imageUrl: this.buildImageUrl(imgPath, cdnToken || undefined),
        })
      );

      return pages;
    } catch (error: any) {
      if (error.response) {
        throw new Error(
          `Gagal mengambil page list: ${error.response.status} - ${
            error.response.data?.message || error.message
          }`
        );
      }
      throw new Error(`Gagal mengambil page list: ${error.message}`);
    }
  }

  /**
   * Download gambar dengan header yang sesuai untuk Softkomik CDN (psy1.komik.im)
   *
   * @param imageUrl - URL lengkap gambar (termasuk ?id= token)
   * @returns Buffer berisi data gambar
   */
  async downloadImage(imageUrl: string): Promise<Buffer> {
    const response = await axios.get(imageUrl, {
      headers: this.getImageHeaders(),
      responseType: "arraybuffer",
      timeout: 30000,
    });

    return response.data;
  }
}
