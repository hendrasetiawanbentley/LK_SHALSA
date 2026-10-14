"""Pembuat data tiruan output ai_parse_document (format versi 2.0)."""


def parsed_v2(halaman: list[list[tuple[str, str]]]) -> dict:
    """halaman = [[(tipe, isi), ...], ...] -> dict seperti to_json(ai_parse_document(...))."""
    elemen, i = [], 0
    for pid, isi_halaman in enumerate(halaman):
        for tipe, isi in isi_halaman:
            elemen.append({"id": i, "type": tipe, "content": isi,
                           "bbox": [{"coord": [0, 0, 10, 10], "page_id": pid}]})
            i += 1
    return {
        "document": {"pages": [{"id": p} for p in range(len(halaman))], "elements": elemen},
        "error_status": [],
        "metadata": {"version": "2.0"},
    }


KOP = [("page_header", "PT CONTOH EMITEN TBK")]


def halaman_laporan(judul: str, tabel: str, satuan="(Dinyatakan dalam jutaan Rupiah)"):
    return KOP + [
        ("title", judul),
        ("text", "31 Desember 2024 dan 2023"),
        ("text", satuan),
        ("table", tabel),
        ("page_footer", "Catatan atas laporan keuangan terlampir merupakan bagian yang tidak terpisahkan"),
    ]


def tabel(baris):
    isi = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in b) + "</tr>" for b in baris)
    return f"<table>{isi}</table>"


def dokumen_contoh() -> dict:
    """Sampul, daftar isi, laporan auditor, 4 laporan utama (posisi keuangan 2 hal), CaLK 2 hal."""
    return parsed_v2([
        [("title", "PT CONTOH EMITEN TBK"), ("text", "Laporan Keuangan 31 Desember 2024")],
        [("title", "DAFTAR ISI"), ("text", "Laporan Posisi Keuangan 1\nLaporan Laba Rugi dan Penghasilan Komprehensif Lain 3\n"
                                          "Laporan Perubahan Ekuitas 4\nLaporan Arus Kas 5\nCatatan atas Laporan Keuangan 6")],
        halaman_laporan("LAPORAN POSISI KEUANGAN", tabel([
            ["", "Catatan", "2024", "2023"],
            ["Kas dan setara kas", "4", "1.250", "1.100"],
            ["Jumlah aset lancar", "", "5.400", "4.900"],
        ])),
        KOP + [("section_header", "LAPORAN POSISI KEUANGAN (lanjutan)"), ("text", "(Dinyatakan dalam jutaan Rupiah)"),
               ("table", tabel([["Jumlah aset", "", "12.000", "11.000"],
                                ["Jumlah liabilitas", "", "(7.000)", "6.500"],
                                ["Jumlah ekuitas", "", "5.000", "4.500"]]))],
        halaman_laporan("LAPORAN LABA RUGI DAN PENGHASILAN KOMPREHENSIF LAIN", tabel([
            ["Pendapatan", "20", "9.000", "8.000"],
            ["Laba tahun berjalan", "", "700", "650"],
        ])),
        halaman_laporan("LAPORAN PERUBAHAN EKUITAS", tabel([
            ["", "Modal saham", "Penghasilan komprehensif lain", "Saldo laba"],
            ["Saldo 31 Desember 2024", "1.000", "50", "3.950"],
        ])),
        halaman_laporan("LAPORAN ARUS KAS", tabel([
            ["Kas bersih diperoleh dari aktivitas operasi", "", "900", "800"],
        ])),
        KOP + [("title", "CATATAN ATAS LAPORAN KEUANGAN"), ("text", "1. UMUM\nPT Contoh Emiten Tbk didirikan ...")],
        KOP + [("text", "4. KAS DAN SETARA KAS\nRincian kas dan setara kas adalah sebagai berikut ...")],
    ])
