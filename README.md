# wmdl

CLI tool berbasis Python untuk mencari dan mengunduh chapter manga/manhwa dari **Shinigami.id** dan **Softkomik.co** langsung ke komputer tanpa memerlukan browser.

## Fitur

- Mendukung dua sumber: **Shinigami.id** dan **Softkomik.co**.
- Ekstraksi langsung via API dan SSR data (termasuk auto-decrypt payload `_stk` Softkomik).
- Tanpa browser dan tanpa akun atau API key.
- Pilihan download: single chapter, rentang chapter (range), atau seluruh chapter sekaligus.
- Resume capability: otomatis lewati (skip) gambar yang sudah berhasil diunduh sebelumnya.
- Retry otomatis jika koneksi gagal atau timeout.

## Instalasi

1. Pastikan Python 3.8 atau lebih baru sudah terpasang.
2. Pasang dependensi yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```

## Penggunaan

### 1. Mode Interaktif

Jalankan perintah berikut di terminal:
```bash
py -m wmdl
```
Masukkan URL komik atau judul pencarian (contoh: `melting slowly` atau `solo-leveling`), lalu pilih nomor komik dan opsi chapter yang ingin diunduh.

### 2. Mode Langsung (CLI)

Anda bisa menggunakan flag `--chapter` atau `--chapters` secara bergantian untuk single maupun rentang chapter.

#### Softkomik.co

```bash
# Menggunakan URL komik
py -m wmdl https://softkomik.co/melting-slowly-bahasa-indonesia --chapter 0

# Menggunakan Judul
py -m wmdl "Melting Slowly" --chapter 0

# Download rentang chapter (range)
py -m wmdl "Melting Slowly" --chapter 0-5
py -m wmdl "Melting Slowly" --chapters 0,1,5

# Download semua chapter yang tersedia
py -m wmdl "Melting Slowly" --all
```

#### Shinigami.id

```bash
# Menggunakan URL komik
py -m wmdl https://app.shinigami.asia/series/solo-leveling --chapter 1

# Menggunakan ID / Slug
py -m wmdl solo-leveling --chapter 1

# Download rentang chapter
py -m wmdl solo-leveling --chapters 1-10

# Download semua chapter
py -m wmdl solo-leveling --all
```

## Struktur Hasil Unduhan

Gambar yang diunduh akan otomatis tersimpan rapi di folder `downloads/`:
```text
downloads/
└── {Judul Komik}/
    ├── chapter-1/
    │   ├── 01.webp
    │   ├── 02.webp
    │   └── ...
    └── chapter-2/
        └── ...
```

## Catatan & Troubleshooting

- **Proteksi Anti-bot / 403 Forbidden**: Script sudah menyertakan header dan referer yang disesuaikan untuk masing-masing domain CDN.
- **Koneksi Timeout**: Script otomatis mencoba kembali hingga 3 kali (retry mechanism) sebelum menandai gambar gagal.
