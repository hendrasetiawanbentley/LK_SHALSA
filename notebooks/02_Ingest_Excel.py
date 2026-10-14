# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Ingestion LK Excel (tanpa AI)
# MAGIC Angka di Excel sudah terstruktur: sheet dibaca sesuai `sheet_config`, label baris dipetakan ke
# MAGIC `kode_akun` lewat `mapping_akun_excel` lalu nama/sinonim di `rules_akun` → `angka_excel`.
# MAGIC Label yang belum terpetakan tetap disimpan (kode_akun NULL) dan ditampilkan di akhir notebook.

# COMMAND ----------

# MAGIC %run ./_setup

# COMMAND ----------

pemeta = akun.PemetaAkun(rules)
angka_rows, peringatan, jumlah_file = [], [], 0
for folder, _, files in os.walk(cfg["path_excel"]):
    for nama in sorted(files):
        if not nama.lower().endswith((".xlsx", ".xlsm")) or nama.startswith("~$"):
            continue
        jumlah_file += 1
        path = os.path.join(folder, nama)
        info = entitas.info_dari_nama_file(path, cfg, rules)
        if not info["entitas_dikenal"]:
            peringatan.append(f"{nama}: entity_id/doc_type tidak dikenali dari nama file, dilewati")
            continue
        try:
            baris, pesan = excel.baca_excel(path, info, rules, pemeta)
        except Exception as e:  # file rusak / terkunci password: catat dan lanjut
            peringatan.append(f"{nama}: gagal dibaca ({type(e).__name__}: {e})")
            continue
        angka_rows.extend(baris)
        peringatan.extend(pesan)

tabel.tulis(spark, angka_rows, T("angka_excel"), "angka_excel")
print(f"{jumlah_file} file Excel, {len(angka_rows)} angka ditulis ke angka_excel")
print("\n".join(peringatan) or "Tidak ada peringatan")

# COMMAND ----------

# MAGIC %md ### Label yang belum terpetakan
# MAGIC Tambahkan label di bawah ke `rules/mapping_akun_excel.csv` (atau sebagai sinonim di `rules_akun.csv`),
# MAGIC lalu jalankan ulang `00_Muat_Rules` dan notebook ini.

# COMMAND ----------

display(spark.sql(f"""
    SELECT doc_type, sheet, seksi, label_asli, cara_pemetaan, count(DISTINCT sumber_file) AS jumlah_file
    FROM {T('angka_excel')}
    WHERE kode_akun IS NULL
    GROUP BY ALL ORDER BY jumlah_file DESC, doc_type, sheet
"""))
