# File yang perlu disediakan

Daftar hal yang masih perlu dilengkapi atau dikonfirmasi agar hasil komparasi akurat untuk data OJK.

## A. Rules: satu file `rules/Extraction_Rules.xlsx`

Sudah disediakan (sheet **Master**, 182 akun untuk EPP, MI, RD, dan DES). Format kolom dan cara kerjanya ada di
README bagian "Rules". Yang masih perlu dari Anda:

- Konfirmasi entitas **DES** (akun utang berbasis bunga dan pendapatan non halal): file LK mana yang memakai
  akun ini? Saat ini akun DES hanya dipakai untuk file berawalan `DES_`.
- Penambahan alias di kolom `description` bila ada label PDF/Excel yang belum tercocokkan (lihat sheet
  Peringatan dan baris EXCEL_ONLY/PDF_ONLY di hasil).

Pengaturan tata letak dokumen (`config/mapping_seksi.csv`, `config/sheet_config.csv`) sudah disesuaikan dengan
template MI, RD, dan XBRL IDX (EPP) dan jarang perlu diubah.

## B. Konvensi dan contoh data

| No | Yang dibutuhkan | Untuk apa |
|----|-----------------|-----------|
| 6 | **Konvensi nama file** `JENIS_KODE_keterangan`, PDF dan Excel bernama sama (sudah diterapkan) | `entitas.pola_nama_file` di `config/pipeline.yaml` |
| 7 | **1–2 PDF LK per jenis entitas** (EPP, MI, RD) beserta Excel pasangannya | Kalibrasi deteksi seksi (jumlah baris zona atas) dan uji ekstraksi |
| 8 | Notebook lama `Analisis_Komparasi` dan ekspor tabel `extraction_rules` | Menyamakan kode akun dan kolom output dengan yang sudah dipakai |

File PDF/Excel diunggah ke `input/pdf/` dan `input/excel/`. Repo ini publik, jadi ubah menjadi private sebelum mengunggah LK asli.

## C. Bentuk output yang perlu disepakati

Output adalah file `hasil_komparasi.xlsx` (sheet Komparasi) dengan kolom utama:

| Kolom | Arti |
|-------|------|
| `entity_key`, `entity_id`, `doc_type`, `tahun` | identitas entitas (prefiks nama file + doc_type + tahun) |
| `seksi`, `kode_akun`, `nama_akun`, `periode` | akun yang dibandingkan; `periode` = `berjalan`/`lalu` |
| `satuan_pdf` | satuan penyajian PDF, mis. `jutaan Rupiah`; semua nilai di baris ini memakai satuan ini |
| `nilai_pdf` | angka PDF persis seperti tertulis (tidak dikalikan) |
| `nilai_excel` | angka Excel yang sudah **dibagi** sesuai satuan PDF, mis. 1.250.400.000 → 1.250,4 |
| `nilai_excel_asli` | angka Excel asli (Rupiah penuh) |
| `selisih`, `selisih_persen` | `nilai_pdf − nilai_excel` dalam satuan PDF, dan persentasenya terhadap Excel |
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
