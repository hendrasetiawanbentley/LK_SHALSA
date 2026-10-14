"""Normalisasi teks dan angka laporan keuangan.

Semua fungsi di sini murni Python (tanpa Spark) supaya bisa diuji lokal.
"""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalisasi_teks(teks: str | None) -> str:
    """Huruf kecil, buang aksen dan tanda baca, rapatkan spasi.

    "LAPORAN LABA (RUGI) dan Penghasilan" -> "laporan laba rugi dan penghasilan"
    Pola di mapping_seksi dan label akun dinormalisasi dengan cara yang sama.
    """
    if not teks:
        return ""
    teks = unicodedata.normalize("NFKD", str(teks))
    teks = "".join(c for c in teks if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", teks.lower()).strip()


_TANDA_STRIP = "—–−‒-"  # berbagai jenis tanda hubung yang dipakai sebagai nol
_BUANG = re.compile(r"(?i)\b(rp|idr|usd)\b\.?|\s| ")


def parse_angka(nilai) -> float | None:
    """Ubah angka seperti tertulis di laporan menjadi float.

    - "(1.234.567)" -> -1234567.0   (kurung = negatif)
    - "1,234,567"   -> 1234567.0
    - "1.234,56"    -> 1234.56      (format Indonesia)
    - "-" / "—"     -> 0.0          (strip di laporan berarti nihil)
    - "" / None     -> None         (tidak ada nilai)

    Satu titik atau koma yang diikuti tepat tiga digit dianggap pemisah ribuan,
    karena angka laporan keuangan disajikan dalam bilangan bulat.
    """
    if nilai is None:
        return None
    if isinstance(nilai, bool):
        return None
    if isinstance(nilai, (int, float)):
        return float(nilai)

    s = _BUANG.sub("", str(nilai))
    if not s:
        return None
    if s.strip(_TANDA_STRIP) == "":
        return 0.0
    if s.lower() in {"nihil", "nil"}:
        return 0.0

    negatif = False
    if s.startswith("(") and s.endswith(")"):
        negatif, s = True, s[1:-1]
    if s and s[0] in _TANDA_STRIP:
        negatif, s = not negatif, s[1:]
    if s.endswith("-") or s.endswith(")"):
        return None
    if not re.fullmatch(r"[0-9.,]+", s) or not re.search(r"\d", s):
        return None

    titik, koma = s.count("."), s.count(",")
    if titik and koma:
        # pemisah yang muncul terakhir adalah pemisah desimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif titik or koma:
        pemisah = "." if titik else ","
        bagian = s.split(pemisah)
        if len(bagian) > 2 or len(bagian[-1]) == 3:
            s = s.replace(pemisah, "")
        else:
            s = s.replace(",", ".")
    try:
        angka = float(s)
    except ValueError:
        return None
    return -angka if negatif else angka


_POLA_SKALA = [
    (re.compile(r"\b(miliar|milyar|billions?)\b"), 1_000_000_000),
    (re.compile(r"\b(jutaan|juta|millions?)\b"), 1_000_000),
    (re.compile(r"\b(ribuan|ribu|thousands?)\b"), 1_000),
]


def deteksi_skala(teks: str | None) -> int | None:
    """Cari keterangan satuan seperti "(Dinyatakan dalam jutaan Rupiah)".

    Mengembalikan pengali (1_000, 1_000_000, ...) atau None bila tidak ada
    keterangan. Hanya kalimat "dalam ..."/"in ..." yang dipertimbangkan supaya
    kata "ribu" di tempat lain tidak ikut terbaca.
    """
    t = normalisasi_teks(teks)
    for m in re.finditer(r"\b(?:dalam|in|expressed in|disajikan dalam)\b(.{0,40})", t):
        potongan = m.group(1)
        for pola, pengali in _POLA_SKALA:
            if pola.search(potongan):
                return pengali
        if re.search(r"\b(rupiah penuh|full rupiah|full amount)\b", potongan):
            return 1
    return None
