"""Jalur AI diuji dengan klien tiruan; tidak ada panggilan ke API sungguhan."""
import json
from types import SimpleNamespace

import pytest
from test_excel_akun import buat_excel
from test_lokal import buat_pdf

from sikuli import ai
from sikuli.akun import PemetaAkun
from sikuli.entitas import info_dari_nama_file
from sikuli.excel import baca_excel
from sikuli.lokal import jalankan


# ---------- KlienAI dengan SDK tiruan ----------
class StreamTiruan:
    def __init__(self, pesan, catat, kwargs):
        self.pesan, catat["kwargs"] = pesan, kwargs

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.pesan


def sdk_tiruan(teks, stop_reason="end_turn"):
    catat = {}
    pesan = SimpleNamespace(stop_reason=stop_reason,
                            content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=teks)])
    stream = lambda **kw: StreamTiruan(pesan, catat, kw)  # noqa: E731
    klien = SimpleNamespace(messages=SimpleNamespace(stream=stream),
                            beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    return klien, catat


def test_minta_json_mengirim_skema_dan_fallback():
    sdk, catat = sdk_tiruan('{"a": 1}')
    k = ai.KlienAI({"model": "claude-opus-5-5", "effort": "medium"}, client=sdk)
    assert k.minta_json("sys", [{"type": "text", "text": "x"}], {"type": "object"}) == {"a": 1}
    kw = catat["kwargs"]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_minta_json_error(stop):
    sdk, _ = sdk_tiruan("{}", stop)
    with pytest.raises(ai.ErrorAI):
        ai.KlienAI({}, client=sdk).minta_json("s", [], {})


def test_buat_klien_tanpa_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ai.buat_klien({"ai": {"aktif": True}}) is None
    assert ai.buat_klien({"ai": {"aktif": False}}) is None


# ---------- tahap pipeline dengan KlienAI tiruan ----------
class KlienTiruan:
    model = "claude-tiruan"

    def __init__(self, gagal_pdf=False):
        self.gagal_pdf, self.panggilan = gagal_pdf, []

    def minta_json(self, system, konten, skema):
        self.panggilan.append(system)
        if system == ai.SYSTEM_PDF:
            if self.gagal_pdf:
                raise ai.ErrorAI("API error tiruan")
            assert konten[0]["type"] == "document" and konten[0]["source"]["media_type"] == "application/pdf"
            return {"seksi": [{"kode": "financial_position", "judul": "LAPORAN POSISI KEUANGAN",
                               "halaman_mulai": 3, "halaman_akhir": 3, "satuan": "jutaan"},
                              {"kode": "income", "judul": "LAPORAN LABA RUGI", "halaman_mulai": 4,
                               "halaman_akhir": 4, "satuan": "jutaan"}],
                    "akun": [{"kode_akun": "FP_KAS", "label_di_dokumen": "Kas dan setara kas",
                              "nilai_berjalan": "1.250", "nilai_lalu": "1.100", "halaman": 3},
                             {"kode_akun": "FP_JUMLAH_ASET", "label_di_dokumen": "Jumlah aset",
                              "nilai_berjalan": "99.999", "nilai_lalu": "", "halaman": 3},   # halusinasi
                             {"kode_akun": "IS_LABA_TAHUN_BERJALAN", "label_di_dokumen": "Laba tahun berjalan",
                              "nilai_berjalan": "703", "nilai_lalu": "650", "halaman": 4}],
                    "catatan": ""}
        if system == ai.SYSTEM_EXCEL:
            label = konten[0]["text"].split("dipetakan:\n")[1].splitlines()
            no = next(i for i, l in enumerate(label) if "belum dikenal" in l)
            return {"pemetaan": [{"no": no, "kode_akun": "FP_JUMLAH_LIABILITAS"}]}
        if system == ai.SYSTEM_ANALISIS:
            return {"catatan_baris": [{"no": 0, "catatan": "Catatan analis AI."}],
                    "kesimpulan": "Sebagian besar sesuai.", "rekomendasi": ["Konfirmasi laba tahun berjalan."]}
        raise AssertionError("system prompt tidak dikenal")


def siapkan(tmp_path):
    pdf, xls = tmp_path / "AAAA_LK_2024.pdf", tmp_path / "AAAA_2024.xlsx"
    buat_pdf(pdf)
    buat_excel(xls)
    return str(pdf), str(xls)


def test_ekstraksi_pdf_ai_dan_verifikasi(tmp_path, cfg, rules):
    pdf, _ = siapkan(tmp_path)
    info = info_dari_nama_file(pdf, cfg, rules)
    teks = ["", "", "Kas dan setara kas 4 1.250 1.100\nJumlah aset 12.000 11.000", "Laba 703 650", ""]
    lokasi, angka, pesan = ai.ekstraksi_pdf(KlienTiruan(), pdf, info, rules, cfg, teks)
    assert [(l["seksi"], l["halaman_mulai"], l["satuan"]) for l in lokasi] == [
        ("financial_position", 3, "jutaan"), ("income", 4, "jutaan")]
    per = {(a["kode_akun"], a["periode"]): a for a in angka}
    assert per[("FP_KAS", "berjalan")]["nilai"] == 1250 and per[("FP_KAS", "berjalan")]["skala"] == 1e6
    assert per[("FP_KAS", "berjalan")]["verifikasi"] == "cocok"
    assert per[("FP_JUMLAH_ASET", "berjalan")]["verifikasi"] == "tidak_ditemukan_di_halaman"
    assert all(a["sumber_ekstraksi"] == "ai" for a in angka)
    assert any("tidak ditemukan di halaman rujukan" in p for p in pesan)


def test_pemetaan_excel_ai(tmp_path, cfg, rules):
    _, xls = siapkan(tmp_path)
    info = info_dari_nama_file(xls, cfg, rules)
    baris, _ = baca_excel(xls, info, rules, PemetaAkun(rules))
    assert ai.pemetaan_excel(KlienTiruan(), baris, rules, "EPP") == 1
    b = next(b for b in baris if b["label_asli"] == "Akun yang belum dikenal")
    assert (b["kode_akun"], b["cara_pemetaan"]) == ("FP_JUMLAH_LIABILITAS", "ai")


def test_jalankan_dengan_ai(tmp_path, cfg, rules):
    pdf, xls = siapkan(tmp_path)
    hasil = jalankan([pdf], [xls], cfg, rules, KlienTiruan())
    assert hasil["mode"] == "AI (claude-tiruan)"
    status = {b["kode_akun"]: b for b in hasil["komparasi"]}
    assert status["FP_KAS"]["status"] == "MATCH" and status["FP_KAS"]["verifikasi_pdf"] == "cocok"
    pertama = hasil["komparasi"][0]
    assert pertama["status"] != "MATCH" and pertama["catatan"] == "Catatan analis AI."
    assert pertama["sumber_catatan"] == "ai"
    assert hasil["kesimpulan"] == [{"entity_key": "AAAA|EPP|2024", "kesimpulan": "Sebagian besar sesuai.",
                                    "rekomendasi": "- Konfirmasi laba tahun berjalan."}]


def test_ai_gagal_kembali_ke_aturan(tmp_path, cfg, rules):
    pdf, xls = siapkan(tmp_path)
    hasil = jalankan([pdf], [xls], cfg, rules, KlienTiruan(gagal_pdf=True))
    assert any("ekstraksi AI gagal" in p and "memakai aturan" in p for p in hasil["peringatan"])
    assert {a["sumber_ekstraksi"] for a in hasil["angka_pdf"]} == {"aturan"}
    assert {b["kode_akun"]: b["status"] for b in hasil["komparasi"]}["FP_KAS"] == "MATCH"


def test_ai_wajib_tidak_kembali_ke_aturan(tmp_path, cfg, rules):
    pdf, xls = siapkan(tmp_path)
    cfg["ai"]["wajib"] = True
    hasil = jalankan([pdf], [xls], cfg, rules, KlienTiruan(gagal_pdf=True))
    assert any("GAGAL" in p and "tidak diproses" in p for p in hasil["peringatan"])
    assert hasil["angka_pdf"] == []
