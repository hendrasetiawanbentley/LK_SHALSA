# -*- coding: utf-8 -*-
"""
Sunburst & Treemap Dimensi -> Subdimensi -> Butir (Q) dari file Skor Hasil Survei.

Kolom yang dipakai (sesuai file Anda):
  Map_Dimensi    : Kode Dimensi, Dimensi, Jumlah Subdimensi, Pusat, Daerah, Selisih
  Map_Subdimensi : Kode Subdimensi, Subdimensi, Kode Dimensi, Dimensi,
                   Deskripsi Pertanyaan, Jumlah Butir, Pusat, Daerah, Selisih
  Map_Butir      : Q, Kode Subdimensi, Subdimensi, Kode Dimensi, Dimensi,
                   Deskripsi Pertanyaan, Pusat, Daerah, Selisih

Warna tiap irisan diambil LANGSUNG dari skor di sheet masing-masing level
(dimensi dari Map_Dimensi, subdimensi dari Map_Subdimensi, butir dari Map_Butir),
bukan dihitung ulang. Luas irisan = jumlah butir.

Cara pakai di Spyder:
  1. Ubah PATH_EXCEL dan SKOR (Pusat / Daerah / Selisih).
  2. Tekan F5. Grafik terbuka di browser dan juga disimpan sebagai file .html.
  Jika df_map_dimensi, df_map_subdimensi, df_map_butir sudah ada di Variable
  Explorer, cukup panggil: buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, "Pusat")
"""

import textwrap
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------------------
PATH_EXCEL = Path(r"C:\Users\NamaAnda\Documents\Skor Hasil Survei.xlsx")
SKOR = "Pusat"          # pilih: "Pusat", "Daerah", atau "Selisih"
pio.renderers.default = "browser"   # agar grafik tampil dari Spyder
# ---------------------------------------------------------------------------


def _bungkus(teks, lebar=50):
    """Pecah teks panjang jadi beberapa baris untuk hover/label."""
    if pd.isna(teks):
        return ""
    return "<br>".join(textwrap.wrap(str(teks), lebar))


def _fmt(x):
    return "-" if pd.isna(x) else f"{x:,.2f}"


def _hover(judul, row, deskripsi=None):
    teks = f"<b>{judul}</b>"
    if deskripsi:
        teks += f"<br>{_bungkus(deskripsi)}"
    teks += (f"<br><br>Pusat   : {_fmt(row['Pusat'])}"
             f"<br>Daerah  : {_fmt(row['Daerah'])}"
             f"<br>Selisih : {_fmt(row['Selisih'])}")
    return teks


def susun_hierarki(df_dim, df_sub, df_butir, skor="Pusat"):
    """Gabungkan 3 sheet jadi satu tabel ids/parents/values/warna untuk Plotly."""
    df_dim, df_sub, df_butir = df_dim.copy(), df_sub.copy(), df_butir.copy()
    for df, kolom in [(df_dim, ["Kode Dimensi"]),
                      (df_sub, ["Kode Subdimensi", "Kode Dimensi"]),
                      (df_butir, ["Q", "Kode Subdimensi", "Kode Dimensi"])]:
        for k in kolom:
            df[k] = df[k].astype(str).str.strip()
        for k in ["Pusat", "Daerah", "Selisih"]:
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


def _skala(skor, warna):
    if skor == "Selisih":   # diverging, 0 di tengah
        return dict(colorscale="RdBu", cmid=0)
    return dict(colorscale="RdYlGn", cmin=warna.min(), cmax=warna.max())


def buat_grafik(df_dim, df_sub, df_butir, skor="Pusat", simpan=True):
    h = susun_hierarki(df_dim, df_sub, df_butir, skor)
    marker = dict(colors=h["warna"], line=dict(color="white", width=1.5),
                  showscale=True, colorbar=dict(title=skor), **_skala(skor, h["warna"]))
    umum = dict(ids=h["id"], parents=h["parent"], values=h["value"], branchvalues="total",
                hovertext=h["hover"], hoverinfo="text", marker=marker)

    fig_sun = go.Figure(go.Sunburst(labels=h["label"], insidetextorientation="radial",
                                    maxdepth=3, **umum))
    fig_sun.update_layout(title=f"Sunburst Skor Survei: {skor}  (klik irisan untuk zoom)",
                          margin=dict(t=60, l=10, r=10, b=10), height=800)

    fig_tree = go.Figure(go.Treemap(labels=h["label_panjang"], tiling=dict(pad=3),
                                    pathbar=dict(visible=True), **umum))
    fig_tree.update_layout(title=f"Treemap Skor Survei: {skor}  (klik kotak untuk zoom)",
                           margin=dict(t=60, l=10, r=10, b=10), height=800)

    fig_sun.show()
    fig_tree.show()
    if simpan:
        fig_sun.write_html(f"sunburst_{skor}.html")
        fig_tree.write_html(f"treemap_{skor}.html")
        print(f"Tersimpan: sunburst_{skor}.html dan treemap_{skor}.html")
    return fig_sun, fig_tree


if __name__ == "__main__":
    dfs = pd.read_excel(PATH_EXCEL, sheet_name=["Map_Dimensi", "Map_Subdimensi", "Map_Butir"])
    for df in dfs.values():
        df.columns = [str(c).strip() for c in df.columns]
    df_map_dimensi = dfs["Map_Dimensi"]
    df_map_subdimensi = dfs["Map_Subdimensi"]
    df_map_butir = dfs["Map_Butir"]

    fig_sun, fig_tree = buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, SKOR)
