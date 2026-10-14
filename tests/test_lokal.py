"""Pipeline tanpa Databricks dengan PDF sungguhan (dibuat reportlab) dan Excel."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from test_excel_akun import buat_excel

from sikuli.ekstraksi_lokal import pecah_baris
from sikuli.lokal import jalankan, main, tulis_excel

HALAMAN = [
    ["PT CONTOH EMITEN TBK", "Laporan Keuangan 31 Desember 2024"],
    ["DAFTAR ISI", "Laporan Posisi Keuangan 1", "Laporan Laba Rugi 3", "Laporan Arus Kas 5",
     "Catatan atas Laporan Keuangan 6"],
    ["PT CONTOH EMITEN TBK", "LAPORAN POSISI KEUANGAN", "31 Desember 2024 dan 2023",
     "(Dinyatakan dalam jutaan Rupiah)", "Catatan 2024 2023",
     "Kas dan setara kas 4 1.250 1.100 Cash and cash equivalents",
     "Total aset lancar 5.400 4.900", "Jumlah aset 12.000 11.000", "Jumlah liabilitas (7.000) 6.500"],
    ["PT CONTOH EMITEN TBK", "LAPORAN LABA RUGI DAN PENGHASILAN KOMPREHENSIF LAIN",
     "(Dinyatakan dalam jutaan Rupiah)", "Pendapatan usaha 20 9.000 8.000",
     "Laba (rugi) tahun berjalan 701 650"],
    ["PT CONTOH EMITEN TBK", "CATATAN ATAS LAPORAN KEUANGAN", "1. UMUM"],
]
FOOTER = "Catatan atas laporan keuangan terlampir merupakan bagian yang tidak terpisahkan"


def buat_pdf(path):
    c = canvas.Canvas(str(path), pagesize=A4)
    for baris in HALAMAN:
        y = 800
        for teks in baris:
            c.drawString(50, y, teks)
            y -= 18
        c.drawString(50, 40, FOOTER)
        c.showPage()
    c.save()


def test_pecah_baris():
    assert pecah_baris("Kas dan setara kas 4 1.250 (1.100) Cash") == ("Kas dan setara kas", ["1.250", "(1.100)"], "Cash")
    assert pecah_baris("Pendapatan 2c,5 9.000 8.000") == ("Pendapatan", ["9.000", "8.000"], "")
    assert pecah_baris("Kas 4 1.250") == ("Kas", ["1.250"], "")
    assert pecah_baris("Beban lain-lain - 300") == ("Beban lain-lain", ["-", "300"], "")
    assert pecah_baris("LAPORAN POSISI KEUANGAN") is None


def test_pipeline_lokal_pdf_dan_excel(tmp_path, cfg, rules):
    pdf, xls = tmp_path / "AAAA_LK_2024.pdf", tmp_path / "AAAA_2024.xlsx"
    buat_pdf(pdf)
    buat_excel(xls)
    hasil = jalankan([str(pdf)], [str(xls)], cfg, rules)

    assert [(l["seksi"], l["halaman_mulai"], l["halaman_akhir"]) for l in hasil["lokasi_seksi"]] == [
        ("financial_position", 3, 3), ("income", 4, 4), ("calk", 5, 5)]
    status = {b["kode_akun"]: b["status"] for b in hasil["komparasi"]}
    assert status["FP_KAS"] == "MATCH"                 # 1.250 juta vs 1.250.400.000
    assert status["FP_JUMLAH_ASET_LANCAR"] == "MATCH"
    assert status["FP_JUMLAH_ASET"] == "MATCH"
    assert status["FP_JUMLAH_LIABILITAS"] == "PDF_ONLY"
    assert status["IS_PENDAPATAN"] == "PDF_ONLY"
    assert status["IS_LABA_TAHUN_BERJALAN"] == "DIFFERENT"   # 701 juta vs 700 juta
    beda = next(b for b in hasil["komparasi"] if b["kode_akun"] == "IS_LABA_TAHUN_BERJALAN")
    assert beda["selisih"] == 1_000_000 and "Selisih 1,000,000" in beda["catatan"]
    assert hasil["ringkasan"][0]["entity_key"] == "AAAA|EPP|2024"

    out = tmp_path / "hasil.xlsx"
    tulis_excel(hasil, out)
    assert out.stat().st_size > 0


def test_cli(tmp_path, capsys):
    (tmp_path / "pdf").mkdir()
    (tmp_path / "xls").mkdir()
    buat_pdf(tmp_path / "pdf" / "AAAA_LK_2024.pdf")
    buat_excel(tmp_path / "xls" / "AAAA_2024.xlsx")
    out = tmp_path / "hasil"
    assert main(["--pdf", str(tmp_path / "pdf"), "--excel", str(tmp_path / "xls"), "--out-dir", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == {
        "hasil_komparasi.xlsx", "ringkasan.md", "ringkasan.csv", "komparasi.csv", "angka_pdf.csv",
        "angka_excel.csv", "lokasi_seksi.csv", "peringatan.csv"}
    md = (out / "ringkasan.md").read_text()
    assert "| AAAA\\|EPP\\|2024 | 3 | 1 | 2 | 0 | 50.0 |" in md
    assert "IS_LABA_TAHUN_BERJALAN" in md
    assert (out / "komparasi.csv").read_text(encoding="utf-8-sig").startswith("entity_key,seksi,kode_akun")


def test_cli_tanpa_file(tmp_path):
    assert main(["--pdf", str(tmp_path / "x"), "--excel", str(tmp_path / "y"), "--out-dir", str(tmp_path / "o")]) == 0
    assert "Belum ada file" in (tmp_path / "o" / "ringkasan.md").read_text()
