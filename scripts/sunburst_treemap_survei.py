# -*- coding: utf-8 -*-
"""
Modul sunburst + treemap Dimensi -> Subdimensi -> Butir (Q) dalam SATU halaman.

Simpan file ini di folder yang sama dengan .py utama, lalu:

    from sunburst_treemap_survei import buat_grafik

    fig = buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, skor="Pusat")

Hasilnya satu halaman: sunburst di kiri, treemap di kanan, satu skala warna.
Keduanya terhubung: klik di sunburst -> treemap ikut zoom (dan sebaliknya).

Kolom yang dipakai:
  Map_Dimensi    : Kode Dimensi, Dimensi, Pusat, Daerah, Selisih
  Map_Subdimensi : Kode Subdimensi, Subdimensi, Kode Dimensi, Deskripsi Pertanyaan, Pusat, Daerah, Selisih
  Map_Butir      : Q, Kode Subdimensi, Kode Dimensi, Deskripsi Pertanyaan, Pusat, Daerah, Selisih

Warna tiap irisan diambil langsung dari skor di sheet level masing-masing.
Luas irisan = jumlah butir.
"""

import tempfile
import textwrap
import webbrowser
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

__all__ = ["buat_grafik", "susun_hierarki", "simpan_html"]

PILIHAN_SKOR = ("Pusat", "Daerah", "Selisih")

# Palet lembut (tidak menyilaukan): koral -> pasir -> sage -> hijau teal
SKALA_SKOR = [[0.00, "#e4876f"], [0.35, "#f3cf96"], [0.65, "#b5d3a6"], [1.00, "#5c9f8c"]]
# Untuk Selisih: koral (negatif) <- krem (0) -> biru baja (positif)
SKALA_SELISIH = [[0.00, "#d9826b"], [0.50, "#f6f1e7"], [1.00, "#5f8fb3"]]

LATAR = "#fbfaf7"
TEKS = "#33403f"
GARIS = "#ffffff"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def _bungkus(teks, lebar=50):
    if pd.isna(teks):
        return ""
    return "<br>".join(textwrap.wrap(str(teks), lebar))


def _fmt(x):
    return "-" if pd.isna(x) else f"{x:,.2f}"


def _hover(judul, row, deskripsi=None):
    teks = f"<b>{judul}</b>"
    if deskripsi is not None and not pd.isna(deskripsi):
        teks += f"<br>{_bungkus(deskripsi)}"
    teks += (f"<br><br>Pusat   : {_fmt(row['Pusat'])}"
             f"<br>Daerah  : {_fmt(row['Daerah'])}"
             f"<br>Selisih : {_fmt(row['Selisih'])}")
    return teks


def susun_hierarki(df_map_dimensi, df_map_subdimensi, df_map_butir, skor="Pusat"):
    """Gabungkan 3 DataFrame jadi satu tabel ids/parents/values/warna untuk Plotly."""
    if skor not in PILIHAN_SKOR:
        raise ValueError(f"skor harus salah satu dari {PILIHAN_SKOR}, bukan {skor!r}")

    df_dim, df_sub, df_butir = df_map_dimensi.copy(), df_map_subdimensi.copy(), df_map_butir.copy()
    for df, kolom in [(df_dim, ["Kode Dimensi"]),
                      (df_sub, ["Kode Subdimensi", "Kode Dimensi"]),
                      (df_butir, ["Q", "Kode Subdimensi", "Kode Dimensi"])]:
        df.columns = [str(c).strip() for c in df.columns]
        for k in kolom:
            df[k] = df[k].astype(str).str.strip()
        for k in PILIHAN_SKOR:
            df[k] = pd.to_numeric(df[k], errors="coerce")

    n_sub = df_butir.groupby("Kode Subdimensi").size()
    n_dim = df_butir.groupby("Kode Dimensi").size()

    baris = []
    for _, r in df_dim.iterrows():
        kd = r["Kode Dimensi"]
        baris.append(dict(id=f"D:{kd}", parent="", label=f"<b>{kd}</b><br>{_bungkus(r['Dimensi'], 18)}",
                          value=int(n_dim.get(kd, 0)), warna=r[skor],
                          hover=_hover(f"{kd} · {r['Dimensi']}", r)))
    for _, r in df_sub.iterrows():
        ks, kd = r["Kode Subdimensi"], r["Kode Dimensi"]
        baris.append(dict(id=f"S:{ks}", parent=f"D:{kd}", label=f"{ks}<br>{_bungkus(r['Subdimensi'], 18)}",
                          value=int(n_sub.get(ks, 0)), warna=r[skor],
                          hover=_hover(f"{ks} · {r['Subdimensi']}", r, r.get("Deskripsi Pertanyaan"))))
    for _, r in df_butir.iterrows():
        q, ks = r["Q"], r["Kode Subdimensi"]
        baris.append(dict(id=f"Q:{ks}:{q}", parent=f"S:{ks}", label=q, value=1, warna=r[skor],
                          label_panjang=f"<b>{q}</b><br>{_bungkus(r['Deskripsi Pertanyaan'], 24)}",
                          hover=_hover(q, r, r["Deskripsi Pertanyaan"])))

    h = pd.DataFrame(baris)
    h["label_panjang"] = h["label_panjang"].fillna(h["label"])
    h = h[h["value"] > 0].reset_index(drop=True)

    yatim = set(h["parent"]) - set(h["id"]) - {""}
    if yatim:
        print("PERINGATAN: kode induk tidak ditemukan di sheet atasnya:", sorted(yatim))
    return h


def _sumbu_warna(h, skor):
    """Satu skala warna dipakai bersama oleh sunburst & treemap."""
    if skor == "Selisih":
        batas = max(abs(h["warna"].min()), abs(h["warna"].max())) or 1
        return dict(colorscale=SKALA_SELISIH, cmin=-batas, cmax=batas)
    return dict(colorscale=SKALA_SKOR, cmin=h["warna"].min(), cmax=h["warna"].max())


def buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, skor="Pusat",
                tampilkan=True, simpan_ke=None, tinggi=780):
    """
    Satu halaman: sunburst (kiri) + treemap (kanan).

    skor      : "Pusat", "Daerah", atau "Selisih"
    tampilkan : True -> buka halaman di browser
    simpan_ke : folder untuk menyimpan .html (None = file sementara saja)

    Klik di sunburst membuat treemap ikut zoom ke bagian yang sama, dan sebaliknya.

    Mengembalikan satu figure Plotly.
    """
    h = susun_hierarki(df_map_dimensi, df_map_subdimensi, df_map_butir, skor)

    umum = dict(ids=h["id"], parents=h["parent"], values=h["value"], branchvalues="total",
                hovertext=h["hover"], hoverinfo="text",
                marker=dict(colors=h["warna"], coloraxis="coloraxis", line=dict(color=GARIS, width=1.5)),
                textfont=dict(color=TEKS, family=FONT))

    fig = make_subplots(rows=1, cols=2, column_widths=[0.45, 0.55], horizontal_spacing=0.03,
                        specs=[[{"type": "domain"}, {"type": "domain"}]],
                        subplot_titles=("Sunburst · klik irisan untuk memilih",
                                        "Treemap · ikut pilihan sunburst (klik tengah sunburst untuk kembali)"))
    fig.add_trace(go.Sunburst(labels=h["label"], insidetextorientation="radial", **umum), 1, 1)
    fig.add_trace(go.Treemap(labels=h["label_panjang"], tiling=dict(pad=3), root=dict(color=LATAR),
                             pathbar=dict(visible=False), **umum), 1, 2)
    fig.update_traces(textfont_size=15, selector=dict(type="treemap"))   # diperkecil otomatis bila sempit

    fig.update_layout(
        title=dict(text=f"<b>Skor Hasil Survei</b> · warna = skor {skor}", x=0.01,
                   font=dict(size=20, color=TEKS, family=FONT)),
        coloraxis=dict(**_sumbu_warna(h, skor),
                       colorbar=dict(title=dict(text=skor, font=dict(color=TEKS)), thickness=12, len=0.6,
                                     outlinewidth=0, tickfont=dict(color=TEKS))),
        paper_bgcolor=LATAR, plot_bgcolor=LATAR,
        font=dict(family=FONT, color=TEKS),
        hoverlabel=dict(bgcolor="white", bordercolor="#d8d4cc", font=dict(color=TEKS, family=FONT)),
        margin=dict(t=90, l=20, r=20, b=20), height=tinggi,
    )
    for judul in fig.layout.annotations:   # judul kecil di atas tiap grafik
        judul.font = dict(size=13, color="#6b7675", family=FONT)

    path = simpan_html(fig, skor, simpan_ke)
    if tampilkan:
        webbrowser.open(path.resolve().as_uri())
    return fig


# JavaScript yang menghubungkan kedua grafik: klik di sunburst -> treemap ikut
# zoom ke dimensi/subdimensi yang sama (dan sebaliknya), jadi teks pertanyaan
# panjang di treemap selalu mengikuti pilihan di sunburst.
JS_SINKRON = """
var gd = document.getElementById('{plot_id}');
function sinkron(e) {
    var lvl = e.nextLevel;
    if (lvl === undefined) { return false; }   // klik butir (daun): tidak ada zoom
    if (gd.data[0].ids.indexOf(lvl) < 0) { lvl = ''; }   // kembali ke tampilan penuh
    Plotly.restyle(gd, {level: [lvl, lvl]}, [0, 1]);
    return false;                              // ganti zoom bawaan dengan zoom bersama
}
gd.on('plotly_sunburstclick', sinkron);
gd.on('plotly_treemapclick', sinkron);
"""


def simpan_html(fig, skor, simpan_ke=None):
    """Tulis figure ke .html dengan sunburst & treemap yang saling terhubung."""
    if simpan_ke is None:
        folder = Path(tempfile.gettempdir())
    else:
        folder = Path(simpan_ke)
        folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"sunburst_treemap_{skor}.html"
    fig.write_html(path, post_script=JS_SINKRON, config={"displaylogo": False})
    if simpan_ke is not None:
        print("Tersimpan:", path)
    return path
