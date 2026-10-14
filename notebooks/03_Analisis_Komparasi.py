# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · B · Analisis_Komparasi
# MAGIC Membandingkan nilai akun PDF vs Excel per entitas:
# MAGIC 1. **Bentuk entity_key**: prefiks nama file + doc_type (+ tahun), digabung dengan kode_akun dan periode
# MAGIC 2. **Full outer join** PDF ↔ Excel → `angka_combined`
# MAGIC 3. **Tentukan status**: MATCH · DIFFERENT · PDF_ONLY · EXCEL_ONLY (deterministik, dengan toleransi di config)
# MAGIC 4. **ai_gen catatan** hanya untuk baris bukan MATCH; baris MATCH diberi catatan tetap → `result_komparasi`

# COMMAND ----------

# MAGIC %run ./_setup

# COMMAND ----------

import uuid

cfg_k = cfg["komparasi"]
angka_pdf = [r.asDict() for r in spark.table(T("angka_pdf")).collect()]
angka_excel = [r.asDict() for r in spark.table(T("angka_excel")).collect()]
nama_akun = {a["kode_akun"]: a["nama_akun"] for a in rules.rules_akun}

gabungan = komparasi.bandingkan(angka_pdf, angka_excel, cfg_k, nama_akun)
tabel.tulis(spark, gabungan, T("angka_combined"), "angka_combined")
print(f"{len(gabungan)} baris di angka_combined")

# COMMAND ----------

# MAGIC %md ## ai_gen catatan → result_komparasi

# COMMAND ----------

RUN_ID = str(uuid.uuid4())
perlu_catatan = [b for b in gabungan
                 if b["status"] != komparasi.MATCH or not cfg_k["ai_gen_hanya_non_match"]]
spark.createDataFrame(
    [(b["entity_key"], b["kode_akun"], b["periode"], komparasi.prompt_catatan(b)) for b in perlu_catatan],
    "entity_key STRING, kode_akun STRING, periode STRING, prompt_ai STRING",
).createOrReplaceTempView("_prompt_catatan")

kolom = ", ".join(f"c.{k}" for k, _ in tabel.SKEMA["angka_combined"] if k != "processed_at")
catatan_match = cfg_k["catatan_match"].replace("'", "\\'")
spark.sql(f"""
    CREATE OR REPLACE TABLE {T('result_komparasi')} AS
    WITH catatan AS (
        SELECT entity_key, kode_akun, periode, ai_gen(prompt_ai) AS catatan_ai FROM _prompt_catatan
    )
    SELECT {kolom},
           coalesce(n.catatan_ai, CASE WHEN c.status = 'MATCH' THEN '{catatan_match}' END) AS catatan_ai,
           '{RUN_ID}' AS run_id,
           current_timestamp() AS processed_at
    FROM {T('angka_combined')} c
    LEFT JOIN catatan n USING (entity_key, kode_akun, periode)
""")
print(f"result_komparasi ditulis, run_id {RUN_ID}, {len(perlu_catatan)} catatan AI")

# COMMAND ----------

# MAGIC %md ## Ringkasan untuk pengawas

# COMMAND ----------

display(spark.sql(f"""
    SELECT entity_key, doc_type,
           count_if(status = 'MATCH') AS match,
           count_if(status = 'DIFFERENT') AS different,
           count_if(status = 'PDF_ONLY') AS pdf_only,
           count_if(status = 'EXCEL_ONLY') AS excel_only,
           round(100 * count_if(status = 'MATCH') / count(*), 1) AS persen_match
    FROM {T('result_komparasi')} GROUP BY entity_key, doc_type ORDER BY persen_match
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT entity_key, seksi, kode_akun, nama_akun, periode, nilai_pdf, nilai_excel, selisih,
           selisih_persen, indikasi, halaman_pdf, sumber_excel, catatan_ai
    FROM {T('result_komparasi')}
    WHERE status = 'DIFFERENT'
    ORDER BY abs(selisih) DESC
"""))
