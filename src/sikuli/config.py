"""Membaca config/pipeline.yaml dan mengisi nilai bawaan."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

BAWAAN: dict = {
    "catalog": "sikuli",
    "schema": "lk",
    "path_pdf": "/Volumes/sikuli/lk/sumber/docs/ALL",
    "path_excel": "/Volumes/sikuli/lk/sumber/excel",
    "path_rules": "rules",
    "entitas": {
        # Grup bernama: entity_id (wajib), doc_type dan tahun (opsional).
        "pola_nama_file": r"^(?P<entity_id>[A-Za-z0-9]+)",
        "doc_type_bawaan": None,
    },
    "deteksi_seksi": {
        "baris_zona_atas": 8,
        "min_seksi_daftar_isi": 3,
        "label_tidak_dikenal": "tidak_dikenal",
        "label_daftar_isi": "daftar_isi",
    },
    "ekstraksi": {
        "ai_extract_version": "2.0",
        "maks_akun_per_panggilan": 40,
        "maks_karakter_per_seksi": 60000,
        "seksi_dilewati": ["calk"],
    },
    "komparasi": {
        "periode": ["berjalan"],
        "toleransi_absolut": 1.0,
        "toleransi_relatif": 0.0,
        "toleransi_pembulatan_skala": True,
        "ai_gen_hanya_non_match": True,
        "catatan_match": "Nilai sesuai",
    },
}


def _gabung(dasar: dict, tambahan: dict) -> dict:
    hasil = copy.deepcopy(dasar)
    for kunci, nilai in (tambahan or {}).items():
        if isinstance(nilai, dict) and isinstance(hasil.get(kunci), dict):
            hasil[kunci] = _gabung(hasil[kunci], nilai)
        else:
            hasil[kunci] = nilai
    return hasil


def muat_config(path: str | Path | None = None) -> dict:
    """Gabungkan nilai bawaan dengan isi file YAML (bila ada)."""
    if path is None:
        return copy.deepcopy(BAWAAN)
    with open(path, encoding="utf-8") as f:
        isi = yaml.safe_load(f) or {}
    return _gabung(BAWAAN, isi)


def nama_tabel(cfg: dict, tabel: str) -> str:
    """Nama tabel lengkap Unity Catalog: catalog.schema.tabel."""
    return f"{cfg['catalog']}.{cfg['schema']}.{tabel}"
