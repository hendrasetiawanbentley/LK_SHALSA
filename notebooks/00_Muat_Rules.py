# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Muat rules (Stage 0, satu kali)
# MAGIC Kertas kerja di folder `rules/` divalidasi lalu disimpan sebagai tabel Delta terpisah per jenis rules
# MAGIC (`mapping_seksi`, `rules_akun`, `sheet_config`, `mapping_akun_excel`, `daftar_entitas`) supaya tidak saling
# MAGIC menimpa seperti `extraction_rules` lama (catatan desain no. 5). Jalankan ulang setiap kali rules diubah.

# COMMAND ----------

# MAGIC %run ./_setup

# COMMAND ----------

masalah = rules_mod.validasi_rules(rules)
if masalah:
    print("\n".join(masalah))
    raise ValueError(f"{len(masalah)} masalah di file rules, perbaiki dulu sebelum lanjut")
print("Rules valid:", {k: len(getattr(rules, k)) for k in rules_mod.KOLOM_WAJIB})

# COMMAND ----------

try:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {cfg['catalog']}")
except Exception as e:  # biasanya catalog dibuat admin; cukup pastikan sudah ada
    print(f"Lewati CREATE CATALOG ({type(e).__name__}); pastikan catalog '{cfg['catalog']}' sudah ada.")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {cfg['catalog']}.{cfg['schema']}")

for nama in rules_mod.KOLOM_WAJIB:
    tabel.tulis(spark, getattr(rules, nama), T(nama), nama)
    print(f"{T(nama)}: {len(getattr(rules, nama))} baris")

# Tabel hasil dibuat lebih awal supaya notebook berikutnya bisa berjalan inkremental.
for nama in ("pdf_parsed", "teks_pdf", "lokasi_seksi", "angka_pdf", "angka_excel",
             "angka_combined", "result_komparasi"):
    spark.sql(tabel.ddl(T(nama), nama))

# COMMAND ----------

display(spark.table(T("mapping_seksi")))
