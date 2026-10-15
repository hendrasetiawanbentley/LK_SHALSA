"""Integrasi Claude (Anthropic API) di setiap tahap pipeline.

Tahap yang memakai AI (masing-masing bisa dimatikan di config `ai`):
1. ekstraksi_pdf    : Claude membaca PDF langsung (termasuk PDF hasil scan),
                      menentukan halaman tiap seksi + satuan, dan mengambil
                      angka akun sesuai rules_akun.
2. pemetaan_excel   : label Excel yang tidak terpetakan oleh rules dipetakan
                      ke kode_akun oleh Claude.
3. catatan_dan_kesimpulan : catatan per baris bukan MATCH, serta kesimpulan dan
                      rekomendasi per entitas.

Angka tetap dikonversi secara deterministik (normalisasi.parse_angka) dan setiap
angka dari AI dicek ulang ke teks halaman PDF (kolom `verifikasi`). Jika API key
tidak ada atau panggilan gagal, pipeline memakai jalur aturan (tanpa AI).
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from .normalisasi import parse_angka
from .rules import Rules, berlaku_untuk

SATUAN = {"rupiah": 1, "ribuan": 1_000, "jutaan": 1_000_000, "miliar": 1_000_000_000}


class ErrorAI(Exception):
    pass


class KlienAI:
    """Pembungkus tipis Anthropic SDK: satu permintaan -> JSON sesuai skema."""

    def __init__(self, cfg_ai: dict, client=None):
        import anthropic

        self.cfg = cfg_ai
        self.model = cfg_ai.get("model", "claude-opus-5-5")
        self.client = client or anthropic.Anthropic()

    def minta_json(self, system: str, konten: list[dict], skema: dict, kunci: dict | None = None) -> dict:
        # `kunci` hanya dipakai KlienRekaman (identitas permintaan); API tidak membutuhkannya.
        kwargs = dict(
            model=self.model,
            max_tokens=int(self.cfg.get("maks_token_output", 64000)),
            system=system,
            messages=[{"role": "user", "content": konten}],
            output_config={
                "effort": self.cfg.get("effort", "medium"),
                "format": {"type": "json_schema", "schema": skema},
            },
        )
        # Streaming: input PDF besar dan output panjang tidak terkena timeout HTTP.
        if self.cfg.get("fallback_server", True):
            stream = self.client.beta.messages.stream(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        else:
            stream = self.client.messages.stream(**kwargs)
        with stream as s:
            pesan = s.get_final_message()

        if pesan.stop_reason == "refusal":
            raise ErrorAI("permintaan ditolak model (refusal)")
        if pesan.stop_reason == "max_tokens":
            raise ErrorAI("output AI terpotong (max_tokens)")
        teks = next((b.text for b in pesan.content if b.type == "text"), None)
        if not teks:
            raise ErrorAI("respons AI tanpa teks")
        return json.loads(teks)


class KlienRekaman:
    """Memutar ulang jawaban AI yang sudah direkam sebagai file JSON (tanpa memanggil API).

    Dipakai bila ekstraksi/pemetaan/analisis sudah dikerjakan model di luar pipeline
    (mis. di sesi Claude Code) dan hasilnya disimpan di folder `folder`:
      pdf/<nama file PDF tanpa ekstensi>.json   format sama dengan keluaran SYSTEM_PDF
      pemetaan_excel_<doc_type>.json           {"label": {"label Excel": "kode_akun"},
                                                "turunan": [{"kode_akun": "...", "label": ["...",
                                                             {"label": "...", "seksi": "..."}]}]}
      ocr/<nama file PDF>.json                 {"halaman": {"12": "teks halaman 12", ...}}
      analisis/<entity_key>.json               {"catatan": {"kode_akun/periode": "..."},
                                                "kesimpulan": "...", "rekomendasi": ["..."]}
    Permintaan tanpa rekaman menimbulkan ErrorAI (sama seperti panggilan API yang gagal).
    """

    def __init__(self, folder, model: str = "rekaman"):
        self.folder = Path(folder)
        self.model = model

    def _baca(self, relatif: str) -> dict:
        path = self.folder / relatif
        if not path.exists():
            raise ErrorAI(f"rekaman AI tidak ada: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def minta_json(self, system: str, konten: list[dict], skema: dict, kunci: dict | None = None) -> dict:
        tahap = (kunci or {}).get("tahap")
        if tahap == "pdf":
            return self._baca(f"pdf/{kunci['nama_file']}.json")
        if tahap == "excel":
            rekaman = self._baca(f"pemetaan_excel_{kunci['doc_type']}.json")
            label = [" ".join(x.split()) for x in kunci["label"]]
            peta = {" ".join(k.split()): v for k, v in (rekaman.get("label") or {}).items()}
            seksi = kunci.get("seksi") or [None] * len(label)
            turunan = []
            for t in rekaman.get("turunan") or []:
                # Komponen: "label" atau {"label": ..., "seksi": ...} bila label sama muncul di beberapa seksi.
                cari = [(" ".join(x.split()), None) if isinstance(x, str) else (" ".join(x["label"].split()), x["seksi"])
                        for x in t["label"]]
                no = [i for i, x in enumerate(label) if any(x == c and s in (None, seksi[i]) for c, s in cari)]
                if no:
                    turunan.append({"kode_akun": t["kode_akun"], "no": no})
            return {"pemetaan": [{"no": i, "kode_akun": peta[x]} for i, x in enumerate(label) if peta.get(x)],
                    "turunan": turunan}
        if tahap == "analisis":
            rekaman = self._baca(f"analisis/{kunci['entity_key']}.json")
            catatan = rekaman.get("catatan") or {}
            return {"catatan_baris": [{"no": i, "catatan": catatan[k]}
                                      for i, k in enumerate(kunci["baris"]) if catatan.get(k)],
                    "kesimpulan": rekaman.get("kesimpulan", ""),
                    "rekomendasi": rekaman.get("rekomendasi", [])}
        if tahap == "ocr":
            rekaman = self._baca(f"ocr/{kunci['nama_file']}.json").get("halaman") or {}
            return {"halaman": [{"halaman": i, "teks": rekaman[str(n)]}
                                for i, n in enumerate(kunci["halaman"], start=1) if rekaman.get(str(n))]}
        raise ErrorAI(f"permintaan tanpa kunci rekaman: {kunci}")


def buat_klien(cfg: dict) -> KlienAI | None:
    """KlienAI bila AI aktif dan ANTHROPIC_API_KEY tersedia; selain itu None."""
    cfg_ai = cfg.get("ai") or {}
    if not cfg_ai.get("aktif", False) or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return KlienAI(cfg_ai)


def _objek(properti: dict) -> dict:
    """Objek JSON schema untuk structured outputs: semua field wajib, tanpa field lain."""
    return {"type": "object", "properties": properti, "required": list(properti),
            "additionalProperties": False}


# ---------------------------------------------------------------- 1. PDF

SYSTEM_PDF = """Anda adalah analis laporan keuangan yang membantu pengawas OJK.
Anda menerima satu laporan keuangan (PDF) dan daftar seksi serta akun yang dicari.

Tugas:
1. Tentukan rentang halaman setiap seksi yang ada di dokumen (nomor halaman PDF, mulai dari 1),
   judul seksi seperti tertulis, dan satuan penyajian angkanya ("rupiah", "ribuan", "jutaan",
   atau "miliar") dari keterangan seperti "(Dinyatakan dalam jutaan Rupiah)".
   Abaikan daftar isi, laporan auditor, dan surat pernyataan direksi.
2. Untuk setiap akun di daftar, cari barisnya di seksi yang sesuai dan salin angka periode
   berjalan (kolom tahun terbaru) dan periode pembanding PERSIS seperti tertulis, termasuk tanda
   kurung dan pemisah ribuan, misalnya "(1.234.567)". Jangan membulatkan atau mengubah satuan.
   Tulis "" bila angka tidak ada. Hitung (menjumlahkan/mengurangkan) hanya bila uraian akun
   memintanya (mis. "jumlahkan seluruh sub baris", "NAB akhir dikurangi NAB awal"); sebutkan
   komponennya di `label_di_dokumen`.
3. Hanya laporkan akun yang benar-benar ditemukan. Jangan menebak; akun yang tidak ada
   cukup tidak dicantumkan. Gunakan kode_akun persis dari daftar.
4. `halaman` adalah nomor halaman PDF tempat angka akun itu ditemukan.
5. `satuan_akun`: isi bila satuan angka akun itu berbeda dari satuan seksinya (mis. laba per
   saham "dalam jumlah penuh" di laporan yang disajikan dalam miliaran); selain itu ""."""


def _skema_pdf(kode_seksi: list[str], kode_akun: list[str]) -> dict:
    return _objek({
        "seksi": {"type": "array", "items": _objek({
            "kode": {"type": "string", "enum": kode_seksi},
            "judul": {"type": "string"},
            "halaman_mulai": {"type": "integer"},
            "halaman_akhir": {"type": "integer"},
            "satuan": {"type": "string", "enum": list(SATUAN)},
        })},
        "akun": {"type": "array", "items": _objek({
            "kode_akun": {"type": "string", "enum": kode_akun},
            "label_di_dokumen": {"type": "string"},
            "nilai_berjalan": {"type": "string"},
            "nilai_lalu": {"type": "string"},
            "halaman": {"type": "integer"},
            "satuan_akun": {"type": "string", "enum": list(SATUAN) + [""]},
        })},
        "catatan": {"type": "string"},
    })


def _daftar_seksi(rules: Rules, doc_type: str | None) -> list[tuple[str, str]]:
    hasil: dict[str, str] = {}
    for m in rules.mapping_seksi:
        if berlaku_untuk(m.get("entitas"), doc_type):
            hasil.setdefault(m["kode"], m.get("seksi") or m["kode"])
    return list(hasil.items())


def _cek_di_halaman(nilai_asli: str, teks_halaman: str | None) -> str:
    """Pastikan angka dari AI memang tertulis di halaman yang dirujuk."""
    if teks_halaman is None:
        return "halaman_tidak_ada"
    if not teks_halaman.strip():
        return "tanpa_teks"  # PDF scan: tidak bisa dicek otomatis
    digit = re.sub(r"\D", "", nilai_asli or "")
    if not digit:
        return "cocok"  # "-" (nihil)
    return "cocok" if digit in re.sub(r"[.,\s]", "", teks_halaman) else "tidak_ditemukan_di_halaman"


def ekstraksi_pdf(klien: KlienAI, path: str, info: dict, rules: Rules, cfg: dict,
                  teks_halaman: list[str]) -> tuple[list[dict], list[dict], list[str]]:
    """Kembalikan (lokasi_seksi, angka_pdf, peringatan) untuk satu PDF."""
    cfg_ai = cfg.get("ai") or {}
    ukuran_mb = Path(path).stat().st_size / 1_048_576
    if ukuran_mb > float(cfg_ai.get("maks_mb_pdf", 30)):
        raise ErrorAI(f"PDF {ukuran_mb:.1f} MB melebihi batas maks_mb_pdf")

    doc_type = info["doc_type"]
    dilewati = set((cfg.get("ekstraksi") or {}).get("seksi_dilewati") or [])
    seksi = _daftar_seksi(rules, doc_type)
    akun = [a for a in rules.rules_akun if berlaku_untuk(a["doc_type"], doc_type) and a["seksi"] not in dilewati]
    if not akun:
        return [], [], [f"{info['nama_file']}: tidak ada akun di rules_akun untuk doc_type '{doc_type}'"]

    daftar_seksi = "\n".join(f"- {k}: {n}" for k, n in seksi)
    def uraian(a: dict) -> str:
        # Kolom description di sheet Master sudah berisi alias + instruksi ekstraksi per akun.
        if a.get("deskripsi"):
            return " ".join(a["deskripsi"].split())
        return a["nama_akun"] + (f" | sinonim: {a['sinonim'].replace('|', '; ')}" if a.get("sinonim") else "")

    daftar_akun = "\n".join(f"- {a['kode_akun']} (seksi {a['seksi']}): {uraian(a)}" for a in akun)
    data = base64.standard_b64encode(Path(path).read_bytes()).decode()
    hasil = klien.minta_json(SYSTEM_PDF, [
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
        {"type": "text", "text": f"Jenis entitas: {doc_type}\n\nSeksi:\n{daftar_seksi}\n\nAkun yang dicari:\n{daftar_akun}"},
    ], _skema_pdf([k for k, _ in seksi], [a["kode_akun"] for a in akun]),
        kunci={"tahap": "pdf", "nama_file": Path(path).stem})

    identitas = {"doc_id": path, "nama_file": info["nama_file"], "entity_key": info["entity_key"],
                 "entity_id": info["entity_id"], "doc_type": doc_type}
    lokasi = [{**identitas, "seksi": s["kode"], "halaman_mulai": s["halaman_mulai"],
               "halaman_akhir": s["halaman_akhir"], "judul_cocok": s["judul"], "satuan": s["satuan"]}
              for s in hasil.get("seksi", [])]
    satuan_seksi = {s["kode"]: SATUAN.get(s["satuan"], 1) for s in hasil.get("seksi", [])}
    seksi_akun = {a["kode_akun"]: a["seksi"] for a in akun}

    angka, peringatan, sudah = [], [], set()
    for item in hasil.get("akun", []):
        kode = item["kode_akun"]
        if kode in sudah:
            continue
        sudah.add(kode)
        sek = seksi_akun.get(kode)
        hal = item.get("halaman") or None
        teks = teks_halaman[hal - 1] if hal and 0 < hal <= len(teks_halaman) else None
        for periode, kunci in (("berjalan", "nilai_berjalan"), ("lalu", "nilai_lalu")):
            mentah = (item.get(kunci) or "").strip()
            nilai = parse_angka(mentah)
            if nilai is None:
                if mentah:
                    peringatan.append(f"{info['nama_file']}: {kode}/{periode} angka tidak terbaca '{mentah}'")
                continue
            angka.append({
                "doc_id": path, "sumber_file": info["nama_file"], "entity_key": info["entity_key"],
                "entity_id": info["entity_id"], "doc_type": doc_type, "tahun": info.get("tahun"),
                "seksi": sek, "kode_akun": kode, "label_di_dokumen": item.get("label_di_dokumen"),
                "periode": periode, "nilai": nilai, "nilai_asli": mentah,
                "skala": float(SATUAN.get(item.get("satuan_akun") or "", satuan_seksi.get(sek, 1))),
                "halaman": hal,
                "sumber_ekstraksi": "ai", "verifikasi": _cek_di_halaman(mentah, teks),
            })
    tidak_ada = [a["kode_akun"] for a in akun if a["kode_akun"] not in sudah]
    if tidak_ada:
        peringatan.append(f"{info['nama_file']}: akun tidak ditemukan oleh AI: {', '.join(tidak_ada)}")
    belum_cek = [b for b in angka if b["verifikasi"] == "tidak_ditemukan_di_halaman"]
    if belum_cek:
        peringatan.append(f"{info['nama_file']}: {len(belum_cek)} angka AI tidak ditemukan di halaman rujukan; "
                          "periksa kolom verifikasi")
    if hasil.get("catatan"):
        peringatan.append(f"{info['nama_file']} (catatan AI): {hasil['catatan']}")
    return lokasi, angka, peringatan


# ---------------------------------------------------------------- 2. Excel

SYSTEM_EXCEL = """Anda memetakan label baris laporan keuangan di file Excel ke kode akun standar.
Untuk setiap label, pilih kode_akun yang maknanya sama persis dengan label tersebut
(perhatikan seksi dan sheet). Jika tidak ada yang sama persis (misalnya label adalah subtotal,
rincian, atau akun lain), isi kode_akun dengan "". Jangan memaksakan kecocokan.
Bila suatu akun tidak punya satu baris total di Excel tetapi nilainya adalah jumlah beberapa
baris (mis. portofolio efek = efek ekuitas + efek utang + instrumen pasar uang), isi `turunan`
dengan kode_akun dan daftar `no` baris yang dijumlahkan."""


def pemetaan_excel(klien: KlienAI, baris_excel: list[dict], rules: Rules, doc_type: str | None) -> int:
    """Isi kode_akun baris Excel yang belum terpetakan. Mengembalikan jumlah label yang dipetakan.

    Selain pemetaan satu label -> satu akun, AI boleh mengusulkan `turunan`: akun yang di Excel
    tidak punya satu baris total sehingga nilainya = jumlah beberapa baris (mis. portofolio efek =
    efek ekuitas + efek utang + pasar uang). Baris turunan ditambahkan dengan cara_pemetaan
    `ai_turunan`; baris yang dipetakan langsung tetap diutamakan saat komparasi.
    """
    # Baris bernilai 0 ikut dikirim: akun nihil (mis. penghasilan komprehensif lain "-") tetap
    # perlu dipasangkan dengan PDF. Komparasi mengutamakan baris bernilai bukan nol.
    belum = sorted({(b["label_asli"], b["sheet"], b["seksi"]) for b in baris_excel if not b.get("kode_akun")})
    akun = [a for a in rules.rules_akun if berlaku_untuk(a["doc_type"], doc_type)]
    if not belum or not akun:
        return 0
    enum_akun = [a["kode_akun"] for a in akun]
    skema = _objek({
        "pemetaan": {"type": "array", "items": _objek({
            "no": {"type": "integer"},
            "kode_akun": {"type": "string", "enum": enum_akun + [""]},
        })},
        "turunan": {"type": "array", "items": _objek({
            "kode_akun": {"type": "string", "enum": enum_akun},
            "no": {"type": "array", "items": {"type": "integer"}},
        })},
    })
    daftar_akun = "\n".join(f"- {a['kode_akun']} (seksi {a['seksi']}): {a['nama_akun']}" for a in akun)
    daftar_label = "\n".join(f"{i}. [{sheet} / {seksi}] {' '.join(label.split())}"
                             for i, (label, sheet, seksi) in enumerate(belum))
    hasil = klien.minta_json(SYSTEM_EXCEL, [{"type": "text", "text":
        f"Kode akun:\n{daftar_akun}\n\nLabel Excel yang perlu dipetakan:\n{daftar_label}"}], skema,
        kunci={"tahap": "excel", "doc_type": doc_type, "label": [label for label, _, _ in belum],
               "seksi": [seksi for _, _, seksi in belum]})

    peta = {}
    for p in hasil.get("pemetaan", []):
        if p.get("kode_akun") and 0 <= p.get("no", -1) < len(belum):
            peta[belum[p["no"]]] = p["kode_akun"]
    for b in baris_excel:
        kode = peta.get((b["label_asli"], b["sheet"], b["seksi"]))
        if not b.get("kode_akun") and kode:
            b["kode_akun"], b["cara_pemetaan"] = kode, "ai"

    tambahan = []
    for t in hasil.get("turunan", []):
        bagian = {belum[n] for n in t.get("no", []) if 0 <= n < len(belum)}
        if not t.get("kode_akun") or not bagian:
            continue
        per_periode: dict[str, list[dict]] = {}
        for b in baris_excel:
            if (b["label_asli"], b["sheet"], b["seksi"]) in bagian and b.get("nilai") is not None:
                per_periode.setdefault(b["periode"], []).append(b)
        for periode, isi in per_periode.items():
            acuan = isi[0]
            tambahan.append({**acuan, "kode_akun": t["kode_akun"], "cara_pemetaan": "ai_turunan",
                             "label_asli": " + ".join(" ".join(b["label_asli"].split()) for b in isi),
                             "nilai": sum(b["nilai"] for b in isi), "nilai_asli": None,
                             "baris": ",".join(str(b["baris"]) for b in isi)})
    baris_excel.extend(tambahan)
    return len(peta) + len(hasil.get("turunan", []))


# ---------------------------------------------------------------- 3. Catatan + kesimpulan

SYSTEM_ANALISIS = """Anda membantu pengawas OJK menelaah hasil komparasi angka laporan keuangan
PDF (laporan yang diaudit) dengan data Excel yang disampaikan entitas. Nilai sudah dalam satuan
PDF. Tulis dalam Bahasa Indonesia yang ringkas dan faktual; jangan mengarang angka yang tidak
diberikan.

1. `catatan_baris`: untuk setiap baris, satu sampai dua kalimat tentang kemungkinan penyebab
   perbedaan dan hal yang perlu dikonfirmasi ke entitas. Gunakan `no` dari input.
2. `kesimpulan`: satu paragraf tentang konsistensi PDF dan Excel entitas ini secara keseluruhan.
3. `rekomendasi`: daftar tindak lanjut yang konkret untuk pengawas (boleh kosong bila semua sesuai)."""


def analisis_entitas(klien: KlienAI, entity_key: str, baris: list[dict]) -> dict:
    """Catatan untuk baris bukan MATCH + kesimpulan/rekomendasi satu entitas."""
    perlu = [b for b in baris if b["status"] != "MATCH"]
    skema = _objek({
        "catatan_baris": {"type": "array", "items": _objek({"no": {"type": "integer"}, "catatan": {"type": "string"}})},
        "kesimpulan": {"type": "string"},
        "rekomendasi": {"type": "array", "items": {"type": "string"}},
    })
    ringkas = {s: sum(1 for b in baris if b["status"] == s) for s in ("MATCH", "DIFFERENT", "PDF_ONLY", "EXCEL_ONLY")}
    data = [{"no": i, "akun": f"{b['kode_akun']} - {b.get('nama_akun') or b.get('label_pdf') or b.get('label_excel')}",
             "seksi": b.get("seksi"), "periode": b["periode"], "satuan": b.get("satuan_pdf"),
             "nilai_pdf": b.get("nilai_pdf"), "nilai_excel": b.get("nilai_excel"), "selisih": b.get("selisih"),
             "status": b["status"], "indikasi": b.get("indikasi"), "halaman_pdf": b.get("halaman_pdf")}
            for i, b in enumerate(perlu)]
    hasil = klien.minta_json(SYSTEM_ANALISIS, [{"type": "text", "text":
        f"Entitas: {entity_key}\nJumlah per status: {json.dumps(ringkas)}\n\n"
        f"Baris yang perlu ditinjau:\n{json.dumps(data, ensure_ascii=False)}"}], skema,
        kunci={"tahap": "analisis", "entity_key": entity_key,
               "baris": [f"{b['kode_akun']}/{b['periode']}" for b in perlu]})

    for c in hasil.get("catatan_baris", []):
        if 0 <= c.get("no", -1) < len(perlu) and c.get("catatan"):
            perlu[c["no"]]["catatan"] = c["catatan"]
            perlu[c["no"]]["sumber_catatan"] = "ai"
    return {"entity_key": entity_key, "kesimpulan": hasil.get("kesimpulan", ""),
            "rekomendasi": "\n".join(f"- {r}" for r in hasil.get("rekomendasi", []))}
