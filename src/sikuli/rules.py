"""Memuat dan memvalidasi file rules (kertas kerja) di folder rules/.

Setiap file adalah CSV UTF-8 dengan baris judul. Kolom yang tidak dikenal
dibiarkan (diabaikan), kolom wajib yang hilang menghasilkan error.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

SEMUA = {"", "*", "semua", "all"}

KOLOM_WAJIB: dict[str, list[str]] = {
    "mapping_seksi": ["kode", "seksi", "entitas", "pola"],
    "rules_akun": ["doc_type", "seksi", "kode_akun", "nama_akun"],
    "sheet_config": ["doc_type", "sheet", "seksi", "kolom_label", "kolom_nilai", "baris_mulai"],
    "mapping_akun_excel": ["doc_type", "label_excel", "kode_akun"],
    "daftar_entitas": ["entity_id", "doc_type"],
}

# File yang boleh tidak ada.
OPSIONAL = {"mapping_akun_excel", "daftar_entitas"}


def berlaku_untuk(nilai_kolom: str | None, doc_type: str | None) -> bool:
    """True bila kolom entitas/doc_type ('Semua', 'RD', 'EPP,MI') mencakup doc_type."""
    nilai = (nilai_kolom or "").strip().lower()
    if nilai in SEMUA:
        return True
    if not doc_type:
        return False
    daftar = {x.strip().lower() for x in nilai.replace(";", ",").split(",")}
    return doc_type.strip().lower() in daftar


def _aktif(baris: dict) -> bool:
    return (baris.get("aktif") or "1").strip().lower() not in {"0", "false", "tidak", "n", "no"}


def baca_csv(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        baris = [
            {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            for r in csv.DictReader(f)
        ]
    return [r for r in baris if any(r.values()) and _aktif(r)]


@dataclass
class Rules:
    mapping_seksi: list[dict] = field(default_factory=list)
    rules_akun: list[dict] = field(default_factory=list)
    sheet_config: list[dict] = field(default_factory=list)
    mapping_akun_excel: list[dict] = field(default_factory=list)
    daftar_entitas: list[dict] = field(default_factory=list)

    def akun_untuk(self, doc_type: str | None, seksi: str) -> list[dict]:
        return [
            a for a in self.rules_akun
            if a["seksi"] == seksi and berlaku_untuk(a["doc_type"], doc_type)
        ]

    def entitas(self, entity_id: str) -> dict | None:
        for e in self.daftar_entitas:
            if e["entity_id"].lower() == entity_id.lower():
                return e
        return None


def muat_rules(folder: str | Path) -> Rules:
    folder = Path(folder)
    data = {}
    for nama in KOLOM_WAJIB:
        path = folder / f"{nama}.csv"
        if not path.exists():
            if nama in OPSIONAL:
                data[nama] = []
                continue
            raise FileNotFoundError(f"File rules wajib tidak ditemukan: {path}")
        data[nama] = baca_csv(path)
    return Rules(**data)


def validasi_rules(rules: Rules) -> list[str]:
    """Kembalikan daftar masalah; list kosong berarti rules siap dipakai."""
    masalah: list[str] = []
    for nama, kolom in KOLOM_WAJIB.items():
        isi = getattr(rules, nama)
        for i, baris in enumerate(isi, start=2):
            kosong = [k for k in kolom if not baris.get(k)]
            if kosong:
                masalah.append(f"{nama}.csv baris {i}: kolom wajib kosong/tidak ada {kosong}")

    kode_seksi = {m["kode"] for m in rules.mapping_seksi}
    for nama in ("rules_akun", "sheet_config"):
        for i, baris in enumerate(getattr(rules, nama), start=2):
            if baris.get("seksi") and baris["seksi"] not in kode_seksi:
                masalah.append(
                    f"{nama}.csv baris {i}: seksi '{baris['seksi']}' tidak ada di mapping_seksi"
                )

    dilihat: dict[tuple, int] = {}
    for i, a in enumerate(rules.rules_akun, start=2):
        kunci = (a.get("doc_type", "").lower(), a.get("kode_akun"))
        if kunci in dilihat:
            masalah.append(
                f"rules_akun.csv baris {i}: kode_akun '{a.get('kode_akun')}' duplikat "
                f"untuk doc_type '{a.get('doc_type')}' (lihat baris {dilihat[kunci]})"
            )
        dilihat[kunci] = i

    kode_akun = {a.get("kode_akun") for a in rules.rules_akun}
    for i, m in enumerate(rules.mapping_akun_excel, start=2):
        if m.get("kode_akun") and m["kode_akun"] not in kode_akun:
            masalah.append(
                f"mapping_akun_excel.csv baris {i}: kode_akun '{m['kode_akun']}' tidak ada di rules_akun"
            )

    for i, s in enumerate(rules.sheet_config, start=2):
        for kolom in ("baris_mulai", "baris_akhir", "skala"):
            if s.get(kolom) and not s[kolom].replace(".", "", 1).isdigit():
                masalah.append(f"sheet_config.csv baris {i}: {kolom} harus angka, isinya '{s[kolom]}'")
    return masalah
