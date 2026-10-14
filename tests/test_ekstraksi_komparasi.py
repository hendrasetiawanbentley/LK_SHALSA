import json

import pytest

from sikuli.ekstraksi import nama_field, parse_hasil_ekstraksi, skema_ekstraksi, sql_literal
from sikuli.komparasi import bandingkan, prompt_catatan, tentukan_status

AKUN = [{"kode_akun": "FP_KAS", "nama_akun": "Kas dan setara kas", "sinonim": "Cash|Kas"},
        {"kode_akun": "1-ASET", "nama_akun": "Jumlah aset", "sinonim": ""}]
CFG = {"periode": ["berjalan"], "toleransi_absolut": 1, "toleransi_relatif": 0,
       "toleransi_pembulatan_skala": True}


def test_skema_dari_rules():
    skema = json.loads(skema_ekstraksi(AKUN))
    assert set(skema) == {"FP_KAS", "a_1_ASET"}
    assert "Cash" in skema["FP_KAS"]["description"]
    assert skema["FP_KAS"]["properties"]["halaman"]["type"] == "integer"
    assert nama_field("1-ASET") == "a_1_ASET"


@pytest.mark.parametrize("bungkus", [
    lambda v: v,                                          # versi 2.0: nilai polos
    lambda v: {"value": v, "confidence": 0.9},            # versi 2.1: nilai dibungkus
])
def test_parse_hasil_ekstraksi(bungkus):
    hasil = {"response": {
        "FP_KAS": {"nilai_berjalan": bungkus("1.250"), "nilai_lalu": bungkus("(1.100)"),
                   "halaman": bungkus(3), "label_di_dokumen": bungkus("Kas dan setara kas")},
        "a_1_ASET": {"nilai_berjalan": bungkus(None), "nilai_lalu": bungkus("n/a"), "halaman": bungkus(None)},
    }, "error_message": None}
    baris, peringatan = parse_hasil_ekstraksi(json.dumps(hasil), AKUN, {"doc_id": "d"},
                                              zona_atas="(Dinyatakan dalam jutaan Rupiah)")
    assert [(b["kode_akun"], b["periode"], b["nilai"], b["halaman"]) for b in baris] == [
        ("FP_KAS", "berjalan", 1_250_000_000, 3), ("FP_KAS", "lalu", -1_100_000_000, 3)]
    assert baris[0]["doc_id"] == "d" and baris[0]["skala"] == 1_000_000
    assert peringatan == ["1-ASET/lalu: angka tidak terbaca 'n/a'"]


def test_sql_literal():
    assert sql_literal("a'b\\c") == "'a\\'b\\\\c'"


@pytest.mark.parametrize("pdf,excel,skala,status,indikasi", [
    (1000.0, 1000.4, 1, "MATCH", None),
    (1000.0, 1002.0, 1, "DIFFERENT", None),
    (1_250_000_000, 1_250_400_000, 1_000_000, "MATCH", None),       # pembulatan "dalam jutaan"
    (1_250_000_000, 1_251_000_000, 1_000_000, "DIFFERENT", None),
    (-500.0, 500.0, 1, "DIFFERENT", "BEDA_TANDA"),
    (1250.0, 1_250_000.0, 1, "DIFFERENT", "BEDA_SKALA"),
    (5.0, None, 1, "PDF_ONLY", None),
    (None, 5.0, 1, "EXCEL_ONLY", None),
])
def test_tentukan_status(pdf, excel, skala, status, indikasi):
    hasil = tentukan_status(pdf, excel, skala, CFG)
    assert (hasil["status"], hasil["indikasi"]) == (status, indikasi)


def test_toleransi_relatif():
    cfg = {**CFG, "toleransi_relatif": 0.01}
    assert tentukan_status(1000.0, 1009.0, 1, cfg)["status"] == "MATCH"


def test_bandingkan_full_outer_join():
    pdf = [
        {"entity_key": "A|EPP", "kode_akun": "K1", "periode": "berjalan", "nilai": 10.0, "skala": 1, "sumber_file": "a.pdf", "halaman": 3},
        {"entity_key": "A|EPP", "kode_akun": "K1", "periode": "berjalan", "nilai": 99.0, "skala": 1},  # duplikat
        {"entity_key": "A|EPP", "kode_akun": "K2", "periode": "berjalan", "nilai": 5.0, "skala": 1},
        {"entity_key": "A|EPP", "kode_akun": "K1", "periode": "lalu", "nilai": 7.0, "skala": 1},     # periode tidak dibandingkan
    ]
    excel = [
        {"entity_key": "A|EPP", "kode_akun": "K1", "periode": "berjalan", "nilai": 10.0, "sumber_file": "a.xlsx", "sheet": "S", "baris": 9},
        {"entity_key": "A|EPP", "kode_akun": "K3", "periode": "berjalan", "nilai": 1.0, "sumber_file": "a.xlsx", "sheet": "S", "baris": 10},
        {"entity_key": "A|EPP", "kode_akun": None, "periode": "berjalan", "nilai": 1.0},              # tidak terpetakan
    ]
    hasil = {r["kode_akun"]: r for r in bandingkan(pdf, excel, CFG, {"K1": "Kas"})}
    assert {k: r["status"] for k, r in hasil.items()} == {"K1": "MATCH", "K2": "PDF_ONLY", "K3": "EXCEL_ONLY"}
    assert hasil["K1"]["jumlah_baris_pdf"] == 2
    assert hasil["K1"]["nama_akun"] == "Kas"
    assert hasil["K1"]["sumber_excel"] == "a.xlsx!S!9"
    assert "EXCEL_ONLY" in prompt_catatan(hasil["K3"])
