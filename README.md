# SIKULI: analisis laporan keuangan (parsing sampai komparasi)

Implementasi alur di deck *SIKULI: alur analisis laporan keuangan*, mulai dari **parse PDF** sampai
**B · Analisis_Komparasi** (PDF vs Excel). Jalan **tanpa Databricks**: sebagai web app (Render) untuk upload
file dan melihat hasil, atau lewat command line.

```
LK PDF ──► parse (pdfplumber) ─► deteksi entitas + seksi ─► ekstraksi akun per seksi ─► angka PDF ──┐
LK Excel ─► baca (openpyxl, sheet_config) ─► mapping label → kode_akun ─────────────► angka Excel ─┴─► komparasi ─► hasil_komparasi.xlsx
rules/ (kertas kerja): mapping_seksi, rules_akun, sheet_config, mapping_akun_excel, daftar_entitas
```

## Cara pakai

### Web app (Render)
1. Di Render: **New → Web Service** (bukan Static Site), pilih repo ini dan branch-nya. Atau **New → Blueprint**
   supaya isian diambil dari `render.yaml`.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn webapp.app:app --workers 1 --threads 4 --timeout 300 --bind 0.0.0.0:$PORT`
   - Environment variable **`APP_PASSWORD`**: wajib diisi supaya data LK tidak bisa dibuka publik
     (login: username bebas, password sesuai isian).
2. Buka URL Render → upload PDF dan Excel → **Jalankan analisis** → lihat hasil dan **Unduh hasil (.xlsx)**.
3. Setiap push ke GitHub, Render deploy ulang otomatis, dan GitHub Actions menjalankan tes.

### Command line
```bash
pip install -r requirements.txt
PYTHONPATH=src python -m sikuli.lokal --pdf folder_pdf --excel folder_excel --out hasil_komparasi.xlsx
```

Hasil `.xlsx` berisi sheet Ringkasan, Komparasi (status + catatan), Angka_PDF, Angka_Excel, Lokasi_Seksi, Peringatan.

### Batasan saat ini
- PDF harus punya lapisan teks; PDF hasil scan perlu OCR dulu.
- Ekstraksi akun PDF memakai pencocokan label baris dengan `nama_akun`/`sinonim` di `rules_akun.csv` (tanpa AI).
  Akun yang tidak ditemukan dicantumkan di Peringatan; tambahkan sinonimnya di rules.
- Catatan per baris dibuat otomatis dari status dan indikasi (`BEDA_TANDA`, `BEDA_SKALA`), bukan oleh LLM.

**Daftar file yang perlu Anda sediakan ada di [docs/FILE_YANG_PERLU_DISEDIAKAN.md](docs/FILE_YANG_PERLU_DISEDIAKAN.md).**

## Struktur repo

| Path | Isi |
|------|-----|
| `webapp/` | Web app Flask: upload, hasil, unduh .xlsx, lihat rules |
| `src/sikuli/lokal.py` | Pipeline lengkap tanpa Databricks + CLI + penulisan .xlsx |
| `render.yaml` | Konfigurasi deploy Render (Web Service) |
| `notebooks/00_Muat_Rules.py` | (opsional, Databricks) Stage 0: validasi rules dan simpan ke tabel Delta, buat tabel hasil |
| `notebooks/01_Ingest_PDF.py` | Parse PDF 1× per dokumen, deteksi seksi, ekstraksi akun |
| `notebooks/02_Ingest_Excel.py` | Baca Excel tanpa AI, mapping akun, daftar label belum terpetakan |
| `notebooks/03_Analisis_Komparasi.py` | Full outer join, status, catatan `ai_gen`, ringkasan untuk pengawas |
| `notebooks/99_Jalankan_Semua.py` | Menjalankan 00 → 01 → 02 → 03 berurutan |
| `src/sikuli/` | Logika inti Python murni (bisa diuji tanpa Databricks) |
| `rules/` | Kertas kerja: `mapping_seksi` (dari slide 6) dan **contoh** rules lain yang perlu diganti |
| `config/pipeline.yaml` | Catalog/schema, path Volume, pola nama file, toleransi komparasi |
| `sql/ddl.sql` | Definisi semua tabel (referensi) |
| `tests/` | Uji unit dan uji end-to-end lokal (AI Functions diganti tiruan) |

| Modul `src/sikuli/` | Langkah di deck |
|---------------------|-----------------|
| `pdf_lokal.py`, `ekstraksi_lokal.py` | Parse PDF dengan pdfplumber; ekstraksi akun dari baris teks tanpa AI |
| `parse_pdf.py` | Output `ai_parse_document` → teks per halaman + zona atas (footer dikecualikan) |
| `entitas.py` | Entitas dari prefiks nama file (+ `daftar_entitas`) |
| `seksi.py` | Deteksi seksi slide 5: daftar isi (≥3 cocok), mulai seksi baru, lanjutkan, `tidak_dikenal` |
| `ekstraksi.py` | Skema `ai_extract` dari `rules_akun`; angka disalin apa adanya lalu dikonversi deterministik |
| `normalisasi.py` | Angka format Indonesia `(1.234)`, `-`, skala "dalam jutaan Rupiah" |
| `excel.py`, `akun.py` | SHEET_CONFIG dan mapping label → `kode_akun` |
| `komparasi.py` | entity_key, full outer join, MATCH/DIFFERENT/PDF_ONLY/EXCEL_ONLY, prompt catatan |
| `tabel.py` | Skema tabel Delta (satu sumber untuk notebook dan DDL) |

## Opsional: menjalankan di Databricks

1. Hubungkan repo ini sebagai **Git folder** di workspace.
2. Sesuaikan `config/pipeline.yaml` (catalog, schema, `path_pdf`, `path_excel`, `pola_nama_file`).
3. Unggah PDF ke `path_pdf` dan Excel ke `path_excel` (Volume Unity Catalog).
4. Isi file di `rules/` (lihat dokumen file yang perlu disediakan).
5. Jalankan `notebooks/99_Jalankan_Semua` di Serverless (atau cluster DBR terbaru dengan AI Functions).
   - `01_Ingest_PDF` hanya mem-parse PDF baru dan hanya mengekstraksi dokumen yang belum ada di `angka_pdf`.
     Set widget `parse_ulang` / `ekstraksi_ulang` = `ya` untuk mengulang semuanya.
   - Deteksi seksi selalu dibangun ulang dari `pdf_parsed`, jadi perubahan `mapping_seksi` tidak perlu parse ulang.

## Uji lokal

```bash
pip install -r requirements.txt
python -m pytest
```

Uji end-to-end (`tests/test_end_to_end.py`) menjalankan dokumen tiruan 9 halaman (sampul, daftar isi, laporan
utama, CaLK) dan file Excel tiruan melalui kode yang sama dengan notebook, sampai status komparasi.
Bagian yang memanggil Spark dan AI Functions hanya bisa diuji di Databricks.

## Keputusan desain yang diterapkan (slide 13)

1. **Parse PDF cukup sekali**: hasil mentah di `pdf_parsed`, teks per halaman di `teks_pdf`.
2. **Satu cara deteksi entitas dan seksi**: prefiks nama file + judul zona atas lewat `mapping_seksi`.
3. **Excel dibaca tanpa AI**: SHEET_CONFIG + mapping akun.
4. **Tabel sementara tidak disimpan**: input AI memakai temp view.
5. **Rules dipisah per jenis** (`rules_akun`, `sheet_config`, ...) sehingga tidak saling menimpa.

Masih terbuka (perlu keputusan Anda): arti `maks_halaman`, MKBD, penanda akhir CaLK/lampiran, dan penanganan
halaman `tidak_dikenal` (saat ini ditandai dan dilewati; `ai_classify` belum dipakai).

Belum termasuk (tahap berikutnya): A · Kepatuhan, D · CaLK, C · Rasio, dan Kesimpulan & Rekomendasi.
Tabel `teks_pdf`, `lokasi_seksi`, dan `angka_combined` sudah disiapkan sebagai input notebook tersebut.

## Opsional: situs dokumentasi statis

`scripts/build_site.py` membangun situs statis ke `site/`: ringkasan, file yang perlu disediakan, tabel rules
(dengan unduhan CSV), dan hasil tes saat build. Pengaturan di Render (New → Static Site, pilih repo ini dan
branch yang dipakai):

| Isian | Nilai |
|-------|-------|
| Build Command | `pip install -r requirements.txt && python scripts/build_site.py` |
| Publish Directory | `site` |

Build gagal bila ada tes yang gagal, sehingga situs yang tampil selalu dari kode yang lulus tes.
Situs ini publik dan hanya memuat dokumentasi serta rules, tanpa data laporan keuangan.
