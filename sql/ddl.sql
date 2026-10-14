-- Dibangkitkan dari src/sikuli/tabel.py (SKEMA). Ganti sikuli.lk dengan catalog.schema Anda.
-- Notebook 00_Muat_Rules menjalankan DDL ini otomatis; file ini untuk referensi.

CREATE TABLE IF NOT EXISTS sikuli.lk.mapping_seksi (
  kode STRING,
  seksi STRING,
  entitas STRING,
  pola STRING,
  maks_halaman STRING
);

CREATE TABLE IF NOT EXISTS sikuli.lk.rules_akun (
  doc_type STRING,
  seksi STRING,
  kode_akun STRING,
  nama_akun STRING,
  sinonim STRING,
  deskripsi STRING
);

CREATE TABLE IF NOT EXISTS sikuli.lk.sheet_config (
  doc_type STRING,
  sheet STRING,
  seksi STRING,
  kolom_label STRING,
  kolom_nilai STRING,
  kolom_nilai_lalu STRING,
  baris_mulai STRING,
  baris_akhir STRING,
  skala STRING
);

CREATE TABLE IF NOT EXISTS sikuli.lk.mapping_akun_excel (
  doc_type STRING,
  sheet STRING,
  label_excel STRING,
  kode_akun STRING
);

CREATE TABLE IF NOT EXISTS sikuli.lk.daftar_entitas (
  entity_id STRING,
  nama_entitas STRING,
  doc_type STRING
);

CREATE TABLE IF NOT EXISTS sikuli.lk.pdf_parsed (
  path STRING,
  nama_file STRING,
  parsed VARIANT,
  parsed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sikuli.lk.teks_pdf (
  doc_id STRING,
  nama_file STRING,
  entity_key STRING,
  entity_id STRING,
  doc_type STRING,
  tahun STRING,
  halaman INT,
  seksi STRING,
  status_deteksi STRING,
  judul_cocok STRING,
  zona_atas STRING,
  teks STRING,
  processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sikuli.lk.lokasi_seksi (
  doc_id STRING,
  nama_file STRING,
  entity_key STRING,
  entity_id STRING,
  doc_type STRING,
  seksi STRING,
  halaman_mulai INT,
  halaman_akhir INT,
  judul_cocok STRING,
  processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sikuli.lk.angka_pdf (
  doc_id STRING,
  sumber_file STRING,
  entity_key STRING,
  entity_id STRING,
  doc_type STRING,
  tahun STRING,
  seksi STRING,
  kode_akun STRING,
  label_di_dokumen STRING,
  periode STRING,
  nilai DOUBLE,
  nilai_asli STRING,
  skala DOUBLE,
  halaman INT,
  processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sikuli.lk.angka_excel (
  sumber_file STRING,
  entity_key STRING,
  entity_id STRING,
  doc_type STRING,
  tahun STRING,
  sheet STRING,
  baris INT,
  seksi STRING,
  label_asli STRING,
  kode_akun STRING,
  cara_pemetaan STRING,
  periode STRING,
  nilai DOUBLE,
  nilai_asli STRING,
  skala DOUBLE,
  processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sikuli.lk.angka_combined (
  entity_key STRING,
  entity_id STRING,
  doc_type STRING,
  tahun STRING,
  kode_akun STRING,
  nama_akun STRING,
  periode STRING,
  seksi STRING,
  nilai_pdf DOUBLE,
  nilai_excel DOUBLE,
  skala_pdf DOUBLE,
  halaman_pdf INT,
  sumber_pdf STRING,
  sumber_excel STRING,
  label_pdf STRING,
  label_excel STRING,
  jumlah_baris_pdf INT,
  jumlah_baris_excel INT,
  status STRING,
  selisih DOUBLE,
  selisih_persen DOUBLE,
  indikasi STRING,
  processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sikuli.lk.result_komparasi (
  entity_key STRING,
  entity_id STRING,
  doc_type STRING,
  tahun STRING,
  kode_akun STRING,
  nama_akun STRING,
  periode STRING,
  seksi STRING,
  nilai_pdf DOUBLE,
  nilai_excel DOUBLE,
  skala_pdf DOUBLE,
  halaman_pdf INT,
  sumber_pdf STRING,
  sumber_excel STRING,
  label_pdf STRING,
  label_excel STRING,
  jumlah_baris_pdf INT,
  jumlah_baris_excel INT,
  status STRING,
  selisih DOUBLE,
  selisih_persen DOUBLE,
  indikasi STRING,
  catatan_ai STRING,
  run_id STRING,
  processed_at TIMESTAMP
);

