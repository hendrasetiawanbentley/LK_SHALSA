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
    # "(11.967.340.240 )" -> "(11.967.340.240)" supaya angka dalam kurung tetap satu token.
    baris = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", baris))
    token = baris.split()
    def awal_angka(i: int) -> bool:
        if i == 0 or not _ANGKA.match(token[i]):
            return False
        # "-" yang diikuti kata adalah bagian label ("JUMLAH EKUITAS - NETO 17.375"), bukan nihil.
        if token[i] in "-−–—" and i + 1 < len(token) and not _ANGKA.match(token[i + 1]):
            return False
        return True

    mulai = next((i for i in range(len(token)) if awal_angka(i)), None)
    if mulai is None:
        return None
    akhir = mulai
    while akhir < len(token) and _ANGKA.match(token[akhir]):
        akhir += 1
    label = token[:mulai]
    angka = token[mulai:akhir]
    # Nomor catatan ("4", "2c,5", "3,32,37") bisa muncul di depan atau di antara angka
    # (format bilingual). Buang bila masih ada angka lain yang bukan nomor catatan.
    while label and _CATATAN.match(label[-1]):
        label = label[:-1]
    bukan_catatan = [t for t in angka if not _CATATAN.match(t)]
    if bukan_catatan and len(bukan_catatan) < len(angka):
        angka = bukan_catatan
    # Kolom pertama = periode berjalan, kedua = pembanding (kolom berikutnya, mis.
    # saldo awal tahun pembanding, diabaikan).
    angka = angka[:2]
    return " ".join(label), angka, " ".join(token[akhir:])


def _kunci_akun(akun: dict) -> set[str]:
    return {normalisasi_teks(x) for x in [akun["nama_akun"], *(akun.get("sinonim") or "").split("|")] if x.strip()}


def ekstraksi_seksi(halaman: list[dict], akun: list[dict], konteks: dict,
                    zona_atas: str = "") -> tuple[list[dict], list[str]]:
    """halaman = baris teks_pdf satu seksi. Kembalikan (baris angka_pdf, akun_tidak_ditemukan)."""
    # Satuan dibaca per halaman (kepala halaman), karena halaman pertama seksi bisa
    # berupa laporan auditor tanpa keterangan satuan; cadangan: satuan pertama di seksi.
    skala_halaman = {h["halaman"]: deteksi_skala("\n".join(h["teks"].splitlines()[:15])) for h in halaman}
    skala_seksi = deteksi_skala(zona_atas) or next(
        (v for _, v in sorted(skala_halaman.items()) if v), None) or 1
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
        skala = skala_halaman.get(temuan["halaman"]) or skala_seksi
        for periode, mentah in zip(("berjalan", "lalu"), temuan["angka"]):
            nilai = parse_angka(mentah)
            if nilai is None:
                continue
            hasil.append({**konteks, "kode_akun": a["kode_akun"], "label_di_dokumen": temuan["label"],
                          "periode": periode, "nilai": nilai, "nilai_asli": mentah,
                          "skala": float(skala), "halaman": temuan["halaman"]})
    tidak_ada = [a["kode_akun"] for a in akun if a["kode_akun"] not in ditemukan]
    return hasil, tidak_ada
