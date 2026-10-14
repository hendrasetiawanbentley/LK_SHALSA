import base64
import importlib
import io
import sys
from pathlib import Path

import pytest
from test_excel_akun import buat_excel
from test_lokal import buat_pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def klien(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "rahasia")
    import webapp.app as modul
    modul = importlib.reload(modul)
    return modul.app.test_client()


def auth(pw="rahasia"):
    return {"Authorization": "Basic " + base64.b64encode(f"x:{pw}".encode()).decode()}


def test_password_wajib(klien):
    assert klien.get("/").status_code == 401
    assert klien.get("/", headers=auth("salah")).status_code == 401
    assert klien.get("/sehat").status_code == 200
    assert klien.get("/", headers=auth()).status_code == 200
    assert klien.get("/rules", headers=auth()).status_code == 200
    assert klien.get("/rules/rules_akun.csv", headers=auth()).status_code == 200
    assert klien.get("/rules/../config.csv", headers=auth()).status_code == 404


def test_upload_dan_unduh(klien, tmp_path):
    buat_pdf(tmp_path / "AAAA_LK_2024.pdf")
    buat_excel(tmp_path / "AAAA_2024.xlsx")
    data = {
        "pdf": [(io.BytesIO((tmp_path / "AAAA_LK_2024.pdf").read_bytes()), "AAAA_LK_2024.pdf")],
        "excel": [(io.BytesIO((tmp_path / "AAAA_2024.xlsx").read_bytes()), "AAAA_2024.xlsx")],
    }
    r = klien.post("/analisis", data=data, headers=auth(), content_type="multipart/form-data")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "AAAA|EPP|2024" in html and "DIFFERENT" in html
    id_hasil = html.split("/unduh/")[1].split('"')[0]
    unduh = klien.get(f"/unduh/{id_hasil}", headers=auth())
    assert unduh.status_code == 200 and unduh.data[:2] == b"PK"


def test_tanpa_file(klien):
    r = klien.post("/analisis", data={}, headers=auth(), content_type="multipart/form-data")
    assert r.status_code == 400
