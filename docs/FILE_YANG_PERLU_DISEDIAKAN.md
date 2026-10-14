# File yang perlu disediakan

Pipeline sudah berjalan memakai **rules contoh** di folder `rules/`. Supaya hasilnya benar untuk data
OJK, file di bawah perlu diganti atau dilengkapi. Semua rules berupa CSV UTF-8 dengan baris judul. Boleh
disusun di Excel lalu di-*Save As* CSV UTF-8. Kolom `aktif` (opsional, `1`/`0`) dipakai untuk
menonaktifkan baris tanpa menghapusnya. Setelah mengubah rules, jalankan ulang `00_Muat_Rules`.

## A. Rules (kertas kerja), letakkan di `rules/`

| No | File | Status | Isi |
|----|------|--------|-----|
| 1 | `rules_akun.csv` | **Wajib, paling penting** | Skema akun per jenis entitas dan seksi; dipakai ekstraksi PDF dan mapping Excel |
| 2 | `sheet_config.csv` | **Wajib** | Letak angka di LK Excel (SHEET_CONFIG) |
| 3 | `mapping_seksi.csv` | Sudah terisi dari deck (slide 6), **perlu dikonfirmasi** | Pola judul seksi |
| 4 | `daftar_entitas.csv` | Wajib bila jenis entitas tidak ada di nama file | Prefiks nama file → nama entitas dan doc_type |
| 5 | `mapping_akun_excel.csv` | Opsional | Label Excel yang tidak sama dengan nama/sinonim akun |

### 1. `rules_akun.csv`: skema akun (master rules komparasi)

Satu baris = satu akun yang ingin dibandingkan. Ini pengganti `extraction_rules` komparasi yang lama.

| Kolom | Wajib | Keterangan | Contoh |
|-------|-------|------------|--------|
| `doc_type` | ya | `EPP`, `MI`, `RD`, gabungan `EPP,MI`, atau `Semua` | `EPP,MI` |
| `seksi` | ya | kode seksi dari `mapping_seksi.csv` | `financial_position` |
| `kode_akun` | ya | kode unik per doc_type; kunci join PDF ↔ Excel | `FP_KAS` |
| `nama_akun` | ya | nama baris seperti di laporan | `Kas dan setara kas` |
| `sinonim` | tidak | nama lain dipisah `\|` (Inggris, label Excel, variasi penulisan) | `Kas dan bank\|Cash and cash equivalents` |
| `deskripsi` | tidak | petunjuk tambahan untuk AI | `Bisa negatif bila "digunakan untuk"` |

Yang saya butuhkan dari Anda: **daftar akun lengkap per EPP, MI, RD** beserta kode akun yang biasa dipakai
pengawas. Bila sudah ada di tabel `extraction_rules` atau kertas kerja Excel, kirim saja file/ekspornya dan
saya konversi ke format ini.

### 2. `sheet_config.csv`: letak angka di Excel

Satu baris = satu sheet yang dibaca.

| Kolom | Wajib | Keterangan | Contoh |
|-------|-------|------------|--------|
| `doc_type` | ya | jenis entitas pemilik format ini | `RD` |
| `sheet` | ya | nama sheet persis, atau regex diawali `re:` | `Posisi Keuangan` / `re:^42100\d+` |
| `seksi` | ya | kode seksi | `financial_position` |
| `kolom_label` | ya | huruf kolom label akun | `A` |
| `kolom_nilai` | ya | huruf kolom angka periode berjalan | `B` |
| `kolom_nilai_lalu` | tidak | huruf kolom angka tahun pembanding | `C` |
| `baris_mulai` | ya | baris pertama data | `5` |
| `baris_akhir` | tidak | baris terakhir (kosong = sampai habis) | |
| `skala` | tidak | pengali bila Excel dalam ribuan/jutaan (bawaan 1) | `1000` |

Yang saya butuhkan: **1–2 contoh file LK Excel per jenis entitas** (boleh disamarkan) supaya
`sheet_config` bisa saya isi tepat, termasuk bila formatnya XBRL IDX.

### 3. `mapping_seksi.csv`: pola judul seksi

Sudah berisi 7 seksi dan pola dari slide 6, satu baris per pola. Kolom: `no`, `kode`, `seksi`, `entitas`
(`Semua`/`RD`/...), `pola` (frasa biasa, atau regex bila mengandung karakter regex; dicocokkan pada teks yang
sudah huruf kecil tanpa tanda baca), `maks_halaman` (opsional).

Perlu konfirmasi dari Anda (keputusan terbuka di slide 13):
- **`maks_halaman`**: saya terapkan sebagai "jumlah halaman maksimum seksi dihitung dari halaman judul";
  halaman tanpa judul setelah batas itu menjadi `tidak_dikenal`. Kosong = tanpa batas. Mohon konfirmasi arti dari
  dict awal, beserta nilainya.
- **MKBD**: belum ada di 7 seksi. Bila perlu, cukup tambah baris, misalnya `8,mkbd,MKBD,MI,modal kerja bersih disesuaikan`.
- **Akhir CaLK / lampiran**: tambah seksi `lampiran` dengan pola judul lampiran supaya CaLK berhenti di sana.

### 4. `daftar_entitas.csv`

| Kolom | Wajib | Contoh |
|-------|-------|--------|
| `entity_id` | ya | `AAAA` (prefiks nama file) |
| `nama_entitas` | tidak | `PT Contoh Emiten Tbk` |
| `doc_type` | ya | `EPP` |

### 5. `mapping_akun_excel.csv` (opsional)

Kolom: `doc_type`, `sheet` (kosong = semua sheet), `label_excel`, `kode_akun`. Notebook `02_Ingest_Excel`
menampilkan label yang belum terpetakan; label itulah yang ditambahkan ke sini.

## B. Konvensi dan contoh data

| No | Yang dibutuhkan | Untuk apa |
|----|-----------------|-----------|
| 6 | **Konvensi nama file** PDF dan Excel, misalnya `AAAA_LK_2024.pdf` dan `AAAA_2024.xlsx` | Mengisi `entitas.pola_nama_file` di `config/pipeline.yaml`; prefiks yang sama memasangkan PDF dan Excel |
| 7 | **1–2 PDF LK per jenis entitas** (EPP, MI, RD) beserta Excel pasangannya | Kalibrasi deteksi seksi (jumlah baris zona atas) dan uji ekstraksi |
| 8 | Notebook lama `Analisis_Komparasi` dan ekspor tabel `extraction_rules` | Menyamakan kode akun dan kolom output dengan yang sudah dipakai |

File PDF/Excel diunggah ke `input/pdf/` dan `input/excel/`. Repo ini publik, jadi ubah menjadi private sebelum mengunggah LK asli.

## C. Bentuk output yang perlu disepakati

Output adalah file `hasil_komparasi.xlsx` (sheet Komparasi) dengan kolom utama:

| Kolom | Arti |
|-------|------|
| `entity_key`, `entity_id`, `doc_type`, `tahun` | identitas entitas (prefiks nama file + doc_type + tahun) |
| `seksi`, `kode_akun`, `nama_akun`, `periode` | akun yang dibandingkan; `periode` = `berjalan`/`lalu` |
| `nilai_pdf`, `nilai_excel` | nilai dalam Rupiah penuh (skala PDF "dalam jutaan" sudah dikalikan) |
| `selisih`, `selisih_persen` | `nilai_pdf - nilai_excel`, dan persentasenya terhadap Excel |
| `status` | `MATCH` / `DIFFERENT` / `PDF_ONLY` / `EXCEL_ONLY` |
| `indikasi` | petunjuk otomatis untuk DIFFERENT: `BEDA_TANDA`, `BEDA_SKALA` |
| `halaman_pdf`, `sumber_pdf`, `sumber_excel` | jejak sumber (`file.xlsx!sheet!baris`) |
| `label_pdf`, `label_excel` | nama baris persis di masing-masing sumber |
| `catatan` | catatan otomatis per status/indikasi, atau "Nilai sesuai" |

Mohon konfirmasi atau kirim contoh format yang diharapkan pengawas, terutama:
1. **Toleransi MATCH**: bawaan selisih ≤ Rp1, ditambah toleransi pembulatan setengah satuan bila PDF disajikan dalam
   ribuan/jutaan. Perlu toleransi persentase?
2. **Periode**: hanya tahun berjalan (bawaan), atau tahun pembanding juga?
3. **Tanda**: beban yang ditulis `(xxx)` di PDF tapi positif di Excel saat ini menjadi DIFFERENT dengan indikasi
   `BEDA_TANDA`. Apakah seharusnya dianggap MATCH?
4. Bila ada **template laporan** (Excel/PDF) yang biasa dibaca pengawas, kirim contohnya supaya kolom
   hasil disesuaikan dengan format itu.
