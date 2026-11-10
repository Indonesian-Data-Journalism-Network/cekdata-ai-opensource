# Cek Data AI Open Source

Prototipe pemeriksaan data statistik berbahasa Indonesia menggunakan **LlamaIndex, Qdrant, FastAPI, React**, dan **OpenAI API**. Dikembangkan oleh Indonesian Data Journalism Network dari prototipe lokal Cek Data AI.

Status: **prototipe lokal**, bukan layanan publik siap produksi. Kode terbuka tidak berarti penggunaan model gratis: panggilan OpenAI dan layanan sumber mengikuti biaya masing-masing. Tidak ada dataset pengguna atau API key dalam repo ini.

## Cara kerja

Pertanyaan/klaim → AI memahami maksud → pemilihan katalog indikator → pencarian payload Qdrant → pemeriksaan wilayah, periode, kategori, satuan, dan perhitungan → jawaban dengan sumber.

- Pertanyaan data dibedakan dari klaim.
- Perhitungan angka memakai `Decimal`; jawaban mengikuti bukti yang ditemukan.
- Temuan beberapa periode disajikan dalam tabel, dengan perhitungan dan kesimpulan tren/perbandingan.
- Klaim dengan data tidak cukup mendapat konteks yang tersedia dan batas penilaiannya.
- Tautan sumber berasal dari metadata, tidak dibuat oleh model.
- Angka terstruktur dicari melalui katalog dan pemilihan indikator: Qdrant untuk data lokal, atau [Pinecone langsung untuk General](docs/pinecone-live.md) bila koneksinya aktif. Laporan NGO memakai pencarian embedding multilingual lokal, pemeriksaan kutipan/halaman, dan seleksi bukti.

## Pembaruan 7 November 2026

- Perbaikan pemahaman wilayah/alias, periode dan perubahan tahunan, pemilihan indikator, perhitungan, serta label klaim.
- Impor GFW kabupaten/kota dan indikator tambahan; [MapBiomas](docs/mapbiomas.md); [laporan NGO dan metadata konteks](docs/ngo-reports.md).
- Pemeriksaan bukti NGO mencakup cakupan wilayah, entitas, subjek survei, satuan, risiko/rencana versus kejadian, serta sumber dan halaman PDF.
- Tampilan chat dengan kolom ketik tetap terlihat, status proses, panel riwayat, kategori General/Environment/Legal, tabel temuan dan tautan sumber/unduhan.
- [Rekap benchmark 500](docs/benchmarks/20261107/rekap-benchmark.html): **428/500 akurat (85,6%)**, 43 bermasalah, 26 terbatas, dan 3 gangguan layanan. Jawaban parsial yang faktanya tepat diterima. Ini gabungan jawaban terakhir yang tersimpan dari beberapa revisi, **bukan uji ulang 500 soal pada satu versi kode**.

Kenaikan dari 404 menjadi 428 terdiri dari delapan jawaban revisi yang lolos dan
16 jawaban parsial yang diterima karena perubahan kriteria. Klaim manfaat/dampak
umum masih lemah (2/20). Angka agregat tidak menjamin keandalan semua jenis pertanyaan.
Lihat [status rilis dan pekerjaan berikutnya](docs/release-20261107.txt).

Arah “jawaban data utama, lalu konteks NGO yang menjelaskan isi laporan secara
langsung” sudah disepakati, tetapi **belum diimplementasikan** dalam rilis ini.
Laporan NGO tetap dapat menjadi sumber angka utama bila bukti relevan tersedia.
Dataset sumber, PDF, model embedding, isi Qdrant, kredensial dan paket evaluasi
mentah tidak disertakan. Impor masing-masing sumber diperlukan di instalasi baru.

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

## Data Global Forest Watch lokal

Importer `workflow/gfw_data.py` mengambil statistik Indonesia nasional dan provinsi
dari versi tetap `v20260424`, dengan batas GADM `v4.1` dan ambang tajuk 30%.
Indikator dipisahkan: kehilangan tutupan pohon dan kehilangan akibat kebakaran
(2001–2025), serta kehilangan dalam hutan primer tropis basah tahun acuan 2001
(2002–2025). Kehilangan tutupan pohon bukan otomatis deforestasi permanen.

```sh
# GFW_API_KEY dari lingkungan, atau kredensial lokal .local/gfw-credentials.json.
.venv/bin/python workflow/gfw_data.py           # unduh, arsipkan, dan validasi
.venv/bin/python workflow/gfw_data.py --publish # terbitkan ke koleksi GFW kosong
```

Respons asli, checksum, SQL, waktu pengambilan, katalog, serta laporan kelengkapan
disimpan di `data/gfw/`. Koleksi `cekdata_gfw_idn_20260424_t30` terpisah dari pilot
dan menggunakan payload tanpa embedding. Koleksi berisi data tidak ditimpa.
Tautan metadata resmi dan unduhan terfilter untuk setiap angka disimpan tanpa key.
Sumber Global Forest Watch aktif di aplikasi setelah laporan publikasi selesai;
pilihan General tetap menggunakan koleksi pilot sendiri.

Impor awal 5 November 2026: 2.532 observasi, tiga indikator, nasional dan 34 provinsi
sumber. Batas Papua/Papua Barat belum mengikuti pemekaran terbaru. Beberapa tahun
Jakarta Raya dan seri hutan primer Jakarta Raya/Yogyakarta tidak memiliki baris
sumber; baris yang tidak ada tidak diganti nol. Total provinsi direkonsiliasi dengan
nasional, dengan toleransi maksimum 0,01 ha per indikator/tahun. Angka pada sumber
tetap dipertahankan sebagai teks desimal.

Statistik luas sawit, luas hutan tersisa, konversi hutan menjadi sawit, dan data
sementara 2026 belum tercakup dalam impor ini. Pengujian alur tanpa key OpenAI
menggunakan AI simulasi; ini tidak membuktikan akurasi pemahaman model langsung.

Tambahan tingkat kabupaten/kota menggunakan `workflow/gfw_district_data.py`:

```sh
.venv/bin/python workflow/gfw_district_data.py
.venv/bin/python workflow/gfw_district_data.py --publish
```

Arsip dan laporan ada di `data/gfw-adm2/`; koleksi gabungan
`cekdata_gfw_idn_adm2_20260424_t30` aktif hanya setelah publikasi berhasil.
Koleksi nasional/provinsi sebelumnya tetap disimpan dan menjadi cadangan jika
snapshot kabupaten belum diterbitkan. Snapshot terbit tidak ditimpa.
Impor 5 November 2026 menambahkan 33.225 observasi dari 497 wilayah yang memiliki
baris data, sehingga koleksi GFW gabungan berisi 35.757 observasi.
Direktori sumber memuat 493 kabupaten/kota berlabel jenis, lima wilayah ADM2 di
Kalimantan Utara tanpa label jenis, dan empat perairan. Perairan diarsipkan untuk
rekonsiliasi, tetapi tidak dimasukkan ke pencarian kabupaten/kota. Jakarta Pusat
tidak memiliki baris observasi dalam cakupan impor; ini bukan klaim kehilangan nol.
Nama lengkap mencantumkan provinsi; alias nama pendek hanya digunakan bila unik,
tanpa menebak antara kota dan kabupaten bernama sama. Batas ini mengikuti GADM 4.1,
bukan daftar kabupaten/kota hasil pemekaran terbaru.
Total seluruh geometri ADM2 direkonsiliasi dengan provinsi per indikator/tahun
(toleransi 0,01 ha; selisih maksimum impor ini 0,00000000001705418 ha).
Setiap tautan unduhan observasi memfilter provinsi, kabupaten/kota, tahun, indikator,
dan ambang tajuk. Tahun kosong dan jenis wilayah yang kosong tidak ditebak.

Tautan sumber pada jawaban menggunakan halaman publik, dengan URL API asli
tetap dipertahankan sebagai `api_source_url` untuk audit. Daftar halaman wilayah
yang judulnya cocok dengan nama GADM ada di
`web/frontend/src/config/gfwPublicSources.json`; pemeriksaan anonim dan laporan
HTTP dapat diulang dengan `.venv/bin/python tools/verify_gfw_public_sources.py`.
Wilayah yang belum lolos pemeriksaan memakai halaman dataset dasar resmi UMD
versi 1.13 (2000–2025). Dashboard dapat berubah atau mengalami gangguan layanan;
tautan UMD tetap ditawarkan sebagai penjelasan metode, bukan tabel angka kabupaten.
Angka jawaban tetap berasal dari arsip API, dengan filter dan versi yang tercatat.
Riwayat jawaban lokal ikut diperbarui pada saat dimuat, termasuk teks salinan.
Tombol CSV mengekspor angka bukti dan rujukannya dari jawaban di browser tanpa
memerlukan API key GFW atau mengubah data Qdrant. Berkas ini bisa dibagikan;
alamat localhost aplikasi sendiri bukan tautan yang dapat dibuka pembaca lain.
Jawaban lama yang belum menyimpan bukti terstruktur menawarkan tabel wilayah
sebagai CSV. Buat ulang tabel dengan
`.venv/bin/python tools/export_gfw_public_tables.py`, lalu bangun frontend.
Tabel ini disajikan oleh aplikasi lokal dari `web/frontend/public/gfw-evidence/`
dan tidak dimasukkan ke Git. Gunakan `--refresh` pada pemeriksa tautan untuk
memeriksa ulang jaringan, bukan memakai laporan pemeriksaan sebelumnya.

## Pengujian

Pembaruan mesin dan antarmuka per 10 November 2026 dijelaskan dalam
[catatan versi](docs/pembaruan-20261110.txt). General mendukung Pinecone dan
BPS lokal di Qdrant; lihat [BPS lokal](docs/bps-local.md),
[Pinecone](docs/pinecone-live.md), dan [kontrak pertanyaan](docs/request-contract.md).
Koleksi Qdrant, arsip sumber, kredensial, dan akun pengguna tidak ikut dalam Git.
Mengambil kode terbaru tidak otomatis menyalin data atau konfigurasi server.

```sh
PYTHONPATH=workflow python -m unittest discover -s workflow/tests -v
PYTHONPATH=workflow:web python -m unittest discover -s web -p 'test_*.py' -v
PYTHONPATH=tools/pinecone python -m unittest discover -s tools/pinecone -p 'test_*.py' -v
PYTHONPATH=workflow:. python -m unittest discover -s tools/bps -p 'test_*.py' -v
node --test netlify/tests/*.test.mjs
cd web/frontend
npm test
npm run build
npm run build:public
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

Frontend lokal menyediakan General untuk data pilot, Environment untuk GFW, MapBiomas dan laporan NGO yang telah diimpor, serta Legal yang belum tersedia. Jalur laporan dapat menggabungkan temuan NGO dengan seri GFW yang sesuai; angka antarpenyedia tidak otomatis digabung. Pemanggilan canonical MySQL belum tersedia. Pertanyaan statistik murni belum otomatis diperkaya konteks NGO. Beberapa komponen frontend warisan untuk layanan produksi tetap ada di sumber, tetapi tidak diaktifkan oleh `LocalApp` dan endpoint produksi tersebut tidak disediakan server ini.

Server dan Qdrant dimaksudkan untuk loopback. Jangan membuka port aplikasi ke internet tanpa autentikasi, TLS, pembatasan penggunaan, dan pengelolaan sesi untuk produksi.

## Tambahan karbon, habitat, dan tanaman GFW

Importer `workflow/gfw_expansion.py` menambah emisi tahunan 2001–2025,
total/rata-rata periode karbon, mangrove acuan 2020, gambut gabungan berbagai
tahun, dan kategori tanaman SDPT acuan 2020. Arsip dan laporan berada di
`data/gfw-expansion/`. Jalankan berurutan: unduh tanpa opsi, `--build` untuk
normalisasi dan rekonsiliasi, lalu `--publish` untuk menambah koleksi aktif.
Snapshot semula dicadangkan; publikasi ulang tidak menduplikasi catatan.
Tidak ada observasi 2026 atau konsesi Indonesia yang dibatasi dalam tambahan ini.
Lihat `docs/data-contract.md` untuk periode, nilai yang ditahan, dan metode.

## Lisensi dan asal kode

MIT, lihat [LICENSE](LICENSE). Frontend diadaptasi dari proyek [Cek Data AI](https://github.com/Indonesian-Data-Journalism-Network/cekdata-ai) milik organisasi yang sama. Lisensi kode tidak memberikan hak atas dataset eksternal, merek, atau logo penyedia data. Dependensi mempertahankan lisensinya masing-masing.
