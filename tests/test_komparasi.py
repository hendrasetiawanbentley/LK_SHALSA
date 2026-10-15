

def test_beda_tanda_dianggap_match_bila_diaktifkan():
    from sikuli.komparasi import tentukan_status
    cfg = {"toleransi_absolut": 1, "toleransi_relatif": 0}
    assert tentukan_status(-5206.0, 5206.0, 1.0, cfg)["status"] == "DIFFERENT"
    hasil = tentukan_status(-5206.0, 5206.0, 1.0, {**cfg, "abaikan_beda_tanda": True})
    assert (hasil["status"], hasil["indikasi"], hasil["selisih"]) == ("MATCH", "BEDA_TANDA", 0.0)


def test_toleransi_digit_terakhir_dan_tanda_diabaikan():
    from sikuli.komparasi import desimal_teks, tentukan_status
    cfg = {"toleransi_digit_terakhir": 1, "abaikan_beda_tanda": True}
    assert tentukan_status(376.0, 374.77, 1.0, cfg)["status"] == "MATCH"            # 374,77 -> 375
    assert tentukan_status(20558.0, 20559.775, 1e6, cfg)["status"] == "DIFFERENT"   # 20.560: selisih 2
    hasil = tentukan_status(-244431.0, 244430.4, 1e6, cfg)                          # beda arah + selisih 1
    assert (hasil["status"], hasil["indikasi"]) == ("MATCH", "BEDA_TANDA")
    assert tentukan_status(4397.88, 4397.8778, 1.0, cfg, 2)["status"] == "MATCH"
    assert tentukan_status(487368.88, 487368.50, 1.0, cfg, 2)["status"] == "DIFFERENT"
    assert tentukan_status(-208.43, 208.42, 1.0, cfg, 2)["status"] == "MATCH"
    assert tentukan_status(-5.0, 5.0, 1.0, {**cfg, "abaikan_beda_tanda": False})["status"] == "DIFFERENT"
    assert [desimal_teks(t, v) for t, v in [("4.397,88", 4397.88), ("6.929", 6929), ("1,068,697.19", 1068697.19),
                                            ("709.863.919,7765", 709863919.7765), ("(1.115.249.979)", -1115249979)]] == [2, 0, 2, 4, 0]
