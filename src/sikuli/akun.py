"""Pemetaan label akun (Excel) ke kode_akun berdasarkan skema akun di rules."""

from __future__ import annotations

from .normalisasi import normalisasi_teks
from .rules import Rules, berlaku_untuk


def _sinonim(akun: dict) -> list[str]:
    nilai = [akun["nama_akun"]] + (akun.get("sinonim") or "").split("|")
    return [s for s in (normalisasi_teks(x) for x in nilai) if s]


class PemetaAkun:
    """Urutan pencarian label:
    1. mapping_akun_excel.csv (doc_type + sheet bila diisi + label persis),
    2. nama_akun / sinonim di rules_akun pada seksi yang sama,
    3. nama_akun / sinonim di rules_akun pada seksi lain doc_type yang sama,
       hanya bila hasilnya tunggal (tidak ambigu).
    Label dibandingkan setelah dinormalisasi (huruf kecil, tanpa tanda baca).
    """

    def __init__(self, rules: Rules):
        self.rules = rules

    def petakan(self, label: str, doc_type: str | None, seksi: str | None,
                sheet: str | None = None) -> tuple[str | None, str]:
        """Kembalikan (kode_akun, cara_pemetaan). kode_akun None = tidak terpetakan."""
        kunci = normalisasi_teks(label)
        if not kunci:
            return None, "label_kosong"

        for m in self.rules.mapping_akun_excel:
            if not berlaku_untuk(m.get("doc_type"), doc_type):
                continue
            if m.get("sheet") and sheet and m["sheet"].strip().lower() != sheet.strip().lower():
                continue
            if normalisasi_teks(m["label_excel"]) == kunci:
                return m["kode_akun"], "mapping_akun_excel"

        kandidat_seksi, kandidat_lain = [], []
        for a in self.rules.rules_akun:
            if not berlaku_untuk(a["doc_type"], doc_type) or kunci not in _sinonim(a):
                continue
            (kandidat_seksi if a["seksi"] == seksi else kandidat_lain).append(a["kode_akun"])

        if kandidat_seksi:
            return kandidat_seksi[0], "rules_akun"
        if len(set(kandidat_lain)) == 1:
            return kandidat_lain[0], "rules_akun_seksi_lain"
        if kandidat_lain:
            return None, "ambigu"
        return None, "tidak_terpetakan"
