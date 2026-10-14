"""Buat dashboard HTML (satu file, tanpa server) dari hasil pipeline SIKULI.

Pemakaian:
    PYTHONPATH=src python scripts/buat_dashboard.py --hasil hasil --out hasil/dashboard.html

Membaca `hasil/hasil.json` (ditulis oleh `python -m sikuli.lokal`) dan rules Master untuk
menampilkan akun yang diharapkan tetapi tidak tersaji di PDF maupun Excel.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sikuli.rules import berlaku_untuk, muat_rules

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).with_name("dashboard_template.html")
KOLOM_BARIS = ["entity_key", "doc_type", "seksi", "kode_akun", "nama_akun", "periode", "satuan_pdf", "nilai_pdf",
               "nilai_excel", "nilai_excel_asli", "selisih", "selisih_persen", "status", "indikasi", "catatan",
               "sumber_catatan", "halaman_pdf", "verifikasi_pdf", "label_pdf", "label_excel", "sumber_excel"]


def nama_entitas(entity_key: str) -> str:
    bagian = entity_key.split("_")
    return " ".join(bagian[2:]) or entity_key


def siapkan_data(hasil: dict, rules) -> dict:
    komparasi = [{k: b.get(k) for k in KOLOM_BARIS} for b in hasil["komparasi"]]
    kesimpulan = {k["entity_key"]: k for k in hasil.get("kesimpulan", [])}
    lokasi: dict[str, list] = {}
    for s in hasil.get("lokasi_seksi", []):
        lokasi.setdefault(s["entity_key"], []).append(
            {"seksi": s["seksi"], "mulai": s["halaman_mulai"], "akhir": s["halaman_akhir"], "judul": s.get("judul_cocok")})

    entitas = []
    for r in hasil["ringkasan"]:
        key = r["entity_key"]
        baris = [b for b in komparasi if b["entity_key"] == key]
        doc_type = baris[0]["doc_type"] if baris else key.split("_")[0]
        ada = {b["kode_akun"] for b in baris}
        kosong = [{"kode_akun": a["kode_akun"], "nama_akun": a["nama_akun"], "seksi": a["seksi"]}
                  for a in rules.rules_akun if berlaku_untuk(a["doc_type"], doc_type) and a["kode_akun"] not in ada]
        satuan = Counter(b["satuan_pdf"] for b in baris if b.get("satuan_pdf")).most_common(1)
        k = kesimpulan.get(key, {})
        entitas.append({
            "entity_key": key, "nama": nama_entitas(key), "kode": key.split("_")[1] if "_" in key else key,
            "doc_type": doc_type, "satuan": satuan[0][0] if satuan else None,
            "MATCH": r["MATCH"], "DIFFERENT": r["DIFFERENT"], "PDF_ONLY": r["PDF_ONLY"],
            "EXCEL_ONLY": r["EXCEL_ONLY"], "persen_match": r["persen_match"],
            "kesimpulan": k.get("kesimpulan", ""),
            "rekomendasi": [x[2:] if x.startswith("- ") else x for x in (k.get("rekomendasi") or "").splitlines() if x.strip()],
            "akun_kosong": kosong, "lokasi": lokasi.get(key, []),
        })
    return {"mode": hasil.get("mode"), "entitas": entitas, "komparasi": komparasi,
            "peringatan": hasil.get("peringatan", [])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dashboard HTML hasil komparasi SIKULI")
    ap.add_argument("--hasil", default=str(ROOT / "hasil"), help="folder berisi hasil.json")
    ap.add_argument("--rules", default=str(ROOT / "rules"))
    ap.add_argument("--config", default=str(ROOT / "config"))
    ap.add_argument("--out", default=None, help="file HTML keluaran (bawaan: <hasil>/dashboard.html)")
    args = ap.parse_args(argv)

    hasil = json.loads((Path(args.hasil) / "hasil.json").read_text(encoding="utf-8"))
    data = siapkan_data(hasil, muat_rules(args.rules, args.config))
    teks = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", teks)
    out = Path(args.out or Path(args.hasil) / "dashboard.html")
    out.write_text(html, encoding="utf-8")
    print(f"Dashboard ditulis ke {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
