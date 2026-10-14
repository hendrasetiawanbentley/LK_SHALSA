"""Skema tabel Delta (satu sumber untuk notebook dan sql/ddl.sql) + helper Spark.

Fungsi Spark mengimpor pyspark secara malas supaya modul ini tetap bisa
diimpor saat uji lokal tanpa Spark.
"""

from __future__ import annotations

from datetime import datetime, timezone

SKEMA: dict[str, list[tuple[str, str]]] = {
    # ---- Stage 0: rules ----
    "mapping_seksi": [("kode", "STRING"), ("seksi", "STRING"), ("entitas", "STRING"),
                      ("pola", "STRING"), ("maks_halaman", "STRING")],
    "rules_akun": [("doc_type", "STRING"), ("seksi", "STRING"), ("kode_akun", "STRING"),
                   ("nama_akun", "STRING"), ("sinonim", "STRING"), ("deskripsi", "STRING")],
    "sheet_config": [("doc_type", "STRING"), ("sheet", "STRING"), ("seksi", "STRING"),
                     ("kolom_label", "STRING"), ("kolom_nilai", "STRING"),
                     ("kolom_nilai_lalu", "STRING"), ("baris_mulai", "STRING"),
                     ("baris_akhir", "STRING"), ("skala", "STRING")],
    "mapping_akun_excel": [("doc_type", "STRING"), ("sheet", "STRING"),
                           ("label_excel", "STRING"), ("kode_akun", "STRING")],
    "daftar_entitas": [("entity_id", "STRING"), ("nama_entitas", "STRING"), ("doc_type", "STRING")],
    # ---- Ingestion PDF ----
    "pdf_parsed": [("path", "STRING"), ("nama_file", "STRING"), ("parsed", "VARIANT"),
                   ("parsed_at", "TIMESTAMP")],
    "teks_pdf": [("doc_id", "STRING"), ("nama_file", "STRING"), ("entity_key", "STRING"),
                 ("entity_id", "STRING"), ("doc_type", "STRING"), ("tahun", "STRING"),
                 ("halaman", "INT"), ("seksi", "STRING"), ("status_deteksi", "STRING"),
                 ("judul_cocok", "STRING"), ("zona_atas", "STRING"), ("teks", "STRING"),
                 ("processed_at", "TIMESTAMP")],
    "lokasi_seksi": [("doc_id", "STRING"), ("nama_file", "STRING"), ("entity_key", "STRING"),
                     ("entity_id", "STRING"), ("doc_type", "STRING"), ("seksi", "STRING"),
                     ("halaman_mulai", "INT"), ("halaman_akhir", "INT"),
                     ("judul_cocok", "STRING"), ("processed_at", "TIMESTAMP")],
    "angka_pdf": [("doc_id", "STRING"), ("sumber_file", "STRING"), ("entity_key", "STRING"),
                  ("entity_id", "STRING"), ("doc_type", "STRING"), ("tahun", "STRING"),
                  ("seksi", "STRING"), ("kode_akun", "STRING"), ("label_di_dokumen", "STRING"),
                  ("periode", "STRING"), ("nilai", "DOUBLE"), ("nilai_asli", "STRING"),
                  ("skala", "DOUBLE"), ("halaman", "INT"), ("processed_at", "TIMESTAMP")],
    # ---- Ingestion Excel ----
    "angka_excel": [("sumber_file", "STRING"), ("entity_key", "STRING"), ("entity_id", "STRING"),
                    ("doc_type", "STRING"), ("tahun", "STRING"), ("sheet", "STRING"),
                    ("baris", "INT"), ("seksi", "STRING"), ("label_asli", "STRING"),
                    ("kode_akun", "STRING"), ("cara_pemetaan", "STRING"), ("periode", "STRING"),
                    ("nilai", "DOUBLE"), ("nilai_asli", "STRING"), ("skala", "DOUBLE"),
                    ("processed_at", "TIMESTAMP")],
    # ---- B · Komparasi ----
    "angka_combined": [("entity_key", "STRING"), ("entity_id", "STRING"), ("doc_type", "STRING"),
                       ("tahun", "STRING"), ("kode_akun", "STRING"), ("nama_akun", "STRING"),
                       ("periode", "STRING"), ("seksi", "STRING"), ("satuan_pdf", "STRING"),
                       ("nilai_pdf", "DOUBLE"), ("nilai_excel", "DOUBLE"),
                       ("nilai_excel_asli", "DOUBLE"), ("skala_pdf", "DOUBLE"), ("halaman_pdf", "INT"),
                       ("sumber_pdf", "STRING"), ("sumber_excel", "STRING"), ("label_pdf", "STRING"),
                       ("label_excel", "STRING"), ("jumlah_baris_pdf", "INT"),
                       ("jumlah_baris_excel", "INT"), ("status", "STRING"), ("selisih", "DOUBLE"),
                       ("selisih_persen", "DOUBLE"), ("indikasi", "STRING"),
                       ("processed_at", "TIMESTAMP")],
}
SKEMA["result_komparasi"] = SKEMA["angka_combined"][:-1] + [
    ("catatan_ai", "STRING"), ("run_id", "STRING"), ("processed_at", "TIMESTAMP")]


def ddl(nama_lengkap: str, tabel: str) -> str:
    kolom = ",\n  ".join(f"{k} {t}" for k, t in SKEMA[tabel])
    return f"CREATE TABLE IF NOT EXISTS {nama_lengkap} (\n  {kolom}\n)"


def sekarang() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ke_dataframe(spark, baris: list[dict], tabel: str):
    """List dict -> DataFrame dengan skema tetap (kolom yang tidak ada diisi None)."""
    kolom = [(k, t) for k, t in SKEMA[tabel] if t != "VARIANT"]
    ddl_skema = ", ".join(f"{k} {t}" for k, t in kolom)
    waktu = sekarang()
    data = []
    for b in baris:
        b = {"processed_at": waktu, **b}
        data.append(tuple(_konversi(b.get(k), t) for k, t in kolom))
    return spark.createDataFrame(data, schema=ddl_skema)


def _konversi(nilai, tipe):
    if nilai is None:
        return None
    if tipe == "STRING":
        return str(nilai)
    if tipe == "INT":
        return int(nilai)
    if tipe == "DOUBLE":
        return float(nilai)
    return nilai


def tulis(spark, baris: list[dict], nama_lengkap: str, tabel: str, mode: str = "overwrite"):
    """Tulis ke Delta. mode 'overwrite' menimpa seluruh tabel, 'append' menambah."""
    df = ke_dataframe(spark, baris, tabel)
    penulis = df.write.format("delta").mode(mode)
    if mode == "overwrite":
        penulis = penulis.option("overwriteSchema", "true")
    penulis.saveAsTable(nama_lengkap)
    return df
