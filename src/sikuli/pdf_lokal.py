"""Parse PDF tanpa Databricks memakai pdfplumber (pengganti ai_parse_document).

Hanya untuk PDF yang teksnya bisa diseleksi. PDF hasil scan (gambar) tidak
punya lapisan teks sehingga perlu OCR terlebih dahulu.
"""

from __future__ import annotations

import pdfplumber

from .parse_pdf import Halaman

# Bagian bawah halaman (footer seperti "Catatan atas laporan keuangan terlampir
# ...") tidak ikut zona atas supaya tidak terbaca sebagai judul seksi CaLK.
BATAS_ZONA_ATAS = 0.88


def halaman_dari_pdf(path, baris_zona_atas: int = 8) -> list[Halaman]:
    hasil = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            teks = page.extract_text() or ""
            atas = page.crop((0, 0, page.width, page.height * BATAS_ZONA_ATAS)).extract_text() or ""
            baris = [b.strip() for b in atas.splitlines() if b.strip()]
            hasil.append(Halaman(i, teks, "\n".join(baris[:baris_zona_atas])))
    return hasil
