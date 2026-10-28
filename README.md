# wmdl (Komik Downloader)

CLI tool berbasis Python untuk mencari dan mengunduh chapter komik/manhwa dari berbagai sumber (Shinigami, Softkomik, Komiku, MyNimeku, Komik Station, dan sumber lainnya di masa mendatang) langsung ke komputer tanpa memerlukan browser.

## Fitur

- **Pencarian Multi-Sumber (Unified Search)**: Cari judul komik secara serentak di semua sumber website dan pilih sumber yang diinginkan dari daftar hasil pencarian.
- **Arsitektur Modular Terstruktur (`wmdl/sources/`)**: Masing-masing source terisolasi dalam provider terpisah (`BaseSource`), memudahkan penambahan provider baru atau perbaikan di masa mendatang tanpa mengubah core engine.
- **Bypass Proteksi Otomatis (Cloudflare WAF)**: Otomatis mendeteksi dan menyelesaikan tantangan Cloudflare (Turnstile / IUAM) via modul bypasser terintegrasi agar pengambilan data tetap stabil.
- **Filter Khusus Anime/Komik**: Pada sumber hibrida seperti MyNimeku, hasil anime disaring otomatis sehingga hanya menyajikan komik/manga.
- **Ekstraksi Cepat & Otomatis**: Memanfaatkan API langsung, HTMX endpoint, dan SSR data (termasuk auto-decrypt payload `_stk` pada Softkomik).
- **Fleksibel**: Download single chapter, rentang chapter (`1-10` atau `1,3,5`), atau seluruh chapter sekaligus.
- **Resume & Skip**: Otomatis melewati gambar yang sudah berhasil diunduh sebelumnya.
- **Batal Bersih**: Pilihan `0` pada menu seleksi untuk membatalkan proses kapan saja tanpa error.

## Status Sumber (Supported Sources)

| Sumber | Website | Status |
| :--- | :--- | :---: |
| **Shinigami** | [app.shinigami.asia](https://app.shinigami.asia) | 🟢 Aktif |
| **Softkomik** | [softkomik.app](https://softkomik.app) / [softkomik.co](https://softkomik.co) | 🟢 Aktif |
| **Komiku** | [komiku.org](https://komiku.org) | 🟢 Aktif |
| **MyNimeku** | [mynimeku.com](https://www.mynimeku.com) | 🟢 Aktif |
| **Komik Station** | [komikstation.org](https://komikstation.org) | 🟢 Aktif |

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
  3. [Komiku] Solo Leveling (Ongoing)
  4. [Softkomik] Solo Leveling: Ragnarok (Ongoing)
  ...

Select comic (1-8, or 0 to cancel):
```
Pilih nomor komik yang diinginkan (atau masukkan `0` untuk batal), lalu pilih opsi download chapter.

### 2. Mode Langsung (CLI)

Anda bisa menggunakan flag `--chapter` atau `--chapters` secara bergantian untuk single maupun rentang chapter.

```bash
# Menggunakan URL komik (Komiku, MyNimeku, Komik Station, Softkomik, atau Shinigami)
py -m wmdl "https://komiku.org/manga/solo-leveling-id/" --chapter 1
py -m wmdl "https://www.mynimeku.com/komik/solo-leveling/" --chapter 1
py -m wmdl "https://komikstation.org/manga/solo-leveling-ragnarok/" --chapter 1
py -m wmdl "https://softkomik.app/melting-slowly-bahasa-indonesia" --chapter 0

# Menggunakan Judul Komik
py -m wmdl "Solo Leveling" --chapter 1
py -m wmdl "Melting Slowly" --chapter 0

# Download rentang chapter (range)
py -m wmdl "https://komiku.org/manga/solo-leveling-id/" --chapters 1-10

# Download chapter tertentu
py -m wmdl "Solo Leveling" --chapters 1,5,10

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
