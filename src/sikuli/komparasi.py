"""Analisis komparasi angka PDF vs Excel (slide 10).

Langkah: bentuk entity_key -> full outer join per entity_key + kode_akun +
periode -> tentukan status MATCH / DIFFERENT / PDF_ONLY / EXCEL_ONLY.
Perbandingan dilakukan dalam SATUAN PDF: angka PDF dipakai persis seperti
tertulis, angka Excel (Rupiah penuh) dibagi skala PDF. Contoh: PDF "dalam
jutaan Rupiah" menulis 1.250, Excel 1.250.400.000 -> Excel disesuaikan 1.250,4.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

MATCH, DIFFERENT, PDF_ONLY, EXCEL_ONLY = "MATCH", "DIFFERENT", "PDF_ONLY", "EXCEL_ONLY"


NAMA_SATUAN = {1: "Rupiah", 1_000: "ribuan Rupiah", 1_000_000: "jutaan Rupiah",
               1_000_000_000: "miliar Rupiah"}


def nama_satuan(skala: float | None) -> str:
    return NAMA_SATUAN.get(int(skala or 1), f"x{skala:,.0f}")


def toleransi(nilai_pdf: float, nilai_excel: float, skala_pdf: float, cfg: dict) -> float:
    """Selisih maksimum (dalam satuan PDF) yang masih dianggap sama.

    Bila PDF disajikan dalam ribuan/jutaan, Excel yang sudah dibagi skala
    hampir selalu berkoma; selisih sampai `toleransi_pembulatan_satuan` (bawaan
    1 satuan) dianggap pembulatan wajar.
    """
    # toleransi_absolut ditulis dalam Rupiah, dikonversi ke satuan PDF.
    tol = float(cfg.get("toleransi_absolut", 0) or 0) / (skala_pdf or 1)
    tol = max(tol, float(cfg.get("toleransi_relatif", 0) or 0) * max(abs(nilai_pdf), abs(nilai_excel)))
    if cfg.get("toleransi_pembulatan_skala", True) and (skala_pdf or 1) > 1:
        # Jumlah/total di PDF dibulatkan dari komponen yang sudah dibulatkan, jadi
        # selisih sampai 1 satuan penyajian masih wajar (bisa diubah di config).
        tol = max(tol, float(cfg.get("toleransi_pembulatan_satuan", 1.0)))
    return tol


def indikasi_selisih(nilai_pdf: float, nilai_excel: float, tol: float) -> str | None:
    """Petunjuk deterministik penyebab DIFFERENT, untuk membantu pengawas dan prompt AI."""
    if abs(nilai_pdf + nilai_excel) <= tol and nilai_pdf != 0:
        return "BEDA_TANDA"
    if nilai_pdf and nilai_excel:
        rasio = abs(nilai_excel / nilai_pdf)
        for faktor in (1e3, 1e6, 1e9):
            for r in (faktor, 1 / faktor):
                if abs(rasio - r) <= 0.005 * r:
                    return "BEDA_SKALA"
    return None


def desimal_teks(teks: str | None, nilai: float | None) -> int:
    """Jumlah digit di belakang koma pada angka PDF seperti tertulis.

    "4.397,88" -> 2, "1,068,697.19" -> 2, "709.863.919,7765" -> 4, "6.929" / "(1.115.249.979)" -> 0
    (tiga digit setelah pemisah terakhir pada bilangan bulat = pemisah ribuan)."""
    if not teks or nilai is None:
        return 0
    t = re.sub(r"[^\d.,]", "", teks)
    akhir = max(t.rfind("."), t.rfind(","))
    if akhir < 0:
        return 0
    d = len(t) - akhir - 1
    if d == 0 or (d == 3 and float(nilai).is_integer()):
        return 0
    return d if abs(nilai * 10 ** d - round(nilai * 10 ** d)) < 1e-6 else 0


def _bulatkan(x: float, desimal: int) -> float:
    return float(Decimal(str(x)).quantize(Decimal(1).scaleb(-desimal), rounding=ROUND_HALF_UP))


def tentukan_status(nilai_pdf: float | None, nilai_excel: float | None,
                    skala_pdf: float, cfg: dict, desimal_pdf: int = 0) -> dict:
    if nilai_pdf is None and nilai_excel is None:
        raise ValueError("minimal salah satu nilai harus ada")
    # Rules Master: akun nihil ("-" di PDF, 0 di Excel, atau tidak disajikan sama sekali) di kedua
    # sisi dianggap sesuai (MATCH) dengan indikasi NIHIL, bukan PDF_ONLY/EXCEL_ONLY.
    if cfg.get("nihil_dianggap_match") and (nilai_pdf or 0) == 0 and (nilai_excel or 0) == 0:
        return {"status": MATCH, "selisih": None if None in (nilai_pdf, nilai_excel) else 0.0,
                "selisih_persen": None, "indikasi": "NIHIL"}
    if nilai_excel is None:
        return {"status": PDF_ONLY, "selisih": None, "selisih_persen": None, "indikasi": None}
    if nilai_pdf is None:
        return {"status": EXCEL_ONLY, "selisih": None, "selisih_persen": None, "indikasi": None}

    # Rules Master: perbedaan tanda saja (mis. -5.206 vs 5.206) bukan perbedaan nilai, jadi bila
    # abaikan_beda_tanda aktif yang dibandingkan adalah nilai absolutnya.
    beda_tanda = nilai_pdf * nilai_excel < 0
    abaikan = bool(cfg.get("abaikan_beda_tanda"))
    a, e = (abs(nilai_pdf), abs(nilai_excel)) if abaikan else (nilai_pdf, nilai_excel)
    digit = cfg.get("toleransi_digit_terakhir")
    if digit is not None:
        # Excel dibulatkan ke presisi angka PDF (jumlah desimal yang tertulis), lalu selisih sampai
        # `digit` satuan pada digit terakhir masih dianggap sama (mis. 376 vs 374,77 -> 375: selisih 1).
        satuan_digit = 10.0 ** -desimal_pdf
        e_banding = _bulatkan(e, desimal_pdf)
        tol = max(float(digit) * satuan_digit,
                  float(cfg.get("toleransi_relatif", 0) or 0) * max(abs(a), abs(e)))
        cocok = abs(a - e_banding) <= tol + satuan_digit * 1e-6
    else:
        tol = toleransi(nilai_pdf, nilai_excel, skala_pdf, cfg)
        cocok = abs(a - e) <= tol
    selisih = a - e
    persen = None if e == 0 else round(selisih / abs(e) * 100, 4)
    indikasi = "BEDA_TANDA" if beda_tanda else None
    if cocok:
        return {"status": MATCH, "selisih": selisih, "selisih_persen": persen, "indikasi": indikasi}
    return {"status": DIFFERENT, "selisih": selisih, "selisih_persen": persen,
            "indikasi": indikasi or indikasi_selisih(nilai_pdf, nilai_excel, tol)}


def _indeks(baris: list[dict], periode: set[str], sisi: str) -> dict[tuple, dict]:
    """Kunci join -> baris pertama bernilai bukan nol (atau baris pertama bila semua nol);
    duplikat dihitung di kolom jumlah_baris_*."""
    hasil: dict[tuple, dict] = {}
    for b in baris:
        if not b.get("kode_akun") or b.get("periode") not in periode or b.get("nilai") is None:
            continue
        kunci = (b["entity_key"], b["kode_akun"], b["periode"])
        if kunci in hasil:
            jumlah = hasil[kunci][f"jumlah_baris_{sisi}"] + 1
            if hasil[kunci]["nilai"] == 0 and b["nilai"] != 0:
                hasil[kunci] = {**b}
            hasil[kunci][f"jumlah_baris_{sisi}"] = jumlah
        else:
            hasil[kunci] = {**b, f"jumlah_baris_{sisi}": 1}
    return hasil


def _skala_pdf(angka_pdf: list[dict]) -> tuple[dict, dict]:
    """Skala PDF per (entity_key, seksi) dan per entity_key (yang paling sering)."""
    per_seksi: dict[tuple, float] = {}
    hitung: dict[str, dict[float, int]] = {}
    for b in angka_pdf:
        skala = b.get("skala") or 1.0
        per_seksi.setdefault((b["entity_key"], b.get("seksi")), skala)
        c = hitung.setdefault(b["entity_key"], {})
        c[skala] = c.get(skala, 0) + 1
    per_entitas = {k: max(c, key=c.get) for k, c in hitung.items()}
    return per_seksi, per_entitas


def bandingkan(angka_pdf: list[dict], angka_excel: list[dict], cfg_komparasi: dict,
               nama_akun: dict[str, str] | None = None) -> list[dict]:
    """Full outer join angka_pdf <-> angka_excel lalu tentukan status per baris."""
    periode = set(cfg_komparasi.get("periode") or ["berjalan"])
    pdf = _indeks(angka_pdf, periode, "pdf")
    excel = _indeks(angka_excel, periode, "excel")
    nama_akun = nama_akun or {}
    skala_seksi, skala_entitas = _skala_pdf(angka_pdf)

    hasil = []
    for kunci in sorted(set(pdf) | set(excel)):
        p, e = pdf.get(kunci), excel.get(kunci)
        acuan = p or e
        seksi = (p or {}).get("seksi") or (e or {}).get("seksi")
        if p:
            skala_pdf = p.get("skala") or 1.0
        else:  # EXCEL_ONLY: pakai satuan PDF seksi/entitas yang sama
            skala_pdf = skala_seksi.get((kunci[0], seksi)) or skala_entitas.get(kunci[0]) or 1.0
        nilai_pdf = p["nilai"] if p else None
        nilai_excel_asli = e["nilai"] if e else None
        nilai_excel = None if e is None else nilai_excel_asli / skala_pdf
        hasil.append({
            "entity_key": kunci[0],
            "entity_id": acuan.get("entity_id"),
            "doc_type": acuan.get("doc_type"),
            "tahun": acuan.get("tahun"),
            "kode_akun": kunci[1],
            "nama_akun": nama_akun.get(kunci[1]),
            "periode": kunci[2],
            "seksi": seksi,
            "satuan_pdf": nama_satuan(skala_pdf),
            "nilai_pdf": nilai_pdf,
            "nilai_excel": nilai_excel,
            "nilai_excel_asli": nilai_excel_asli,
            "skala_pdf": skala_pdf,
            "halaman_pdf": (p or {}).get("halaman"),
            "verifikasi_pdf": (p or {}).get("verifikasi"),
            "sumber_pdf": (p or {}).get("sumber_file"),
            "sumber_excel": f"{e['sumber_file']}!{e['sheet']}!{e['baris']}" if e else None,
            "label_pdf": (p or {}).get("label_di_dokumen"),
            "label_excel": (e or {}).get("label_asli"),
            "jumlah_baris_pdf": (p or {}).get("jumlah_baris_pdf", 0),
            "jumlah_baris_excel": (e or {}).get("jumlah_baris_excel", 0),
            "desimal_pdf": desimal_teks((p or {}).get("nilai_asli"), nilai_pdf),
            **tentukan_status(nilai_pdf, nilai_excel, skala_pdf, cfg_komparasi,
                              desimal_teks((p or {}).get("nilai_asli"), nilai_pdf)),
        })
    return hasil


def prompt_catatan(baris: dict) -> str:
    """Prompt ai_gen untuk satu baris non-MATCH."""
    def fmt(x):
        return "tidak ada" if x is None else f"{x:,.2f}"
    return (
        "Anda membantu pengawas OJK menelaah laporan keuangan. Tulis catatan singkat "
        "(maksimal 2 kalimat, Bahasa Indonesia, tanpa pembuka) tentang perbedaan berikut "
        "antara laporan keuangan PDF dan data Excel, beserta kemungkinan penyebab dan hal "
        "yang perlu dikonfirmasi ke entitas. Jangan mengarang angka lain.\n"
        f"Entitas: {baris.get('entity_id')} ({baris.get('doc_type')}), periode: {baris.get('periode')}\n"
        f"Akun: {baris.get('kode_akun')} - {baris.get('nama_akun') or baris.get('label_pdf') or baris.get('label_excel')}\n"
        f"Status: {baris['status']}\n"
        f"Satuan: {baris.get('satuan_pdf')}\n"
        f"Nilai PDF: {fmt(baris.get('nilai_pdf'))} (halaman {baris.get('halaman_pdf') or '-'})\n"
        f"Nilai Excel (disesuaikan ke satuan PDF): {fmt(baris.get('nilai_excel'))}\n"
        f"Selisih: {fmt(baris.get('selisih'))}\n"
        f"Indikasi otomatis: {baris.get('indikasi') or '-'}"
    )
