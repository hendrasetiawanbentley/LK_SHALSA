"""Web app SIKULI: upload LK PDF + Excel, lihat dan unduh hasil komparasi.

Jalankan lokal:   flask --app webapp.app run
Di Render:        gunicorn webapp.app:app (lihat render.yaml)

File yang diunggah hanya disimpan sementara selama analisis lalu dihapus.
Isi APP_PASSWORD (environment variable) supaya halaman tidak bisa dibuka publik.
"""

from __future__ import annotations

import hmac
import io
import os
import shutil
import sys
import tempfile
import uuid
from collections import OrderedDict
from pathlib import Path

from flask import Flask, Response, abort, render_template, request, send_file
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sikuli.config import muat_config  # noqa: E402
from sikuli.lokal import jalankan, tulis_excel  # noqa: E402
from sikuli.rules import KOLOM_WAJIB, baca_csv, muat_rules, validasi_rules  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAKS_UPLOAD_MB", "200")) * 1024 * 1024
PASSWORD = os.environ.get("APP_PASSWORD", "")
CONFIG = ROOT / "config" / "pipeline.yaml"
RULES = ROOT / "rules"
MAKS_HASIL = 20
HASIL: OrderedDict[str, dict] = OrderedDict()  # id -> {"xlsx": bytes, "nama": str}


@app.before_request
def cek_password():
    if not PASSWORD or request.path == "/sehat":
        return None
    auth = request.authorization
    if auth and hmac.compare_digest(auth.password or "", PASSWORD):
        return None
    return Response("Perlu login", 401, {"WWW-Authenticate": 'Basic realm="SIKULI"'})


@app.get("/sehat")
def sehat():
    return {"status": "ok"}


@app.get("/")
def index():
    rules = muat_rules(RULES)
    return render_template("index.html", rules=rules, masalah=validasi_rules(rules),
                           maks_mb=app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024))


def _simpan(files, folder: Path, akhiran: tuple[str, ...]) -> list[str]:
    paths = []
    for f in files:
        nama = secure_filename(f.filename or "")
        if nama and nama.lower().endswith(akhiran):
            path = folder / nama
            f.save(path)
            paths.append(str(path))
    return paths


@app.post("/analisis")
def analisis():
    kerja = Path(tempfile.mkdtemp(prefix="sikuli_"))
    try:
        (kerja / "pdf").mkdir()
        (kerja / "excel").mkdir()
        rules_dir = kerja / "rules"
        shutil.copytree(RULES, rules_dir)
        # CSV rules yang diunggah menimpa rules bawaan dengan nama file yang sama.
        rules_upload = [f for f in request.files.getlist("rules")
                        if secure_filename(f.filename or "").removesuffix(".csv") in KOLOM_WAJIB]
        _simpan(rules_upload, rules_dir, (".csv",))

        pdf = _simpan(request.files.getlist("pdf"), kerja / "pdf", (".pdf",))
        excel = _simpan(request.files.getlist("excel"), kerja / "excel", (".xlsx", ".xlsm"))
        if not pdf and not excel:
            return render_template("pesan.html", judul="Tidak ada file",
                                   pesan="Unggah minimal satu file PDF atau Excel."), 400

        rules = muat_rules(rules_dir)
        masalah = validasi_rules(rules)
        if masalah:
            return render_template("pesan.html", judul="Rules tidak valid", daftar=masalah), 400

        hasil = jalankan(pdf, excel, muat_config(CONFIG), rules)
        buffer = io.BytesIO()
        tulis_excel(hasil, buffer)
    finally:
        shutil.rmtree(kerja, ignore_errors=True)

    id_hasil = uuid.uuid4().hex
    HASIL[id_hasil] = {"xlsx": buffer.getvalue(), "nama": "hasil_komparasi.xlsx"}
    while len(HASIL) > MAKS_HASIL:
        HASIL.popitem(last=False)
    return render_template("hasil.html", hasil=hasil, id_hasil=id_hasil,
                           jumlah_pdf=len(pdf), jumlah_excel=len(excel))


@app.get("/unduh/<id_hasil>")
def unduh(id_hasil: str):
    data = HASIL.get(id_hasil)
    if not data:
        abort(404)
    return send_file(io.BytesIO(data["xlsx"]), as_attachment=True, download_name=data["nama"],
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/rules/<nama>.csv")
def unduh_rules(nama: str):
    if nama not in KOLOM_WAJIB or not (RULES / f"{nama}.csv").exists():
        abort(404)
    return send_file(RULES / f"{nama}.csv", as_attachment=True, download_name=f"{nama}.csv")


@app.get("/rules")
def lihat_rules():
    isi = {n: baca_csv(RULES / f"{n}.csv") for n in KOLOM_WAJIB if (RULES / f"{n}.csv").exists()}
    return render_template("rules.html", isi=isi)


@app.errorhandler(413)
def terlalu_besar(_):
    return render_template("pesan.html", judul="File terlalu besar",
                           pesan=f"Total upload melebihi {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB."), 413
