# Pengambilan data BPS lokal

## Aktivasi General — 8 November 2026

General kini memakai `workflow/general_data.py` untuk mencari katalog BPS lokal
bersama katalog Pinecone. Snapshot aktif `cekdata_bps_all_7717193f89ad39` memuat
123.628 observasi periode 2019–2026 dari 62 tabel; **118.945 observasi usable**
dapat digunakan, sedangkan 4.683 observasi tertahan tetap tidak disajikan.
Pemahaman awal pertanyaan diteruskan ke satu pemilihan indikator. Masing-masing
penyimpanan mendapat jatah kandidat agar katalog besar tidak menutupi lainnya.
Jika konsep, wilayah, kategori, dan periode setara serta cukup, pemilih diinstruksikan
mengutamakan tabel lokal. Pinecone tetap dicari untuk cakupan yang lebih luas.

Referensi wilayah dan alias administratif dari kode/sumbu BPS menerjemahkan nama
permintaan ke nama asli tiap penyimpanan. Nama penerbit BPS/Badan Pusat Statistik
diselaraskan saat membaca; payload dan angka sumber tidak diubah. ID seri asli
tetap dipertahankan, sehingga dua tabel tidak otomatis disambung atau dijumlahkan.
Duplikat bukti yang benar-benar identik disatukan; pemilihan satu tabel yang setara
masih melibatkan model dan perlu pengujian lanjutan pada cakupan pertanyaan besar.

Aktivasi ini mencakup observasi angka terstruktur. Koleksi 9.205 potongan dokumen
BRS/tabel statis belum memiliki jalur jawaban dokumen General pada perubahan ini.
Flag `chat_provider_activated`/`public_provider_changed` pada manifest impor adalah
catatan kondisi ketika impor dibuat, bukan status routing runtime saat ini.

Kedua server (lokal dan publik Netlify melalui komputer) memakai runner yang sama.
Tanpa konfigurasi Pinecone, snapshot lokal terverifikasi dapat berjalan sendiri.
Jika Pinecone dikonfigurasi tetapi koneksinya gagal, gangguan tetap dilaporkan;
tidak disamarkan menjadi data tidak tersedia. Tidak ada perubahan index Pinecone,
isi Qdrant, kredensial, atau bundel frontend untuk aktivasi ini.

Hasil pengujian integrasi tersimpan di
`docs/test-evidence/20261108/general-combined/`; ini uji sambungan terbatas,
bukan pengganti benchmark 500 pertanyaan.

Status tahap 7 November 2026: **82.546 observasi periode 2021–2026** telah
diimpor dan dibaca ulang dari Qdrant. Snapshot mencakup 12 tabel sumber, termasuk
TPAK 2021–2026 dan penduduk bekerja menurut sektor pada Februari 2026.
Adapter lokal memakai `qdrant-current-manifest.json`; snapshot khusus 2026
sebelumnya tetap tersedia untuk reproduksi. General publik tetap memakai
Pinecone; sumber produksi belum dialihkan. Riwayat tahap awal di bawah
dipertahankan sebagai catatan perkembangan, bukan inventaris terbaru.

## Sasaran awal

Kemiskinan, ketenagakerjaan, dan PDRB; periode awal 2021 sampai tahun berjalan,
hanya tahun yang benar-benar tersedia dalam katalog BPS. Mulai dari domain
pusat `0000`: domain menunjukkan penerbit tabel, bukan berarti setiap baris
bercakupan nasional. Tabel pusat dapat memuat provinsi. Perluasan ke domain
provinsi/kabupaten mengikuti pemeriksaan cakupan dan duplikasi sumber.

Angka dan identitas dimensi diarsipkan di SQLite. Snapshot 2026 di Qdrant
memakai payload terstruktur dan indeks filter, tanpa embedding per sel.
Adapter uji `workflow/bps_local.py` memakai katalog untuk pemilihan indikator
oleh model, lalu mengambil bukti terfilter dari Qdrant.

## Koneksi privat

```sh
.venv/bin/python tools/bps/connect_server.py
```

Buka `http://127.0.0.1:8783/`. Isi kunci dari portal resmi BPS. Form memeriksa
akses baca katalog sebelum menyimpan `.local/bps-connection.json` dengan izin
0600. `enabled=false` menunjukkan sumber belum diaktifkan untuk jawaban publik;
alat akuisisi tetap dapat memakai kunci tersebut. Alternatif operator adalah
environment `BPS_API_KEY`, tanpa menaruhnya pada argumen perintah.

Form hanya di loopback, memeriksa Host dan Origin, membatasi ukuran permintaan,
dan tidak merekam access log. Jangan mencetak URL permintaan BPS: key merupakan
segmen URL API. Jangan menaruhnya dalam tautan sumber atau respons ke pengunjung.

## Penemuan dan pengambilan

```sh
.venv/bin/python -m tools.bps.ingest discover --domains 0000 --start-year 2021 --end-year 2026
```

Katalog kandidat tersimpan di `data/bps/candidate-plan.json`. Pencocokan kata
topik hanya menemukan kandidat; bukan penetapan indikator jawaban. Tinjau judul,
satuan, definisi, kategori, harga berlaku/konstan, dan wilayah tabel. Pilih tabel
dengan `selected=true`. Isi `source_url` dari halaman publik BPS yang benar-benar
telah diperiksa, lalu `source_verified=true`. Tanpa sumber terverifikasi, angka
boleh disimpan untuk inspeksi tetapi belum layak diaktifkan sebagai bukti publik.

Katalog subjek resmi memungkinkan pencarian lebih terarah melalui `--subjects`.
Pengambilan awal memakai ID 23 (kemiskinan), 6 (tenaga kerja), 52/171 (PDRB),
dan 19 (upah buruh), setelah mencocokkannya dengan katalog resmi. Daftar kandidat
berisi 93 tabel dari 127 variabel pada subjek tersebut. Sepuluh tabel dipilih
untuk tahap awal; ID tabel adalah identitas sumber, bukan aturan jawaban kasus
tertentu. Rencana aktual tersimpan lokal di `data/bps/plan-2021-2026.json`.

```sh
.venv/bin/python -m tools.bps.ingest import --plan data/bps/candidate-plan.json
```

Katalog periode menentukan ID tahun; alat tidak menghitung ID dari tahun atau
mengasumsikan 2026 sudah tersedia. Respons mentah disimpan menurut SHA-256,
disertai waktu pengambilan dan parameter tanpa kredensial. Cache memungkinkan
kelanjutan setelah koneksi putus. `--refresh` mengambil ulang respons untuk
memeriksa revisi; arsip lama tetap tersimpan. Permintaan berjarak minimal satu
detik pada versi awal; setelah respons 429 pada layanan nyata, jeda diperpanjang
menjadi **3,2 detik**. Pengambilan dibatasi 250 permintaan per sesi secara default.
Batas sesi dapat disetel melalui
`--max-requests`; ini batas operator, bukan klaim kuota resmi BPS.

SQLite `data/bps/bps.sqlite3` menyimpan angka sebagai teks desimal agar tidak
kehilangan presisi. Kunci setiap sel mencakup domain, variabel vertikal,
variabel, variabel turunan, tahun, dan periode turunan. Tahun yang diambil ulang
diganti secara transaksional, sehingga sel yang telah ditarik sumber tidak
tertinggal sebagai data terkini. Snapshot mentah lama tetap tersedia.

## Batas penggunaan bukti

- Label sumbu vertikal disimpan apa adanya. Sumbu itu bisa wilayah, lapangan
  usaha, atau kategori lain; kode domain tidak boleh dianggap wilayah baris.
- Total/perkotaan/perdesaan, bulan, dan kategori lainnya tidak digabung.
- Angka hilang tidak diisi nol. String angka dengan tanda/format yang belum
  dipahami disimpan sebagai `unparsed_value`, bukan diperbaiki dengan tebakan.
- Unit kosong/`Tidak Ada Satuan` ditahan, kecuali judul tabel itu sendiri secara
  eksplisit memuat satuan dalam kurung (contoh `Ribu Jiwa`). Asal unit disimpan
  pada `unit_origin` dan unit mentah tetap pada `unit_raw`. Unit tidak disalin
  dari tabel lain atau ditebak dari besar angka.
- Semua sel sumber harus cocok dengan lima dimensi resmi. Kode gabungan yang
  ambigu, dimensi hilang, dan tahun/variabel yang tidak cocok menahan tabel.
- Status `observed` hanya berarti nilai numerik dan unit terbaca, bukan seluruh
  bukti telah diverifikasi atau siap dipakai mesin jawaban.
- Pemeriksaan sebelum aktivasi meliputi pemetaan wilayah, konsep indikator,
  kesetaraan periode, tautan langsung sumber, revisi/provisional, dan uji angka
  serta jawaban terhadap BPS. `source_verified` merupakan catatan tinjauan
  operator, bukan hasil verifikasi URL otomatis oleh alat.
- API dan respons yang diuji otomatis menggunakan fixture sintetis; pengujian
  tersebut bukan bukti keberhasilan koneksi atau cakupan data BPS sebenarnya.

## Validasi dan sumber teknis

```sh
.venv/bin/python -m unittest tools.bps.test_ingest -v
```

Dokumentasi resmi yang dipakai:

- [Referensi API BPS](https://webapi.bps.go.id/documentation/)
- [Resep pengambilan tabel](https://webapi.bps.go.id/documentation/docs/recipes.md)
- [Paginasi](https://webapi.bps.go.id/documentation/docs/pagination-and-limits.md)
- [Autentikasi](https://webapi.bps.go.id/documentation/docs/authentication.md)

Tidak ada angka hasil contoh dokumentasi yang dimasukkan sebagai data produksi.

## Cakupan 2026 yang ditemukan pada pengambilan awal

| Tabel API | Periode observasi 2026 yang tersedia |
| --- | --- |
| 185 dan 192: jumlah/persentase penduduk miskin provinsi dan daerah | Maret |
| 543: TPT provinsi | Februari dan Agustus |
| 2562: TPT provinsi triwulanan | Februari, Mei, Agustus |
| 2267/2268: PDRB provinsi ADHK/ADHB | Triwulan I–III |
| 2775/2776: PDRB kabupaten/kota ADHK/ADHB, 17 lapangan usaha | Triwulan I–II |
| 619/621: jumlah/persentase penduduk miskin kabupaten/kota | Belum terdaftar; katalog tabel pusat masih sampai 2025 |

Ini batas tabel API yang diperiksa, bukan pernyataan bahwa angka 2026 tidak ada
di seluruh publikasi/siaran pers BPS daerah. Catatan sumber tentang angka
sementara PDRB dan perubahan wilayah disimpan pada setiap rekaman. Data TPT
yang bertumpang tindih pada tabel 543 dan 2562 dipertahankan sebagai sumber
terpisah; jangan menjumlahkan atau menghitungnya sebagai observasi independen.

Verifikasi angka dan ekspor tahun tertentu:

```sh
.venv/bin/python -m tools.bps.report --year 2026
```

`data/bps/audit.json` memeriksa checksum respons mentah, kelengkapan kode sel,
nilai asli, nilai desimal, dan satuan. CSV `data/bps/bps-2026.csv` berisi periode,
kategori, angka, catatan sumber, tautan halaman publik, serta waktu pengambilan.
Pemeriksaan ini mengukur integritas pemindahan data, bukan akurasi jawaban AI.

Hasil batch pertama: **81.526 sel sumber**, termasuk **41.539 sel tahun 2026**,
dari 10 tabel terpilih (8 tersedia untuk 2026). Audit seluruh sel terhadap
respons mentah tidak menemukan perbedaan; 16 uji otomatis alat pengambilan lulus.
Sel mencakup kategori sektor/daerah dan periode, sehingga bukan jumlah indikator
unik. Deret 2021–2025 hanya diambil untuk tabel/tahun yang tersedia: dua tabel
PDRB kabupaten/kota 2775/2776 yang dipilih baru memuat 2026; penyambungan dengan
seri lama memerlukan pemeriksaan kesetaraan dimensi terlebih dahulu.

## Qdrant: snapshot angka 2026

Atas permintaan pengguna, angka tahun 2026 telah dimasukkan ke koleksi terpisah
`cekdata_bps_2026_56692b426102db`: **41.539 point**, 8 tabel sumber, dan 80 entri
katalog indikator/kategori. Seluruh payload dibaca kembali dan hash-nya cocok
dengan sumber yang disiapkan; 8 pemeriksaan filter tabel berhasil. Tidak ada
tahun selain 2026 dalam koleksi ini.

```sh
.venv/bin/python -m tools.bps.qdrant_import --year 2026
```

Importer memeriksa ulang respons asli terhadap SQLite, identitas tahun,
satuan, dan tautan publik sebelum menulis. Nama koleksi berasal dari hash isi;
snapshot baru tidak mengganti koleksi lama. Impor terputus dapat dilanjutkan ke
koleksi dengan isi yang sama, setelah memeriksa payload yang sudah ada. Semua
koleksi GFW, MapBiomas, NGO, dan pilot tetap dipertahankan.

Penyimpanan menggunakan payload terstruktur dan indeks filter seperti data GFW,
tanpa vektor embedding buatan atau satu embedding per sel. Nilai tetap berupa
teks desimal presisi asli. Identitas variabel/kategori, kode vertikal BPS, label
sumbu, periode, definisi, catatan sumber, URL publik, checksum snapshot, serta
waktu pengambilan ikut disimpan. Level wilayah belum dipaksakan dari nama
baris: label sumbu dan kode sumber dipertahankan untuk adapter geografi.

Manifest: `data/bps/qdrant-2026-manifest.json`; katalog:
`data/bps/qdrant-2026-catalog.json`; pemeriksaan filter:
`data/bps/qdrant-2026-query-check.json`. **General belum dialihkan ke koleksi
ini.** Adapter uji tersedia melalui `workflow/bps_local.py`, belum terhubung
ke rute aplikasi publik.

## Uji 10 pertanyaan, 7 November 2026

Satu putaran melalui workflow dan model nyata (gpt-4.1-mini-2025-04-14),
bukan pengujian browser: **5 jawaban akurat, 3 bermasalah, 2 keterbatasan
ditangani tepat**. Delapan soal tersedia datanya; lima dijawab sepenuhnya
tepat (62,5%). Penanganan tepat termasuk keterbatasan berjumlah 7/10 (70%).
Ini sampel kecil yang terpisah dari benchmark500 sebelumnya.

Masalah pada uji awal (diperbaiki pada uji ulang di bawah): representasi triwulan bertabrakan dengan filter bulan;
selisih persentase masih berlabel persen; perbandingan dua bulan dalam
satu tahun kehilangan bulan awal dan membandingkan periode akhir dengan
dirinya sendiri. Jangan mengaktifkan adapter sebagai sumber produksi
sebelum batas periode tersebut ditangani dan diuji ulang.

Bukti lokal lengkap: `docs/test-evidence/20261107/bps-qdrant-10/rekap.html`,
`cases.json`, `case-01.json` sampai `case-10.json`, `assessments.json`,
`summary.json`. Berkas bukti berada di direktori yang diabaikan Git.
Sembilan sel bukti yang tampil dicocokkan kembali dengan nilai, satuan,
dan identitas sumber di SQLite: tidak ada perbedaan. Pemeriksaan ini
tidak menyatakan semua kesimpulan jawaban benar.


## Penyeragaman format BPS dengan inti GFW

Versi `cekdata-statistical-observation-v2` menambahkan kolom inti bukti yang
langsung dibaca adapter. Parsing label periode dan satuan dilakukan saat
persiapan impor, bukan diulang ketika bukti dipakai. Format wilayah BPS,
periode bulan/triwulan, kategori, status sementara, sumber dan angka asli
mengikuti [kontrak data](data-contract.md#bps-format-observasi-standar-7-november-2026).

Koleksi v1 `cekdata_bps_2026_56692b426102db` dipertahankan sebagai snapshot
sebelum migrasi. Manifest `data/bps/qdrant-2026-manifest.json` menunjuk koleksi
terverifikasi terbaru dan katalog yang sesuai. Identitas indikator dan point
tetap stabil walaupun nama koleksinya berubah. Tidak ada pengambilan ulang API,
penggantian sumber General publik, atau perubahan angka sumber.

Uji migrasi mencocokkan semua 41.539 `original_row` dengan SQLite. Uji unit
meliputi periode triwulan tanpa bulan palsu, bulan Februari tahun kabisat,
label semester dengan bulan eksplisit, skala satuan, kategori, dan catatan
sementara khusus tahun observasi. Format baru tidak dengan sendirinya
memperbaiki kontrak intent untuk periode awal/akhir; hasil 10 pertanyaan
sebelumnya tetap dicatat apa adanya sampai ada pengujian ulang mesin.


Hasil migrasi: koleksi aktif uji **`cekdata_bps_2026_3e768fc0611056`**,
41.539 payload terverifikasi (41.112 triwulanan dan 427 bulanan), 8 tabel,
80 entri katalog. Rincian audit ada di
`data/bps/qdrant-2026-format-v2-audit.json`. Tiga pengambilan nyata dari
Qdrant memeriksa kemiskinan total/perdesaan dan PDRB triwulan II; semuanya
cocok. Pemeriksaan tersebut adalah uji struktur/pengambilan bukti, bukan
pengulangan 10 pertanyaan melalui model.


## Perbaikan periode dan uji ulang mesin, 7 November 2026

Kontrak `requested_periods` pada intent dan `periods` pada pencarian membawa
seluruh periode awal/akhir. Triwulan memakai kolom quarter, bukan month.
Perhitungan mencocokkan identitas periode penuh dan menolak perbandingan satu
observasi dengan dirinya sendiri. Selisih persen menggunakan poin persentase
setelah normalisasi satuan. Status sementara ditampilkan sesuai tahun sumber.

Putaran final 10 pertanyaan dengan model nyata dan koleksi v2: **8 akurat,
0 bermasalah, 2 keterbatasan ditangani tepat**. Semua 8 soal dengan data
tersedia terjawab akurat, tetapi sampel kecil ini bukan ukuran akurasi global.
Dua keterbatasan tetap sama: sejarah 2024–2025 belum masuk koleksi uji 2026,
dan kemiskinan kabupaten 2026 tidak tersedia pada tabel yang diimpor.
110 uji regresi offline lulus, termasuk jalur tahunan GFW, perubahan relatif,
nilai awal nol, kontrak intent dan adapter Pinecone. Uji offline bukan
pengukuran akurasi model langsung.

Laporan: `docs/test-evidence/20261107/bps-qdrant-10-period-fix/rekap.html`.
Jawaban sebelum perbaikan dan putaran awal perbaikan tetap diarsipkan.
Dua belas sel bukti dari putaran final cocok dengan nilai, unit, periode dan
identitas sumber di SQLite. Satu catatan penyajian tersisa: dua tabel TPT
menampilkan angka Bali yang sama; angka tetap benar dan tidak dijumlahkan.
General publik tetap Pinecone; adapter BPS belum diaktifkan sebagai default.

## Perluasan historis dan ketenagakerjaan — 7 November 2026

Koleksi aktif adapter lokal: `cekdata_bps_2021_2026_e11792742524c7`.
Manifest: `data/bps/qdrant-current-manifest.json` (status `verified`).
Jumlah: **82.546 payload**, seluruhnya cocok dengan arsip sumber setelah dibaca
ulang dari Qdrant; **42.193** di antaranya merupakan observasi 2026.
Dibanding snapshot sebelumnya (41.539), bertambah **41.007** observasi:
39.987 historis yang sudah diarsipkan, 405 TPAK dan 615 penduduk bekerja.

| Kelompok | Tahun observasi yang diimpor | Catatan |
| --- | --- | --- |
| Jumlah/persentase miskin provinsi | 2021–2026 | Bulan yang tersedia saja; 2026 Maret |
| Jumlah/persentase miskin kabupaten/kota | 2021–2025 | 2026 belum tersedia pada tabel pusat yang dipilih |
| TPT provinsi | 2021–2026 | Tabel 543 dan 2562 tetap terpisah; tidak dijumlahkan |
| PDRB provinsi ADHB/ADHK | 2021–2026 | Triwulan dan tahunan dibedakan; 2026 hanya I–III |
| PDRB kabupaten/kota ADHB/ADHK | 2026 | Triwulan I–II; seri lama tidak disambung sembarangan |
| TPAK nasional/provinsi (2396) | 2021–2026 | 2021–2025 Februari/Agustus; 2026 Februari |
| Penduduk bekerja menurut provinsi/sektor (2333) | 2026 | Februari; sektor dan total tetap terpisah, satuan orang |

Pembaruan penyiapan data memperlakukan kode provinsi berakhiran `00` pada
sumbu campuran Provinsi/Kabupaten/Kota sebagai provinsi. Markup HTML dan
singkatan administratif pada label tampilan dinormalisasi; label dan dimensi
asli tetap disimpan di `original_row`. Angka tidak diubah atau diskalakan.
Tahun, bulan, triwulan, status sementara, dan tautan publik sumber dipertahankan.

```sh
.venv/bin/python -m tools.bps.qdrant_import --year 2021 --end-year 2026 --activate-trial
```

`--activate-trial` hanya memperbarui pointer adapter lokal setelah seluruh
payload lulus verifikasi. Tidak mengubah provider General publik. Memanggil
adapter dengan `year=2026` tetap memakai snapshot khusus 2026. Koleksi lama,
GFW, MapBiomas, dan NGO tidak dihapus atau diganti.

Pemeriksaan perluasan selanjutnya disimpan dalam `data/bps/expansion-periods.json`
dan `expansion-2026-probe.json`:

- Gini (98): data Maret 2026 ditemukan, respons mentah diarsipkan. Belum
  diaktifkan karena metadata satuan menyebut `Tidak Ada Satuan`; perlu kontrak
  rasio tanpa satuan yang terverifikasi, bukan dianggap persen.
- Upah KBLI 2025 (2819): 526 sel Februari 2026 ditemukan dan diarsipkan.
  Belum diaktifkan: halaman publik tabel belum berhasil diverifikasi (Cloudflare
  403), dan baris rata-rata nasional perlu ditinjau. Jangan menyambung langsung
  klasifikasi sektor lama 2475 dengan KBLI 2025.
- IPM (494/413): katalog API yang diperiksa berhenti pada 2024. Ini batas tabel
  yang diperiksa, bukan klaim tidak ada publikasi IPM lebih baru di seluruh BPS.
  Pemeriksaan lanjutan pada 7 November 2026 menemukan **BRS IPM Indonesia 2026**,
  ID 171255, rilis 5 November 2026. Detail API menyediakan abstrak dan PDF;
  belum diimpor ke Qdrant. Jangan menggunakan batas katalog dinamis sebagai
  kesimpulan ketiadaan data pada jalur BRS, tabel statis atau Yearbook Dataset.
- Pengeluaran rumah tangga: tabel publik pengeluaran per kapita sebulan yang
  ditemukan memuat 2025. Ketersediaan 2026 untuk indikator ini belum dikonfirmasi;
  pengeluaran per kapita disesuaikan untuk IPM bukan pengganti indikator tersebut.

Pengujian kode: 41 pemeriksaan importer, standardisasi, adapter, dan periode
lulus. Pengujian jawaban langsung serta acuan sumber tersimpan di
`docs/test-evidence/20261107/bps-history-expansion/`. Ini uji integrasi perluasan,
bukan pengganti benchmark dua batch 100 pertanyaan sebelumnya.

### Pemeriksaan jalur API selain tabel dinamis

Dokumentasi OpenAPI resmi dan respons langsung domain `0000` diperiksa pada
7 November 2026. `statictable` menyediakan isi tabel HTML dan field `excel`;
`pressrelease` menyediakan abstrak, `pdf`, dan pada contoh respons juga `slide`
serta infografik; `publication` menyediakan metadata/abstrak dan `pdf`.
Katalog `tablestatistic` menggabungkan sumber tabel menurut subjek CSA dan
memuat `tablesource`; ada jalur Yearbook Dataset/SIMDASI tersendiri.

Tiga tautan unduh contoh (Excel tabel statis, PDF BRS, PDF publikasi) berhasil
diakses tanpa API key dengan HTTP 200 dan tipe berkas yang sesuai. Ini uji
sampel, bukan jaminan setiap tautan tetap berlaku. Tanggal rilis/pembaruan
harus dipisahkan dari tahun observasi: contoh publikasi rilis November 2026
berjudul Statistik Pendaratan Ikan Tradisional 2025.

Bukti pemeriksaan: `docs/test-evidence/20261107/bps-api-coverage/`.
Pemeriksaan ini bersifat baca saja; importer tetap hanya tabel dinamis dan
tidak ada data dari endpoint tambahan yang diaktifkan ke Qdrant.

### BRS: arsip teks tanpa mengunduh PDF

```sh
.venv/bin/python -m tools.bps.brs --year 2026
```

Collector mengambil katalog BRS pusat dan detail API: judul, teks `abstract`,
tanggal terbit/pembaruan, subjek, dan referensi sumber. Tidak ada permintaan
ke URL PDF, infografik, atau bahan tayang. Judul harus ikut disimpan karena
beberapa angka utama hanya tertulis di judul, bukan di abstrak.

Respons JSON asli dan checksum disimpan di `data/bps/brs/raw`; dokumen teks
di `data/bps/brs/documents`. Link PDF resmi tetap disimpan sebagai referensi
unduh bagi pengguna, tetapi berkas tidak diambil. Tautan halaman publik dibangun
dari metadata rilis resmi dan ditandai belum diverifikasi per dokumen. Arsip ini
belum mengaktifkan sumber jawaban atau mengganti koleksi angka BPS.

Tahun filter adalah **tahun rilis**, bukan otomatis tahun observasi. Angka
perlu dibaca bersama periode, wilayah, satuan, cakupan dan basis perbandingan
yang tertulis dalam teks. Abstrak dapat cukup untuk angka utama, tetapi tidak
menjamin seluruh rincian provinsi/sektor, seri panjang atau tabel lampiran ada.
Abstrak kosong tidak diisi dengan dugaan. Jika suatu rincian tidak ada dalam
teks, cari tabel statistik yang sesuai; jangan menganggapnya tidak tersedia
di seluruh BPS atau melengkapi angka dengan perkiraan.

Hasil pengambilan 7 November 2026: **114 BRS pusat**, rilis 5 Januari–5 November
2026, seluruhnya memiliki abstrak; 112.923 karakter judul dan teks. Seluruh
114 teks cocok dengan respons API dan checksum arsip. **Nol PDF diunduh**.
Manifest `data/bps/brs/brs-0000-2026-manifest.json`; kumpulan teks
`data/bps/brs/brs-0000-2026-texts.json`. Inventaris dan audit tersedia pada
`docs/test-evidence/20261107/bps-brs-text/rekap.html`.
Statusnya arsip teks, belum diindeks ke Qdrant atau diaktifkan di jawaban publik.

## Tabel statis: sasaran 2019–2026 dan sepuluh tema

Permintaan 7 November 2026 memperluas rentang ke **2019–2026**, agar 2019
tersedia sebagai pembanding sebelum pandemi. Tahun 2020–2021 tetap disimpan.
Sepuluh tema: kemiskinan/ketimpangan, pekerjaan/pendapatan, ekonomi daerah,
harga/daya beli, pembangunan manusia, pertanian/perkebunan, konsumsi,
pendidikan, politik/demokrasi, kriminalitas. Pemilihan kata pada katalog hanya
menemukan kandidat, bukan aturan intent atau penetapan bukti jawaban.

```sh
.venv/bin/python -m tools.bps.static --start-year 2019 --end-year 2026
.venv/bin/python -m tools.bps.static_report
```

Alat memeriksa seluruh katalog tabel statis penerbit pusat (`0000`), tanpa
memfilter tahun pembaruan sebagai tahun observasi. Respons detail JSON beserta
HTML tabel asli diarsipkan dengan checksum dan waktu pengambilan. Grid menyimpan
asal setiap sel dan rentang `rowspan`/`colspan`, termasuk judul bertingkat,
tanda kosong, dan catatan kaki. Tabel sumber lengkap tetap disimpan agar tahun
di luar sasaran dan catatan metode tidak terhapus.

Hasil berada di `data/bps/static`: `catalog.json`, `plan.json`, `documents/`,
`raw/`, dan `manifest.json`. `year_cell_candidates` hanya petunjuk pencocokan
label tahun; belum membuktikan cakupan observasi numerik (angka, tahun dasar,
atau catatan bisa menyerupai tahun). Tanggal pembaruan dan tahun judul tidak
dipakai untuk mengarang tahun setiap sel. Normalisasi indikator, wilayah,
satuan dan periode diperlukan sebelum arsip ini dapat dipakai adapter angka.

Tautan unduh Excel berasal langsung dari API; tidak ada PDF/Excel yang diunduh.
Halaman publik dibentuk dari ID tabel resmi dan ditandai belum diverifikasi
satu per satu. Laporan HTML lokal meng-escape isi sumber dan tidak mengeksekusi
HTML/script sumber. Audit mencocokkan checksum respons dan seluruh HTML dengan respons API
tersimpan; parser grid diuji dengan kasus sel gabungan dan contoh sumber. Ini audit integritas pemindahan, bukan uji akurasi jawaban.

Arsip statis tidak otomatis mengganti data dinamis, pointer Qdrant, maupun
sumber General publik. Data yang belum ditinjau tidak diaktifkan sebagai
observasi numerik. Cakupan katalog provinsi/kabupaten penerbit belum diklaim
lengkap oleh pemeriksaan katalog pusat ini.

### Hasil pengambilan statis 7 November 2026

- Seluruh **722 entri** katalog pusat selesai diperiksa untuk penemuan kandidat.
- **285 kandidat tema**; **85 dikeluarkan** karena periode pada judul dan tanggal
  pembaruannya sama-sama sebelum 2019. Kandidat berjudul lama tetapi diperbarui
  lebih baru tetap diperiksa.
- **200 entri berhasil diarsipkan**, tanpa kegagalan permintaan. **199 berisi
  tabel HTML**, sedangkan tabel ID 2008 adalah daftar publikasi pendidikan,
  bukan tabel angka HTML.
- Checksum respons dan HTML seluruh 200 entri cocok dengan arsip API; tidak ada
  selisih integritas sumber. Parser dan alat terkait lulus **26 pengujian**.
- Terdapat 3.680.602 sel asal dalam grid, termasuk judul, kategori, tahun di luar
  sasaran, catatan, dan sel kosong. **Ini bukan jumlah observasi numerik siap
  pakai.** Label tahun sasaran ditemukan dalam sel 74 tabel; angka ini bukan
  ukuran kelengkapan periode, sebab banyak tabel satu tahun menaruh periode
  hanya pada judul.
- Banyak tabel konsumsi/pendidikan tersedia hingga 2025; pemilu memuat 2019
  dan 2024; tabel selang waktu tindak pidana mencapai 2024. Katalog statis pusat
  yang disaring belum memberi kandidat PDRB/IPM yang sesuai. Satu kandidat
  pertanian yang diperbarui lebih baru tetap berjudul periode 2017; belum
  memenuhi sasaran 2019–2026.
- Tidak ada PDF diunduh. **Belum dimasukkan ke Qdrant atau jawaban publik**;
  pemetaan dimensi numerik, satuan, wilayah, dan periode masih diperlukan.

Rekap lokal: `docs/test-evidence/20261107/bps-static-2019-2026/rekap.html`.
Statistik audit: `summary.json` pada direktori yang sama. Setiap entri memiliki
salinan lokal yang menampilkan grid dan teks sumber, tautan halaman BPS, serta
unduh Excel bila tersedia. Tautan kosong tidak ditampilkan sebagai unduhan.


### Tabel dinamis nasional 2019–2026

Pengambilan nasional memakai `tools.bps.national`, dengan rencana tabel dan
catatan tinjauan pada `data/bps/national-2019-2026/plan.json`. Katalog penemuan
berisi 530 variabel dari 13 subjek BPS, bukan seluruh katalog seluruh domain.
Paket awal berisi 60 tabel terpilih untuk 10 tema; empat di antaranya adalah
tabel bulanan padi/jagung pengganti seri tahunan yang dihentikan.

```sh
.venv/bin/python -m tools.bps.national --plan data/bps/national-2019-2026/plan.json
.venv/bin/python -m tools.bps.national_report
```

Penyimpanan terpisah berisi respons API asli, checksum, katalog periode, serta
SQLite observasi dengan lima dimensi sumber. Angka nasional berasal dari
anggota Indonesia/Nasional atau tinjauan spesifik cakupan tabel sumber.
Tidak ada penjumlahan persentase/indeks provinsi. Tabel dengan kategori sektor
atau komoditas memerlukan tinjauan sumbu dan seluruh label kategori; perubahan
kategori yang belum ditinjau akan ditahan. Baris RATA-RATA tidak secara umum
dianggap Indonesia: tinjauan terikat pada tabel, kode, label, dan sumbu sumber.

Angka asli, nol, nilai kosong, unit tidak jelas, serta label periode yang belum
terpetakan dibedakan. Unit pada judul kategori hanya dibaca jika eksplisit dan
termasuk satuan yang dikenal. Tabel konsumsi perkotaan dan perdesaan menyimpan
cakupan penduduknya, tidak disamakan dengan gabungan seluruh penduduk.
Metode dan catatan sumber tetap tersimpan; seri lama/baru tidak disambung otomatis.
Status sementara hanya berasal dari catatan BPS yang sesuai tahun/bulan, bukan
karena tahun pengambilan sama dengan tahun observasi.

Laporan nasional mencocokkan setiap rekaman hasil penyaringan dengan respons
API yang diarsipkan; ini audit pemindahan, belum benchmark jawaban AI. Rekap
HTML menyediakan CSV gabungan dan per tabel. Halaman sumber publik dibentuk
dari ID resmi dan belum diverifikasi satu per satu; CSV adalah ekspor lokal,
bukan berkas unduhan resmi BPS. API key tidak ditulis ke tautan atau ekspor.
Paket ini belum mengganti pointer Qdrant atau provider General publik.


Hasil paket nasional 7 November 2026:

- 60 tabel diperiksa; 56 memuat angka nasional dalam periode sasaran.
- 41.189 rekaman numerik nasional, termasuk 1.873 rekaman tahun 2026.
- 36.520 rekaman memiliki unit dan periode terpetakan. Sisanya 4.669 dari
  tabel konsumsi 2090 ditahan karena unitnya hanya "Satuan Komoditas"; petunjuk
  sumber mengarah ke kuesioner Susenas yang belum dipetakan. Tidak mengarang
  satuan atau memakai rupiah untuk volume konsumsi.
- Tabel 44, 54, 55 tidak memiliki tahun sasaran pada katalog periode API.
  Tabel 2159 hanya memiliki provinsi; nilai IDI nasional baru diambil dari
  anggota Nasional* pada tabel 2161/2162, bukan agregat Provinsi**.
- 41.189 rekaman cocok dengan hasil pembacaan respons sumber tersimpan;
  tidak ada selisih audit. 25 pengujian parser/pemilahan nasional lulus.
- Data 2026 yang tersedia: kemiskinan Maret; ketenagakerjaan sampai Februari
  atau Agustus menurut seri; PDB sampai triwulan III; harga/NTP sampai Oktober;
  pertanian sampai September atau November menurut seri. September–November
  pada empat seri pertanian bulanan adalah angka potensi, bukan realisasi pasti.
- Label Tahunan pada sumber 2345 untuk 2026 tetap disimpan sebagai label asli.
  `period_ended_at_retrieval` membedakan periode yang belum berakhir pada waktu
  pengambilan; label tahunan tidak otomatis berarti realisasi 12 bulan.
- Konsumsi dinamis terpilih baru sampai 2021; tabel statis yang sudah diarsipkan
  sebelumnya memiliki seri konsumsi lebih baru. Pendidikan sampai 2025;
  kriminalitas sampai 2024; politik/demokrasi sampai 2024/2025 menurut seri.
  Ini keterbatasan paket/tabel yang diperiksa, bukan pernyataan bahwa seluruh
  BPS tidak memiliki rilis lebih baru.

Rekap dan CSV: `docs/test-evidence/20261107/bps-national-2019-2026/rekap.html`.
Rencana akuisisi/tinjauan sumber disalin ke `acquisition-plan.json` di folder
rekap agar aturan cakupan dan unit dapat diperiksa. Semua data nasional disimpan
terpisah dari koleksi aktif; **belum dimasukkan ke Qdrant atau jawaban publik**.

### Pembaruan: seluruh unduhan dimasukkan ke Qdrant, 7 November 2026

Status staging di atas digantikan oleh impor terverifikasi berikut. Jalankan
`python -m tools.bps.bundle --activate-trial` untuk mengulang verifikasi/impor
secara idempoten. Manifest aktif ada di `data/bps/qdrant-current-manifest.json`;
salinan lengkap ada di `data/bps/bundle/manifest.json`.

- Koleksi angka `cekdata_bps_all_7717193f89ad39`: 123.628 rekaman unik,
  gabungan 82.546 rekaman lama dan 41.189 nasional, dengan 107 rekaman sumber
  yang tumpang tindih digantikan versi nasional yang ditinjau.
- Sebanyak 118.945 rekaman boleh dipakai adapter; 4.683 ditahan. Rinciannya
  4.669 tanpa satuan komoditas yang jelas, 12 angka potensi, dan dua angka
  tahunan 2026 yang periodenya belum selesai. Hitungan alasan pada manifest
  bisa bertumpang tindih; jumlah rekaman ditahan tidak dihitung dari jumlah alasan.
- Koleksi dokumen `cekdata_bps_documents_2c65c0f2ac2b49`: 314 dokumen,
  terdiri dari 200 tabel statis dan 114 BRS, dalam 9.205 potongan metadata,
  teks, dan HTML asli. PDF tidak diunduh. Dokumen disimpan beserta tautan
  publik dan checksum; penyimpanan ini belum berarti semua sel tabel telah
  dinormalisasi menjadi observasi yang bisa dijawab mesin.
- Seluruh 132.833 payload dibaca kembali dan cocok dengan snapshot impor.
  Kategori sektor/komoditas dipertahankan dalam identitas indikator agar tidak
  tertukar dengan total nasional. Adapter menyaring `usable=true`.
- Impor awal sempat menyebabkan Qdrant kehabisan memori saat membangun
  indeks. Setelah pemulihan otomatis, impor dilanjutkan memakai indeks di
  disk, tanpa mengindeks HTML mentah sebagai teks. Verifikasi lengkap selesai;
  koleksi lama tetap tersedia dan pointer baru ditulis setelah verifikasi.

Koleksi baru aktif untuk adapter pengujian BPS lokal. **Provider General
publik tetap Pinecone**; tidak ada deployment atau pergantian provider publik.

Uji integrasi memakai model nyata dan 34 pertanyaan baru: **28 tepat
(82,35%)**, terdiri dari 27 jawaban angka dan satu keterbatasan yang tepat.
Dua soal gagal format keluaran model; empat soal memiliki angka dalam BRS
atau tabel statis tetapi jalur ekstraksi/jawabannya belum terhubung. Empat
kasus tersebut dihitung gagal, bukan keterbatasan yang benar. Pada 30 soal
jalur angka terstruktur, 28 ditangani tepat (93,33%). Ini sampel integrasi,
bukan pengganti benchmark keseluruhan mesin.

Audit 40 sel bukti tidak menemukan selisih nilai, satuan, periode, wilayah,
atau sumber terhadap data API yang diarsipkan. Uji pencarian dokumen terpisah
menemukan sumber yang diharapkan pada lima hasil teratas untuk 5/5 pertanyaan;
hasil ini hanya mengukur pencarian, bukan kemampuan menyusun jawaban.
Catatan penyajian yang masih ada: peringatan agregasi yang tidak relevan,
pembulatan Gini menjadi dua desimal, dan angka setara dari dua tabel yang
ditampilkan berulang. Angka benar tetap dihitung akurat sesuai kriteria pengguna.

Laporan, pertanyaan, jawaban asli, audit sel, dan manifest impor:
`docs/test-evidence/20261107/bps-all-qdrant-trial/rekap.html`.
