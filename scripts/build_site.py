"""Bangun situs statis dokumentasi SIKULI ke folder site/ (untuk Render Static Site).

Isi: README, daftar file yang perlu disediakan, tabel rules (dengan unduhan CSV),
dan hasil pytest saat build. Tidak memuat data laporan keuangan apa pun.

    python scripts/build_site.py            # hasil di site/
"""

from __future__ import annotations

import csv
import html
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site"

CSS = """
:root{--bg:#fff;--fg:#1d2433;--muted:#5b6475;--line:#dde2ea;--card:#f5f7fa;--accent:#13658f;
--ok:#1f7a3a;--bad:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#11151c;--fg:#e6e9ef;--muted:#9aa3b2;--line:#2a313d;
--card:#1a2029;--accent:#5fb3e0;--ok:#5cc47e;--bad:#f07a6e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header,main,footer{max-width:1080px;margin:0 auto;padding:0 16px}
header{padding-top:28px}nav{display:flex;flex-wrap:wrap;gap:6px 18px;margin:8px 0 20px}
nav a{color:var(--accent);text-decoration:none;font-weight:600}
h1{margin:0;font-size:1.9rem}h2{margin-top:2.2rem;border-bottom:1px solid var(--line);padding-bottom:6px}
.sub{color:var(--muted);margin:2px 0 0}
a{color:var(--accent)}code{background:var(--card);padding:1px 5px;border-radius:4px;font-size:.9em}
pre{background:var(--card);padding:12px;border-radius:8px;overflow-x:auto;font-size:.85em}
pre code{background:none;padding:0}
.tbl{overflow-x:auto;max-width:100%;margin:12px 0}main{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--card)}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;color:#fff}
.ok{background:var(--ok)}.bad{background:var(--bad)}
.pass{color:var(--ok)}.fail{color:var(--bad);font-weight:700}
footer{color:var(--muted);font-size:.85rem;padding:32px 16px}
"""


def halaman(judul: str, isi: str, dibangun: str) -> str:
    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(judul)}</title><style>{CSS}</style></head>
<body><header><h1>SIKULI</h1>
<p class="sub">Alur analisis laporan keuangan: parsing sampai komparasi PDF vs Excel</p>
<nav><a href="index.html">Ringkasan</a><a href="file-yang-perlu-disediakan.html">File yang perlu disediakan</a>
<a href="rules.html">Rules</a><a href="tes.html">Hasil tes</a></nav></header>
<main>{isi}</main><footer>Dibangun {dibangun} dari repo LK_SHALSA.</footer></body></html>"""


def md_ke_html(path: Path) -> str:
    teks = path.read_text(encoding="utf-8")
    # Tautan antar dokumen di repo diarahkan ke halaman situs.
    teks = teks.replace("docs/FILE_YANG_PERLU_DISEDIAKAN.md", "file-yang-perlu-disediakan.html")
    isi = markdown.markdown(teks, extensions=["tables", "fenced_code"])
    return isi.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")


def tabel_csv(path: Path) -> str:
    with open(path, encoding="utf-8-sig", newline="") as f:
        baris = list(csv.reader(f))
    if not baris:
        return "<p>(kosong)</p>"
    kepala = "".join(f"<th>{html.escape(k)}</th>" for k in baris[0])
    badan = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in baris[1:])
    return f'<div class="tbl"><table><thead><tr>{kepala}</tr></thead><tbody>{badan}</tbody></table></div>'


def jalankan_tes() -> tuple[bool, str]:
    xml = OUT / "_pytest.xml"
    hasil = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}"],
                           cwd=ROOT, capture_output=True, text=True)
    lulus = hasil.returncode == 0
    baris = []
    if xml.exists():
        for kasus in ET.parse(xml).getroot().iter("testcase"):
            gagal = kasus.find("failure") is not None or kasus.find("error") is not None
            nama = f"{kasus.get('classname')}::{kasus.get('name')}"
            kelas, label = ("fail", "GAGAL") if gagal else ("pass", "lulus")
            baris.append(f'<tr><td>{html.escape(nama)}</td><td class="{kelas}">{label}</td></tr>')
        xml.unlink()
    ringkas = hasil.stdout.strip().splitlines()[-1] if hasil.stdout.strip() else "pytest tidak menghasilkan output"
    badge = '<span class="badge ok">LULUS</span>' if lulus else '<span class="badge bad">GAGAL</span>'
    isi = (f"<h2>Hasil tes {badge}</h2><p><code>{html.escape(ringkas)}</code></p>"
           f'<div class="tbl"><table><thead><tr><th>Tes</th><th>Status</th></tr></thead>'
           f"<tbody>{''.join(baris)}</tbody></table></div>")
    if not lulus:
        isi += f"<h3>Output</h3><pre>{html.escape(hasil.stdout[-8000:])}</pre>"
    return lulus, isi


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "rules").mkdir(parents=True)
    dibangun = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lulus, isi_tes = jalankan_tes()
    (OUT / "index.html").write_text(halaman("SIKULI", md_ke_html(ROOT / "README.md"), dibangun), encoding="utf-8")
    (OUT / "file-yang-perlu-disediakan.html").write_text(
        halaman("File yang perlu disediakan", md_ke_html(ROOT / "docs" / "FILE_YANG_PERLU_DISEDIAKAN.md"), dibangun),
        encoding="utf-8")

    bagian = ["<h2>Rules (kertas kerja)</h2><p>Isi folder <code>rules/</code> saat ini. Selain "
              "<code>mapping_seksi.csv</code>, isinya masih <strong>contoh</strong> yang perlu diganti.</p>"]
    for path in sorted((ROOT / "rules").glob("*.csv")):
        shutil.copy(path, OUT / "rules" / path.name)
        bagian.append(f'<h3>{path.name} <a href="rules/{path.name}" download>unduh</a></h3>{tabel_csv(path)}')
    (OUT / "rules.html").write_text(halaman("Rules SIKULI", "".join(bagian), dibangun), encoding="utf-8")
    (OUT / "tes.html").write_text(halaman("Hasil tes SIKULI", isi_tes, dibangun), encoding="utf-8")

    print(f"Situs dibangun di {OUT} (tes {'lulus' if lulus else 'GAGAL'})")
    return 0 if lulus else 1


if __name__ == "__main__":
    sys.exit(main())
