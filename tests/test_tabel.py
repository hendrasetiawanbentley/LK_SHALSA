from sikuli import tabel


class SparkTiruan:
    def createDataFrame(self, data, schema):
        self.data, self.schema = data, schema
        return self


def test_ke_dataframe_urutan_dan_tipe_kolom():
    spark = SparkTiruan()
    tabel.ke_dataframe(spark, [{"kode_akun": "K1", "halaman": "3", "nilai": 5, "kolom_lain": "x"}], "angka_pdf")
    kolom = [k for k, _ in tabel.SKEMA["angka_pdf"]]
    baris = dict(zip(kolom, spark.data[0]))
    assert spark.schema.startswith("doc_id STRING, sumber_file STRING")
    assert baris["halaman"] == 3 and baris["nilai"] == 5.0 and baris["doc_id"] is None
    assert baris["processed_at"] is not None


def test_variant_tidak_ikut_dataframe_dan_result_punya_catatan():
    spark = SparkTiruan()
    tabel.ke_dataframe(spark, [], "pdf_parsed")
    assert spark.schema == "path STRING, nama_file STRING, parsed_at TIMESTAMP"
    kolom = [k for k, _ in tabel.SKEMA["result_komparasi"]]
    assert kolom[-3:] == ["catatan_ai", "run_id", "processed_at"]
    assert "CREATE TABLE IF NOT EXISTS a.b.teks_pdf" in tabel.ddl("a.b.teks_pdf", "teks_pdf")
