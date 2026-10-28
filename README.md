# wmdl (Manga Downloader)

Download manga/manhwa dari **Shinigami.id** dan **Softkomik.co** via Python CLI langsung (cepat & tanpa browser).

## Features

✨ **Fitur Utama**:
- **MULTI-SOURCE**: Mendukung **Shinigami.id** & **Softkomik.co**
- **NO BROWSER NEEDED**: Ekstraksi langsung via API / SSR data (cepat & ringan)
- **TANPA API KEY**: Mengunduh langsung dari web sumber tanpa perlu akun atau API key
- Download single chapter atau batch chapters
- Auto-detect available chapters (termasuk Chapter 0, 000, dst.)
- Retry mechanism untuk download yang gagal
- Resume capability (skip file yang sudah ada)

## Installation

1. Pastikan sudah install Python 3.8+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Interactive Mode (Paling Mudah)
Jalankan tanpa argumen untuk masuk ke mode interaktif:
```bash
py -m wmdl
```
Kemudian masukkan URL manga atau Judul (contoh: `melting slowly` atau `solo-leveling`) dan ikuti petunjuk di layar.

### 2. Direct Mode (CLI)

#### 🔹 Softkomik.co
**Download Single Chapter (URL atau Judul):**
```bash
# Menggunakan URL komik
py -m wmdl https://softkomik.co/melting-slowly-bahasa-indonesia --chapter 0

# Menggunakan Judul
py -m wmdl "Melting Slowly" --chapter 0
```

**Download Chapter Range:**
```bash
# Download chapter 0 sampai 5
py -m wmdl "Melting Slowly" --chapters 0-5

# Download chapter tertentu
py -m wmdl "Melting Slowly" --chapters 0,1,5
```

**Download Semua Chapter:**
```bash
py -m wmdl "Melting Slowly" --all
```

---

#### 🔹 Shinigami.id
**Download Single Chapter:**
```bash
# Menggunakan URL
py -m wmdl https://app.shinigami.asia/series/solo-leveling --chapter 1

# Menggunakan ID / Slug
py -m wmdl solo-leveling --chapter 1
```

**Download Chapter Range:**
```bash
py -m wmdl solo-leveling --chapters 1-10
```

---

## ℹ️ Mengenai folder `shinigami-api` & API Key

Di dalam repositori ini terdapat dua bagian berbeda:
1. **`wmdl/` (Python CLI - Yang Anda gunakan)**:
   - Dijalankan langsung dengan perintah `py -m wmdl ...`.
   - **TIDAK memerlukan API key** sama sekali untuk mendownload dari Softkomik maupun Shinigami.
2. **`shinigami-api/` (Node.js Express REST API server)**:
   - Server REST API terpisah jika Anda ingin menyediakan layanan API untuk aplikasi web/mobile.
   - Endpoint di server ini diamankan dengan header `x-api-key`. Kunci default telah disiapkan di `shinigami-api/.env` (`API_KEY=your_secret_api_key`).
   - Jika Anda hanya ingin mendownload komik ke komputer lokal, Anda **cukup menggunakan Python `wmdl`** tanpa perlu menjalankan server tersebut.


## Structure

File akan didownload ke folder `downloads/` dengan struktur:
```
downloads/
└── {manga-id}/
    ├── chapter-1/
    │   ├── 01.jpg
    │   ├── 02.jpg
    │   └── ...
    └── chapter-2/
        └── ...
```

## Troubleshooting

- **Error: 403 Forbidden / Anti-bot**: Script ini sudah menggunakan headers khusus untuk bypass proteksi dasar. Jika masih gagal, coba tunggu beberapa saat sebelum mencoba lagi.
- **Connection Error**: Cek koneksi internet anda. Script akan mencoba 3x (retry) sebelum menyerah.
