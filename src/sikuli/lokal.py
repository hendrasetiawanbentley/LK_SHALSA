"""Pipeline lengkap tanpa Databricks: PDF + Excel -> hasil komparasi (.xlsx).

    python -m sikuli.lokal --pdf folder_pdf --excel folder_excel --out hasil.xlsx

Dipakai juga oleh web app (webapp/app.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .akun import PemetaAkun
from .config import muat_config
from .ekstraksi_lokal import ekstraksi_seksi
from .entitas import info_dari_nama_file
from .excel import baca_excel
from .komparasi import MATCH, bandingkan
from .pdf_lokal import halaman_dari_pdf
from .pipeline import buat_permintaan_ekstraksi, konteks_permintaan, proses_halaman
from .rules import Rules, muat_rules
from .seksi import kompilasi_pola

ROOT = Path(__file__).resolve().parents[2]


def catatan_otomatis(baris: dict, catatan_match: str = "Nilai sesuai") -> str:
    """Catatan deterministik per baris (pengganti ai_gen)."""
    status = baris["status"]
    if status == MATCH:
        return catatan_match
    if status == "PDF_ONLY":
        return "Akun ada di PDF tetapi tidak ditemukan di Excel; periksa sheet_config atau mapping label Excel."
    if status == "EXCEL_ONLY":
        return ("Akun ada di Excel tetapi tidak terbaca di PDF; periksa apakah akun disajikan di laporan "
                "atau tambahkan sinonim label PDF di rules_akun.")
    indikasi = baris.get("indikasi")
    if indikasi == "BEDA_TANDA":
        return "Nilai sama tetapi tanda berlawanan; kemungkinan beda konvensi penyajian (beban/pengurang)."
    if indikasi == "BEDA_SKALA":
        return "Nilai berbeda kelipatan ribuan/jutaan; periksa satuan penyajian PDF atau skala di sheet_config."
    persen = baris.get("selisih_persen")
    persen_teks = f" ({persen:.2f}%)" if persen is not None else ""
    return f"Selisih {baris['selisih']:,.0f}{persen_teks}; perlu konfirmasi ke entitas."


def jalankan(pdf_paths: list[str], excel_paths: list[str], cfg: dict, rules: Rules) -> dict:
    pola = kompilasi_pola(rules.mapping_seksi)
    teks, lokasi, angka_pdf, peringatan = [], [], [], []
    for path in pdf_paths:
        try:
            halaman = halaman_dari_pdf(path, int(cfg["deteksi_seksi"]["baris_zona_atas"]))
        except Exception as e:  # PDF rusak / terkunci
            peringatan.append(f"{Path(path).name}: gagal dibaca ({type(e).__name__}: {e})")
            continue
        hasil = proses_halaman(path, halaman, cfg, rules, pola)
        teks.extend(hasil["teks"])
        lokasi.extend(hasil["lokasi"])
        peringatan.extend(hasil["peringatan"])

    # Satu permintaan per (dokumen, seksi); kelompok akun digabung kembali.
    per_seksi: dict[tuple, dict] = {}
    for p in buat_permintaan_ekstraksi(teks, cfg, rules):
        kunci = (p["doc_id"], p["seksi"])
        if kunci in per_seksi:
            per_seksi[kunci]["akun"].extend(p["akun"])
        else:
            per_seksi[kunci] = {**p, "akun": list(p["akun"])}
    for (doc_id, seksi), p in per_seksi.items():
        halaman = [t for t in teks if t["doc_id"] == doc_id and t["seksi"] == seksi]
        baris, tidak_ada = ekstraksi_seksi(halaman, p["akun"], konteks_permintaan(p), p["zona_atas"])
        angka_pdf.extend(baris)
        if tidak_ada:
            peringatan.append(f"{p['sumber_file']} / {seksi}: akun tidak ditemukan di PDF: {', '.join(tidak_ada)}")

    angka_excel, pemeta = [], PemetaAkun(rules)
    for path in excel_paths:
        info = info_dari_nama_file(path, cfg, rules)
        if not info["entitas_dikenal"]:
            peringatan.append(f"{info['nama_file']}: entity_id/doc_type tidak dikenali dari nama file, dilewati")
            continue
        try:
            baris, pesan = baca_excel(path, info, rules, pemeta)
        except Exception as e:
            peringatan.append(f"{info['nama_file']}: gagal dibaca ({type(e).__name__}: {e})")
            continue
        angka_excel.extend(baris)
        peringatan.extend(pesan)

    nama_akun = {a["kode_akun"]: a["nama_akun"] for a in rules.rules_akun}
    komparasi = bandingkan(angka_pdf, angka_excel, cfg["komparasi"], nama_akun)
    urutan = {"DIFFERENT": 0, "PDF_ONLY": 1, "EXCEL_ONLY": 2, MATCH: 3}
    komparasi.sort(key=lambda b: (urutan[b["status"]], b["entity_key"], b["kode_akun"]))
    for b in komparasi:
        b["catatan"] = catatan_otomatis(b, cfg["komparasi"].get("catatan_match", "Nilai sesuai"))
    return {"komparasi": komparasi, "angka_pdf": angka_pdf, "angka_excel": angka_excel,
            "lokasi_seksi": lokasi, "teks_pdf": teks, "peringatan": peringatan,
            "ringkasan": ringkasan(komparasi)}


def ringkasan(komparasi: list[dict]) -> list[dict]:
    per: dict[str, dict] = {}
    for b in komparasi:
        r = per.setdefault(b["entity_key"], {"entity_key": b["entity_key"], "MATCH": 0, "DIFFERENT": 0,
                                             "PDF_ONLY": 0, "EXCEL_ONLY": 0})
        r[b["status"]] += 1
    for r in per.values():
        total = r["MATCH"] + r["DIFFERENT"] + r["PDF_ONLY"] + r["EXCEL_ONLY"]
        r["persen_match"] = round(100 * r["MATCH"] / total, 1) if total else 0.0
    return sorted(per.values(), key=lambda r: r["persen_match"])


KOLOM = {
    "Ringkasan": ["entity_key", "MATCH", "DIFFERENT", "PDF_ONLY", "EXCEL_ONLY", "persen_match"],
    "Komparasi": ["entity_key", "seksi", "kode_akun", "nama_akun", "periode", "nilai_pdf", "nilai_excel",
                  "selisih", "selisih_persen", "status", "indikasi", "catatan", "halaman_pdf", "sumber_pdf",
                  "sumber_excel", "label_pdf", "label_excel"],
    "Angka_PDF": ["sumber_file", "entity_key", "seksi", "kode_akun", "label_di_dokumen", "periode", "nilai",
                  "nilai_asli", "skala", "halaman"],
    "Angka_Excel": ["sumber_file", "entity_key", "sheet", "baris", "seksi", "label_asli", "kode_akun",
                    "cara_pemetaan", "periode", "nilai", "nilai_asli"],
    "Lokasi_Seksi": ["nama_file", "entity_key", "seksi", "halaman_mulai", "halaman_akhir", "judul_cocok"],
}
WARNA = {"MATCH": "D9F2E1", "DIFFERENT": "FBDAD7", "PDF_ONLY": "FFF1C2", "EXCEL_ONLY": "FFF1C2"}


def tulis_excel(hasil: dict, path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    sumber = {"Ringkasan": "ringkasan", "Komparasi": "komparasi", "Angka_PDF": "angka_pdf",
              "Angka_Excel": "angka_excel", "Lokasi_Seksi": "lokasi_seksi"}
    for sheet, kolom in KOLOM.items():
        ws = wb.create_sheet(sheet)
        ws.append(kolom)
        for c in ws[1]:
            c.font = Font(bold=True)
        for b in hasil[sumber[sheet]]:
            ws.append([b.get(k) for k in kolom])
            if sheet == "Komparasi" and b["status"] in WARNA:
                ws.cell(ws.max_row, kolom.index("status") + 1).fill = PatternFill("solid", fgColor=WARNA[b["status"]])
        ws.freeze_panes = "A2"
    ws = wb.create_sheet("Peringatan")
    ws.append(["peringatan"])
    for p in hasil["peringatan"]:
        ws.append([p])
    wb.save(path)


def _kumpulkan(folder: str | None, akhiran: tuple[str, ...]) -> list[str]:
    if not folder:
        return []
    return sorted(str(p) for p in Path(folder).rglob("*")
                  if p.suffix.lower() in akhiran and not p.name.startswith("~$"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SIKULI: komparasi LK PDF vs Excel tanpa Databricks")
    ap.add_argument("--pdf", help="folder berisi LK PDF")
    ap.add_argument("--excel", help="folder berisi LK Excel")
    ap.add_argument("--rules", default=str(ROOT / "rules"))
    ap.add_argument("--config", default=str(ROOT / "config" / "pipeline.yaml"))
    ap.add_argument("--out", default="hasil_komparasi.xlsx")
    args = ap.parse_args(argv)

    hasil = jalankan(_kumpulkan(args.pdf, (".pdf",)), _kumpulkan(args.excel, (".xlsx", ".xlsm")),
                     muat_config(args.config), muat_rules(args.rules))
    tulis_excel(hasil, args.out)
    for r in hasil["ringkasan"]:
        print(r)
    print("\n".join(hasil["peringatan"]))
    print(f"Hasil: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
