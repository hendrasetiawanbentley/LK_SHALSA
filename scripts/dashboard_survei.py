# -*- coding: utf-8 -*-
"""
Dasbor Skor Hasil Survei: 4 tab, masing-masing 4 grafik (tema gelap).

Simpan file ini di folder yang sama dengan sunburst_treemap_survei.py dan .py utama, lalu:

    from dashboard_survei import jalankan_dashboard

    jalankan_dashboard(df_map_dimensi, df_map_subdimensi, df_map_butir, target=4)

Browser terbuka otomatis ke http://127.0.0.1:8050
Untuk berhenti: klik tombol stop (kotak merah) di console Spyder, atau Ctrl+C.

Isi tab:
  1. Ringkasan Skor        -> sunburst + tabel pertanyaan (terhubung), gap per dimensi, capaian target
  2. Dimensi & Subdimensi  -> radar, peringkat gap subdimensi, 5 butir terendah, sebaran skor butir
  3. Responden             -> CONTOH (data dikira-kira), menunggu data responden
  4. Tren & Prioritas      -> sebagian CONTOH; gauge & matriks memakai skor asli

Panel berlabel "Data contoh" masih memakai angka perkiraan.

Perlu paket dash:  pip install dash
"""

import threading
import webbrowser

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html
from dash.dash_table.Format import Format, Scheme, Sign
from plotly.colors import sample_colorscale

from sunburst_treemap_survei import _rapikan, susun_hierarki

# --------------------------------------------------------------------------- tema
C = dict(
    bg="#0b1220", sidebar="#0e1626", panel="#121b2d", panel2="#172238", garis="#1f2b42",
    teks="#e7edf6", pudar="#8b98ae", aksen="#f59e0b", biru="#4c8dff", teal="#2cc4b0",
    hijau="#34c38f", merah="#e0735e", ungu="#9b8cff",
)
FONT = "Segoe UI, Inter, Helvetica, Arial, sans-serif"
# merah bata -> sangat muda, gradasi diperkuat (gelap = skor terendah, terang = skor tertinggi)
SKALA = [[0.00, "#4a120c"], [0.20, "#7f2418"], [0.40, "#b5432c"], [0.60, "#dd7a5c"],
         [0.80, "#f3b9a1"], [1.00, "#fff3ec"]]
LIKERT = ["#c45f48", "#e39a7f", "#5d6b82", "#6fb7c9", "#2cc4b0"]

CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: %(bg)s; color: %(teks)s; font-family: %(font)s; }
.app { display: grid; grid-template-columns: 230px minmax(0, 1fr); min-height: 100vh; }
.sidebar { background: %(sidebar)s; border-right: 1px solid %(garis)s; padding: 22px 14px;
           display: flex; flex-direction: column; gap: 6px; }
.brand { padding: 0 8px 18px; }
.brand b { display: block; font-size: 17px; letter-spacing: .04em; }
.brand span { font-size: 11px; color: %(aksen)s; letter-spacing: .12em; text-transform: uppercase; }
.nav { all: unset; cursor: pointer; padding: 11px 12px; border-radius: 8px; color: %(pudar)s;
       font-size: 14px; display: flex; gap: 10px; align-items: center; }
.nav:hover { background: %(panel2)s; color: %(teks)s; }
.nav.on { background: %(aksen)s; color: #1b1205; font-weight: 600; }
.nav i { font-style: normal; width: 18px; text-align: center; }
.side-foot { margin-top: auto; padding: 14px 12px; border: 1px solid %(garis)s; border-radius: 10px;
             font-size: 12px; color: %(pudar)s; line-height: 1.5; }
.side-foot b { color: %(teks)s; font-size: 20px; display: block; }
.main { padding: 20px 24px 32px; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.head { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.head h1 { margin: 0; font-size: 22px; letter-spacing: .02em; }
.head p { margin: 2px 0 0; font-size: 13px; color: %(pudar)s; }
.pill { font-size: 12px; padding: 6px 12px; border-radius: 8px; background: %(panel)s;
        border: 1px solid %(garis)s; color: %(pudar)s; }
.pill b { color: %(aksen)s; }
.legenda { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 12px; color: %(pudar)s; }
.leg-skala { display: flex; flex-direction: column; gap: 4px; min-width: 220px; }
.leg-bar { height: 10px; border-radius: 5px; }
.leg-angka { display: flex; justify-content: space-between; font-variant-numeric: tabular-nums; }
.leg-item { display: flex; align-items: center; gap: 6px; }
.leg-titik { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.kanan { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.kpi { background: %(panel)s; border: 1px solid %(garis)s; border-radius: 10px; padding: 14px 16px; }
.kpi .lbl { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: %(pudar)s; }
.kpi .val { font-size: 26px; font-weight: 700; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi .sub { font-size: 12px; color: %(pudar)s; margin-top: 2px; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.panel { background: %(panel)s; border: 1px solid %(garis)s; border-radius: 10px; padding: 14px 16px; min-width: 0; }
.panel h3 { margin: 0; font-size: 12.5px; letter-spacing: .07em; text-transform: uppercase; display: flex;
            align-items: center; gap: 8px; }
.panel .ket { font-size: 12px; color: %(pudar)s; margin: 3px 0 6px; }
.badge { font-size: 10px; letter-spacing: .04em; text-transform: none; padding: 2px 8px; border-radius: 99px;
         background: #2b2412; color: #f5c45e; font-weight: 600; }
.panel.lebar { grid-column: 1 / -1; }   /* panel selebar halaman */
.halaman { display: none; }
.halaman.on { display: block; }
@media (max-width: 1100px) {
  .app { grid-template-columns: 1fr; }
  .grid { grid-template-columns: 1fr; }
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
""" % dict(C, font=FONT)

INDEX = """<!DOCTYPE html>
<html><head>{%metas%}<title>Dasbor Skor Survei</title>{%favicon%}{%css%}<style>""" + CSS + """</style></head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

TAB = [("t1", "◉", "Ringkasan Skor"), ("t2", "▤", "Dimensi & Subdimensi"),
       ("t3", "◍", "Responden"), ("t4", "↗", "Tren & Prioritas")]


# --------------------------------------------------------------------------- bantuan
def _gaya(fig, tinggi=300, **kw):
    dasar = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=tinggi,
        font=dict(family=FONT, color=C["teks"], size=12), margin=dict(l=10, r=14, t=10, b=10),
        hoverlabel=dict(bgcolor=C["panel2"], bordercolor=C["garis"], font=dict(color=C["teks"], family=FONT)),
        showlegend=False)
    dasar.update(kw)
    fig.update_layout(**dasar)
    fig.update_xaxes(gridcolor=C["garis"], zerolinecolor=C["garis"], linecolor=C["garis"],
                     tickfont=dict(color=C["pudar"]))
    fig.update_yaxes(gridcolor=C["garis"], zerolinecolor=C["garis"], linecolor=C["garis"],
                     tickfont=dict(color=C["pudar"]))
    return fig


def _legenda_atas(fig):
    fig.update_layout(showlegend=True, legend=dict(orientation="h", x=0, y=1.12, font=dict(color=C["pudar"])),
                      margin=dict(l=10, r=14, t=36, b=10))
    return fig


def _graf(id_, fig):
    # tinggi dikunci sesuai figure; lebar mengikuti panel
    return dcc.Graph(id=id_, figure=fig, style={"height": f"{fig.layout.height}px"},
                     config={"displayModeBar": False, "responsive": True})


def _panel(judul, ket, isi, contoh=False, lebar=False):
    kepala = [judul] + ([html.Span("Data contoh", className="badge")] if contoh else [])
    return html.Div(className="panel lebar" if lebar else "panel",
                    children=[html.H3(kepala), html.P(ket, className="ket"), isi])


def _kpi(lbl, val, sub, warna=None):
    return html.Div(className="kpi", children=[
        html.Div(lbl, className="lbl"),
        html.Div(val, className="val", style={"color": warna} if warna else None),
        html.Div(sub, className="sub")])


def _warna_skor(nilai, cmin, cmax):
    t = 0.5 if cmax == cmin else min(max((nilai - cmin) / (cmax - cmin), 0), 1)
    return sample_colorscale(SKALA, [t])[0]


def _gelap(rgb):
    r, g, b = (float(v) for v in rgb[rgb.index("(") + 1:-1].split(",")[:3])
    return 0.299 * r + 0.587 * g + 0.114 * b < 150


def _bungkus_label(teks, lebar=18):
    """Pecah nama panjang jadi beberapa baris (<br>) untuk label grafik."""
    import textwrap
    return "<br>".join(textwrap.wrap(str(teks), lebar))


def _pendek(teks, n=28):
    teks = str(teks)
    return teks if len(teks) <= n else teks[:n - 1] + "…"


# --------------------------------------------------------------------------- aplikasi
def buat_app(df_map_dimensi, df_map_subdimensi, df_map_butir, target=4, kolom_skor="Keseluruhan"):
    df_dim, df_sub, df_butir = _rapikan(df_map_dimensi, df_map_subdimensi, df_map_butir, kolom_skor)
    h = susun_hierarki(df_dim, df_sub, df_butir, target)
    # skala warna direntangkan dari skor terendah sampai skor tertinggi yang ada,
    # supaya seluruh gradasi terpakai dan perbedaan antar-skor terlihat tegas
    cmin = h["warna"].min()
    cmax = h["warna"].max()
    if cmax - cmin < 0.05:
        cmin, cmax = cmin - 0.25, cmax + 0.25
    induk = dict(zip(h["id"], h["parent"]))
    judul_node = dict(zip(h["id"], h["judul"]))
    nama_sub = dict(zip(df_sub["Kode Subdimensi"], df_sub["Subdimensi"]))

    # tabel pertanyaan (satu baris per butir)
    tabel = pd.DataFrame({
        "id": "Q:" + df_butir["Kode Subdimensi"] + ":" + df_butir["Q"],
        "dim": "D:" + df_butir["Kode Dimensi"],
        "sub": "S:" + df_butir["Kode Subdimensi"],
        "Q": df_butir["Q"],
        "Subdimensi": df_butir["Kode Subdimensi"] + " · " + df_butir["Kode Subdimensi"].map(nama_sub).fillna(""),
        "Pertanyaan": df_butir["Deskripsi Pertanyaan"].astype(str),
        "Skor": df_butir["_skor"].round(2),
        "Gap": (df_butir["_skor"] - target).round(2),
    })

    skor_total = df_butir["_skor"].mean()
    gap_total = skor_total - target
    n_capai = int((df_butir["_skor"] >= target).sum())
    n_butir = len(df_butir)
    dim_min = df_dim.loc[df_dim["_skor"].idxmin()]
    sub_min = df_sub.loc[df_sub["_skor"].idxmin()]
    rng = np.random.default_rng(7)   # untuk data contoh

    # ---------------- Tab 1: Ringkasan Skor
    f_sun = go.Figure(go.Sunburst(
        ids=h["id"], parents=h["parent"], values=h["value"], labels=h["label"], branchvalues="total",
        hovertext=h["hover"], hoverinfo="text", insidetextorientation="radial",
        marker=dict(colors=h["warna"], colorscale=SKALA, cmin=cmin, cmax=cmax,
                    line=dict(color=C["panel"], width=1.5)),
        textfont=dict(family=FONT)))
    _gaya(f_sun, 460)

    d_urut = df_dim.sort_values("_skor")
    f_gapdim = go.Figure(go.Bar(
        y=d_urut["Kode Dimensi"] + " · " + d_urut["Dimensi"].map(_pendek), x=d_urut["_skor"], orientation="h",
        marker=dict(color=[_warna_skor(v, cmin, cmax) for v in d_urut["_skor"]]),
        text=[f"{v:.2f}  ({v - target:+.2f})" for v in d_urut["_skor"]], textposition="outside",
        textfont=dict(color=C["teks"]), hovertemplate="%{y}<br>Skor %{x:.2f}<extra></extra>"))
    f_gapdim.add_vline(x=target, line=dict(color=C["aksen"], dash="dash", width=1.5),
                       annotation=dict(text=f"target {target:g}", font=dict(color=C["aksen"]), yanchor="bottom"))
    _gaya(f_gapdim, 300, xaxis=dict(range=[0, max(5, cmax) + 0.6]), bargap=0.35,
          margin=dict(l=10, r=14, t=26, b=10))

    # spider web: capaian tiap dimensi terhadap target (skor / target x 100%)
    capai_pct = df_dim["_skor"] / target * 100
    # label sudut: kode + nama dimensi (dipecah 2 baris agar tidak terpotong)
    label_dim = [f"<b>{k}</b><br>{_bungkus_label(n)}" for k, n in zip(df_dim["Kode Dimensi"], df_dim["Dimensi"])]
    teta_c = label_dim + [label_dim[0]]
    r_c = list(capai_pct) + [capai_pct.iloc[0]]
    skor_c = list(df_dim["_skor"]) + [df_dim["_skor"].iloc[0]]
    nama_c = list(df_dim["Dimensi"]) + [df_dim["Dimensi"].iloc[0]]
    bawah_c = max(0, np.floor((capai_pct.min() - 15) / 10) * 10)      # mulai di bawah capaian terendah
    atas_c = max(110, np.ceil((capai_pct.max() + 5) / 10) * 10)       # selalu tampak garis 100%
    f_capai = go.Figure()
    f_capai.add_trace(go.Scatterpolar(
        r=r_c, theta=teta_c, name="Capaian", mode="lines+markers", fill="toself",
        fillcolor="rgba(224,115,94,0.25)", line=dict(color=C["merah"], width=2),
        marker=dict(size=9, color=[_warna_skor(v, cmin, cmax) for v in skor_c], line=dict(color=C["panel"], width=1)),
        customdata=[[n, float(v)] for n, v in zip(nama_c, skor_c)],
        hovertemplate="%{customdata[0]}<br>Skor %{customdata[1]:.2f} · capaian %{r:.1f}% dari target"
                      "<extra></extra>"))
    _legenda_atas(_gaya(f_capai, 420, polar=dict(
        domain=dict(x=[0.2, 0.8], y=[0.12, 0.84]), bgcolor="rgba(0,0,0,0)",
        # hanya lingkaran 100% (= target) yang dinyalakan sebagai garis target
        radialaxis=dict(range=[bawah_c, atas_c], tickvals=[100], ticktext=[f"100% · target {target:g}"],
                        gridcolor="#ffffff", gridwidth=2, showline=False,
                        tickfont=dict(color=C["teks"], size=10), angle=30, tickangle=30),
        angularaxis=dict(gridcolor="rgba(255,255,255,0.25)", linecolor="rgba(255,255,255,0.25)",
                         tickfont=dict(color=C["teks"], size=11)))))

    kolom_tabel = [
        dict(name="Q", id="Q"), dict(name="Subdimensi", id="Subdimensi"),
        dict(name="Pertanyaan", id="Pertanyaan"),
        dict(name="Skor", id="Skor", type="numeric", format=Format(precision=2, scheme=Scheme.fixed)),
        dict(name=f"Gap (vs {target:g})", id="Gap", type="numeric",
             format=Format(precision=2, scheme=Scheme.fixed, sign=Sign.positive)),
    ]
    komp_tabel = dash_table.DataTable(
        id="tabel", columns=kolom_tabel, data=tabel.to_dict("records"),
        page_action="none",
        style_table={"height": "430px", "overflowY": "auto", "overflowX": "auto"},
        style_header={"backgroundColor": C["panel2"], "color": C["teks"], "fontWeight": "600",
                      "border": f"1px solid {C['garis']}", "fontFamily": FONT, "fontSize": "12px"},
        style_cell={"backgroundColor": C["panel"], "color": C["teks"], "border": f"1px solid {C['garis']}",
                    "fontFamily": FONT, "fontSize": "13px", "textAlign": "left", "whiteSpace": "normal",
                    "height": "auto", "padding": "7px 8px"},
        style_cell_conditional=[
            {"if": {"column_id": "Q"}, "width": "52px"},
            {"if": {"column_id": "Subdimensi"}, "width": "140px"},
            {"if": {"column_id": "Pertanyaan"}, "minWidth": "200px"},
            {"if": {"column_id": "Skor"}, "width": "62px", "textAlign": "right"},
            {"if": {"column_id": "Gap"}, "width": "86px", "textAlign": "right"},
        ])

    hal1 = html.Div(className="grid", children=[
        _panel("Peta skor", "Klik dimensi / subdimensi untuk zoom; klik tengah untuk kembali.", _graf("sunburst", f_sun)),
        _panel(html.Span("Daftar pertanyaan", id="judul-tabel"),
               "Ikut berubah sesuai pilihan di peta skor.", komp_tabel),
        _panel("Capaian target per dimensi",
               f"Skor ÷ target {target:g} × 100%. Lingkaran putih = 100% (target tercapai). "
               f"{n_capai}/{n_butir} butir sudah ≥ target.", _graf("g-capai", f_capai), lebar=True),
        _panel("Skor per dimensi", f"Garis putus-putus = target {target:g}; angka dalam kurung = gap.",
               _graf("g-gapdim", f_gapdim), lebar=True),
    ])

    # ---------------- Tab 2: Dimensi & Subdimensi
    teta = list(df_dim["Kode Dimensi"]) + [df_dim["Kode Dimensi"].iloc[0]]
    nilai = list(df_dim["_skor"]) + [df_dim["_skor"].iloc[0]]
    batas_r = max(5, float(np.ceil(cmax)))
    f_radar = go.Figure()
    f_radar.add_trace(go.Scatterpolar(r=[target] * len(teta), theta=teta, name=f"Target {target:g}",
                                      line=dict(color=C["aksen"], dash="dash", width=1.5), mode="lines"))
    f_radar.add_trace(go.Scatterpolar(r=nilai, theta=teta, name="Skor", fill="toself",
                                      fillcolor="rgba(44,196,176,0.18)", line=dict(color=C["teal"], width=2),
                                      hovertemplate="%{theta}: %{r:.2f}<extra></extra>"))
    _legenda_atas(_gaya(f_radar, 340, polar=dict(domain=dict(x=[0.08, 0.92], y=[0.02, 0.9]),
        bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0, batas_r], gridcolor=C["garis"], linecolor=C["garis"],
                                                 tickfont=dict(color=C["pudar"])),
        angularaxis=dict(gridcolor=C["garis"], linecolor=C["garis"], tickfont=dict(color=C["teks"])))))

    s_urut = df_sub.assign(gap=df_sub["_skor"] - target).sort_values("gap", ascending=False)
    label_s = s_urut["Kode Subdimensi"] + " · " + s_urut["Subdimensi"].map(_pendek)
    garis_x, garis_y = [], []
    for g, lb in zip(s_urut["gap"], label_s):
        garis_x += [0, g, None]
        garis_y += [lb, lb, None]
    f_lolli = go.Figure([
        go.Scatter(x=garis_x, y=garis_y, mode="lines", line=dict(color=C["garis"], width=3), hoverinfo="skip"),
        go.Scatter(x=s_urut["gap"], y=label_s, mode="markers",
                   marker=dict(size=11, color=[C["hijau"] if g >= 0 else C["merah"] for g in s_urut["gap"]]),
                   hovertemplate="%{y}<br>Gap %{x:+.2f}<extra></extra>")])
    f_lolli.add_vline(x=0, line=dict(color=C["aksen"], dash="dash", width=1.5))
    _gaya(f_lolli, max(320, 26 * len(s_urut) + 40))

    terendah = tabel.nsmallest(5, "Skor").iloc[::-1]
    f_bawah = go.Figure(go.Bar(
        y=terendah["Q"] + " · " + terendah["Pertanyaan"].map(lambda t: _pendek(t, 40)), x=terendah["Skor"],
        orientation="h", marker=dict(color=[_warna_skor(v, cmin, cmax) for v in terendah["Skor"]]),
        text=[f"{v:.2f}" for v in terendah["Skor"]], textposition="outside", textfont=dict(color=C["teks"]),
        customdata=terendah["Pertanyaan"], hovertemplate="%{customdata}<br>Skor %{x:.2f}<extra></extra>"))
    f_bawah.add_vline(x=target, line=dict(color=C["aksen"], dash="dash", width=1.5))
    _gaya(f_bawah, 300, xaxis=dict(range=[0, max(5, cmax) + 0.5]), bargap=0.35)

    f_hist = go.Figure(go.Histogram(x=tabel["Skor"], xbins=dict(size=0.2), marker=dict(
        color=C["biru"], line=dict(color=C["panel"], width=1)), hovertemplate="Skor %{x}: %{y} butir<extra></extra>"))
    f_hist.add_vline(x=target, line=dict(color=C["aksen"], dash="dash", width=1.5),
                     annotation=dict(text=f"target {target:g}", font=dict(color=C["aksen"])))
    _gaya(f_hist, 300, bargap=0.05, yaxis=dict(dtick=1, title=dict(text="jumlah butir", font=dict(color=C["pudar"]))))

    hal2 = html.Div(className="grid", children=[
        _panel("Profil dimensi", "Skor tiap dimensi dibanding target.", _graf("g-radar", f_radar)),
        _panel("Gap subdimensi", "Diurutkan dari gap terbesar; merah = di bawah target.", _graf("g-lolli", f_lolli)),
        _panel("5 butir terendah", "Prioritas perbaikan berdasarkan skor butir.", _graf("g-bawah", f_bawah)),
        _panel("Sebaran skor butir", "Berapa banyak butir di tiap rentang skor.", _graf("g-hist", f_hist)),
    ])

    # ---------------- Tab 3: Responden (data contoh)
    unit = ["Kantor Pusat", "Wilayah I", "Wilayah II", "Wilayah III", "Wilayah IV", "Wilayah V"]
    n_unit = rng.integers(40, 160, len(unit))
    f_unit = go.Figure(go.Bar(x=unit, y=n_unit, marker=dict(color=C["biru"]), text=n_unit, textposition="outside",
                              textfont=dict(color=C["teks"]), hovertemplate="%{x}: %{y} responden<extra></extra>"))
    _gaya(f_unit, 300, bargap=0.4)

    jabatan = ["Pimpinan", "Manajer", "Staf", "Pelaksana"]
    f_jab = go.Figure(go.Pie(labels=jabatan, values=[6, 18, 46, 30], hole=0.6, sort=False,
                             marker=dict(colors=[C["aksen"], C["ungu"], C["biru"], C["teal"]],
                                         line=dict(color=C["panel"], width=3)),
                             textinfo="percent", textfont=dict(color="#0b1220")))
    _legenda_atas(_gaya(f_jab, 300))

    kategori = ["Sangat tidak setuju", "Tidak setuju", "Netral", "Setuju", "Sangat setuju"]
    sebaran = rng.dirichlet([1, 2, 4, 6, 3], len(df_dim)) * 100
    f_likert = go.Figure([go.Bar(y=df_dim["Kode Dimensi"], x=sebaran[:, k], name=kategori[k], orientation="h",
                                 marker=dict(color=LIKERT[k]),
                                 hovertemplate="%{y} · " + kategori[k] + ": %{x:.0f}%<extra></extra>")
                          for k in range(5)])
    _legenda_atas(_gaya(f_likert, 300, barmode="stack", bargap=0.35, xaxis=dict(ticksuffix="%", range=[0, 100])))
    f_likert.update_layout(legend=dict(traceorder="normal", y=1.22), margin=dict(l=10, r=14, t=58, b=10))

    minggu = [f"Mg {i}" for i in range(1, 9)]
    partisipasi = np.clip(np.cumsum(rng.uniform(6, 16, len(minggu))), 0, 100)
    f_partisipasi = go.Figure(go.Scatter(x=minggu, y=partisipasi, mode="lines+markers", fill="tozeroy",
                                         line=dict(color=C["teal"], width=2.5),
                                         fillcolor="rgba(44,196,176,0.12)",
                                         hovertemplate="%{x}: %{y:.0f}%<extra></extra>"))
    _gaya(f_partisipasi, 300, yaxis=dict(range=[0, 100], ticksuffix="%"))

    hal3 = html.Div(className="grid", children=[
        _panel("Responden per unit kerja", "Jumlah responden yang mengisi survei.", _graf("g-unit", f_unit), True),
        _panel("Komposisi jabatan", "Proporsi responden per level jabatan.", _graf("g-jab", f_jab), True),
        _panel("Sebaran jawaban per dimensi", "Persentase tiap pilihan jawaban Likert.", _graf("g-likert", f_likert), True),
        _panel("Tingkat partisipasi", "Kumulatif persentase responden per minggu.", _graf("g-part", f_partisipasi), True),
    ])

    # ---------------- Tab 4: Tren & Prioritas
    periode = ["2023", "2024", "2025", "2026"]
    tren = [skor_total - 0.45, skor_total - 0.3, skor_total - 0.12, skor_total]
    f_tren = go.Figure(go.Scatter(x=periode, y=tren, mode="lines+markers+text", line=dict(color=C["biru"], width=2.5),
                                  marker=dict(size=9), text=[f"{v:.2f}" for v in tren], textposition="top center",
                                  textfont=dict(color=C["teks"]), hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
    f_tren.add_hline(y=target, line=dict(color=C["aksen"], dash="dash", width=1.5),
                     annotation=dict(text=f"target {target:g}", font=dict(color=C["aksen"])))
    _gaya(f_tren, 300, yaxis=dict(range=[min(tren) - 0.5, max(max(tren), target) + 0.4]))

    f_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=skor_total,
        number=dict(valueformat=".2f", font=dict(color=C["teks"], size=40)),
        delta=dict(reference=target, valueformat="+.2f", increasing=dict(color=C["hijau"]),
                   decreasing=dict(color=C["merah"])),
        gauge=dict(axis=dict(range=[0, batas_r], tickcolor=C["pudar"], tickfont=dict(color=C["pudar"])),
                   bar=dict(color=C["teal"], thickness=0.28), bgcolor=C["panel2"], borderwidth=0,
                   threshold=dict(line=dict(color=C["aksen"], width=3), thickness=0.8, value=target))))
    _gaya(f_gauge, 300, margin=dict(l=30, r=30, t=30, b=10))

    penting = rng.uniform(3.2, 4.9, len(df_sub))
    f_matriks = go.Figure(go.Scatter(
        x=df_sub["_skor"], y=penting, mode="markers+text", text=df_sub["Kode Subdimensi"], textposition="top center",
        textfont=dict(color=C["pudar"], size=11),
        marker=dict(size=12, color=[_warna_skor(v, cmin, cmax) for v in df_sub["_skor"]],
                    line=dict(color=C["panel"], width=1)),
        customdata=df_sub["Subdimensi"],
        hovertemplate="%{text} · %{customdata}<br>Skor %{x:.2f} · Kepentingan %{y:.2f}<extra></extra>"))
    f_matriks.add_vline(x=target, line=dict(color=C["aksen"], dash="dash", width=1))
    f_matriks.add_hline(y=float(np.median(penting)), line=dict(color=C["garis"], dash="dot", width=1))
    f_matriks.add_annotation(x=0.01, y=0.99, xref="paper", yref="paper", text="PRIORITAS UTAMA", showarrow=False,
                             xanchor="left", yanchor="top", font=dict(color=C["merah"], size=11))
    _gaya(f_matriks, 300, xaxis=dict(title=dict(text="skor (asli)", font=dict(color=C["pudar"]))),
          yaxis=dict(title=dict(text="kepentingan (contoh)", font=dict(color=C["pudar"]))))

    status = ["Selesai", "Berjalan", "Belum mulai"]
    jml = rng.integers(0, 6, (3, len(df_dim)))
    f_aksi = go.Figure([go.Bar(x=df_dim["Kode Dimensi"], y=jml[k], name=status[k],
                               marker=dict(color=[C["hijau"], C["aksen"], "#5d6b82"][k]))
                        for k in range(3)])
    _legenda_atas(_gaya(f_aksi, 300, barmode="stack", bargap=0.4))

    hal4 = html.Div(className="grid", children=[
        _panel("Tren skor keseluruhan", "Perbandingan antarperiode survei.", _graf("g-tren", f_tren), True),
        _panel("Capaian terhadap target", f"Skor keseluruhan (rata-rata butir) vs target {target:g}.",
               _graf("g-gauge", f_gauge)),
        _panel("Matriks prioritas", "Kiri atas = penting tetapi skornya rendah.", _graf("g-matriks", f_matriks), True),
        _panel("Status rencana aksi", "Jumlah rencana aksi per dimensi.", _graf("g-aksi", f_aksi), True),
    ])

    # ---------------- kerangka halaman
    app = Dash(__name__, title="Dasbor Skor Survei")
    app.index_string = INDEX

    sidebar = html.Div(className="sidebar", children=[
        html.Div(className="brand", children=[html.B("SKOR SURVEI"), html.Span("Dasbor hasil survei")]),
        *[html.Button([html.I(ikon), nama], id=f"nav-{kode}", n_clicks=0,
                      className="nav on" if kode == "t1" else "nav") for kode, ikon, nama in TAB],
        html.Div(className="side-foot", children=[
            "Target skor", html.B(f"{target:g}"),
            f"{n_capai} dari {n_butir} butir sudah tercapai."]),
    ])

    warna_gap = C["hijau"] if gap_total >= 0 else C["merah"]
    kepala = html.Div(className="head", children=[
        html.Div([html.H1("Dasbor Skor Hasil Survei"),
                  html.P(f"Skor {kolom_skor.lower()} · {len(df_dim)} dimensi · {len(df_sub)} subdimensi · "
                         f"{n_butir} butir")]),
        html.Div(className="kanan", children=[
            # legenda warna: skala skor (gelap = jauh di bawah target) + arti warna gap
            html.Div(className="legenda", children=[
                html.Div(className="leg-skala", children=[
                    html.Div(className="leg-bar", style={"background": "linear-gradient(to right, " +
                             ", ".join(f"{w} {p * 100:.0f}%" for p, w in SKALA) + ")"}),
                    html.Div(className="leg-angka", children=[
                        html.Span(f"Skor {cmin:.2f} · rendah"), html.Span(f"tinggi · {cmax:.2f}")]),
                ]),
                html.Span(className="leg-item", children=[
                    html.I(className="leg-titik", style={"background": C["merah"]}), "Di bawah target"]),
                html.Span(className="leg-item", children=[
                    html.I(className="leg-titik", style={"background": C["hijau"]}), "Tercapai"]),
            ]),
            html.Div(className="pill", children=["Target ", html.B(f"{target:g}")]),
        ]),
    ])
    kpis = html.Div(className="kpis", children=[
        _kpi("Skor keseluruhan", f"{skor_total:.2f}", "rata-rata seluruh butir"),
        _kpi("Gap terhadap target", f"{gap_total:+.2f}", f"target {target:g}", warna_gap),
        _kpi("Butir tercapai", f"{n_capai}/{n_butir}", f"{n_capai / n_butir:.0%} butir ≥ target"),
        _kpi("Dimensi terendah", f"{dim_min['_skor']:.2f}", f"{dim_min['Kode Dimensi']} · {dim_min['Dimensi']}",
             C["merah"] if dim_min["_skor"] < target else None),
    ])
    halaman = [html.Div(isi, id=f"hal-{kode}", className="halaman on" if kode == "t1" else "halaman")
               for (kode, _, _), isi in zip(TAB, [hal1, hal2, hal3, hal4])]

    app.layout = html.Div(className="app", children=[
        sidebar,
        html.Div(className="main", children=[kepala, kpis, *halaman, dcc.Store(id="level", data="")]),
    ])

    # ---------------- interaksi
    @app.callback(*[Output(f"nav-{k}", "className") for k, _, _ in TAB],
                  *[Output(f"hal-{k}", "className") for k, _, _ in TAB],
                  *[Input(f"nav-{k}", "n_clicks") for k, _, _ in TAB])
    def ganti_tab(*_):
        aktif = (ctx.triggered_id or "nav-t1").replace("nav-", "")
        nav = ["nav on" if k == aktif else "nav" for k, _, _ in TAB]
        hal = ["halaman on" if k == aktif else "halaman" for k, _, _ in TAB]
        return *nav, *hal

    @app.callback(Output("tabel", "data"), Output("tabel", "style_data_conditional"),
                  Output("judul-tabel", "children"), Output("level", "data"),
                  Input("sunburst", "clickData"), State("level", "data"))
    def klik_sunburst(klik, level):
        level = level or ""
        node, sorot = level, None
        if klik:
            pid = klik["points"][0].get("id", "")
            if pid.startswith("Q:"):                 # klik butir: tampilkan subdimensinya, sorot butirnya
                node, sorot = induk.get(pid, ""), pid
            elif pid == level:                       # klik tengah: naik satu tingkat
                level = induk.get(pid, "")
                node = level
            else:                                    # klik dimensi / subdimensi: zoom masuk
                level = node = pid

        if node.startswith("D:"):
            data = tabel[tabel["dim"] == node]
        elif node.startswith("S:"):
            data = tabel[tabel["sub"] == node]
        else:
            data = tabel
        data = data.reset_index(drop=True)

        gaya = []
        for i, r in data.iterrows():
            if pd.notna(r["Skor"]):
                w = _warna_skor(r["Skor"], cmin, cmax)
                gaya.append({"if": {"row_index": i, "column_id": "Skor"}, "backgroundColor": w,
                             "color": "#ffffff" if _gelap(w) else "#1b2230"})
            if pd.notna(r["Gap"]):
                gaya.append({"if": {"row_index": i, "column_id": "Gap"},
                             "backgroundColor": "rgba(52,195,143,0.18)" if r["Gap"] >= 0 else "rgba(224,115,94,0.20)"})
            if r["id"] == sorot:
                gaya.append({"if": {"row_index": i}, "backgroundColor": "#3a2f12", "color": C["teks"],
                             "fontWeight": "600"})

        n_bawah = int((data["Gap"] < 0).sum())
        nama = judul_node.get(node, "Semua pertanyaan")
        judul = f"Daftar pertanyaan · {nama} ({len(data)} butir, {n_bawah} di bawah target)"
        return data.to_dict("records"), gaya, judul, level

    return app


def jalankan_dashboard(df_map_dimensi, df_map_subdimensi, df_map_butir, target=4,
                       kolom_skor="Keseluruhan", port=8050, buka_browser=True):
    """Bangun dan jalankan dasbor. Hentikan dengan tombol stop di console Spyder (atau Ctrl+C)."""
    app = buat_app(df_map_dimensi, df_map_subdimensi, df_map_butir, target, kolom_skor)
    alamat = f"http://127.0.0.1:{port}"
    print(f"Dasbor berjalan di {alamat}  (hentikan dengan tombol stop / Ctrl+C)")
    if buka_browser:
        threading.Timer(1.5, lambda: webbrowser.open(alamat)).start()
    jalan = getattr(app, "run", None) or app.run_server
    jalan(debug=False, port=port)
