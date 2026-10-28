import { Router } from "express";
import { SoftkomikController } from "../controllers/softkomik.controller";

const router = Router();
const softkomikController = new SoftkomikController();

/**
 * @route   GET /api/softkomik/search
 * @desc    Cari komik berdasarkan nama
 * @query   q - Kata kunci pencarian (wajib)
 * @example GET /api/softkomik/search?q=melting+slowly
 */
router.get("/search", softkomikController.searchManga);

/**
 * @route   GET /api/softkomik/chapter/pages
 * @desc    Ambil daftar halaman (gambar) dari sebuah chapter
 * @query   id - Chapter ID dalam format "titleSlug::chapterNum" (wajib)
 * @example GET /api/softkomik/chapter/pages?id=melting-slowly-bahasa-indonesia::001
 * @note    Harus didefinisikan SEBELUM /:titleSlug/chapters agar tidak konflik routing
 */
router.get("/chapter/pages", softkomikController.getPageList);

/**
 * @route   GET /api/softkomik/image
 * @desc    Proxy download gambar dari CDN Softkomik (psy1.komik.im)
 * @query   url - URL gambar lengkap termasuk ?id= token (wajib)
 * @example GET /api/softkomik/image?url=https://psy1.komik.im/img-file/.../softkomik-0.webp?id=TOKEN
 */
router.get("/image", softkomikController.downloadImage);

/**
 * @route   GET /api/softkomik/:titleSlug/chapters
 * @desc    Ambil daftar chapter dari sebuah komik
 * @param   titleSlug - Slug komik, contoh: "melting-slowly-bahasa-indonesia"
 * @example GET /api/softkomik/melting-slowly-bahasa-indonesia/chapters
 */
router.get("/:titleSlug/chapters", softkomikController.getChapterList);

export default router;
