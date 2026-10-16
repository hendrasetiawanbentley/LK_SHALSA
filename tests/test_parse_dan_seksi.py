from helpers import dokumen_contoh, parsed_v2, tabel

from sikuli.parse_pdf import halaman_dari_parse, tabel_html_ke_teks
from sikuli.seksi import deteksi_seksi, kompilasi_pola

CFG_DETEKSI = {"min_seksi_daftar_isi": 3, "label_tidak_dikenal": "tidak_dikenal", "label_daftar_isi": "daftar_isi"}


def test_tabel_html_ke_teks():
    assert tabel_html_ke_teks(tabel([["Kas", "1.000 &amp; 2"], ["Bank", "3"]])) == "Kas | 1.000 & 2\nBank | 3"


def test_halaman_dan_zona_atas_tanpa_footer():
    hal = halaman_dari_parse(dokumen_contoh(), baris_zona_atas=8)
    assert len(hal) == 9
    assert hal[2].nomor == 3
    assert "LAPORAN POSISI KEUANGAN" in hal[2].zona_atas
    assert "Kas dan setara kas | 4 | 1.250 | 1.100" in hal[2].teks
    assert "Catatan atas laporan keuangan terlampir" in hal[2].teks
    assert "terlampir" not in hal[2].zona_atas


def test_page_id_di_level_elemen_dan_halaman_kosong():
    parsed = {"document": {"pages": [{"id": 0}, {"id": 1}, {"id": 2}],
                           "elements": [{"id": 0, "type": "text", "content": "a", "page_id": 0},
                                        {"id": 1, "type": "text", "content": "b", "page_id": 2}]}}
    hal = halaman_dari_parse(parsed)
    assert [h.teks for h in hal] == ["a", "", "b"]


def test_format_lama_pages_content():
    parsed = {"document": {"pages": [{"id": 0, "content": "LAPORAN ARUS KAS\nisi"}]}}
    assert halaman_dari_parse(parsed)[0].zona_atas == "LAPORAN ARUS KAS\nisi"


def test_deteksi_seksi_alur_slide5(rules):
    pola = kompilasi_pola(rules.mapping_seksi)
    hal = halaman_dari_parse(dokumen_contoh())
    label, lokasi = deteksi_seksi([h.zona_atas for h in hal], pola, "EPP", CFG_DETEKSI)
    assert [l["seksi"] for l in label] == [
        "sampul",               # sampul: halaman sebelum seksi pertama
        "sampul",               # daftar isi (>= 3 seksi cocok) sebelum seksi pertama ikut sampul
        "financial_position",
        "financial_position",   # judul diulang "(lanjutan)"
        "income",
        "equity",               # "penghasilan komprehensif" di header tabel kalah oleh judul yang lebih awal
        "cashflow",
        "calk",
        "calk",                 # tanpa judul: lanjutkan seksi sebelumnya
    ]
    assert [(l["seksi"], l["halaman_mulai"], l["halaman_akhir"]) for l in lokasi] == [
        ("sampul", 1, 2), ("financial_position", 3, 4), ("income", 5, 5), ("equity", 6, 6),
        ("cashflow", 7, 7), ("calk", 8, 9)]


def test_pola_khusus_rd_dan_laba_rugi_berkurung(rules):
    pola = kompilasi_pola(rules.mapping_seksi)
    zona = ["LAPORAN KINERJA KEUANGAN", "LAPORAN LABA (RUGI)"]
    label_rd, _ = deteksi_seksi(zona, pola, "RD", CFG_DETEKSI)
    label_epp, _ = deteksi_seksi(zona, pola, "EPP", CFG_DETEKSI)
    assert [l["seksi"] for l in label_rd] == ["rd_performance", "income"]
    assert [l["seksi"] for l in label_epp] == ["sampul", "income"]


def test_maks_halaman_dan_regex():
    pola = kompilasi_pola([
        {"kode": "calk", "entitas": "Semua", "pola": "catatan atas laporan keuangan", "maks_halaman": "2"},
        {"kode": "lampiran", "entitas": "Semua", "pola": r"^lampiran \d+", "maks_halaman": ""},
    ])
    zona = ["Catatan atas laporan keuangan", "lanjut", "lanjut lagi", "LAMPIRAN 1 informasi", "x"]
    label, lokasi = deteksi_seksi(zona, pola, "EPP", CFG_DETEKSI)
    assert [l["seksi"] for l in label] == ["calk", "calk", "tidak_dikenal", "lampiran", "lampiran"]
    assert lokasi[0]["halaman_akhir"] == 2


def test_halaman_tanpa_teks_tidak_memperpanjang_seksi():
    pola = kompilasi_pola([
        {"kode": "laporan_auditor", "entitas": "Semua", "pola": "laporan auditor independen"},
        {"kode": "financial_position", "entitas": "Semua", "pola": "laporan posisi keuangan"},
    ])
    zona = ["PT Contoh Laporan keuangan", "Laporan Auditor Independen", "lanjutan opini", "", "",
            "LAPORAN POSISI KEUANGAN"]
    label, lokasi = deteksi_seksi(zona, pola, "EPP", CFG_DETEKSI)
    assert [l["seksi"] for l in label] == ["sampul", "laporan_auditor", "laporan_auditor", "tanpa_teks",
                                           "tanpa_teks", "financial_position"]
    assert [(l["seksi"], l["halaman_mulai"], l["halaman_akhir"]) for l in lokasi] == [
        ("sampul", 1, 1), ("laporan_auditor", 2, 3), ("financial_position", 6, 6)]
