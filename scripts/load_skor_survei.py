# -*- coding: utf-8 -*-
"""
Load file Excel "Skor Hasil Survei" (4 sheet) ke DataFrame pandas.

Sheet yang dibaca:
    - Score
    - Map_Dimensi
    - Map_Subdimensi
    - Map_Butir

Cara pakai di Spyder:
    1. Ubah PATH_EXCEL di bawah ke lokasi file Excel Anda.
    2. Tekan F5 (Run file).
    3. Buka "Variable Explorer": akan muncul df_score, df_map_dimensi,
       df_map_subdimensi, df_map_butir, dan dict `dfs` berisi semuanya.
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Lokasi file Excel  ->  GANTI sesuai lokasi file Anda
# ---------------------------------------------------------------------------
PATH_EXCEL = Path(r"C:\Users\NamaAnda\Documents\Skor Hasil Survei.xlsx")

SHEETS = ["Score", "Map_Dimensi", "Map_Subdimensi", "Map_Butir"]

# Tampilkan semua kolom/baris lebar di console (tidak terpotong "...")
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)


def load_survei(path, sheets=SHEETS):
    """Baca semua sheet yang diminta; kembalikan dict {nama_sheet: DataFrame}."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    tersedia = pd.ExcelFile(path).sheet_names
    hilang = [s for s in sheets if s not in tersedia]
    if hilang:
        raise ValueError(f"Sheet tidak ada: {hilang}. Sheet di file: {tersedia}")

    dfs = pd.read_excel(path, sheet_name=sheets)  # dict {sheet: DataFrame}
    for nama, df in dfs.items():
        # rapikan nama kolom (hapus spasi di awal/akhir) & buang baris/kolom kosong
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how="all").dropna(axis=1, how="all")
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
        dfs[nama] = df.reset_index(drop=True)
    return dfs


def tampilkan_kolom(dfs):
    """Cetak semua kolom tiap sheet beserta tipe data & jumlah nilai terisi."""
    for nama, df in dfs.items():
        print("=" * 70)
        print(f"Sheet: {nama}   |   {df.shape[0]} baris x {df.shape[1]} kolom")
        print("-" * 70)
        info = pd.DataFrame({
            "kolom": df.columns,
            "tipe": df.dtypes.astype(str).values,
            "terisi": df.notna().sum().values,
            "kosong": df.isna().sum().values,
        })
        print(info.to_string(index=False))
        print("\n5 baris pertama:")
        print(df.head().to_string())
        print()


if __name__ == "__main__":
    dfs = load_survei(PATH_EXCEL)

    # DataFrame per sheet (muncul di Variable Explorer Spyder)
    df_score = dfs["Score"]
    df_map_dimensi = dfs["Map_Dimensi"]
    df_map_subdimensi = dfs["Map_Subdimensi"]
    df_map_butir = dfs["Map_Butir"]

    tampilkan_kolom(dfs)

    # Daftar semua kolom per sheet dalam bentuk list
    semua_kolom = {nama: list(df.columns) for nama, df in dfs.items()}
    for nama, kolom in semua_kolom.items():
        print(f"{nama}: {kolom}")
