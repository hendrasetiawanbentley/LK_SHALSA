"""KlienRekaman: jawaban AI yang sudah direkam (folder hasil_ai) diputar ulang tanpa API."""
import json
from types import SimpleNamespace

import pytest
from test_ai import siapkan

from sikuli import ai
from sikuli.komparasi import tentukan_status
from sikuli.lokal import jalankan, main, turunan_periode_lalu


def rekam(folder, entity_key):
    (folder / "pdf").mkdir(parents=True)
    (folder / "analisis").mkdir()
    (folder / "pdf" / "AAAA_LK_2024.json").write_text(json.dumps({
        "seksi": [{"kode": "financial_position", "judul": "LAPORAN POSISI KEUANGAN", "halaman_mulai": 3,
                   "halaman_akhir": 3, "satuan": "jutaan"}],
        "akun": [{"kode_akun": "FP_KAS", "label_di_dokumen": "Kas dan setara kas", "nilai_berjalan": "1.250",
                  "nilai_lalu": "1.100", "halaman": 3},
                 {"kode_akun": "FP_JUMLAH_LIABILITAS", "label_di_dokumen": "Jumlah liabilitas",
                  "nilai_berjalan": "9", "nilai_lalu": "", "halaman": 3}],
        "catatan": ""}))
    (folder / "pemetaan_excel_EPP.json").write_text(json.dumps({
        "label": {}, "turunan": [{"kode_akun": "FP_JUMLAH_LIABILITAS", "label": ["Akun  yang belum dikenal"]}]}))
    (folder / "analisis" / f"{entity_key}.json").write_text(json.dumps({
        "catatan": {"FP_JUMLAH_LIABILITAS/berjalan": "Catatan rekaman."},
        "kesimpulan": "Kesimpulan rekaman.", "rekomendasi": ["Tindak lanjut A"]}))


def test_jalankan_dengan_rekaman(tmp_path, cfg, rules):
    pdf, xls = siapkan(tmp_path)
    rekam(tmp_path / "rekaman", "AAAA|EPP|2024")
    hasil = jalankan([pdf], [xls], cfg, rules, ai.KlienRekaman(tmp_path / "rekaman"))
    per = {b["kode_akun"]: b for b in hasil["komparasi"]}
    assert per["FP_KAS"]["status"] == "MATCH"
    liab = per["FP_JUMLAH_LIABILITAS"]                     # PDF 9 juta vs Excel turunan 5 / 1 juta
    assert liab["status"] == "DIFFERENT" and liab["label_excel"] == "Akun yang belum dikenal"
    assert (liab["catatan"], liab["sumber_catatan"]) == ("Catatan rekaman.", "ai")
    assert hasil["kesimpulan"][0]["rekomendasi"] == "- Tindak lanjut A"


def test_rekaman_tidak_ada_menjadi_error(tmp_path):
    with pytest.raises(ai.ErrorAI, match="rekaman AI tidak ada"):
        ai.KlienRekaman(tmp_path).minta_json("s", [], {}, kunci={"tahap": "pdf", "nama_file": "X"})


def test_cli_ai_rekaman_tanpa_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "pdf").mkdir()
    (tmp_path / "xl").mkdir()
    rc = main(["--pdf", str(tmp_path / "pdf"), "--excel", str(tmp_path / "xl"), "--out-dir", str(tmp_path / "o"),
               "--ai-rekaman", str(tmp_path / "rek")])
    assert rc == 0


def test_turunan_periode_lalu():
    rules = SimpleNamespace(rules_akun=[{"kode_akun": "total_aset", "doc_type": "EPP"},
                                        {"kode_akun": "total_aset_periode_sebelumnya", "doc_type": "EPP"}])
    baris = [{"kode_akun": "total_aset", "periode": "berjalan", "nilai": 10.0, "label_asli": "Jumlah aset"},
             {"kode_akun": "total_aset", "periode": "lalu", "nilai": 8.0, "label_asli": "Jumlah aset"}]
    assert turunan_periode_lalu(baris, rules, "EPP") == 1
    assert baris[-1] | {} == {"kode_akun": "total_aset_periode_sebelumnya", "periode": "berjalan", "nilai": 8.0,
                              "label_asli": "Jumlah aset (kolom periode lalu)", "cara_pemetaan": "turunan_periode_lalu"}


def test_nihil_dianggap_match():
    cfg = {"toleransi_absolut": 1, "toleransi_relatif": 0, "nihil_dianggap_match": True}
    assert tentukan_status(0.0, None, 1.0, cfg)["indikasi"] == "NIHIL"
    assert tentukan_status(None, 0.0, 1.0, cfg)["status"] == "MATCH"
    assert tentukan_status(5.0, None, 1.0, cfg)["status"] == "PDF_ONLY"


def test_rekaman_repo_memakai_kode_akun_master():
    from pathlib import Path
    from sikuli.rules import muat_rules
    root = Path(__file__).resolve().parents[1]
    kode = {a["kode_akun"] for a in muat_rules(root / "rules", root / "config").rules_akun}
    for f in (root / "hasil_ai" / "pdf").glob("*.json"):
        data = json.loads(f.read_text())
        assert {a["kode_akun"] for a in data["akun"]} <= kode, f.name
    for f in (root / "hasil_ai").glob("pemetaan_excel_*.json"):
        data = json.loads(f.read_text())
        assert set(data["label"].values()) | {t["kode_akun"] for t in data["turunan"]} <= kode, f.name
