from sikuli.entitas import info_dari_nama_file
from sikuli.rules import berlaku_untuk, validasi_rules


def test_rules_bawaan_valid(rules):
    assert validasi_rules(rules) == []


def test_berlaku_untuk():
    assert berlaku_untuk("Semua", "RD")
    assert berlaku_untuk("RD", "rd")
    assert berlaku_untuk("EPP,MI", "MI")
    assert not berlaku_untuk("RD", "EPP")
    assert not berlaku_untuk("RD", None)


def test_entitas_dari_prefiks_dan_daftar(cfg, rules):
    info = info_dari_nama_file("/Volumes/x/docs/ALL/AAAA_LK_Audit_2024.pdf", cfg, rules)
    assert info["entity_id"] == "AAAA"
    assert info["doc_type"] == "EPP"
    assert info["tahun"] == "2024"
    assert info["entity_key"] == "AAAA|EPP|2024"
    excel = info_dari_nama_file("AAAA_2024.xlsx", cfg, rules)
    assert excel["entity_key"] == info["entity_key"]


def test_entitas_tidak_terdaftar(cfg, rules):
    info = info_dari_nama_file("ZZZZ_2024.pdf", cfg, rules)
    assert info["entity_id"] == "ZZZZ"
    assert info["doc_type"] is None
    assert not info["entitas_dikenal"]


def test_doc_type_dari_nama_file(cfg, rules):
    cfg["entitas"]["pola_nama_file"] = r"^(?P<doc_type>EPP|MI|RD)_(?P<entity_id>[A-Za-z0-9]+)_(?P<tahun>\d{4})"
    info = info_dari_nama_file("rd_RDXX_2023.pdf", cfg, rules)
    assert (info["entity_id"], info["doc_type"], info["tahun"]) == ("RDXX", "RD", "2023")
