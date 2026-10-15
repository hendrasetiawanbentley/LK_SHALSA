"""Rasio kertas kerja dari angka laporan keuangan audited (PDF).

Definisi rasio dibaca dari template kertas kerja `config/rasio_kk_template.xlsx` (kolom No, Kategori,
Entitas, field_key, dtype, Description; baris bertanda "tidak dipakai" dilewati), dengan cadangan
Sheet3 file rules. Rumus perhitungan ada di `config/rasio.yaml`. Perhitungan deterministik dan hanya
memakai angka PDF; analisis per rasio ditulis AI (ai.analisis_rasio).
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .komparasi import _indeks

KOLOM_KK = ["No", "Kategori", "Entitas", "field_key", "dtype", "Description", "Nilai Y-1", "Nilai Y",
            "Rumus Rasio AI", "Hasil Rasio"]
KOLOM_TAMBAHAN = ["Hasil Rasio Y-1", "Hasil Rasio Y", "Satuan", "Analisis AI", "Keterangan"]
KOLOM = ["entity_key", "no", "kategori", "entitas", "field_key", "dtype", "description", "nilai_y1", "nilai_y",
         "rumus_ai", "hasil_rasio", "rasio_y1", "rasio_y", "satuan", "analisis_ai", "sumber_analisis", "keterangan"]
FUNGSI = {"rata2", "opsional", "abs", "min", "max"}
SATUAN = {"persen": "%", "kali": "x", "nominal": "nominal"}


class AkunHilang(Exception):
    pass


def _baca_definisi_xlsx(path: Path, sheet: str | None = None) -> list[dict]:
    """Baris definisi dari template kertas kerja (atau Sheet3 rules), urut seperti di file."""
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if sheet else wb.worksheets[0]
        baris = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    kepala = [str(k).strip() if k else "" for k in baris[0]]
    hasil = []
    for r in baris[1:]:
        d = dict(zip(kepala, r))
        if d.get("No") is None or not d.get("Entitas"):
            continue
        tanda = " ".join(str(v) for k, v in d.items() if k in ("Nilai Y-1", "Nilai Y") and v)
        hasil.append({"no": int(d["No"]), "entitas": str(d["Entitas"]).strip(),
                      "kategori": str(d.get("Kategori") or "").strip(), "field_key": str(d.get("field_key") or "").strip(),
                      "dtype": d.get("dtype") or "number", "description": d.get("Description") or "",
                      "dipakai": "tidak dipakai" not in tanda.lower()})
    return hasil


def muat_rasio(path_template: str | Path, path_yaml: str | Path, folder_rules: str | Path | None = None) -> list[dict]:
    """Definisi rasio yang dipakai: urutan dan uraian dari template, rumus dari yaml.

    Rasio di template tanpa rumus di yaml tetap dikembalikan (rumus None) supaya terlihat di
    kertas kerja sebagai "rumus belum didefinisikan"."""
    path_yaml, path_template = Path(path_yaml), Path(path_template)
    if not path_yaml.exists():
        return []
    isi = yaml.safe_load(path_yaml.read_text(encoding="utf-8"))
    kelompok = isi.get("kelompok") or {}
    rumus = {}
    for r in isi.get("rasio", []):
        _cek_rumus(r["rumus"])
        rumus[(int(r["nomor"]), r["entitas"])] = r
    if path_template.exists():
        definisi = _baca_definisi_xlsx(path_template)
    else:
        master = next(iter(sorted(Path(folder_rules).glob("*.xlsx"))), None) if folder_rules else None
        definisi = _baca_definisi_xlsx(master, "Sheet3") if master else []
    hasil = []
    for d in definisi:
        if not d.pop("dipakai"):
            continue
        r = rumus.get((d["no"], d["entitas"]), {})
        hasil.append({**d, "rumus": r.get("rumus"), "satuan": r.get("satuan", "persen"), "teks": r.get("teks", ""),
                      "ambang": r.get("ambang"), "ambang_maks": r.get("ambang_maks"), "periode": r.get("periode"),
                      "kelompok": kelompok})
    return hasil


def _cek_rumus(rumus: str) -> None:
    """Rumus hanya boleh berisi angka, nama akun, operator aritmetika, dan fungsi yang diizinkan."""
    izin = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant, ast.Call,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)
    for n in ast.walk(ast.parse(rumus, mode="eval")):
        if not isinstance(n, izin):
            raise ValueError(f"rumus rasio tidak diizinkan: {rumus!r} ({type(n).__name__})")
        if isinstance(n, ast.Call) and not (isinstance(n.func, ast.Name) and n.func.id in FUNGSI):
            raise ValueError(f"fungsi tidak diizinkan di rumus: {rumus!r}")


def _nama_akun(rumus: str) -> list[str]:
    nama = []
    for n in ast.walk(ast.parse(rumus, mode="eval")):
        if isinstance(n, ast.Name) and n.id not in FUNGSI and n.id not in nama:
            nama.append(n.id)
    return nama


def evaluasi(rumus: str, nilai) -> float:
    """`nilai(nama)` -> float atau None. Akun yang hilang -> AkunHilang (kecuali dalam opsional())."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.Name):
            v = nilai(n.id)
            if v is None:
                raise AkunHilang(n.id)
            return v
        if isinstance(n, ast.UnaryOp):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if b == 0:
                raise ZeroDivisionError
            return a / b
        f = n.func.id
        if f == "opsional":
            try:
                return ev(n.args[0])
            except AkunHilang:
                return 0.0
        args = [ev(a) for a in n.args]
        if f == "rata2":
            return sum(args) / len(args)
        return {"abs": abs, "min": min, "max": max}[f](*args)
    return ev(ast.parse(rumus, mode="eval"))


def _nilai_entitas(angka_pdf: list[dict], entity_key: str) -> dict[tuple[str, str], float]:
    """(kode_akun, periode) -> nilai PDF dalam mata uang penuh (nilai x satuan penyajian)."""
    hasil = {}
    for (ek, kode, periode), b in _indeks(angka_pdf, {"berjalan", "lalu"}, "pdf").items():
        if ek == entity_key:
            hasil[(kode, periode)] = b["nilai"] * (b.get("skala") or 1.0)
    return hasil


def _pengambil(data: dict, periode: str):
    def ambil(nama: str):
        if nama.endswith("__lalu"):
            return data.get((nama[:-6], "lalu")) if periode == "berjalan" else None
        return data.get((nama, periode))
    return ambil


def _hitung(rumus: str, satuan: str, ambil) -> tuple[float | None, str | None]:
    try:
        v = evaluasi(rumus, ambil)
    except AkunHilang as e:
        return None, f"akun {e.args[0]} tidak tersedia di PDF"
    except ZeroDivisionError:
        return None, "pembagi bernilai nol"
    return (v * 100 if satuan == "persen" else v), None


def fmt_angka(x: float, desimal: int = 2) -> str:
    return f"{x:,.{desimal}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_rasio(x: float | None, satuan: str) -> str:
    if x is None:
        return "tidak dapat dihitung"
    if satuan == "persen":
        return fmt_angka(x) + "%"
    if satuan == "kali":
        return fmt_angka(x) + " x"
    return fmt_angka(x, 0)


def _komponen(rumus: str, ambil, nama_akun: dict[str, str]) -> str:
    bagian = []
    for n in _nama_akun(rumus):
        dasar = n[:-6] if n.endswith("__lalu") else n
        label = nama_akun.get(dasar) or dasar.replace("_", " ").capitalize()
        label += " (periode sebelumnya)" if n.endswith("__lalu") else ""
        v = ambil(n)
        bagian.append(f"{label} = {fmt_angka(v) if v is not None else 'tidak ada'}")
    return "\n".join(bagian)


def _dengan_kelompok(ambil, kelompok: dict[str, list[str]]):
    """Nama kelompok (mis. utang_berbasis_bunga_des) = jumlah anggota yang tersedia; None bila tidak ada."""
    def f(nama: str):
        if nama in kelompok:
            nilai = [v for v in (ambil(k) for k in kelompok[nama]) if v is not None]
            return sum(nilai) if nilai else None
        return ambil(nama)
    return f


def _rincian_kelompok(kelompok: list[str], ambil, nama_akun: dict[str, str]) -> str:
    return "\n".join(f"  - {nama_akun.get(k, k)} = {fmt_angka(ambil(k))}" for k in kelompok if ambil(k) is not None)


def hitung_rasio(definisi: list[dict], angka_pdf: list[dict], entitas: dict[str, str],
                 nama_akun: dict[str, str] | None = None,
                 kriteria_tambahan: dict[str, list[str]] | None = None) -> list[dict]:
    """`entitas`: entity_key -> doc_type. Satu baris per entitas x rasio yang berlaku, dari angka PDF saja.
    `kriteria_tambahan` mis. {"EPP": ["DES"]}: rasio DES juga dihitung untuk emiten."""
    nama_akun = nama_akun or {}
    kriteria_tambahan = kriteria_tambahan or {}
    hasil = []
    for entity_key, doc_type in sorted(entitas.items()):
        pdf = _nilai_entitas(angka_pdf, entity_key)
        jenis = [doc_type] + list(kriteria_tambahan.get(doc_type, []))
        for d in (x for x in definisi if x["entitas"] in jenis):
            satuan = d["satuan"]
            baris = {"entity_key": entity_key, "no": d["no"], "kategori": d["kategori"], "entitas": doc_type,
                     "field_key": d["field_key"], "dtype": d["dtype"], "description": d["description"],
                     "rumus_ai": d["teks"], "satuan": SATUAN.get(satuan, satuan), "analisis_ai": "",
                     "sumber_analisis": None}
            if not d.get("rumus"):
                hasil.append({**baris, "nilai_y1": "", "nilai_y": "", "rasio_y1": None, "rasio_y": None,
                              "hasil_rasio": "rumus belum didefinisikan di config/rasio.yaml",
                              "keterangan": "rumus belum didefinisikan"})
                continue
            kel = d.get("kelompok") or {}
            ambil_y = _dengan_kelompok(_pengambil(pdf, "berjalan"), kel)
            ambil_y1 = _dengan_kelompok(_pengambil(pdf, "lalu"), kel)
            y, ket_y = _hitung(d["rumus"], satuan, ambil_y)
            y1, ket_y1 = _hitung(d["rumus"], satuan, ambil_y1)
            periode = d.get("periode")             # None = Y-1 dan Y; "lalu" / "berjalan" = satu periode saja
            if periode == "lalu":
                y, ket_y = None, None
            elif periode == "berjalan":
                y1, ket_y1 = None, None
            ket = [f"Y: {ket_y}"] if ket_y else []
            ket += [f"Y-1: {ket_y1}"] if ket_y1 else []
            bagian = []
            if periode != "berjalan":
                bagian.append(f"Y-1: {fmt_rasio(y1, satuan)}" + _status(y1, d))
            if periode != "lalu":
                bagian.append(f"Y: {fmt_rasio(y, satuan)}" + _status(y, d))

            def komponen(ambil_kel, ambil_dasar):
                teks = _komponen(d["rumus"], ambil_kel, nama_akun)
                for nama, anggota in kel.items():
                    if nama in _nama_akun(d["rumus"]):
                        judul = nama_akun.get(nama) or nama.replace("_", " ").capitalize()
                        teks += f"\nRincian {judul}:\n" + _rincian_kelompok(anggota, ambil_dasar, nama_akun)
                return teks
            hasil.append({**baris,
                          "nilai_y1": "" if periode == "berjalan" else komponen(ambil_y1, _pengambil(pdf, "lalu")),
                          "nilai_y": "" if periode == "lalu" else komponen(ambil_y, _pengambil(pdf, "berjalan")),
                          "rasio_y1": y1, "rasio_y": y, "hasil_rasio": "\n".join(bagian), "keterangan": "; ".join(ket)})
    return hasil


def _status(x: float | None, d: dict) -> str:
    if x is None:
        return ""
    if d.get("ambang") is not None:
        return " (memenuhi)" if x >= float(d["ambang"]) else " (tidak memenuhi)"
    if d.get("ambang_maks") is not None:
        maks = float(d["ambang_maks"])
        return f" (memenuhi, maks {fmt_angka(maks)}%)" if x <= maks else f" (tidak memenuhi, maks {fmt_angka(maks)}%)"
    return ""


def nama_sheet(entity_keys: list[str]) -> dict[str, str]:
    """Nama sheet pendek dan unik: JENIS_KODE, ditambah bagian berikutnya bila bentrok."""
    hasil = {}
    for e in entity_keys:
        bagian = e.split("_")
        n = 2
        while n < len(bagian) and sum(1 for x in entity_keys if x.split("_")[:n] == bagian[:n]) > 1:
            n += 1
        hasil[e] = "_".join(bagian[:n])[:31]
    return hasil


def tulis_kk(rasio: list[dict], path) -> None:
    """Kertas kerja rasio: satu sheet per entitas dengan kolom template, plus sheet Semua."""
    wb = Workbook()
    wb.remove(wb.active)
    kolom = KOLOM_KK + KOLOM_TAMBAHAN
    kunci = ["no", "kategori", "entitas", "field_key", "dtype", "description", "nilai_y1", "nilai_y", "rumus_ai",
             "hasil_rasio", "rasio_y1", "rasio_y", "satuan", "analisis_ai", "keterangan"]
    lebar = [5, 16, 8, 30, 8, 45, 45, 45, 36, 24, 14, 14, 9, 70, 30]
    kepala = PatternFill("solid", fgColor="DCE3F2")

    def sheet(nama: str, isi: list[dict], dengan_entitas: bool):
        ws = wb.create_sheet(nama[:31])
        geser = 1 if dengan_entitas else 0
        ws.append((["entity_key"] if dengan_entitas else []) + kolom)
        for c in ws[1]:
            c.font, c.fill = Font(bold=True), kepala
        for r in isi:
            ws.append(([r["entity_key"]] if dengan_entitas else []) + [r.get(k) for k in kunci])
            for c in ws[ws.max_row]:
                c.alignment = Alignment(wrap_text=True, vertical="top")
            fmt = "#,##0" if r["satuan"] == "nominal" else "#,##0.00"
            for kol in (11, 12):
                ws.cell(ws.max_row, kol + geser).number_format = fmt
        for i, w in enumerate(([40] if dengan_entitas else []) + lebar, start=1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = w
        ws.freeze_panes = "A2"

    for e, nama in nama_sheet(sorted({r["entity_key"] for r in rasio})).items():
        sheet(nama, [r for r in rasio if r["entity_key"] == e], False)
    sheet("Semua", rasio, True)
    wb.save(path)
