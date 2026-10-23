# Cek Data AI Open Source

Prototipe pemeriksaan data statistik berbahasa Indonesia menggunakan **LlamaIndex, Qdrant, FastAPI, React**, dan **OpenAI API**. Dikembangkan oleh Indonesian Data Journalism Network dari prototipe lokal Cek Data AI.

Status: **prototipe lokal**, bukan layanan publik siap produksi. Kode terbuka tidak berarti penggunaan model gratis: panggilan OpenAI dan layanan sumber mengikuti biaya masing-masing. Tidak ada dataset pengguna atau API key dalam repo ini.

## Cara kerja

Pertanyaan/klaim → AI memahami maksud → pemilihan katalog indikator → pencarian payload Qdrant → pemeriksaan wilayah, periode, kategori, satuan, dan perhitungan → jawaban dengan sumber.

- Pertanyaan data dibedakan dari klaim.
- Perhitungan angka memakai `Decimal`; jawaban mengikuti bukti yang ditemukan.
- Temuan beberapa periode disajikan sebagai butir terpisah, lalu kesimpulan tren/perbandingan.
- Klaim dengan data tidak cukup mendapat konteks yang tersedia dan batas penilaiannya.
- Tautan sumber berasal dari metadata, tidak dibuat oleh model.
- Pencarian saat ini menggunakan katalog leksikal + pemilihan AI + filter Qdrant. **Pencarian kemiripan embedding belum diaktifkan.**

## Menjalankan lokal

Perlu Python 3.12, Node.js 22.12+, serta Qdrant. Docker Compose hanya diperlukan jika belum menjalankan Qdrant sendiri.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Lewati langkah berikut jika Qdrant sudah berjalan di port 6333.
docker compose up -d
cd web/frontend
npm ci
npm run build
cd ../..
```

Siapkan katalog dan bukti dengan **salah satu** cara berikut.

### Data simulasi untuk mencoba aplikasi

```sh
python scripts/seed_demo.py
```

Contoh ini berisi nilai buatan, ditandai SIMULASI. Jangan menggunakannya sebagai statistik nyata. Coba: “Berapa jumlah pekerja di Kota Contoh pada 2025?” atau “Bagaimana tren jumlah pekerja di Kota Contoh dari 2023 sampai 2025?”.

### Data sendiri dari ekspor Pinecone

```sh
python tools/pinecone/server.py
```

Buka http://127.0.0.1:8766, masukkan key Pinecone berizin baca, pilih index dan namespace. Pengambilan dibatasi 10.000 record per percobaan; memakai kuota baca/transfer Pinecone. File asli dan metadata dipertahankan. Sampel mengikuti urutan ID, bukan sampel acak.

Impor folder yang berisi `manifest.json` dan `records.jsonl`:

```sh
python workflow/pilot_data.py /path/to/export-folder
```

Importer ditujukan untuk format metadata statistik pilot: `value`, `year`, `area_name`, `unit`, `title`, `source`, serta `dataset_id`/`series_label` untuk membedakan seri. Lihat [kontrak data](docs/data-contract.md). Importer menolak koleksi yang sudah berisi data; untuk dataset baru gunakan `CEKDATA_COLLECTION` dan `CEKDATA_DATA_DIR` baru. Jangan menggabungkan index/namespace berbeda tanpa memeriksa identitas record.

**Metadata lingkungan yang hanya berisi `mysql_reference` belum didukung sebagai bukti angka.** Pengambilan nilai canonical dari MySQL belum diimplementasikan. Vektor `values` bukan nilai statistik.

Jalankan aplikasi:

```sh
python web/server.py
```

Buka http://127.0.0.1:8765 dan masukkan OpenAI API key melalui Pengaturan. Key disimpan dalam memori sesi, bukan file. Pertanyaan dan bukti terpilih dikirim ke OpenAI. Riwayat jawaban disimpan di browser, maksimal 20 percakapan.

Konfigurasi opsional melalui variabel shell: `QDRANT_URL`, `CEKDATA_COLLECTION`, `CEKDATA_DATA_DIR`, dan `CEKDATA_MODEL`. `.env.example` hanya contoh; aplikasi tidak otomatis membaca `.env`.

## Pengujian

```sh
PYTHONPATH=workflow python -m unittest discover -s workflow/tests -v
PYTHONPATH=workflow:web python -m unittest discover -s web -p 'test_*.py' -v
PYTHONPATH=tools/pinecone python -m unittest discover -s tools/pinecone -p 'test_*.py' -v
cd web/frontend
npm test
npm run build
```

Pengujian otomatis memakai respons AI simulasi dan Qdrant dalam memori; tidak membutuhkan API key dan tidak mengukur akurasi model langsung. Sebagian kasus regresi menggunakan angka contoh dari pengujian pilot. Keberhasilan tes tidak membuktikan kebenaran data sumber atau akurasi seluruh database.

## Struktur

- `workflow/`: pemahaman pertanyaan, pencarian, penilaian, format jawaban, impor.
- `web/`: server lokal, frontend yang diadaptasi dari Cek Data AI, tes HTTP.
- `tools/pinecone/`: ekspor baca dengan pembatasan jumlah dan checksum.
- `scripts/seed_demo.py`: data buatan untuk demonstrasi lokal.
- `docs/`: aturan editorial, kontrak data, keterbatasan dan rencana pengembangan.

[Aturan saat ini](docs/editorial-rules.md) · [Rancangan analisis “mengapa”](docs/why-analysis-plan.md) · [Keamanan](SECURITY.md)

## Batas versi ini

Frontend lokal mengaktifkan sumber BPS sebagai kategori pilot. Data multi-sumber, pemanggilan canonical MySQL, dan pencarian indikator pendukung untuk analisis sebab belum tersedia secara lengkap. Beberapa komponen frontend warisan untuk layanan produksi tetap ada di sumber, tetapi tidak diaktifkan oleh `LocalApp` dan endpoint produksi tersebut tidak disediakan server ini.

Server dan Qdrant dimaksudkan untuk loopback. Jangan membuka port aplikasi ke internet tanpa autentikasi, TLS, pembatasan penggunaan, dan pengelolaan sesi untuk produksi.

## Lisensi dan asal kode

MIT, lihat [LICENSE](LICENSE). Frontend diadaptasi dari proyek [Cek Data AI](https://github.com/Indonesian-Data-Journalism-Network/cekdata-ai) milik organisasi yang sama. Lisensi kode tidak memberikan hak atas dataset eksternal, merek, atau logo penyedia data. Dependensi mempertahankan lisensinya masing-masing.
