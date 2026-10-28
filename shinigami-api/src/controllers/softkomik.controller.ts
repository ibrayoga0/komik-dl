import { Request, Response } from "express";
import { SoftkomikService } from "../services/softkomik.service";
import { ApiResponse } from "../types/manga.types";

export class SoftkomikController {
  private softkomikService: SoftkomikService;

  constructor() {
    this.softkomikService = new SoftkomikService();
  }

  /**
   * GET /api/softkomik/search?q={query}
   * Cari komik berdasarkan nama
   */
  searchManga = async (req: Request, res: Response): Promise<void> => {
    try {
      const query = req.query.q as string;

      if (!query || query.trim().length === 0) {
        const response: ApiResponse<null> = {
          success: false,
          error: 'Query parameter "q" wajib diisi',
        };
        res.status(400).json(response);
        return;
      }

      const result = await this.softkomikService.searchManga(query);

      const response: ApiResponse<typeof result> = {
        success: true,
        data: result,
      };

      res.status(200).json(response);
    } catch (error) {
      const response: ApiResponse<null> = {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
      res.status(500).json(response);
    }
  };

  /**
   * GET /api/softkomik/:titleSlug/chapters
   * Ambil daftar chapter dari sebuah komik
   *
   * :titleSlug = slug komik dari hasil search, contoh: "melting-slowly-bahasa-indonesia"
   */
  getChapterList = async (req: Request, res: Response): Promise<void> => {
    try {
      const { titleSlug } = req.params;

      if (!titleSlug) {
        const response: ApiResponse<null> = {
          success: false,
          error: "titleSlug wajib diisi",
        };
        res.status(400).json(response);
        return;
      }

      const result = await this.softkomikService.getChapterList(titleSlug);

      const response: ApiResponse<typeof result> = {
        success: true,
        data: result,
      };

      res.status(200).json(response);
    } catch (error) {
      const response: ApiResponse<null> = {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
      res.status(500).json(response);
    }
  };

  /**
   * GET /api/softkomik/chapter/pages?id={chapterId}
   * Ambil daftar halaman (gambar) dari sebuah chapter
   *
   * ?id = chapterId dalam format "titleSlug::chapterNum"
   * Contoh: "melting-slowly-bahasa-indonesia::001"
   */
  getPageList = async (req: Request, res: Response): Promise<void> => {
    try {
      const chapterId = req.query.id as string;

      if (!chapterId) {
        const response: ApiResponse<null> = {
          success: false,
          error:
            'Query parameter "id" wajib diisi. Format: "titleSlug::chapterNum"',
        };
        res.status(400).json(response);
        return;
      }

      const result = await this.softkomikService.getPageList(chapterId);

      const response: ApiResponse<typeof result> = {
        success: true,
        data: result,
      };

      res.status(200).json(response);
    } catch (error) {
      const response: ApiResponse<null> = {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
      res.status(500).json(response);
    }
  };

  /**
   * GET /api/softkomik/image?url={imageUrl}
   * Proxy download gambar dengan header yang sesuai untuk CDN Softkomik
   */
  downloadImage = async (req: Request, res: Response): Promise<void> => {
    try {
      const imageUrl = req.query.url as string;

      if (!imageUrl) {
        const response: ApiResponse<null> = {
          success: false,
          error: 'Query parameter "url" wajib diisi',
        };
        res.status(400).json(response);
        return;
      }

      const imageBuffer = await this.softkomikService.downloadImage(imageUrl);

      // Deteksi content type dari URL
      const isWebp = imageUrl.toLowerCase().includes(".webp");
      const contentType = isWebp ? "image/webp" : "image/jpeg";

      res.set("Content-Type", contentType);
      res.send(imageBuffer);
    } catch (error) {
      const response: ApiResponse<null> = {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
      res.status(500).json(response);
    }
  };
}
