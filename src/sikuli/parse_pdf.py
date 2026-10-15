"""Mengubah output ai_parse_document menjadi teks per halaman.

ai_parse_document mengembalikan VARIANT. Notebook mengubahnya ke JSON
(`to_json(parsed)`) lalu fungsi di sini menyusun teks tiap halaman berdasarkan
urutan elemen. Format versi 2.x (elements + bbox.page_id) dan versi 1.x
(pages[].content) sama-sama didukung.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

# Elemen yang tidak ikut dipakai untuk zona atas: footer halaman sering berisi
# "Catatan atas laporan keuangan terlampir ..." yang akan salah terbaca sebagai
# judul seksi CaLK.
TIPE_BUKAN_ZONA_ATAS = {"page_footer", "footnote", "page_number"}


@dataclass
class Halaman:
    nomor: int            # 1-based
    teks: str             # seluruh teks halaman, tabel sudah jadi baris "a | b | c"
    zona_atas: str        # beberapa baris teratas, untuk deteksi seksi
    jumlah_gambar: int = 0  # gambar di halaman; halaman tanpa teks tapi bergambar = kemungkinan scan
    sumber_teks: str = "lapisan_teks"  # lapisan_teks / ocr_claude / gambar_perlu_ocr / kosong


def tabel_html_ke_teks(isi: str) -> str:
    """<table><tr><td>Kas</td><td>1.000</td></tr></table> -> 'Kas | 1.000'."""
    if "<" not in isi:
        return isi
    t = re.sub(r"(?i)<br\s*/?>", " ", isi)
    t = re.sub(r"(?i)</t[dh]>\s*<t[dh][^>]*>", " | ", t)
    t = re.sub(r"(?i)</tr>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    baris = [re.sub(r"[ \t]+", " ", b).strip(" |") for b in t.splitlines()]
    return "\n".join(b for b in baris if b)


def _page_id(elemen: dict) -> int | None:
    if elemen.get("page_id") is not None:
        return int(elemen["page_id"])
    for kotak in elemen.get("bbox") or []:
        if isinstance(kotak, dict) and kotak.get("page_id") is not None:
            return int(kotak["page_id"])
    return None


def halaman_dari_parse(parsed: dict | str, baris_zona_atas: int = 8) -> list[Halaman]:
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    dokumen = (parsed or {}).get("document") or {}
    elemen = dokumen.get("elements") or []
    pages = dokumen.get("pages") or []

    per_halaman: dict[int, list[tuple[str, str]]] = {}
    if elemen:
        for i, e in enumerate(sorted(elemen, key=lambda x: x.get("id", 0))):
            pid = _page_id(e)
            if pid is None:
                continue
            tipe = (e.get("type") or "text").lower()
            isi = e.get("content") or ""
            if tipe == "table":
                isi = tabel_html_ke_teks(isi)
            elif tipe == "figure" and not isi:
                isi = e.get("description") or ""
            if isi.strip():
                per_halaman.setdefault(pid, []).append((tipe, isi.strip()))
    else:
        # Format lama: teks sudah tersedia per halaman.
        for p in pages:
            pid = p.get("id", p.get("page_number", 1) - 1)
            isi = "\n".join(x for x in (p.get("header"), p.get("content")) if x)
            per_halaman[int(pid)] = [("text", tabel_html_ke_teks(isi))] if isi else []

    jumlah = max([len(pages)] + [pid + 1 for pid in per_halaman])
    hasil = []
    for pid in range(jumlah):
        potongan = per_halaman.get(pid, [])
        teks = "\n".join(isi for _, isi in potongan)
        baris_atas: list[str] = []
        for tipe, isi in potongan:
            if tipe in TIPE_BUKAN_ZONA_ATAS:
                continue
            baris_atas.extend(b.strip() for b in isi.splitlines() if b.strip())
            if len(baris_atas) >= baris_zona_atas:
                break
        hasil.append(Halaman(pid + 1, teks, "\n".join(baris_atas[:baris_zona_atas])))
    return hasil


def error_parse(parsed: dict | str) -> list[str]:
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    return [
        f"halaman {e.get('page_id')}: {e.get('error_message')}"
        for e in (parsed or {}).get("error_status") or []
    ]
