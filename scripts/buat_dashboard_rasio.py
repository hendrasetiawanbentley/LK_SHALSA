"""Buat dashboard HTML rasio (satu file, tanpa server) dari hasil pipeline SIKULI.

Pemakaian:
    PYTHONPATH=src python scripts/buat_dashboard_rasio.py --hasil hasil --out hasil/dashboard_rasio.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sikuli.rasio import nama_sheet

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).with_name("dashboard_rasio_template.html")
KOLOM = ["entity_key", "no", "kategori", "entitas", "field_key", "satuan", "rasio_y1", "rasio_y", "hasil_rasio",
         "rumus_ai", "perhitungan_y1", "perhitungan_y", "sumber_y1", "sumber_y", "analisis_ai", "sumber_analisis",
         "keterangan"]


def siapkan_data(hasil: dict) -> dict:
    rasio = [{k: r.get(k) for k in KOLOM} for r in hasil.get("rasio", [])]
    entitas = []
    kunci = list(dict.fromkeys(r["entity_key"] for r in rasio))
    kode = nama_sheet(kunci)
    for key in kunci:
        doc_type = next((r["entitas"] for r in rasio if r["entity_key"] == key), key.split("_")[0])
        sisa = key[len(kode[key]):].strip("_")
        entitas.append({"entity_key": key, "doc_type": doc_type, "kode": kode[key],
                        "nama": sisa.replace("_", " ") or key})
    urut = {"EPP": 0, "MI": 1, "RD": 2}
    entitas.sort(key=lambda e: (urut.get(e["doc_type"], 9), e["entity_key"]))
    return {"mode": hasil.get("mode"), "entitas": entitas, "rasio": rasio}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dashboard HTML rasio SIKULI")
    ap.add_argument("--hasil", default=str(ROOT / "hasil"), help="folder berisi hasil.json")
    ap.add_argument("--out", default=None, help="file HTML keluaran (bawaan: <hasil>/dashboard_rasio.html)")
    args = ap.parse_args(argv)
    hasil = json.loads((Path(args.hasil) / "hasil.json").read_text(encoding="utf-8"))
    teks = json.dumps(siapkan_data(hasil), ensure_ascii=False, default=str).replace("</", "<\\/")
    out = Path(args.out or Path(args.hasil) / "dashboard_rasio.html")
    out.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", teks), encoding="utf-8")
    print(f"Dashboard rasio ditulis ke {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
