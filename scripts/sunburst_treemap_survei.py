# -*- coding: utf-8 -*-
"""
Modul sunburst & treemap Dimensi -> Subdimensi -> Butir (Q).

Dipanggil dari .py utama yang sudah memuat df_map_dimensi, df_map_subdimensi,
dan df_map_butir. Simpan file ini di folder yang sama dengan .py utama, lalu:

    from sunburst_treemap_survei import buat_grafik

    fig_sun, fig_tree = buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, skor="Pusat")

Kolom yang dipakai:
  Map_Dimensi    : Kode Dimensi, Dimensi, Pusat, Daerah, Selisih
  Map_Subdimensi : Kode Subdimensi, Subdimensi, Kode Dimensi, Deskripsi Pertanyaan, Pusat, Daerah, Selisih
  Map_Butir      : Q, Kode Subdimensi, Kode Dimensi, Deskripsi Pertanyaan, Pusat, Daerah, Selisih

Warna tiap irisan diambil langsung dari skor di sheet level masing-masing.
Luas irisan = jumlah butir.
"""

import textwrap
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

__all__ = ["buat_grafik", "buat_sunburst", "buat_treemap", "susun_hierarki"]

PILIHAN_SKOR = ("Pusat", "Daerah", "Selisih")


def _bungkus(teks, lebar=50):
    """Pecah teks panjang jadi beberapa baris untuk hover/label."""
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

    # jumlah butir per subdimensi & dimensi (untuk luas irisan)
    n_sub = df_butir.groupby("Kode Subdimensi").size()
    n_dim = df_butir.groupby("Kode Dimensi").size()

    baris = []
    for _, r in df_dim.iterrows():
        kd = r["Kode Dimensi"]
        baris.append(dict(id=f"D:{kd}", parent="", label=f"{kd}<br>{_bungkus(r['Dimensi'], 18)}",
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
                          label_panjang=f"<b>{q}</b><br>{_bungkus(r['Deskripsi Pertanyaan'], 30)}",
                          hover=_hover(q, r, r["Deskripsi Pertanyaan"])))

    h = pd.DataFrame(baris)
    h["label_panjang"] = h["label_panjang"].fillna(h["label"])

    # buang subdimensi/dimensi tanpa butir (luas 0 bikin Plotly error)
    h = h[h["value"] > 0].reset_index(drop=True)

    # peringatan bila ada kode yang tidak cocok antar sheet
    yatim = set(h["parent"]) - set(h["id"]) - {""}
    if yatim:
        print("PERINGATAN: kode induk tidak ditemukan di sheet atasnya:", sorted(yatim))
    return h


def _trace_umum(h, skor):
    if skor == "Selisih":   # diverging, 0 di tengah
        skala = dict(colorscale="RdBu", cmid=0)
    else:
        skala = dict(colorscale="RdYlGn", cmin=h["warna"].min(), cmax=h["warna"].max())
    marker = dict(colors=h["warna"], line=dict(color="white", width=1.5),
                  showscale=True, colorbar=dict(title=skor), **skala)
    return dict(ids=h["id"], parents=h["parent"], values=h["value"], branchvalues="total",
                hovertext=h["hover"], hoverinfo="text", marker=marker)


def buat_sunburst(df_map_dimensi, df_map_subdimensi, df_map_butir, skor="Pusat", tinggi=800):
    """Kembalikan figure sunburst (belum ditampilkan)."""
    h = susun_hierarki(df_map_dimensi, df_map_subdimensi, df_map_butir, skor)
    fig = go.Figure(go.Sunburst(labels=h["label"], insidetextorientation="radial",
                                **_trace_umum(h, skor)))
    fig.update_layout(title=f"Sunburst Skor Survei: {skor}  (klik irisan untuk zoom)",
                      margin=dict(t=60, l=10, r=10, b=10), height=tinggi)
    return fig


def buat_treemap(df_map_dimensi, df_map_subdimensi, df_map_butir, skor="Pusat", tinggi=800):
    """Kembalikan figure treemap (belum ditampilkan)."""
    h = susun_hierarki(df_map_dimensi, df_map_subdimensi, df_map_butir, skor)
    fig = go.Figure(go.Treemap(labels=h["label_panjang"], tiling=dict(pad=3),
                               pathbar=dict(visible=True), **_trace_umum(h, skor)))
    fig.update_layout(title=f"Treemap Skor Survei: {skor}  (klik kotak untuk zoom)",
                      margin=dict(t=60, l=10, r=10, b=10), height=tinggi)
    return fig


def buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, skor="Pusat",
                tampilkan=True, simpan_ke=None, renderer="browser"):
    """
    Buat sunburst + treemap sekaligus.

    skor      : "Pusat", "Daerah", atau "Selisih"
    tampilkan : True -> buka grafik (default di browser, cocok untuk Spyder)
    simpan_ke : folder untuk menyimpan .html (None = tidak disimpan)
    renderer  : renderer Plotly, mis. "browser" atau "svg" (gambar statis di Plots pane)

    Mengembalikan (fig_sunburst, fig_treemap).
    """
    fig_sun = buat_sunburst(df_map_dimensi, df_map_subdimensi, df_map_butir, skor)
    fig_tree = buat_treemap(df_map_dimensi, df_map_subdimensi, df_map_butir, skor)

    if tampilkan:
        fig_sun.show(renderer=renderer)
        fig_tree.show(renderer=renderer)
    if simpan_ke is not None:
        folder = Path(simpan_ke)
        folder.mkdir(parents=True, exist_ok=True)
        for nama, fig in [("sunburst", fig_sun), ("treemap", fig_tree)]:
            path = folder / f"{nama}_{skor}.html"
            fig.write_html(path)
            print("Tersimpan:", path)
    return fig_sun, fig_tree
