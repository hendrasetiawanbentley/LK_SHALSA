"""OCR oleh Claude untuk halaman PDF yang tidak punya lapisan teks (hasil scan).

Halaman bertanda `gambar_perlu_ocr` (lihat pdf_lokal) dikirim ke Claude per kelompok kecil
sebagai PDF potongan; Claude menyalin teksnya baris per baris. Hasilnya mengisi teks halaman
sehingga dipakai untuk deteksi seksi (mode aturan), verifikasi angka AI, dan sheet Teks_PDF.
Aktifkan dengan `ai.ocr: true` di config/pipeline.yaml (butuh ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from .parse_pdf import Halaman

SYSTEM_OCR = """Anda melakukan OCR halaman laporan keuangan (PDF hasil scan) untuk pengawas OJK.
Salin seluruh teks setiap halaman apa adanya, baris demi baris dari atas ke bawah.
- Satu baris tabel = satu baris teks; pisahkan kolom dengan " | ".
- Salin angka PERSIS seperti tercetak, termasuk tanda kurung, tanda minus, dan pemisah
  ribuan/desimal. Jangan membulatkan, menghitung, atau menerjemahkan.
- Bagian yang tidak terbaca tulis "[tidak terbaca]". Jangan menebak.
- `halaman` adalah urutan halaman di PDF yang Anda terima (mulai dari 1)."""

SKEMA_OCR = {
    "type": "object", "additionalProperties": False, "required": ["halaman"],
    "properties": {"halaman": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["halaman", "teks"],
        "properties": {"halaman": {"type": "integer"}, "teks": {"type": "string"}}}}},
}


def perlu_ocr(halaman: list[Halaman]) -> list[int]:
    return [h.nomor for h in halaman if h.sumber_teks == "gambar_perlu_ocr"]


def _potong_pdf(path: str, nomor: list[int]) -> bytes:
    from pypdf import PdfReader, PdfWriter

    reader, writer = PdfReader(path), PdfWriter()
    for n in nomor:
        writer.add_page(reader.pages[n - 1])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def ocr_halaman(klien, path: str, nomor: list[int], per_permintaan: int = 10) -> dict[int, str]:
    """Kembalikan {nomor halaman: teks} untuk halaman yang berhasil dibaca Claude."""
    hasil: dict[int, str] = {}
    for i in range(0, len(nomor), per_permintaan):
        kelompok = nomor[i:i + per_permintaan]
        data = base64.standard_b64encode(_potong_pdf(path, kelompok)).decode()
        jawaban = klien.minta_json(SYSTEM_OCR, [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
            {"type": "text", "text": f"PDF ini berisi {len(kelompok)} halaman. Salin teks setiap halaman."},
        ], SKEMA_OCR, kunci={"tahap": "ocr", "nama_file": Path(path).stem, "halaman": kelompok})
        for item in jawaban.get("halaman", []):
            urut = item.get("halaman", 0)
            if 1 <= urut <= len(kelompok) and (item.get("teks") or "").strip():
                hasil[kelompok[urut - 1]] = item["teks"]
    return hasil


def terapkan_ocr(halaman: list[Halaman], teks_ocr: dict[int, str], baris_zona_atas: int) -> int:
    n = 0
    for h in halaman:
        if h.nomor in teks_ocr:
            h.teks = teks_ocr[h.nomor]
            baris = [b.strip() for b in h.teks.splitlines() if b.strip()]
            h.zona_atas = "\n".join(baris[:baris_zona_atas])
            h.sumber_teks = "ocr_claude"
            n += 1
    return n


def baris_teks(info: dict, halaman: list[Halaman], lokasi: list[dict]) -> list[dict]:
    """Baris tabel Teks_PDF: satu baris per baris teks; halaman kosong tetap satu baris."""
    def seksi(n: int) -> str | None:
        # Seksi tersempit yang mencakup halaman ini (CaLK biasanya rentang paling lebar).
        cocok = [s for s in lokasi if (s.get("halaman_mulai") or 0) <= n <= (s.get("halaman_akhir") or 0)]
        cocok.sort(key=lambda s: s["halaman_akhir"] - s["halaman_mulai"])
        return cocok[0]["seksi"] if cocok else None

    hasil = []
    for h in halaman:
        dasar = {"entity_key": info["entity_key"], "nama_file": info["nama_file"], "halaman": h.nomor,
                 "seksi": seksi(h.nomor), "sumber_teks": h.sumber_teks}
        baris = [b for b in h.teks.splitlines() if b.strip()]
        if not baris:
            hasil.append({**dasar, "no_baris": None, "teks": ""})
        for i, b in enumerate(baris, start=1):
            hasil.append({**dasar, "no_baris": i, "teks": b})
    return hasil
