# Input analisis

- `input/pdf/`   : LK PDF, misalnya `AAAA_LK_2024.pdf`
- `input/excel/` : LK Excel pasangannya, misalnya `AAAA_2024.xlsx`

PDF dan Excel dipasangkan dari prefiks nama file (lihat `entitas.pola_nama_file` di `config/pipeline.yaml`).
Setiap push ke folder ini (atau ke `rules/` / `config/`) menjalankan workflow **analisis** di GitHub Actions.
