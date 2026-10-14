"""Analisis komparasi angka PDF vs Excel (slide 10).

Langkah: bentuk entity_key -> full outer join per entity_key + kode_akun +
periode -> tentukan status MATCH / DIFFERENT / PDF_ONLY / EXCEL_ONLY.
Logika status ditulis di Python murni supaya sama persis antara uji lokal dan
notebook Databricks; catatan AI ditambahkan di notebook (ai_gen).
"""

from __future__ import annotations

MATCH, DIFFERENT, PDF_ONLY, EXCEL_ONLY = "MATCH", "DIFFERENT", "PDF_ONLY", "EXCEL_ONLY"


def toleransi(nilai_pdf: float, nilai_excel: float, skala_pdf: float, cfg: dict) -> float:
    """Selisih maksimum yang masih dianggap sama.

    Bila PDF disajikan dalam ribuan/jutaan, selisih pembulatan sampai setengah
    satuan penyajian dianggap wajar (toleransi_pembulatan_skala).
    """
    tol = float(cfg.get("toleransi_absolut", 0) or 0)
    tol = max(tol, float(cfg.get("toleransi_relatif", 0) or 0) * max(abs(nilai_pdf), abs(nilai_excel)))
    if cfg.get("toleransi_pembulatan_skala", True) and (skala_pdf or 1) > 1:
        tol = max(tol, 0.5 * skala_pdf)
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


def tentukan_status(nilai_pdf: float | None, nilai_excel: float | None,
                    skala_pdf: float, cfg: dict) -> dict:
    if nilai_pdf is None and nilai_excel is None:
        raise ValueError("minimal salah satu nilai harus ada")
    if nilai_excel is None:
        return {"status": PDF_ONLY, "selisih": None, "selisih_persen": None, "indikasi": None}
    if nilai_pdf is None:
        return {"status": EXCEL_ONLY, "selisih": None, "selisih_persen": None, "indikasi": None}
    selisih = nilai_pdf - nilai_excel
    persen = None if nilai_excel == 0 else round(selisih / abs(nilai_excel) * 100, 4)
    tol = toleransi(nilai_pdf, nilai_excel, skala_pdf, cfg)
    if abs(selisih) <= tol:
        return {"status": MATCH, "selisih": selisih, "selisih_persen": persen, "indikasi": None}
    return {"status": DIFFERENT, "selisih": selisih, "selisih_persen": persen,
            "indikasi": indikasi_selisih(nilai_pdf, nilai_excel, tol)}


def _indeks(baris: list[dict], periode: set[str], sisi: str) -> dict[tuple, dict]:
    """Kunci join -> baris pertama; duplikat dihitung di kolom jumlah_baris_*."""
    hasil: dict[tuple, dict] = {}
    for b in baris:
        if not b.get("kode_akun") or b.get("periode") not in periode or b.get("nilai") is None:
            continue
        kunci = (b["entity_key"], b["kode_akun"], b["periode"])
        if kunci in hasil:
            hasil[kunci][f"jumlah_baris_{sisi}"] += 1
        else:
            hasil[kunci] = {**b, f"jumlah_baris_{sisi}": 1}
    return hasil


def bandingkan(angka_pdf: list[dict], angka_excel: list[dict], cfg_komparasi: dict,
               nama_akun: dict[str, str] | None = None) -> list[dict]:
    """Full outer join angka_pdf <-> angka_excel lalu tentukan status per baris."""
    periode = set(cfg_komparasi.get("periode") or ["berjalan"])
    pdf = _indeks(angka_pdf, periode, "pdf")
    excel = _indeks(angka_excel, periode, "excel")
    nama_akun = nama_akun or {}

    hasil = []
    for kunci in sorted(set(pdf) | set(excel)):
        p, e = pdf.get(kunci), excel.get(kunci)
        acuan = p or e
        nilai_pdf = p["nilai"] if p else None
        nilai_excel = e["nilai"] if e else None
        skala_pdf = (p or {}).get("skala") or 1.0
        hasil.append({
            "entity_key": kunci[0],
            "entity_id": acuan.get("entity_id"),
            "doc_type": acuan.get("doc_type"),
            "tahun": acuan.get("tahun"),
            "kode_akun": kunci[1],
            "nama_akun": nama_akun.get(kunci[1]),
            "periode": kunci[2],
            "seksi": (p or {}).get("seksi") or (e or {}).get("seksi"),
            "nilai_pdf": nilai_pdf,
            "nilai_excel": nilai_excel,
            "skala_pdf": skala_pdf if p else None,
            "halaman_pdf": (p or {}).get("halaman"),
            "sumber_pdf": (p or {}).get("sumber_file"),
            "sumber_excel": f"{e['sumber_file']}!{e['sheet']}!{e['baris']}" if e else None,
            "label_pdf": (p or {}).get("label_di_dokumen"),
            "label_excel": (e or {}).get("label_asli"),
            "jumlah_baris_pdf": (p or {}).get("jumlah_baris_pdf", 0),
            "jumlah_baris_excel": (e or {}).get("jumlah_baris_excel", 0),
            **tentukan_status(nilai_pdf, nilai_excel, skala_pdf, cfg_komparasi),
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
        f"Nilai PDF: {fmt(baris.get('nilai_pdf'))} (halaman {baris.get('halaman_pdf') or '-'})\n"
        f"Nilai Excel: {fmt(baris.get('nilai_excel'))}\n"
        f"Selisih: {fmt(baris.get('selisih'))}\n"
        f"Indikasi otomatis: {baris.get('indikasi') or '-'}"
    )
