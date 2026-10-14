

def test_beda_tanda_dianggap_match_bila_diaktifkan():
    from sikuli.komparasi import tentukan_status
    cfg = {"toleransi_absolut": 1, "toleransi_relatif": 0}
    assert tentukan_status(-5206.0, 5206.0, 1.0, cfg)["status"] == "DIFFERENT"
    hasil = tentukan_status(-5206.0, 5206.0, 1.0, {**cfg, "abaikan_beda_tanda": True})
    assert (hasil["status"], hasil["indikasi"], hasil["selisih"]) == ("MATCH", "BEDA_TANDA", 0.0)
