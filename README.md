# wmdl (Komik Downloader)

CLI tool berbasis Python untuk mencari dan mengunduh chapter komik/manhwa dari berbagai sumber (Shinigami, Softkomik, dan sumber lainnya di masa mendatang) langsung ke komputer tanpa memerlukan browser.

## Fitur

- **Pencarian Multi-Sumber (Unified Search)**: Cari judul komik secara serentak di semua sumber website dan pilih sumber yang diinginkan dari daftar hasil pencarian.
- **Dukungan Berbagai Sumber**: Mendukung **Shinigami** serta **Softkomik** (`softkomik.app` & `softkomik.co`).
- **Ekstraksi Cepat & Otomatis**: Memanfaatkan API dan SSR data (termasuk auto-decrypt payload `_stk` pada Softkomik).
- **Tanpa Browser & API Key**: Berjalan ringan langsung melalui HTTP/asyncio tanpa headless browser ataupun setup akun.
- **Fleksibel**: Download single chapter, rentang chapter (`1-10` atau `1,3,5`), atau seluruh chapter sekaligus.
- **Resume & Skip**: Otomatis melewati gambar yang sudah berhasil diunduh sebelumnya.
- **Batal Bersih**: Pilihan `0` pada menu seleksi untuk membatalkan proses kapan saja tanpa error.

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
Masukkan URL komik, URL pencarian, ID, atau judul komik (contoh: `solo leveling` atau `melting slowly`). Hasil pencarian dari semua sumber akan ditampilkan dalam daftar bernomor:
```text
Multiple results found for 'solo leveling':
  1. [Shinigami] Solo Leveling (Ongoing)
  2. [Softkomik] Solo Leveling (Ongoing)
  3. [Shinigami] Solo Leveling : Ragnarok (Unknown)
  ...

Select comic (1-9, or 0 to cancel):
```
Pilih nomor komik yang diinginkan (atau masukkan `0` untuk batal), lalu pilih opsi download chapter.

### 2. Mode Langsung (CLI)

Anda bisa menggunakan flag `--chapter` atau `--chapters` secara bergantian untuk single maupun rentang chapter.

```bash
# Menggunakan URL komik (Softkomik atau Shinigami)
py -m wmdl https://softkomik.app/melting-slowly-bahasa-indonesia --chapter 0

# Menggunakan Judul Komik
py -m wmdl "Melting Slowly" --chapter 0

# Download rentang chapter (range)
py -m wmdl "Solo Leveling" --chapters 1-10

# Download chapter tertentu
py -m wmdl "Melting Slowly" --chapters 0,1,5

# Download semua chapter yang tersedia
py -m wmdl "Solo Leveling" --all
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
