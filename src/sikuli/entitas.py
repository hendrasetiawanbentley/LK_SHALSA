"""Menentukan entitas dari prefiks nama file (PDF maupun Excel)."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from .rules import Rules


def info_dari_nama_file(path: str, cfg: dict, rules: Rules | None = None) -> dict:
    """Ambil entity_id, doc_type, tahun dari nama file.

    Pola regex diambil dari config `entitas.pola_nama_file` dan harus punya grup
    bernama `entity_id`; grup `doc_type` dan `tahun` opsional. Bila doc_type tidak
    ada di nama file, dicari di rules/daftar_entitas.csv.

    Nilai `entity_key` dipakai komparasi untuk memasangkan PDF dan Excel milik
    entitas dan periode yang sama.
    """
    nama_file = PurePosixPath(path).name
    stem = nama_file.rsplit(".", 1)[0]
    pola = re.compile(cfg["entitas"]["pola_nama_file"], re.IGNORECASE)
    m = pola.search(stem)
    grup = m.groupdict() if m else {}

    entity_id = (grup.get("entity_id") or "").upper() or None
    doc_type = (grup.get("doc_type") or "").upper() or None
    tahun = grup.get("tahun") or None
    nama_entitas = None

    if entity_id and rules is not None:
        terdaftar = rules.entitas(entity_id)
        if terdaftar:
            doc_type = doc_type or (terdaftar.get("doc_type") or "").upper() or None
            nama_entitas = terdaftar.get("nama_entitas") or None
    doc_type = doc_type or cfg["entitas"].get("doc_type_bawaan")

    bagian_kunci = [entity_id or "?", doc_type or "?"]
    if tahun:
        bagian_kunci.append(str(tahun))
    return {
        "nama_file": nama_file,
        "entity_id": entity_id,
        "doc_type": doc_type,
        "tahun": tahun,
        "nama_entitas": nama_entitas,
        "entity_key": "|".join(bagian_kunci),
        "entitas_dikenal": bool(entity_id and doc_type),
    }
