"""Ekstraksi akun dari teks seksi PDF memakai ai_extract (slide 4).

Skema ai_extract dibentuk dari rules_akun: setiap akun menjadi satu field
(nama field = kode_akun) dengan deskripsi nama akun + sinonim. AI diminta
menyalin angka persis seperti tertulis; konversi ke bilangan dilakukan
deterministik oleh normalisasi.parse_angka supaya bisa ditelusuri.
"""

from __future__ import annotations

import json
import re

from .normalisasi import deteksi_skala, parse_angka

_FIELD_AMAN = re.compile(r"[^A-Za-z0-9_]")


def nama_field(kode_akun: str) -> str:
    """Nama field skema harus aman sebagai identifier JSON/SQL."""
    nama = _FIELD_AMAN.sub("_", kode_akun)
    return nama if not nama[:1].isdigit() else f"a_{nama}"


def skema_ekstraksi(akun: list[dict]) -> str:
    """Skema JSON untuk ai_extract versi 2.x."""
    skema = {}
    for a in akun:
        deskripsi = a["nama_akun"]
        if a.get("sinonim"):
            deskripsi += " (juga ditulis: " + ", ".join(a["sinonim"].split("|")) + ")"
        if a.get("deskripsi"):
            deskripsi += ". " + a["deskripsi"]
        skema[nama_field(a["kode_akun"])] = {
            "type": "object",
            "description": deskripsi,
            "properties": {
                "nilai_berjalan": {
                    "type": "string",
                    "description": "Angka periode berjalan (kolom tahun terbaru) persis seperti tertulis, "
                                   "termasuk tanda kurung dan titik, misalnya (1.234.567). Kosongkan bila tidak ada.",
                },
                "nilai_lalu": {
                    "type": "string",
                    "description": "Angka periode pembanding (tahun sebelumnya) persis seperti tertulis. "
                                   "Kosongkan bila tidak ada.",
                },
                "halaman": {
                    "type": "integer",
                    "description": "Nomor halaman dari penanda [HALAMAN n] tempat angka ditemukan.",
                },
                "label_di_dokumen": {
                    "type": "string",
                    "description": "Nama baris akun persis seperti tertulis di dokumen.",
                },
            },
        }
    return json.dumps(skema, ensure_ascii=False)


def kelompokkan_akun(akun: list[dict], maks: int) -> list[list[dict]]:
    """Pecah daftar akun supaya satu panggilan ai_extract tidak terlalu besar."""
    return [akun[i:i + maks] for i in range(0, len(akun), maks)] or [[]]


def teks_seksi(halaman: list[dict], maks_karakter: int) -> str:
    """Gabungkan halaman seksi dengan penanda nomor halaman."""
    potongan = [f"[HALAMAN {h['halaman']}]\n{h['teks']}" for h in sorted(halaman, key=lambda x: x["halaman"])]
    return "\n\n".join(potongan)[:maks_karakter]


def _buka(nilai):
    """Versi 2.1 membungkus nilai daun sebagai {"value": ..., "confidence": ...}."""
    if isinstance(nilai, dict) and "value" in nilai and not ({"nilai_berjalan", "nilai_lalu"} & nilai.keys()):
        return nilai.get("value")
    return nilai


def parse_hasil_ekstraksi(hasil_json: str | dict | None, akun: list[dict], konteks: dict,
                          zona_atas: str = "") -> tuple[list[dict], list[str]]:
    """Ubah output ai_extract (to_json) menjadi baris angka_pdf.

    `konteks` berisi kolom identitas dokumen/seksi yang disalin ke setiap baris.
    Akun yang tidak ditemukan (nilai kosong) tidak menghasilkan baris, sehingga
    pada komparasi muncul sebagai EXCEL_ONLY.
    """
    if hasil_json is None:
        return [], ["hasil ai_extract kosong"]
    data = json.loads(hasil_json) if isinstance(hasil_json, str) else hasil_json
    peringatan = []
    if isinstance(data, dict) and data.get("error_message"):
        peringatan.append(str(data["error_message"]))
    respons = data.get("response", data) if isinstance(data, dict) else {}
    respons = _buka(respons) or {}

    skala = deteksi_skala(zona_atas) or 1
    baris = []
    for a in akun:
        item = _buka(respons.get(nama_field(a["kode_akun"])))
        if not isinstance(item, dict):
            continue
        halaman = _buka(item.get("halaman"))
        try:
            halaman = int(halaman) if halaman not in (None, "") else None
        except (TypeError, ValueError):
            halaman = None
        for periode, kunci in (("berjalan", "nilai_berjalan"), ("lalu", "nilai_lalu")):
            mentah = _buka(item.get(kunci))
            nilai = parse_angka(mentah)
            if nilai is None:
                if mentah not in (None, ""):
                    peringatan.append(f"{a['kode_akun']}/{periode}: angka tidak terbaca '{mentah}'")
                continue
            baris.append({
                **konteks,
                "kode_akun": a["kode_akun"],
                "label_di_dokumen": _buka(item.get("label_di_dokumen")),
                "periode": periode,
                "nilai": nilai,
                "nilai_asli": str(mentah),
                "skala": float(skala),
                "halaman": halaman,
            })
    return baris, peringatan


def sql_literal(teks: str) -> str:
    """Literal string Spark SQL yang aman untuk skema JSON."""
    return "'" + teks.replace("\\", "\\\\").replace("'", "\\'") + "'"
