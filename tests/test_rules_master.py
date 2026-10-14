from openpyxl import Workbook

from sikuli.rules import alias_dari_deskripsi, baca_master, muat_rules, seksi_dari_bagian, validasi_rules


def test_alias_dari_deskripsi():
    d = ("Nama Akun : Kas dan Setara Kas',  'Kas dan setara kas', 'Cash and cash equivalents'. \n\n"
         "Keterangan Akun :Ambil nilai untuk periode berjalan")
    assert alias_dari_deskripsi(d) == ["Kas dan Setara Kas", "Kas dan setara kas", "Cash and cash equivalents"]
    assert alias_dari_deskripsi("MKBD. Aliases: 'Modal Kerja Bersih Disesuaikan', 'MKBD'. Found in the notes") == [
        "Modal Kerja Bersih Disesuaikan", "MKBD"]
    assert alias_dari_deskripsi("Nama Akun; 'Total Pendapatan'  Penjelasan Akun: ...") == ["Total Pendapatan"]
    assert alias_dari_deskripsi(None) == []


def test_seksi_dari_bagian():
    gabungan = "Laporan Perubahan Modal (epp) / Laporan Posisi Keuangan (mi)"
    assert seksi_dari_bagian(gabungan, "EPP") == "equity"
    assert seksi_dari_bagian(gabungan, "MI") == "financial_position"
    assert seksi_dari_bagian("Catatan Atas Laporan Keuangan (CaLK)", "RD") == "calk"
    assert seksi_dari_bagian("Laporan Lain", "RD") is None


def buat_master(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Master"
    ws.append(["no", "entitas", "bagian", "akun", "field_key", "dtype", "description"])
    ws.append([1, "EPP", "Laporan Posisi Keuangan", "Total Aset", "total_aset", "number",
               "Nama Akun: 'Total Aset', 'Jumlah aset', 'Total assets'\n\nKeterangan Akun : ambil periode berjalan"])
    ws.append([2, "RD", "Laporan Kinerja Keuangan", "Total Pendapatan", "total_pendapatan", "number", "Nama Akun: 'Total Pendapatan'"])
    ws.append([3, "MI", "Laporan Aneh", "X", "x", "number", ""])
    wb.save(path)


def test_muat_rules_dari_master(tmp_path):
    folder = tmp_path / "rules"
    folder.mkdir()
    buat_master(folder / "Extraction_Rules.xlsx")
    rules = muat_rules(folder, "config")          # konfigurasi teknis dari config/ repo
    a = rules.rules_akun[0]
    assert (a["doc_type"], a["seksi"], a["kode_akun"], a["nama_akun"]) == ("EPP", "financial_position", "total_aset", "Total Aset")
    assert a["sinonim"] == "Jumlah aset|Total assets"
    assert "ambil periode berjalan" in a["deskripsi"]
    assert rules.akun_untuk("RD", "rd_performance")[0]["kode_akun"] == "total_pendapatan"
    masalah = validasi_rules(rules)
    assert any("Laporan Aneh" in m for m in masalah)


def test_rules_repo_valid():
    rules = muat_rules("rules", "config")
    assert validasi_rules(rules) == []
    assert len(rules.rules_akun) > 100
