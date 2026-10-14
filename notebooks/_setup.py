# Databricks notebook source
# MAGIC %md
# MAGIC # _setup
# MAGIC Dipanggil oleh notebook lain lewat `%run ./_setup`. Menambahkan `src/` ke `sys.path`,
# MAGIC memuat `config/pipeline.yaml` dan file rules.

# COMMAND ----------

import os
import sys

ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

import importlib

import sikuli
from sikuli import (akun, config, ekstraksi, entitas, excel, komparasi, normalisasi,
                    parse_pdf, pipeline, rules as rules_mod, seksi, tabel)

# Muat ulang modul supaya perubahan kode di repo langsung terpakai tanpa restart.
for _m in (normalisasi, config, rules_mod, entitas, parse_pdf, seksi, akun, excel,
           ekstraksi, komparasi, tabel, pipeline):
    importlib.reload(_m)

cfg = config.muat_config(os.path.join(ROOT, "config", "pipeline.yaml"))
PATH_RULES = cfg["path_rules"] if os.path.isabs(cfg["path_rules"]) else os.path.join(ROOT, cfg["path_rules"])
rules = rules_mod.muat_rules(PATH_RULES)


def T(nama: str) -> str:
    """Nama tabel lengkap catalog.schema.nama."""
    return config.nama_tabel(cfg, nama)


print(f"SIKULI {sikuli.__version__} | schema {cfg['catalog']}.{cfg['schema']} | rules {PATH_RULES}")
