"""Langkah-langkah pipeline yang tidak bergantung pada Spark.

Notebook Databricks hanya mengurus baca/tulis tabel dan pemanggilan AI
Functions; logikanya ada di sini sehingga bisa diuji end-to-end secara lokal.
"""

from __future__ import annotations

from .ekstraksi import kelompokkan_akun, skema_ekstraksi, teks_seksi
from .entitas import info_dari_nama_file
from .parse_pdf import error_parse, halaman_dari_parse
from .rules import Rules
from .seksi import PolaSeksi, deteksi_seksi


def proses_dokumen_pdf(path: str, parsed, cfg: dict, rules: Rules,
                       pola: list[PolaSeksi]) -> dict:
    """Output ai_parse_document satu dokumen -> baris teks_pdf + lokasi_seksi."""
    info = info_dari_nama_file(path, cfg, rules)
    cfg_deteksi = cfg["deteksi_seksi"]
    halaman = halaman_dari_parse(parsed, int(cfg_deteksi["baris_zona_atas"]))
    label, lokasi = deteksi_seksi([h.zona_atas for h in halaman], pola, info["doc_type"], cfg_deteksi)

    identitas = {
        "doc_id": path,
        "nama_file": info["nama_file"],
        "entity_key": info["entity_key"],
        "entity_id": info["entity_id"],
        "doc_type": info["doc_type"],
    }
    teks = [
        {**identitas, "tahun": info["tahun"], "halaman": h.nomor, "seksi": lb["seksi"],
         "status_deteksi": lb["status_deteksi"], "judul_cocok": lb["judul_cocok"],
         "zona_atas": h.zona_atas, "teks": h.teks}
        for h, lb in zip(halaman, label)
    ]
    peringatan = error_parse(parsed)
    if not info["entitas_dikenal"]:
        peringatan.append(f"{info['nama_file']}: entity_id/doc_type tidak dikenali dari nama file")
    if not lokasi:
        peringatan.append(f"{info['nama_file']}: tidak ada seksi yang terdeteksi")
    return {
        "teks": teks,
        "lokasi": [{**identitas, **l} for l in lokasi],
        "peringatan": peringatan,
    }


def buat_permintaan_ekstraksi(teks_pdf: list[dict], cfg: dict, rules: Rules) -> list[dict]:
    """Satu permintaan ai_extract per (dokumen, seksi, kelompok akun).

    Hanya seksi yang punya akun di rules_akun untuk doc_type dokumen tersebut.
    """
    cfg_eks = cfg["ekstraksi"]
    dilewati = set(cfg_eks.get("seksi_dilewati") or [])
    per_seksi: dict[tuple, list[dict]] = {}
    for b in teks_pdf:
        if b["status_deteksi"] in ("daftar_isi", "tidak_dikenal") or b["seksi"] in dilewati:
            continue
        per_seksi.setdefault((b["doc_id"], b["seksi"]), []).append(b)

    permintaan = []
    for (doc_id, seksi), halaman in sorted(per_seksi.items()):
        pertama = min(halaman, key=lambda x: x["halaman"])
        akun = rules.akun_untuk(pertama["doc_type"], seksi)
        if not akun:
            continue
        teks = teks_seksi(halaman, int(cfg_eks["maks_karakter_per_seksi"]))
        for i, kelompok in enumerate(kelompokkan_akun(akun, int(cfg_eks["maks_akun_per_panggilan"]))):
            permintaan.append({
                "id_permintaan": f"{doc_id}::{seksi}::{i}",
                "doc_id": doc_id,
                "sumber_file": pertama["nama_file"],
                "entity_key": pertama["entity_key"],
                "entity_id": pertama["entity_id"],
                "doc_type": pertama["doc_type"],
                "tahun": pertama["tahun"],
                "seksi": seksi,
                "zona_atas": pertama["zona_atas"],
                "akun": kelompok,
                "skema": skema_ekstraksi(kelompok),
                "teks": teks,
            })
    return permintaan


def konteks_permintaan(p: dict) -> dict:
    """Kolom identitas yang disalin ke setiap baris angka_pdf."""
    return {k: p[k] for k in ("doc_id", "sumber_file", "entity_key", "entity_id",
                              "doc_type", "tahun", "seksi")}
