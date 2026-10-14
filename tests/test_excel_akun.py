from openpyxl import Workbook

from sikuli.akun import PemetaAkun
from sikuli.entitas import info_dari_nama_file
from sikuli.excel import baca_excel


def buat_excel(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Posisi Keuangan"
    ws.append(["PT Contoh Emiten Tbk"])
    ws.append(["Laporan posisi keuangan"])
    ws.append([])
    ws.append(["Akun", "2024", "2023"])
    ws.append(["ASET", None, None])                         # subjudul tanpa angka
    ws.append(["Kas dan setara kas - bersih", 1_250_400_000, 1_100_000_000])  # via mapping_akun_excel
    ws.append(["Total aset lancar", 5_400_000_000, "4.900.000.000"])          # via sinonim
    ws.append(["Jumlah aset", 12_000_000_000, 11_000_000_000])
    ws.append(["Akun yang belum dikenal", 5, 4])
    ws2 = wb.create_sheet("Laba Rugi")
    for _ in range(4):
        ws2.append([])
    ws2.append(["Laba (rugi) tahun berjalan", 700_000_000, 650_000_000])
    wb.save(path)


def test_baca_excel(tmp_path, cfg, rules):
    path = tmp_path / "AAAA_2024.xlsx"
    buat_excel(path)
    info = info_dari_nama_file(str(path), cfg, rules)
    baris, peringatan = baca_excel(str(path), info, rules, PemetaAkun(rules))
    assert peringatan == ["AAAA_2024.xlsx: sheet 'Arus Kas' tidak ditemukan"]
    berjalan = {(b["label_asli"]): b for b in baris if b["periode"] == "berjalan"}
    assert berjalan["Kas dan setara kas - bersih"]["kode_akun"] == "FP_KAS"
    assert berjalan["Kas dan setara kas - bersih"]["cara_pemetaan"] == "mapping_akun_excel"
    assert berjalan["Total aset lancar"]["kode_akun"] == "FP_JUMLAH_ASET_LANCAR"
    assert berjalan["Laba (rugi) tahun berjalan"]["kode_akun"] == "IS_LABA_TAHUN_BERJALAN"
    assert berjalan["Akun yang belum dikenal"]["kode_akun"] is None
    assert "ASET" not in berjalan
    lalu = [b for b in baris if b["label_asli"] == "Total aset lancar" and b["periode"] == "lalu"]
    assert lalu[0]["nilai"] == 4_900_000_000
    assert berjalan["Jumlah aset"]["entity_key"] == "AAAA|EPP|2024"
    assert berjalan["Jumlah aset"]["baris"] == 8


def test_pemeta_ambigu_dan_seksi_lain(rules):
    pemeta = PemetaAkun(rules)
    assert pemeta.petakan("Total assets", "EPP", "income") == ("FP_JUMLAH_ASET", "rules_akun_seksi_lain")
    assert pemeta.petakan("Jumlah aset", "RD", "financial_position") == ("RD_JUMLAH_ASET", "rules_akun")
    assert pemeta.petakan("", "EPP", "income") == (None, "label_kosong")
