# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Ingestion LK PDF
# MAGIC 1. **Parse PDF** dengan `ai_parse_document`, satu kali per dokumen → `pdf_parsed`
# MAGIC 2. **Entitas + seksi**: prefiks nama file, zona atas halaman, pola `mapping_seksi` → `teks_pdf`, `lokasi_seksi`
# MAGIC 3. **Ekstraksi akun**: `ai_extract` per seksi, skema dari `rules_akun` → `angka_pdf`
# MAGIC
# MAGIC Langkah 2 murah (tanpa AI) dan selalu dibangun ulang dari `pdf_parsed`, jadi perubahan pola seksi
# MAGIC tidak perlu parse ulang. Langkah 1 dan 3 inkremental kecuali widget diset `ya`.

# COMMAND ----------

# MAGIC %run ./_setup

# COMMAND ----------

dbutils.widgets.dropdown("parse_ulang", "tidak", ["tidak", "ya"], "Parse ulang semua PDF")
dbutils.widgets.dropdown("ekstraksi_ulang", "tidak", ["tidak", "ya"], "Ekstraksi ulang semua akun")
PARSE_ULANG = dbutils.widgets.get("parse_ulang") == "ya"
EKSTRAKSI_ULANG = dbutils.widgets.get("ekstraksi_ulang") == "ya"

# COMMAND ----------

# MAGIC %md ## 1. Parse PDF (ai_parse_document, 1× per dokumen)

# COMMAND ----------

(spark.read.format("binaryFile")
    .option("pathGlobFilter", "*.[pP][dD][fF]")
    .option("recursiveFileLookup", "true")
    .load(cfg["path_pdf"])
    .createOrReplaceTempView("_pdf_sumber"))

if PARSE_ULANG:
    spark.sql(f"DELETE FROM {T('pdf_parsed')}")

spark.sql(f"""
    INSERT INTO {T('pdf_parsed')}
    SELECT path,
           regexp_extract(path, '[^/]+$', 0) AS nama_file,
           ai_parse_document(content, map('version', '2.0')) AS parsed,
           current_timestamp() AS parsed_at
    FROM _pdf_sumber
    WHERE path NOT IN (SELECT path FROM {T('pdf_parsed')})
""")
display(spark.sql(f"SELECT count(*) AS jumlah_dokumen, max(parsed_at) AS terakhir FROM {T('pdf_parsed')}"))

# COMMAND ----------

# MAGIC %md ## 2. Entitas + deteksi seksi → teks_pdf, lokasi_seksi

# COMMAND ----------

pola = seksi.kompilasi_pola(rules.mapping_seksi)
teks_rows, lokasi_rows, peringatan = [], [], []
for r in spark.sql(f"SELECT path, to_json(parsed) AS j FROM {T('pdf_parsed')}").toLocalIterator():
    hasil = pipeline.proses_dokumen_pdf(r.path, r.j, cfg, rules, pola)
    teks_rows.extend(hasil["teks"])
    lokasi_rows.extend(hasil["lokasi"])
    peringatan.extend(hasil["peringatan"])

tabel.tulis(spark, teks_rows, T("teks_pdf"), "teks_pdf")
tabel.tulis(spark, lokasi_rows, T("lokasi_seksi"), "lokasi_seksi")
print(f"{len(teks_rows)} halaman, {len(lokasi_rows)} seksi")
print("\n".join(peringatan) or "Tidak ada peringatan")

# COMMAND ----------

# Ringkasan per dokumen: periksa dokumen yang seksinya tidak lengkap atau banyak halaman tidak_dikenal.
display(spark.sql(f"""
    SELECT nama_file, entity_key,
           concat_ws(', ', collect_set(CASE WHEN status_deteksi = 'judul' THEN seksi END)) AS seksi_ditemukan,
           count_if(status_deteksi = 'tidak_dikenal') AS halaman_tidak_dikenal,
           count_if(status_deteksi = 'daftar_isi') AS halaman_daftar_isi,
           count(*) AS jumlah_halaman
    FROM {T('teks_pdf')} GROUP BY nama_file, entity_key ORDER BY nama_file
"""))

# COMMAND ----------

# MAGIC %md ## 3. Ekstraksi akun (ai_extract per seksi, skema dari rules_akun) → angka_pdf

# COMMAND ----------

permintaan = pipeline.buat_permintaan_ekstraksi(teks_rows, cfg, rules)
if not EKSTRAKSI_ULANG:
    sudah = {r.doc_id for r in spark.sql(f"SELECT DISTINCT doc_id FROM {T('angka_pdf')}").collect()}
    permintaan = [p for p in permintaan if p["doc_id"] not in sudah]
print(f"{len(permintaan)} panggilan ai_extract untuk {len({p['doc_id'] for p in permintaan})} dokumen")

# Skema ai_extract harus berupa literal, jadi satu query per skema (per doc_type × seksi × kelompok akun).
versi = cfg["ekstraksi"]["ai_extract_version"]
hasil_ai = {}
per_skema = {}
for p in permintaan:
    per_skema.setdefault(p["skema"], []).append(p)
for skema_json, kelompok in per_skema.items():
    spark.createDataFrame([(p["id_permintaan"], p["teks"]) for p in kelompok],
                          "id_permintaan STRING, teks STRING").createOrReplaceTempView("_eks_input")
    for r in spark.sql(f"""
        SELECT id_permintaan,
               to_json(ai_extract(teks, {ekstraksi.sql_literal(skema_json)}, map('version', '{versi}'))) AS hasil
        FROM _eks_input
    """).collect():
        hasil_ai[r.id_permintaan] = r.hasil

angka_rows, peringatan_eks = [], []
for p in permintaan:
    baris, pesan = ekstraksi.parse_hasil_ekstraksi(
        hasil_ai.get(p["id_permintaan"]), p["akun"], pipeline.konteks_permintaan(p), p["zona_atas"])
    angka_rows.extend(baris)
    peringatan_eks.extend(f"{p['sumber_file']} / {p['seksi']}: {m}" for m in pesan)

tabel.tulis(spark, angka_rows, T("angka_pdf"), "angka_pdf",
            mode="overwrite" if EKSTRAKSI_ULANG else "append")
print(f"{len(angka_rows)} angka ditulis ke angka_pdf")
print("\n".join(peringatan_eks) or "Tidak ada peringatan")

# COMMAND ----------

display(spark.sql(f"""
    SELECT sumber_file, seksi, count(*) AS jumlah_angka, first(skala) AS skala
    FROM {T('angka_pdf')} GROUP BY sumber_file, seksi ORDER BY sumber_file, seksi
"""))
