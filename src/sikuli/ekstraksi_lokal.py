"""Ekstraksi akun dari teks seksi PDF tanpa AI (pengganti ai_extract).

Setiap baris teks laporan biasanya berbentuk
    "<label> [catatan] <angka berjalan> <angka lalu> [label Inggris]"
Baris dipecah menjadi label + deretan angka; label (atau label Inggris di
belakang angka) dicocokkan dengan nama_akun/sinonim di rules_akun setelah
dinormalisasi. Akun yang tidak ditemukan dilaporkan supaya bisa ditambah
sinonimnya.
"""

from __future__ import annotations

import re

from .normalisasi import deteksi_skala, normalisasi_teks, parse_angka

_ANGKA = re.compile(r"^\(?[-−–—]?[\d.,]*\d[\d.,]*\)?$|^[-−–—]$")
_CATATAN = re.compile(r"^\d{1,2}[a-z]?(?:[,.]\d{1,2}[a-z]?)*$", re.IGNORECASE)


def pecah_baris(baris: str) -> tuple[str, list[str], str] | None:
    """'Kas dan setara kas 4 1.250 (1.100) Cash' -> ('Kas dan setara kas', ['1.250', '(1.100)'], 'Cash')."""
    token = baris.split()
    mulai = next((i for i, t in enumerate(token) if _ANGKA.match(t) and i > 0), None)
    if mulai is None:
        return None
    akhir = mulai
    while akhir < len(token) and _ANGKA.match(token[akhir]):
        akhir += 1
    label = token[:mulai]
    angka = token[mulai:akhir]
    # Nomor catatan seperti "4" atau "2c,5" sebelum angka bukan nilai akun.
    while label and _CATATAN.match(label[-1]):
        label = label[:-1]
    if len(angka) > 2:
        angka = angka[-2:]
    elif len(angka) == 2 and _CATATAN.match(angka[0]) and len(re.sub(r"\D", "", angka[1])) >= 4:
        angka = angka[1:]
    return " ".join(label), angka, " ".join(token[akhir:])


def _kunci_akun(akun: dict) -> set[str]:
    return {normalisasi_teks(x) for x in [akun["nama_akun"], *(akun.get("sinonim") or "").split("|")] if x.strip()}


def ekstraksi_seksi(halaman: list[dict], akun: list[dict], konteks: dict,
                    zona_atas: str = "") -> tuple[list[dict], list[str]]:
    """halaman = baris teks_pdf satu seksi. Kembalikan (baris angka_pdf, akun_tidak_ditemukan)."""
    skala = deteksi_skala(zona_atas) or 1
    kunci = [(a, _kunci_akun(a)) for a in akun]
    ditemukan: dict[str, dict] = {}
    for h in sorted(halaman, key=lambda x: x["halaman"]):
        for baris in h["teks"].splitlines():
            pecahan = pecah_baris(baris.strip())
            if not pecahan:
                continue
            label, angka, ekor = pecahan
            label_n, ekor_n = normalisasi_teks(label), normalisasi_teks(ekor)
            for a, nama in kunci:
                if a["kode_akun"] in ditemukan or not (label_n in nama or (ekor_n and ekor_n in nama)):
                    continue
                ditemukan[a["kode_akun"]] = {"label": label, "angka": angka, "halaman": h["halaman"]}
    hasil = []
    for a in akun:
        temuan = ditemukan.get(a["kode_akun"])
        if not temuan:
            continue
        for periode, mentah in zip(("berjalan", "lalu"), temuan["angka"]):
            nilai = parse_angka(mentah)
            if nilai is None:
                continue
            hasil.append({**konteks, "kode_akun": a["kode_akun"], "label_di_dokumen": temuan["label"],
                          "periode": periode, "nilai": nilai, "nilai_asli": mentah,
                          "skala": float(skala), "halaman": temuan["halaman"]})
    tidak_ada = [a["kode_akun"] for a in akun if a["kode_akun"] not in ditemukan]
    return hasil, tidak_ada
