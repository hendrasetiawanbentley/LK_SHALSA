# SIKULI: komparasi laporan keuangan PDF vs Excel

Implementasi alur di deck *SIKULI: alur analisis laporan keuangan*, mulai dari **parse PDF** sampai
**B · Analisis_Komparasi**, ditambah kesimpulan dan rekomendasi. Analisis dijalankan oleh **GitHub Actions**,
tanpa aplikasi front end, dengan **Claude (Anthropic API)** di hampir setiap tahap.

```
input/pdf/*.pdf   ─► parse (pdfplumber) ─► deteksi entitas + seksi ─► ekstraksi akun per seksi ─► angka PDF ──┐
input/excel/*.xlsx ─► baca sheet (sheet_config) ─► mapping label → kode_akun ──────────────────► angka Excel ─┴─► komparasi ─► hasil/
rules/Extraction_Rules.xlsx (sheet Master) dipakai di setiap langkah
```

## Penggunaan AI (Claude)

| Tahap | Dengan AI (`ANTHROPIC_API_KEY` tersedia) | Cadangan tanpa AI |
|-------|------------------------------------------|-------------------|
| Parsing PDF, seksi, satuan, angka akun | Claude membaca PDF langsung (termasuk PDF hasil scan), menentukan halaman tiap seksi dan satuannya, lalu menyalin angka akun sesuai sheet Master | pdfplumber + pola `mapping_seksi` + pencocokan label |
| Verifikasi angka PDF | Setiap angka dari AI dicek ulang ke teks halaman rujukan (kolom `verifikasi`) | - |
| Pemetaan label Excel | Label yang tidak dikenali rules dipetakan Claude (`cara_pemetaan = ai`) | Label dibiarkan belum terpetakan |
| Komparasi dan status | Deterministik (kode), tidak memakai AI | sama |
| Catatan per baris | Claude menulis catatan analis untuk baris bukan MATCH (`sumber_catatan = ai`) | Catatan template |
| Kesimpulan dan rekomendasi | Claude, per entitas (sheet **Kesimpulan**) | Tidak dibuat |

**Mengaktifkan:**
1. Buat API key di [console.anthropic.com](https://console.anthropic.com) (menu API Keys).
2. Di GitHub: **Settings → Secrets and variables → Actions → New repository secret**, nama
   `ANTHROPIC_API_KEY`, isi dengan key tersebut.
3. Atur model dan tahap mana yang memakai AI di bagian `ai:` pada `config/pipeline.yaml`
   (bawaan: `claude-opus-5-5`, effort `medium`, semua tahap aktif).

Dengan `ai.wajib: true` (bawaan di `config/pipeline.yaml`), workflow **gagal dengan pesan jelas** bila secret
belum diisi, dan dokumen yang gagal diproses AI dicatat GAGAL di Peringatan (tidak dialihkan ke mode aturan).
Set `ai.wajib: false` bila ingin mode aturan sebagai cadangan.

> Dengan AI aktif, isi PDF dan label Excel dikirim ke Anthropic API. Pastikan ini sesuai kebijakan data
> instansi Anda sebelum mengunggah LK asli.

## Cara menjalankan di GitHub

1. **Isi rules** di `rules/Extraction_Rules.xlsx` sheet Master (lihat tabel di bawah), lalu upload ke GitHub.
2. **Upload file LK** ke repo:
   - PDF ke `input/pdf/`, misalnya `MI_CC002_LK_Tahunan_Audited_2025.pdf`
   - Excel ke `input/excel/` dengan **nama file yang sama**, misalnya `MI_CC002_LK_Tahunan_Audited_2025.xlsx`

   Lewat web GitHub: buka folder → **Add file → Upload files** → **Commit changes**. PDF dan Excel dipasangkan
   dari nama file yang sama persis (selain ekstensi). Format nama: `JENIS_KODE_keterangan`, dengan JENIS =
   `EPP` / `MI` / `RD` dan KODE = kode perusahaan/manajer investasi.
3. **Workflow `analisis` jalan otomatis** setiap ada perubahan di `input/`, `rules/`, atau `config/`.
   Untuk menjalankan ulang manual: tab **Actions → analisis → Run workflow**.
4. **Lihat hasil:** tab **Actions** → klik run teratas.
   - Halaman run menampilkan ringkasan per entitas, daftar akun yang perlu ditinjau, dan peringatan.
   - Bagian **Artifacts** di bawah halaman run berisi `hasil-komparasi` (zip): `hasil_komparasi.xlsx` + CSV.
     Artifact disimpan 30 hari.

Menjalankan di komputer sendiri (opsional):
```bash
pip install -r requirements.txt
PYTHONPATH=src python -m sikuli.lokal          # baca input/pdf dan input/excel, tulis ke hasil/
```

> **Repo ini publik.** File di `input/` dan artifact hasil bisa dilihat orang lain. Ubah repo menjadi
> private (Settings → General → Danger Zone → Change visibility) sebelum mengunggah LK asli.

## Rules: satu file `rules/Extraction_Rules.xlsx` (sheet Master)

Semua rules akun ada di **satu file Excel**, sheet **Master**. Satu baris = satu akun yang diekstrak dan
dibandingkan. Sheet lain (rasio, Ref) belum dipakai. Jika rules tidak valid, workflow gagal dan menyebut baris
yang salah.

| Kolom | Wajib | Isi | Dipakai untuk |
|-------|:-----:|-----|---------------|
| `no` | | nomor urut | rujukan |
| `entitas` | ya | `EPP`, `MI`, `RD` (atau `DES`) | memilih akun sesuai jenis entitas dari nama file |
| `bagian` | ya | nama laporan, mis. `Laporan Posisi Keuangan` | menentukan seksi tempat akun dicari (lihat tabel di bawah) |
| `akun` | ya | nama akun, mis. `Kas dan Setara Kas` | nama akun di hasil; dicocokkan dengan label PDF/Excel |
| `field_key` | ya | kode unik per entitas, mis. `kas_dan_setara_kas` | **kunci pasangan PDF ↔ Excel** (`kode_akun` di hasil) |
| `dtype` | | `number` | informasi |
| `description` | ya | `Nama Akun: 'alias 1', 'alias 2', ...` lalu keterangan/instruksi | alias dipakai mencocokkan label PDF dan Excel; **seluruh teks dikirim ke Claude** sebagai instruksi ekstraksi akun itu |

Alias dibaca dari bagian awal `description` sampai baris kosong atau kata "Keterangan Akun"/"Penjelasan Akun",
dengan format `Nama Akun: 'Kas dan Setara Kas', 'Cash and cash equivalents'`.

**Nilai kolom `bagian` yang dikenali:**

| `bagian` | Seksi |
|----------|-------|
| Laporan Posisi Keuangan | `financial_position` |
| Laporan Laba Rugi | `income` |
| Laporan Arus Kas | `cashflow` |
| Laporan Perubahan Aset Bersih | `rd_netassets` |
| Laporan Kinerja Keuangan | `rd_performance` |
| Catatan Atas Laporan Keuangan (CaLK) | `calk` |
| Laporan Perubahan Modal (epp) / Laporan Posisi Keuangan (mi) | EPP: `equity`, MI: `financial_position` |
| Akun Utang Berbasis Bunga / Akun Pendapatan Non Halal | `financial_position` / `income` (entitas `DES`) |

Nilai `bagian` baru perlu ditambahkan di `BAGIAN_KE_SEKSI` pada `src/sikuli/rules.py`.

### Konfigurasi teknis (folder `config/`, jarang diubah)

Bukan rules akun, melainkan tata letak dokumen:

| File | Isi |
|------|-----|
| `config/mapping_seksi.csv` | pola judul laporan untuk mengenali seksi PDF tanpa AI (`kode`, `seksi`, `entitas`, `pola`, `maks_halaman`) |
| `config/sheet_config.csv` | letak angka di Excel per jenis entitas (`doc_type`, `sheet`, `seksi`, `kolom_label`, `kolom_nilai`, `kolom_nilai_lalu`, `baris_mulai`, `baris_akhir`, `skala`) |
| `config/pipeline.yaml` | pola nama file, AI, toleransi komparasi |

## Struktur hasil

Artifact `hasil-komparasi` berisi `hasil_komparasi.xlsx` (satu sheet per tabel di bawah), CSV dengan isi sama,
dan `ringkasan.md`.

**Komparasi** (`komparasi.csv`): satu baris per entitas × akun × periode, urut dari yang perlu ditinjau.

| Kolom | Arti |
|-------|------|
| `entity_key` | nama file tanpa ekstensi (kunci pasangan PDF ↔ Excel), mis. `MI_CC002_LK_Tahunan_Audited_2025` |
| `seksi`, `kode_akun`, `nama_akun`, `periode` | akun yang dibandingkan; `periode` = `berjalan` / `lalu` |
| `satuan_pdf` | satuan penyajian PDF, mis. `jutaan Rupiah`; semua nilai di baris ini memakai satuan ini |
| `nilai_pdf` | angka PDF persis seperti tertulis (tidak dikalikan) |
| `nilai_excel` | angka Excel yang sudah **dibagi** sesuai satuan PDF, mis. 1.250.400.000 → 1.250,4 |
| `nilai_excel_asli` | angka Excel asli (Rupiah penuh) |
| `selisih`, `selisih_persen` | `nilai_pdf − nilai_excel` dalam satuan PDF, dan persentasenya terhadap Excel |
| `status` | `MATCH` (sama dalam toleransi), `DIFFERENT`, `PDF_ONLY`, `EXCEL_ONLY` |
| `indikasi` | petunjuk penyebab DIFFERENT: `BEDA_TANDA`, `BEDA_SKALA` |
| `catatan` | penjelasan per baris (dari AI bila aktif, selain itu template) |
| `sumber_catatan` | `ai` atau `otomatis` |
| `verifikasi_pdf` | hasil cek angka PDF ke teks halaman: `cocok`, `tidak_ditemukan_di_halaman`, `tanpa_teks` (PDF scan) |
| `halaman_pdf`, `sumber_pdf`, `sumber_excel` | jejak sumber; Excel ditulis `file.xlsx!sheet!baris` |
| `label_pdf`, `label_excel` | nama baris persis di masing-masing sumber |

**Ringkasan** (`ringkasan.csv`): per `entity_key`, jumlah baris tiap status dan `persen_match`.

**Angka_PDF** (`angka_pdf.csv`): angka yang terbaca dari PDF: `sumber_file`, `entity_key`, `seksi`,
`kode_akun`, `label_di_dokumen`, `periode`, `nilai` (seperti tertulis, tidak dikalikan), `nilai_asli`, `skala` (satuan yang terdeteksi), `halaman`, `sumber_ekstraksi` (`ai`/`aturan`), `verifikasi`.

**Angka_Excel** (`angka_excel.csv`): angka dari Excel: `sumber_file`, `entity_key`, `sheet`, `baris`,
`seksi`, `label_asli`, `kode_akun` (kosong = label belum terpetakan), `cara_pemetaan`, `periode`, `nilai`,
`nilai_asli`.

**Lokasi_Seksi** (`lokasi_seksi.csv`): seksi per dokumen: `nama_file`, `entity_key`, `seksi`,
`halaman_mulai`, `halaman_akhir`, `judul_cocok`.

**Kesimpulan** (`kesimpulan.csv`): per `entity_key`: `kesimpulan` dan `rekomendasi` dari Claude (kosong bila AI
tidak aktif).

**Peringatan** (`peringatan.csv`): akun tidak ditemukan, sheet tidak ada, nama file tidak dikenali, PDF tanpa teks.

## Batasan

- Tanpa AI: PDF harus punya lapisan teks, dan label akun yang terpotong ke dua baris belum terbaca.
- Dengan AI: PDF maksimal sekitar 30 MB / 600 halaman per file (batas API); file lebih besar memakai aturan.
  Angka PDF hasil scan tidak bisa diverifikasi otomatis ke teks halaman (`verifikasi = tanpa_teks`).
- Batas ukuran file GitHub 100 MB per file.

## Struktur repo

| Path | Isi |
|------|-----|
| `.github/workflows/analisis.yml` | Menjalankan analisis dan menyimpan hasil sebagai artifact |
| `.github/workflows/tests.yml` | Menjalankan tes setiap push |
| `input/` | Tempat upload LK PDF dan Excel |
| `rules/` | Satu file rules: `Extraction_Rules.xlsx` (sheet Master) |
| `config/` | `pipeline.yaml`, `mapping_seksi.csv`, `sheet_config.csv` (konfigurasi teknis) |
| `src/sikuli/` | Kode pipeline (`lokal.py` = titik masuk) |
| `tests/` | Tes unit dan end-to-end dengan PDF/Excel contoh |
| `notebooks/`, `sql/` | Versi Databricks dari alur yang sama (opsional, tidak dipakai workflow) |
