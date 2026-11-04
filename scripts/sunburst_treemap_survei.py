# -*- coding: utf-8 -*-
"""
Sunburst Dimensi -> Subdimensi -> Butir (Q) + tabel daftar pertanyaan, satu halaman.
Skor dibandingkan dengan TARGET (default 4) dan ditampilkan kolom Gap.

Simpan file ini di folder yang sama dengan .py utama, lalu:

    from sunburst_treemap_survei import buat_grafik

    fig = buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir)            # skor keseluruhan, target 4
    fig = buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, target=4.2)

Skor yang dipakai = kolom "Keseluruhan". Jika kolom itu tidak ada di sheet,
skor keseluruhan dihitung sebagai rata-rata kolom Pusat dan Daerah.
(Nanti bisa diganti, mis. kolom_skor="Pusat".)

Gap = Skor - Target  ->  negatif = di bawah target, positif/nol = target tercapai.
Warna sunburst berpusat di target: koral = di bawah target, hijau = di atas target.

Kiri : sunburst (klik irisan untuk zoom, klik tengah untuk kembali).
Kanan: tabel pertanyaan yang ikut berubah sesuai pilihan di sunburst
       - klik dimensi    -> semua pertanyaan di dimensi itu
       - klik subdimensi -> pertanyaan di subdimensi itu
       - klik butir (Q)  -> pertanyaan subdimensinya, butir itu disorot
"""

import json
import textwrap

import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from plotly.subplots import make_subplots

__all__ = ["buat_grafik", "susun_hierarki"]

# Palet lembut berpusat di target: koral (di bawah) -> krem (= target) -> hijau teal (di atas)
SKALA = [[0.00, "#d9765e"], [0.25, "#eba98f"], [0.50, "#f6efdc"], [0.75, "#a9d0b0"], [1.00, "#4f9a83"]]

LATAR = "#fbfaf7"
TEKS = "#33403f"
TEKS_PUDAR = "#6b7675"
GARIS = "#ffffff"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"
BARIS_A, BARIS_B, BARIS_SOROT = "#ffffff", "#f5f3ee", "#fde9c4"
KEPALA_TABEL = "#e9ede9"
GAP_MINUS, GAP_PLUS = "#f6d3c8", "#d3e8d9"


def _bungkus(teks, lebar=50):
    if pd.isna(teks):
        return ""
    return "<br>".join(textwrap.wrap(str(teks), lebar))


def _fmt(x, tanda=False):
    if pd.isna(x):
        return "-"
    return f"{x:+.2f}" if tanda else f"{x:.2f}"


def _siapkan_skor(df, kolom_skor, nama_sheet):
    """Isi kolom '_skor' dari kolom_skor; 'Keseluruhan' dihitung dari Pusat & Daerah bila belum ada."""
    if kolom_skor in df.columns:
        df["_skor"] = pd.to_numeric(df[kolom_skor], errors="coerce")
    elif kolom_skor == "Keseluruhan" and {"Pusat", "Daerah"} <= set(df.columns):
        df["_skor"] = df[["Pusat", "Daerah"]].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        print(f"Info: kolom 'Keseluruhan' tidak ada di {nama_sheet}; dipakai rata-rata Pusat & Daerah.")
    else:
        raise KeyError(f"Kolom {kolom_skor!r} tidak ada di {nama_sheet}. Kolom tersedia: {list(df.columns)}")
    return df


def _rapikan(df_map_dimensi, df_map_subdimensi, df_map_butir, kolom_skor):
    hasil = []
    for df, kolom, nama in [(df_map_dimensi, ["Kode Dimensi"], "Map_Dimensi"),
                            (df_map_subdimensi, ["Kode Subdimensi", "Kode Dimensi"], "Map_Subdimensi"),
                            (df_map_butir, ["Q", "Kode Subdimensi", "Kode Dimensi"], "Map_Butir")]:
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        for k in kolom:
            df[k] = df[k].astype(str).str.strip()
        hasil.append(_siapkan_skor(df, kolom_skor, nama))
    return hasil


def _hover(judul, skor, target, deskripsi=None):
    teks = f"<b>{judul}</b>"
    if deskripsi is not None and not pd.isna(deskripsi):
        teks += f"<br>{_bungkus(deskripsi)}"
    gap = skor - target
    status = "-" if pd.isna(gap) else ("Tercapai" if gap >= 0 else "Di bawah target")
    teks += (f"<br><br>Skor   : {_fmt(skor)}"
             f"<br>Target : {_fmt(target)}"
             f"<br>Gap    : {_fmt(gap, tanda=True)}  ({status})")
    return teks


def susun_hierarki(df_dim, df_sub, df_butir, target=4):
    """Tabel ids/parents/values/warna untuk sunburst (DataFrame sudah dirapikan)."""
    n_sub = df_butir.groupby("Kode Subdimensi").size()
    n_dim = df_butir.groupby("Kode Dimensi").size()

    baris = []
    for _, r in df_dim.iterrows():
        kd = r["Kode Dimensi"]
        judul = f"{kd} · {r['Dimensi']}"
        baris.append(dict(id=f"D:{kd}", parent="", label=f"<b>{kd}</b><br>{_bungkus(r['Dimensi'], 18)}",
                          value=int(n_dim.get(kd, 0)), warna=r["_skor"], judul=judul,
                          hover=_hover(judul, r["_skor"], target)))
    for _, r in df_sub.iterrows():
        ks, kd = r["Kode Subdimensi"], r["Kode Dimensi"]
        judul = f"{ks} · {r['Subdimensi']}"
        baris.append(dict(id=f"S:{ks}", parent=f"D:{kd}", label=f"{ks}<br>{_bungkus(r['Subdimensi'], 18)}",
                          value=int(n_sub.get(ks, 0)), warna=r["_skor"], judul=judul,
                          hover=_hover(judul, r["_skor"], target, r.get("Deskripsi Pertanyaan"))))
    for _, r in df_butir.iterrows():
        q, ks = r["Q"], r["Kode Subdimensi"]
        baris.append(dict(id=f"Q:{ks}:{q}", parent=f"S:{ks}", label=q, value=1, warna=r["_skor"],
                          judul=q, hover=_hover(q, r["_skor"], target, r["Deskripsi Pertanyaan"])))

    h = pd.DataFrame(baris)
    h = h[h["value"] > 0].reset_index(drop=True)

    yatim = set(h["parent"]) - set(h["id"]) - {""}
    if yatim:
        print("PERINGATAN: kode induk tidak ditemukan di sheet atasnya:", sorted(yatim))
    return h


def _data_tabel(df_sub, df_butir, h, target, cmin, cmax):
    """Baris tabel + indeks baris untuk tiap node sunburst (dipakai oleh JavaScript)."""
    nama_sub = dict(zip(df_sub["Kode Subdimensi"], df_sub["Subdimensi"]))
    rentang = (cmax - cmin) or 1

    rows = []
    for _, r in df_butir.iterrows():
        skor = r["_skor"]
        gap = skor - target
        if pd.isna(skor):
            w_skor, w_gap = BARIS_A, BARIS_A
        else:
            w_skor = sample_colorscale(SKALA, [min(max((skor - cmin) / rentang, 0), 1)])[0]
            w_gap = GAP_PLUS if gap >= 0 else GAP_MINUS
        rows.append(dict(
            id=f"Q:{r['Kode Subdimensi']}:{r['Q']}",
            dim=f"D:{r['Kode Dimensi']}", sub=f"S:{r['Kode Subdimensi']}",
            sel=[r["Q"], f"{r['Kode Subdimensi']} · {nama_sub.get(r['Kode Subdimensi'], '')}",
                 str(r["Deskripsi Pertanyaan"]), _fmt(skor), _fmt(gap, tanda=True)],
            warna={"3": w_skor, "4": w_gap}))

    judul = dict(zip(h["id"], h["judul"]))
    nodes = {"": dict(judul="Semua pertanyaan", idx=list(range(len(rows))))}
    for i, r in enumerate(rows):
        for kunci in (r["dim"], r["sub"]):
            nodes.setdefault(kunci, dict(judul=judul.get(kunci, kunci), idx=[]))["idx"].append(i)
    return rows, nodes


# JavaScript: klik sunburst -> tabel diganti dengan pertanyaan dari bagian yang diklik.
JS_TABEL = """
var gd = document.getElementById('{plot_id}');
var D = __DATA__;
function isiTabel(node, sorot) {
    var n = D.nodes[node] || D.nodes[''];
    var r = n.idx.map(function (i) { return D.rows[i]; });
    var nilai = [], warna = [];
    for (var c = 0; c < D.ncol; c++) {
        nilai.push(r.map(function (x) { return x.sel[c]; }));
        warna.push(r.map(function (x, k) {
            if (x.id === sorot) { return D.sorot; }
            if (x.warna[c]) { return x.warna[c]; }
            return k % 2 ? D.barisB : D.barisA;
        }));
    }
    var dibawah = r.filter(function (x) { return x.sel[4].charAt(0) === '-' && x.sel[4] !== '-'; }).length;
    Plotly.restyle(gd, {'cells.values': [nilai], 'cells.fill.color': [warna]}, [1]);
    Plotly.relayout(gd, {'annotations[1].text': 'Daftar pertanyaan · <b>' + n.judul + '</b> (' +
        r.length + ' butir, ' + dibawah + ' di bawah target)'});
}
gd.on('plotly_sunburstclick', function (e) {
    var pt = e.points[0], lvl = e.nextLevel;
    if (lvl === undefined) {               // klik butir: tampilkan subdimensinya, sorot butir itu
        var row = D.rows.filter(function (x) { return x.id === pt.id; })[0];
        if (row) { isiTabel(row.sub, row.id); }
        return false;
    }
    if (!(lvl in D.nodes)) { lvl = ''; }   // kembali ke tampilan penuh
    Plotly.restyle(gd, {level: [lvl]}, [0]);
    isiTabel(lvl, null);
    return false;
});
isiTabel('', null);
"""


def buat_grafik(df_map_dimensi, df_map_subdimensi, df_map_butir, target=4,
                kolom_skor="Keseluruhan", tampilkan=True, simpan_ke=None, tinggi=800):
    """
    Satu halaman: sunburst (kiri) + tabel daftar pertanyaan dengan Gap (kanan), saling terhubung.

    target     : nilai target (default 4); Gap = Skor - target
    kolom_skor : kolom skor yang dipakai (default "Keseluruhan")
    tampilkan  : True -> langsung buka di browser
    simpan_ke  : opsional, path file .html bila ingin menyimpan (mis. "grafik.html")
    """
    df_dim, df_sub, df_butir = _rapikan(df_map_dimensi, df_map_subdimensi, df_map_butir, kolom_skor)
    h = susun_hierarki(df_dim, df_sub, df_butir, target)

    # skala warna simetris di sekitar target, supaya krem = tepat di target
    jarak = max(abs(h["warna"].max() - target), abs(h["warna"].min() - target)) or 0.5
    cmin, cmax = target - jarak, target + jarak
    rows, nodes = _data_tabel(df_sub, df_butir, h, target, cmin, cmax)

    kolom = ["Q", "Subdimensi", "Pertanyaan", "Skor", f"Gap (vs {target:g})"]

    fig = make_subplots(rows=1, cols=2, column_widths=[0.42, 0.58], horizontal_spacing=0.06,
                        specs=[[{"type": "domain"}, {"type": "table"}]],
                        subplot_titles=("Klik irisan untuk memilih · klik tengah untuk kembali",
                                        "Daftar pertanyaan"))
    fig.add_trace(go.Sunburst(
        ids=h["id"], parents=h["parent"], values=h["value"], labels=h["label"], branchvalues="total",
        hovertext=h["hover"], hoverinfo="text", insidetextorientation="radial",
        marker=dict(colors=h["warna"], coloraxis="coloraxis", line=dict(color=GARIS, width=1.5)),
        textfont=dict(color=TEKS, family=FONT)), 1, 1)
    fig.add_trace(go.Table(
        columnwidth=[0.55, 1.6, 4.4, 0.75, 0.95],
        header=dict(values=[f"<b>{k}</b>" for k in kolom], fill_color=KEPALA_TABEL,
                    font=dict(color=TEKS, size=13, family=FONT), align="left", height=32,
                    line_color=GARIS),
        cells=dict(values=[[] for _ in kolom], fill_color=BARIS_A, line_color=GARIS,
                   font=dict(color=TEKS, size=13, family=FONT), align="left", height=30)), 1, 2)

    fig.update_layout(
        title=dict(text=f"<b>Skor Hasil Survei</b> · skor {kolom_skor.lower()} · target {target:g}",
                   x=0.01, font=dict(size=20, color=TEKS, family=FONT)),
        coloraxis=dict(colorscale=SKALA, cmin=cmin, cmax=cmax,
                       colorbar=dict(title=dict(text=f"Skor (krem = target {target:g})", font=dict(color=TEKS),
                                                side="top"),
                                     orientation="h", x=0.21, xanchor="center", y=-0.02, yanchor="top",
                                     thickness=10, len=0.3, outlinewidth=0, tickfont=dict(color=TEKS))),
        paper_bgcolor=LATAR, plot_bgcolor=LATAR,
        font=dict(family=FONT, color=TEKS),
        hoverlabel=dict(bgcolor="white", bordercolor="#d8d4cc", font=dict(color=TEKS, family=FONT)),
        margin=dict(t=90, l=20, r=20, b=70), height=tinggi,
    )
    for judul in fig.layout.annotations:
        judul.font = dict(size=13, color=TEKS_PUDAR, family=FONT)

    data_js = dict(rows=rows, nodes=nodes, ncol=len(kolom),
                   barisA=BARIS_A, barisB=BARIS_B, sorot=BARIS_SOROT)
    js = JS_TABEL.replace("__DATA__", json.dumps(data_js, ensure_ascii=False))

    if tampilkan:
        fig.show(renderer="browser", post_script=js, config={"displaylogo": False})
    if simpan_ke is not None:
        fig.write_html(simpan_ke, post_script=js, config={"displaylogo": False})
        print("Tersimpan:", simpan_ke)
    return fig
