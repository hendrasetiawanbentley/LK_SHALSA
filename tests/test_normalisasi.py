import pytest

from sikuli.normalisasi import deteksi_skala, normalisasi_teks, parse_angka


@pytest.mark.parametrize("masuk,keluar", [
    ("(1.234.567)", -1234567.0),
    ("1.234.567", 1234567.0),
    ("1,234,567", 1234567.0),
    ("1.234,56", 1234.56),
    ("1,234.56", 1234.56),
    ("Rp 12.500", 12500.0),
    ("-1.000", -1000.0),
    ("−1.000", -1000.0),
    ("-", 0.0),
    ("—", 0.0),
    ("12,5", 12.5),
    ("0", 0.0),
    (1500, 1500.0),
    (2.5, 2.5),
    ("", None),
    (None, None),
    ("Catatan 5", None),
    ("abc", None),
])
def test_parse_angka(masuk, keluar):
    assert parse_angka(masuk) == keluar


def test_normalisasi_teks():
    assert normalisasi_teks("LAPORAN LABA (RUGI) dan Penghasilan") == "laporan laba rugi dan penghasilan"
    assert normalisasi_teks(None) == ""


@pytest.mark.parametrize("teks,skala", [
    ("(Dinyatakan dalam jutaan Rupiah, kecuali dinyatakan lain)", 1_000_000),
    ("(Expressed in thousands of Rupiah)", 1_000),
    ("(Disajikan dalam miliar Rupiah)", 1_000_000_000),
    ("(Angka dalam tabel disajikan dalam miliaran Rupiah, kecuali dinyatakan lain)", 1_000_000_000),
    ("(Dinyatakan dalam Rupiah penuh)", 1),
    ("(Dinyatakan dalam Rupiah, kecuali dinyatakan lain)", None),
    ("Pendapatan sewa ribuan unit", None),
])
def test_deteksi_skala(teks, skala):
    assert deteksi_skala(teks) == skala
