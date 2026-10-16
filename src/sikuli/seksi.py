"""Deteksi seksi PDF dari bagian atas halaman (slide 5 deck SIKULI).

Untuk setiap halaman, berurutan:
1. Ambil zona atas (beberapa baris teratas).
2. Cocokkan dengan pola nama laporan di mapping_seksi (sesuai jenis entitas).
3. >= min_seksi_daftar_isi seksi cocok -> daftar isi, dilewati.
4. Ada seksi cocok -> mulai seksi baru (seksi yang judulnya muncul paling awal).
5. Tidak ada yang cocok -> lanjutkan seksi halaman sebelumnya; bila tidak ada
   seksi sebelumnya -> tidak_dikenal (tidak diekstraksi).
Tambahan: halaman sebelum seksi pertama (sampul, daftar isi) diberi label `label_awal`
(bawaan "sampul"); halaman tanpa teks (scan yang belum di-OCR, halaman kosong) diberi label
"tanpa_teks" dan tidak memperpanjang seksi yang sedang berjalan, karena isinya tidak diketahui
(mis. surat pernyataan hasil scan di antara laporan auditor dan laporan posisi keuangan).
Hasilnya label seksi per halaman (untuk teks_pdf) dan rentang halaman per seksi
(untuk lokasi_seksi).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalisasi import normalisasi_teks
from .rules import berlaku_untuk

_META_REGEX = set("\\[]()?*+|^${}")


@dataclass
class PolaSeksi:
    kode: str
    seksi: str
    entitas: str
    pola: str
    regex: re.Pattern
    maks_halaman: int | None


def kompilasi_pola(mapping_seksi: list[dict], awal_baris: bool = True) -> list[PolaSeksi]:
    """Satu baris mapping_seksi = satu pola. Frasa biasa dinormalisasi dan
    dicocokkan per kata utuh; pola yang mengandung karakter regex dipakai apa
    adanya terhadap teks yang sudah dinormalisasi.

    awal_baris=True: judul harus berada di awal baris, supaya frasa di tengah kalimat
    (mis. sampul "... beserta laporan auditor independen" atau isi laporan auditor
    "... through profit or loss") tidak dianggap judul seksi."""
    hasil = []
    # Judul boleh diawali kata pembuka umum: "LAPORAN laba rugi", "Statements of profit or loss",
    # "Consolidated statement of ...", "Catatan atas ..." tetap cocok; kalimat biasa tidak.
    pembuka = r"(?:(?:laporan|statements?|of|the|consolidated|konsolidasian|interim|keuangan)\s+){0,3}"
    awal = r"(?m)^" + pembuka if awal_baris else ""
    for baris in mapping_seksi:
        pola = baris["pola"]
        if any(c in _META_REGEX for c in pola):
            regex = re.compile(awal + "(?:" + pola + ")")
        else:
            regex = re.compile((awal if awal_baris else r"\b") + re.escape(normalisasi_teks(pola)) + r"\b")
        maks = (baris.get("maks_halaman") or "").strip()
        hasil.append(
            PolaSeksi(
                kode=baris["kode"],
                seksi=baris.get("seksi", baris["kode"]),
                entitas=baris.get("entitas", ""),
                pola=pola,
                regex=regex,
                maks_halaman=int(maks) if maks else None,
            )
        )
    return hasil


def cocokkan_zona(zona_atas: str, pola: list[PolaSeksi], doc_type: str | None) -> dict[str, tuple[int, str]]:
    """{kode_seksi: (posisi_pertama, pola_yang_cocok)} untuk seksi yang cocok."""
    # Dinormalisasi per baris supaya batas baris (untuk pola awal baris) tetap ada.
    teks = "\n".join(normalisasi_teks(b) for b in (zona_atas or "").splitlines())
    cocok: dict[str, tuple[int, str]] = {}
    for p in pola:
        if not berlaku_untuk(p.entitas, doc_type):
            continue
        m = p.regex.search(teks)
        if m and (p.kode not in cocok or m.start() < cocok[p.kode][0]):
            cocok[p.kode] = (m.start(), p.pola)
    return cocok


def deteksi_seksi(
    zona_atas_per_halaman: list[str],
    pola: list[PolaSeksi],
    doc_type: str | None,
    cfg_deteksi: dict,
) -> tuple[list[dict], list[dict]]:
    """Kembalikan (label_per_halaman, lokasi_seksi).

    label_per_halaman[i] = {halaman, seksi, status_deteksi, judul_cocok}
    status_deteksi: judul | lanjutan | daftar_isi | tidak_dikenal
    lokasi_seksi = [{seksi, halaman_mulai, halaman_akhir, judul_cocok}]
    """
    min_daftar_isi = int(cfg_deteksi.get("min_seksi_daftar_isi", 3))
    label_tidak_dikenal = cfg_deteksi.get("label_tidak_dikenal", "tidak_dikenal")
    label_daftar_isi = cfg_deteksi.get("label_daftar_isi", "daftar_isi")
    maks_per_kode = {}
    for p in pola:
        if p.maks_halaman is not None:
            maks_per_kode[p.kode] = p.maks_halaman

    label_awal = cfg_deteksi.get("label_awal", "sampul")
    label: list[dict] = []
    lokasi: list[dict] = []
    aktif: dict | None = None  # seksi yang sedang berjalan
    sudah_mulai = False        # sudah ada seksi selain sampul

    def awal(halaman: int, status: str) -> None:
        """Halaman sebelum seksi pertama -> sampul (dibuat atau diperpanjang)."""
        nonlocal aktif
        if aktif and aktif["seksi"] == label_awal:
            aktif["halaman_akhir"] = halaman
        else:
            aktif = dict(seksi=label_awal, halaman_mulai=halaman, halaman_akhir=halaman, judul_cocok=None)
            lokasi.append(aktif)
        label.append(dict(halaman=halaman, seksi=label_awal, status_deteksi=status, judul_cocok=None))

    sampul_pertama = bool(cfg_deteksi.get("halaman_pertama_sampul", False)) and bool(label_awal)
    for i, zona in enumerate(zona_atas_per_halaman):
        halaman = i + 1
        if halaman == 1 and sampul_pertama:
            awal(halaman, "awal")
            continue
        if not (zona or "").strip():
            label.append(dict(halaman=halaman, seksi="tanpa_teks", status_deteksi="tanpa_teks", judul_cocok=None))
            continue
        cocok = cocokkan_zona(zona, pola, doc_type)

        if len(cocok) >= min_daftar_isi:
            if label_awal and not sudah_mulai:
                awal(halaman, "daftar_isi")
                continue
            label.append(dict(halaman=halaman, seksi=label_daftar_isi,
                              status_deteksi="daftar_isi", judul_cocok=None))
            continue

        if cocok:
            kode, (_, judul) = min(cocok.items(), key=lambda kv: kv[1][0])
            if kode == label_awal and not sudah_mulai:
                awal(halaman, "judul")
                continue
            sudah_mulai = sudah_mulai or kode != label_awal
            if aktif and aktif["seksi"] == kode:
                # Judul diulang di halaman lanjutan, misalnya "(lanjutan)".
                aktif["halaman_akhir"] = halaman
                label.append(dict(halaman=halaman, seksi=kode,
                                  status_deteksi="lanjutan", judul_cocok=judul))
            else:
                aktif = dict(seksi=kode, halaman_mulai=halaman,
                             halaman_akhir=halaman, judul_cocok=judul)
                lokasi.append(aktif)
                label.append(dict(halaman=halaman, seksi=kode,
                                  status_deteksi="judul", judul_cocok=judul))
            continue

        if aktif:
            maks = maks_per_kode.get(aktif["seksi"])
            if maks is None or halaman - aktif["halaman_mulai"] < maks:
                aktif["halaman_akhir"] = halaman
                label.append(dict(halaman=halaman, seksi=aktif["seksi"],
                                  status_deteksi="lanjutan", judul_cocok=None))
                continue
            aktif = None  # melewati batas maks_halaman

        if label_awal and not sudah_mulai:
            awal(halaman, "awal")
            continue
        label.append(dict(halaman=halaman, seksi=label_tidak_dikenal,
                          status_deteksi="tidak_dikenal", judul_cocok=None))
    return label, lokasi
