"""OCR Claude untuk halaman scan; klien tiruan, tanpa API."""
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from sikuli import ocr
from sikuli.lokal import jalankan
from sikuli.pdf_lokal import halaman_dari_pdf


def _png():
    import struct, zlib
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * 4 for _ in range(4))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def buat_pdf_scan(path):
    """Halaman 1 berteks, halaman 2 hanya gambar (scan), halaman 3 kosong."""
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawString(72, 800, "LAPORAN POSISI KEUANGAN (Disajikan dalam jutaan Rupiah)")
    c.drawString(72, 780, "Kas dan setara kas 1.250 1.100")
    c.showPage()
    c.drawImage(ImageReader(io.BytesIO(_png())), 72, 400, 300, 300)
    c.showPage()
    c.showPage()
    c.save()


class KlienOCR:
    model = "ocr-tiruan"

    def __init__(self):
        self.permintaan = []

    def minta_json(self, system, konten, skema, kunci=None):
        assert kunci["tahap"] == "ocr"
        self.permintaan.append(kunci["halaman"])
        assert konten[0]["source"]["media_type"] == "application/pdf"
        return {"halaman": [{"halaman": 1, "teks": "LAPORAN LABA RUGI\nLaba tahun berjalan 703 650"}]}


def test_tandai_halaman_scan(tmp_path):
    pdf = tmp_path / "AAAA_LK_2024.pdf"
    buat_pdf_scan(pdf)
    hal = halaman_dari_pdf(str(pdf))
    assert [h.sumber_teks for h in hal] == ["lapisan_teks", "gambar_perlu_ocr", "kosong"]
    assert ocr.perlu_ocr(hal) == [2]


def test_ocr_mengisi_teks_dan_tabel(tmp_path):
    pdf = tmp_path / "AAAA_LK_2024.pdf"
    buat_pdf_scan(pdf)
    hal = halaman_dari_pdf(str(pdf))
    klien = KlienOCR()
    hasil = ocr.ocr_halaman(klien, str(pdf), [2])
    assert klien.permintaan == [[2]] and ocr.terapkan_ocr(hal, hasil, 8) == 1
    assert hal[1].sumber_teks == "ocr_claude" and hal[1].zona_atas.startswith("LAPORAN LABA RUGI")
    baris = ocr.baris_teks({"entity_key": "E", "nama_file": "f.pdf"}, hal,
                           [{"seksi": "income", "halaman_mulai": 2, "halaman_akhir": 2},
                            {"seksi": "calk", "halaman_mulai": 1, "halaman_akhir": 3}])
    assert [(b["halaman"], b["no_baris"], b["seksi"], b["sumber_teks"]) for b in baris] == [
        (1, 1, "calk", "lapisan_teks"), (1, 2, "calk", "lapisan_teks"),
        (2, 1, "income", "ocr_claude"), (2, 2, "income", "ocr_claude"), (3, None, "calk", "kosong")]


def test_jalankan_tanpa_ocr_mencatat_halaman_scan(tmp_path, cfg, rules):
    pdf = tmp_path / "AAAA_LK_2024.pdf"
    buat_pdf_scan(pdf)
    hasil = jalankan([str(pdf)], [], cfg, rules)
    assert any("1 halaman bergambar tanpa teks (hal. 2)" in p for p in hasil["peringatan"])
    assert {b["sumber_teks"] for b in hasil["teks_halaman"]} == {"lapisan_teks", "gambar_perlu_ocr", "kosong"}


def test_jalankan_dengan_ocr_aktif(tmp_path, cfg, rules):
    pdf = tmp_path / "AAAA_LK_2024.pdf"
    buat_pdf_scan(pdf)
    cfg["ai"].update({"ocr": True, "ekstraksi_pdf": False, "catatan_dan_kesimpulan": False})
    hasil = jalankan([str(pdf)], [], cfg, rules, KlienOCR())
    assert any("1 dari 1 halaman scan dibaca dengan OCR Claude" in p for p in hasil["peringatan"])
    assert "Laba tahun berjalan 703 650" in [b["teks"] for b in hasil["teks_halaman"] if b["sumber_teks"] == "ocr_claude"]


def test_rekaman_ocr(tmp_path):
    import json
    from sikuli.ai import KlienRekaman
    (tmp_path / "ocr").mkdir()
    (tmp_path / "ocr" / "X.json").write_text(json.dumps({"halaman": {"5": "teks lima"}}))
    jawab = KlienRekaman(tmp_path).minta_json("s", [], {}, kunci={"tahap": "ocr", "nama_file": "X", "halaman": [4, 5]})
    assert jawab == {"halaman": [{"halaman": 2, "teks": "teks lima"}]}
