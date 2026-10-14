"""Alur lengkap secara lokal: parse PDF -> seksi -> ekstraksi -> Excel -> komparasi.

ai_parse_document dan ai_extract diganti tiruan; selebihnya kode yang sama
dengan yang dipanggil notebook Databricks.
"""
import json

from helpers import dokumen_contoh
from test_excel_akun import buat_excel

from sikuli.akun import PemetaAkun
from sikuli.ekstraksi import nama_field, parse_hasil_ekstraksi
from sikuli.entitas import info_dari_nama_file
from sikuli.excel import baca_excel
from sikuli.komparasi import bandingkan
from sikuli.normalisasi import normalisasi_teks
from sikuli.pipeline import buat_permintaan_ekstraksi, konteks_permintaan, proses_dokumen_pdf
from sikuli.seksi import kompilasi_pola


def ai_extract_tiruan(teks: str, akun: list[dict]) -> str:
    """Cari baris tabel 'label | catatan | 2024 | 2023' untuk setiap akun."""
    respons, halaman = {}, None
    for baris in teks.splitlines():
        if baris.startswith("[HALAMAN "):
            halaman = int(baris[9:-1])
            continue
        sel = [s.strip() for s in baris.split("|")]
        for a in akun:
            nama = {normalisasi_teks(x) for x in [a["nama_akun"], *a.get("sinonim", "").split("|")] if x}
            if normalisasi_teks(sel[0]) in nama and len(sel) >= 4:
                respons[nama_field(a["kode_akun"])] = {
                    "nilai_berjalan": sel[-2], "nilai_lalu": sel[-1],
                    "halaman": halaman, "label_di_dokumen": sel[0]}
    return json.dumps({"response": respons, "error_message": None})


def test_alur_parsing_sampai_komparasi(tmp_path, cfg, rules):
    pola = kompilasi_pola(rules.mapping_seksi)
    hasil_pdf = proses_dokumen_pdf("/Volumes/sikuli/lk/sumber/docs/ALL/AAAA_LK_2024.pdf",
                                   json.dumps(dokumen_contoh()), cfg, rules, pola)
    assert hasil_pdf["peringatan"] == []
    assert len(hasil_pdf["teks"]) == 9

    permintaan = buat_permintaan_ekstraksi(hasil_pdf["teks"], cfg, rules)
    # equity tidak punya akun di rules contoh, calk dilewati
    assert sorted({p["seksi"] for p in permintaan}) == ["cashflow", "financial_position", "income"]

    angka_pdf = []
    for p in permintaan:
        baris, peringatan = parse_hasil_ekstraksi(ai_extract_tiruan(p["teks"], p["akun"]), p["akun"],
                                                  konteks_permintaan(p), p["zona_atas"])
        assert peringatan == []
        angka_pdf.extend(baris)

    path_excel = tmp_path / "AAAA_2024.xlsx"
    buat_excel(path_excel)
    info = info_dari_nama_file(str(path_excel), cfg, rules)
    angka_excel, _ = baca_excel(str(path_excel), info, rules, PemetaAkun(rules))

    nama = {a["kode_akun"]: a["nama_akun"] for a in rules.rules_akun}
    hasil = {r["kode_akun"]: r for r in bandingkan(angka_pdf, angka_excel, cfg["komparasi"], nama)}
    assert {k: r["status"] for k, r in hasil.items()} == {
        "FP_KAS": "MATCH",                       # 1.250 juta vs 1.250.400.000 (pembulatan)
        "FP_JUMLAH_ASET_LANCAR": "MATCH",
        "FP_JUMLAH_ASET": "MATCH",
        "FP_JUMLAH_LIABILITAS": "PDF_ONLY",
        "FP_JUMLAH_EKUITAS": "PDF_ONLY",
        "IS_PENDAPATAN": "PDF_ONLY",
        "IS_LABA_TAHUN_BERJALAN": "MATCH",
        "CF_ARUS_KAS_OPERASI": "PDF_ONLY",
    }
    assert hasil["FP_JUMLAH_LIABILITAS"]["nilai_pdf"] == -7_000_000_000
    assert hasil["FP_JUMLAH_ASET"]["halaman_pdf"] == 4
    assert hasil["FP_KAS"]["entity_key"] == "AAAA|EPP|2024"
