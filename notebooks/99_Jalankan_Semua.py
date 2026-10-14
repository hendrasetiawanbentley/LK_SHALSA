# Databricks notebook source
# MAGIC %md
# MAGIC # 99 · Jalankan semua (parsing sampai komparasi)
# MAGIC Urutan: 00 rules → 01 PDF dan 02 Excel → 03 komparasi. Untuk penjadwalan, notebook ini bisa
# MAGIC dijadikan satu task Databricks Job, atau tiap notebook dijadikan task terpisah dengan urutan yang sama.

# COMMAND ----------

dbutils.widgets.dropdown("parse_ulang", "tidak", ["tidak", "ya"], "Parse ulang semua PDF")
dbutils.widgets.dropdown("ekstraksi_ulang", "tidak", ["tidak", "ya"], "Ekstraksi ulang semua akun")
param = {k: dbutils.widgets.get(k) for k in ("parse_ulang", "ekstraksi_ulang")}

for nama, argumen in [("./00_Muat_Rules", {}), ("./01_Ingest_PDF", param),
                      ("./02_Ingest_Excel", {}), ("./03_Analisis_Komparasi", {})]:
    print(f"Menjalankan {nama} ...")
    dbutils.notebook.run(nama, 0, argumen)
print("Selesai")
