# SIKULI: komparasi laporan keuangan PDF vs Excel

Implementasi alur di deck *SIKULI: alur analisis laporan keuangan*, mulai dari **parse PDF** sampai
**B · Analisis_Komparasi**. Analisis dijalankan oleh **GitHub Actions**, tanpa aplikasi front end.

```
input/pdf/*.pdf   ─► parse (pdfplumber) ─► deteksi entitas + seksi ─► ekstraksi akun per seksi ─► angka PDF ──┐
input/excel/*.xlsx ─► baca sheet (sheet_config) ─► mapping label → kode_akun ──────────────────► angka Excel ─┴─► komparasi ─► hasil/
rules/*.csv (kertas kerja) dipakai di setiap langkah
```

## Cara menjalankan di GitHub

1. **Isi rules** di folder `rules/` (lihat tabel di bawah), commit dan push.
2. **Upload file LK** ke repo:
   - PDF ke `input/pdf/`, misalnya `AAAA_LK_2024.pdf`
   - Excel ke `input/excel/`, misalnya `AAAA_2024.xlsx`

   Lewat web GitHub: buka folder → **Add file → Upload files** → **Commit changes**. PDF dan Excel dipasangkan
   dari prefiks nama file (`AAAA`), dan tahun dari angka 4 digit di nama file.
3. **Workflow `analisis` jalan otomatis** setiap ada perubahan di `input/`, `rules/`, atau `config/`.
   Untuk menjalankan ulang manual: tab **Actions → analisis → Run workflow**.
4. **Lihat hasil:** tab **Actions** → klik run teratas.
   - Halaman run menampilkan ringkasan per entitas, daftar akun yang perlu ditinjau, dan peringatan.
   - Bagian **Artifacts** di bawah halaman run berisi `hasil-komparasi` (zip): `hasil_komparasi.xlsx` + CSV.
     Artifact disimpan 30 hari.

Menjalankan di komputer sendiri (opsional):
```bash
pip install -r requirements.txt
PYTHONPATH=src python -m sikuli.lokal          # baca input/pdf dan input/excel, tulis ke hasil/
```

> **Repo ini publik.** File di `input/` dan artifact hasil bisa dilihat orang lain. Ubah repo menjadi
> private (Settings → General → Danger Zone → Change visibility) sebelum mengunggah LK asli.

## Tabel rules yang harus diisi

Semua file CSV UTF-8 di `rules/` dengan baris judul (bisa disusun di Excel lalu *Save As → CSV UTF-8*).
Kolom `aktif` opsional (`1`/`0`) untuk menonaktifkan baris. Isi sekarang adalah **contoh**, kecuali
`mapping_seksi.csv` yang diambil dari slide 6. Jika rules tidak valid, workflow gagal dan menyebut baris yang salah.

### 1. `rules_akun.csv` (wajib): akun yang dibandingkan

| Kolom | Wajib | Isi | Contoh |
|-------|:-----:|-----|--------|
| `doc_type` | ya | `EPP`, `MI`, `RD`, gabungan `EPP,MI`, atau `Semua` | `EPP,MI` |
| `seksi` | ya | kode seksi dari `mapping_seksi.csv` | `financial_position` |
| `kode_akun` | ya | kode unik per doc_type; kunci pasangan PDF ↔ Excel | `FP_KAS` |
| `nama_akun` | ya | nama baris seperti tertulis di laporan | `Kas dan setara kas` |
| `sinonim` | | nama lain dipisah `\|` (Inggris, label Excel, variasi) | `Kas dan bank\|Cash and cash equivalents` |
| `deskripsi` | | catatan bebas | |

Baris PDF dicocokkan dengan `nama_akun`/`sinonim` (huruf besar-kecil dan tanda baca diabaikan). Akun yang
tidak ketemu di PDF tercantum di Peringatan; tambahkan sinonimnya di sini.

### 2. `sheet_config.csv` (wajib): letak angka di Excel

| Kolom | Wajib | Isi | Contoh |
|-------|:-----:|-----|--------|
| `doc_type` | ya | jenis entitas pemilik format | `EPP,MI` |
| `sheet` | ya | nama sheet, atau regex diawali `re:` | `Posisi Keuangan` |
| `seksi` | ya | kode seksi | `financial_position` |
| `kolom_label` | ya | huruf kolom nama akun | `A` |
| `kolom_nilai` | ya | huruf kolom tahun berjalan | `B` |
| `kolom_nilai_lalu` | | huruf kolom tahun pembanding | `C` |
| `baris_mulai` | ya | baris pertama data | `5` |
| `baris_akhir` | | baris terakhir (kosong = sampai habis) | |
| `skala` | | pengali bila Excel dalam ribuan/jutaan (bawaan 1) | `1000` |

### 3. `mapping_seksi.csv` (sudah terisi): pola judul laporan

| Kolom | Wajib | Isi | Contoh |
|-------|:-----:|-----|--------|
| `no` | | nomor urut seksi | `1` |
| `kode` | ya | kode seksi | `financial_position` |
| `seksi` | ya | nama seksi | `Laporan Posisi Keuangan` |
| `entitas` | ya | `Semua` atau jenis entitas tertentu | `RD` |
| `pola` | ya | satu frasa judul per baris | `statement of financial position` |
| `maks_halaman` | | batas halaman seksi sejak judul (kosong = tanpa batas) | |

Seksi dikenali dari baris teratas halaman: halaman dengan ≥3 judul cocok dianggap daftar isi, halaman tanpa
judul ikut seksi sebelumnya. Untuk MKBD atau penanda akhir CaLK (lampiran), cukup tambah baris.

### 4. `daftar_entitas.csv` (wajib bila jenis entitas tidak ada di nama file)

| Kolom | Wajib | Isi | Contoh |
|-------|:-----:|-----|--------|
| `entity_id` | ya | prefiks nama file | `AAAA` |
| `nama_entitas` | | nama lengkap | `PT Contoh Emiten Tbk` |
| `doc_type` | ya | `EPP` / `MI` / `RD` | `EPP` |

### 5. `mapping_akun_excel.csv` (opsional): label Excel yang tidak sama dengan nama/sinonim

| Kolom | Wajib | Isi | Contoh |
|-------|:-----:|-----|--------|
| `doc_type` | ya | jenis entitas | `EPP,MI` |
| `sheet` | | nama sheet (kosong = semua) | `Posisi Keuangan` |
| `label_excel` | ya | label persis di Excel | `Kas dan setara kas - bersih` |
| `kode_akun` | ya | kode di `rules_akun.csv` | `FP_KAS` |

Pengaturan lain (pola nama file, toleransi selisih, periode yang dibandingkan) ada di `config/pipeline.yaml`.

## Struktur hasil

Artifact `hasil-komparasi` berisi `hasil_komparasi.xlsx` (satu sheet per tabel di bawah), CSV dengan isi sama,
dan `ringkasan.md`.

**Komparasi** (`komparasi.csv`): satu baris per entitas × akun × periode, urut dari yang perlu ditinjau.

| Kolom | Arti |
|-------|------|
| `entity_key` | prefiks nama file \| doc_type \| tahun, mis. `AAAA\|EPP\|2024` |
| `seksi`, `kode_akun`, `nama_akun`, `periode` | akun yang dibandingkan; `periode` = `berjalan` / `lalu` |
| `satuan_pdf` | satuan penyajian PDF, mis. `jutaan Rupiah`; semua nilai di baris ini memakai satuan ini |
| `nilai_pdf` | angka PDF persis seperti tertulis (tidak dikalikan) |
| `nilai_excel` | angka Excel yang sudah **dibagi** sesuai satuan PDF, mis. 1.250.400.000 → 1.250,4 |
| `nilai_excel_asli` | angka Excel asli (Rupiah penuh) |
| `selisih`, `selisih_persen` | `nilai_pdf − nilai_excel` dalam satuan PDF, dan persentasenya terhadap Excel |
| `status` | `MATCH` (sama dalam toleransi), `DIFFERENT`, `PDF_ONLY`, `EXCEL_ONLY` |
| `indikasi` | petunjuk penyebab DIFFERENT: `BEDA_TANDA`, `BEDA_SKALA` |
| `catatan` | penjelasan otomatis per status |
| `halaman_pdf`, `sumber_pdf`, `sumber_excel` | jejak sumber; Excel ditulis `file.xlsx!sheet!baris` |
| `label_pdf`, `label_excel` | nama baris persis di masing-masing sumber |

**Ringkasan** (`ringkasan.csv`): per `entity_key`, jumlah baris tiap status dan `persen_match`.

**Angka_PDF** (`angka_pdf.csv`): angka yang terbaca dari PDF: `sumber_file`, `entity_key`, `seksi`,
`kode_akun`, `label_di_dokumen`, `periode`, `nilai` (seperti tertulis, tidak dikalikan), `nilai_asli`, `skala` (satuan yang terdeteksi), `halaman`.

**Angka_Excel** (`angka_excel.csv`): angka dari Excel: `sumber_file`, `entity_key`, `sheet`, `baris`,
`seksi`, `label_asli`, `kode_akun` (kosong = label belum terpetakan), `cara_pemetaan`, `periode`, `nilai`,
`nilai_asli`.

**Lokasi_Seksi** (`lokasi_seksi.csv`): seksi per dokumen: `nama_file`, `entity_key`, `seksi`,
`halaman_mulai`, `halaman_akhir`, `judul_cocok`.

**Peringatan** (`peringatan.csv`): akun tidak ditemukan, sheet tidak ada, nama file tidak dikenali, PDF tanpa teks.

## Batasan

- PDF harus punya lapisan teks; PDF hasil scan perlu OCR dulu.
- Ekstraksi PDF berbasis baris teks: label akun yang terpotong ke dua baris belum terbaca.
- Batas ukuran file GitHub 100 MB per file.

## Struktur repo

| Path | Isi |
|------|-----|
| `.github/workflows/analisis.yml` | Menjalankan analisis dan menyimpan hasil sebagai artifact |
| `.github/workflows/tests.yml` | Menjalankan tes setiap push |
| `input/` | Tempat upload LK PDF dan Excel |
| `rules/` | Kertas kerja (tabel rules di atas) |
| `config/pipeline.yaml` | Pola nama file, deteksi seksi, toleransi komparasi |
| `src/sikuli/` | Kode pipeline (`lokal.py` = titik masuk) |
| `tests/` | Tes unit dan end-to-end dengan PDF/Excel contoh |
| `notebooks/`, `sql/` | Versi Databricks dari alur yang sama (opsional, tidak dipakai workflow) |
