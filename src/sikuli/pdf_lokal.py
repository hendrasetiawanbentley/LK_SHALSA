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


def _buang_spasi_menumpuk(page):
    """Beberapa PDF menyimpan karakter spasi yang menumpuk di atas digit
    (mis. "1 .336.272.829.434" padahal tercetak 1.336.272.829.434). Spasi yang
    posisinya berada di dalam karakter lain pada baris yang sama dibuang."""
    per_baris: dict[int, list[tuple[float, float]]] = {}
    for c in page.chars:
        if c["text"].strip():
            per_baris.setdefault(round(c["top"]), []).append((c["x0"], c["x1"]))
    buruk = set()
    for c in page.chars:
        if c["text"].strip():
            continue
        baris = round(c["top"])
        for k in (baris - 1, baris, baris + 1):
            if any(x0 - 0.2 <= c["x0"] < x1 - 0.5 for x0, x1 in per_baris.get(k, ())):
                buruk.add((round(c["x0"], 2), round(c["top"], 2)))
                break
    if not buruk:
        return page
    return page.filter(lambda o: not (o.get("object_type") == "char" and not o["text"].strip()
                                      and (round(o["x0"], 2), round(o["top"], 2)) in buruk))


def halaman_dari_pdf(path, baris_zona_atas: int = 8) -> list[Halaman]:
    hasil = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page = _buang_spasi_menumpuk(page)
            teks = page.extract_text() or ""
            # Koordinat halaman tidak selalu mulai dari (0, 0) (mediabox bergeser),
            # jadi area potong dihitung dari bbox halaman itu sendiri.
            x0, atas_y, x1, bawah_y = page.bbox
            try:
                atas = page.crop((x0, atas_y, x1, atas_y + (bawah_y - atas_y) * BATAS_ZONA_ATAS)).extract_text() or ""
            except ValueError:
                atas = teks
            baris = [b.strip() for b in atas.splitlines() if b.strip()]
            hasil.append(Halaman(i, teks, "\n".join(baris[:baris_zona_atas])))
    return hasil
