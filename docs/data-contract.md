# Kontrak data pilot

Qdrant menyimpan payload bukti dengan `id`, `indicator_id`, `indicator`, `area`, `year`, `value` (teks desimal), `unit`, `source`, serta konteks opsional: `month`, `population`, `definition`, `method`, `title`, `source_url`, dan `download_url`.

Satu record harus mewakili satu observasi. Nilai nol bukan nilai hilang. Teks desimal disimpan agar tidak membulat melalui float. Kategori/populasi dipisahkan dan nilai dari seri yang tidak sebanding tidak boleh dihitung bersama.

Importer Pinecone membaca `metadata.value`, `year`, `area_name`, `unit`, `title`, `source`, `dataset_id`, `series_label`, dan kategori tambahan. `period` berisi nama bulan atau penjelasan periode. URL singular `source_url`/`download_url` dipertahankan. Metadata asli disimpan di `original_metadata`. Record yang tidak dapat dipetakan ditandai `usable=false`; tidak dibuatkan angka pengganti.

File ekspor memerlukan manifest dengan dimensi dan checksum SHA-256 `records.jsonl`; eksportir yang disertakan menghasilkan format ini. Jalur impor pilot tidak menggunakan vektor ekspor untuk pencarian semantik. [Adapter Pinecone langsung](pinecone-live.md) memiliki konfigurasi model, validasi dimensi, dan batas skema tersendiri.

## Syarat tautan sumber untuk impor data nyata berikutnya

Keputusan pengguna, 5 November 2026: setiap data yang diambil harus memiliki
tautan langsung ke sumber. Berlaku untuk rencana impor GFW dan sumber nyata
lainnya berikutnya; data simulasi tetap diberi label simulasi.

- `source_url` wajib mengarah ke halaman dataset, tabel, publikasi, atau metadata
  resmi yang mendukung angka tersebut; halaman utama lembaga saja tidak cukup.
- Simpan `download_url` menuju berkas atau endpoint API pengambilan jika tersedia.
  Untuk API, simpan juga versi dataset, parameter/filter atau isi permintaan,
  tanggal pengambilan, serta identitas baris agar angka bisa ditelusuri ulang.
- Verifikasi bahwa tautan sesuai dengan dataset dan cakupan angka. Jangan
  mengarang tautan atau menyisipkan API key/token ke URL yang disimpan/ditampilkan.
  Jika akses sumber memerlukan autentikasi, nyatakan kebutuhan itu dengan jelas.
- Data tanpa tautan sumber yang dapat diverifikasi ditahan dari penggunaan
  sebagai bukti jawaban sampai sumbernya lengkap.
- Jawaban harus menyertakan tautan sumber untuk angka yang dipakai. Hasil
  perhitungan lintas sumber harus mengacu pada semua data masukan yang digunakan.

Status: ketentuan ini menjadi syarat implementasi importer berikutnya. Importer
pilot yang ada belum menegakkan kewajiban tautan ini secara otomatis.

## Tambahan GFW Indonesia, 5 November 2026

`workflow/gfw_expansion.py` mengarsipkan statistik nasional, provinsi, dan kabupaten
dari `carbonflux_*` v20260327 dan `gadm__tcl__*_summary` v20260424. Filter tajuk
dipilih tepat sekali; luas habitat memakai `area__ha` dari seluruh partisi lahan,
termasuk sel di luar model karbon. Jumlah wilayah direkonsiliasi antar tingkat,
emisi tahunan terhadap total periode, dan neraca terhadap emisi dikurangi penyerapan.

- `temporal_basis=annual`: emisi 2001–2025; tahun kosong tidak diisi nol.
- `temporal_basis=model_period`: total dan rata-rata 2001–2025, dengan
  `period_start`/`period_end` dan `aggregation_kind=period_total|period_mean`.
  Rata-rata berasal dari total dibagi 25, bukan nilai tahun 2025.
- `temporal_basis=baseline`: mangrove GMW v3 acuan 2020; kategori SDPT acuan
  global 2020 dengan tahun sumber lokal beragam. Kelas campuran dipisahkan.
- `temporal_basis=map_version`: gambut gabungan sumber berbagai tahun, versi
  v20230315. Tahun indeks 2023 adalah tahun versi, bukan pengamatan.

Arsip, SQL, checksum, sumber peta, catatan yang ditahan, dan hasil rekonsiliasi ada
di `data/gfw-expansion/`. Snapshot sebelum tambahan disalin ke
`data/gfw-expansion/base-backup/`. Publikasi menambah ID baru; katalog diperbarui
setelah payload Qdrant diverifikasi. Tidak ada angka observasi 2026, data konsesi
Indonesia yang dibatasi, atau indikator peringatan dini yang diimpor.

Delapan observasi penyerapan/neraca (total dan rata-rata) di Kabupaten Intan Jaya
dan Paniai ditandai `usable=false` karena nilai penyerapan sumber negatif.
Nilai asli tetap tersimpan. Geometri Water Body juga tidak masuk pencarian.
Total resmi nasional dan Papua tetap dipertahankan dengan catatan sumber tentang
anomali komponennya. CSV mencantumkan periode serta nilai asli, termasuk neraca negatif.

## Canonical di MySQL

Jika Pinecone hanya berisi metadata string dan `mysql_reference`, nilainya memang bisa berada di MySQL. Prototipe ini belum melakukan pengambilan canonical tersebut. Jangan menganggap angka tidak ada dalam sumber hanya karena tidak berada dalam metadata pencarian. Jangan mengubah vektor `values` menjadi nilai statistik. Dukungan MySQL perlu pengambilan record lengkap berdasarkan ID dan pemeriksaan versi sebelum dipakai sebagai bukti.


## BPS: format observasi standar, 7 November 2026

Snapshot BPS menggunakan `cekdata-statistical-observation-v2`. Kolom inti
mengikuti bukti terstruktur GFW: `indicator_id`, `indicator`, `area`, `area_key`,
`year`, `month`, `value`, `unit`, `source`, `source_url`, `source_record_id`,
`population`, `definition`, `method`, `period_start`, dan `period_end`.
Perbedaan metodologi/identitas sumber tetap dipertahankan; format sama bukan
berarti observasi antarpenyedia otomatis sebanding.

- Satu rekaman = satu indikator × kategori × wilayah × periode.
- `temporal_basis=month`: `month` terisi, `quarter=null`.
- `temporal_basis=quarter`: `quarter` 1–4, **`month=null`**. Triwulan II
  mempunyai batas April–Juni; tidak disimpan sebagai angka April atau Juni.
- `temporal_basis=annual`: kedua kolom tersebut null, batas Januari–Desember.
- Batas tanggal menyatakan cakupan kalender periode, bukan tanggal survei
  atau bukti bahwa angka adalah penjumlahan sepanjang periode. `aggregation_kind`
  dibiarkan kosong jika jenis agregasinya tidak dijelaskan sumber.
- `Semester 1 (Maret)` tetap menyimpan label asli di `period_label_raw` dan
  dibaca sebagai observasi Maret. Label semester tanpa bulan eksplisit ditahan.
- `unit` memakai bentuk konsisten: persen, ribu jiwa, miliar rupiah.
  `unit_code`, `unit_scale`, `unit_source`, `unit_raw`, `unit_origin` menyimpan
  identitas, skala, label sumber, serta asal satuan. **Nilai tidak dikalikan,
  dibagi, atau dibulatkan ketika format diseragamkan.**
- `area_code_system=BPS` membedakan kode BPS dari GADM. `geographic_level`
  memakai adm0/adm1/adm2; `boundary_type` membedakan kabupaten dan kota sesuai
  label sumbu sumber. Induk provinsi kabupaten diturunkan dari awalan kode BPS
  dan dicocokkan dengan daftar provinsi pada tabel sumber, bukan kode GADM.
- `category_id/category_label` mempertahankan kategori sumber. Perkotaan dan
  perdesaan juga ditandai `population=urban/rural`; total dan sektor ekonomi
  tetap dibedakan melalui kategori dan indikatornya masing-masing.
- `original_row` adalah salinan persis rekaman SQLite yang telah dicocokkan
  dengan respons mentah. `source_locator` mempertahankan semua ID dimensi BPS.
- Catatan sementara ditetapkan hanya bila catatan sumber menyebut tahun
  observasi terkait. Jika tidak disebutkan, statusnya
  `published_status_unspecified`, bukan otomatis final.

Migrasi membuat koleksi baru; ID rekaman dan indikator tetap stabil. Koleksi
lama dipertahankan. Manifest aktif diperbarui setelah seluruh payload baru
lulus pemeriksaan; katalog versi terkait ditunjuk oleh `catalog_file`.
Keberhasilan migrasi tidak dengan sendirinya berarti benchmark jawaban lulus.
Pengolahan intent dan uji jawaban dicatat terpisah di bawah.


## Kontrak periode permintaan dan perhitungan

`Intent.requested_periods` membawa daftar identitas periode lengkap:
`year` disertai `month` atau `quarter` (tidak boleh keduanya). Pencarian
meneruskan daftar yang sama sebagai `SearchQuery.periods`, termasuk saat
mencari alternatif. Perbandingan Februari–Agustus tidak boleh difilter hanya
ke bulan Agustus. Label bulan/triwulan eksplisit diperiksa dari pertanyaan
asli dengan aturan bahasa umum, tanpa daftar khusus indikator atau lokasi.

Penilaian mencocokkan frekuensi, tahun, dan bulan/triwulan secara bersamaan.
Periode triwulan dan bulan akhir triwulan tidak saling menggantikan. Deret
kontinu menyertakan periode di antaranya; bukti yang hilang dilaporkan, bukan
diganti nol. Perhitungan menolak pasangan dengan ID atau identitas periode
sama. Jalur tahunan tanpa periode sub-tahunan tetap memakai aturan tahunan
sebelumnya.

Satuan selisih persentase ditentukan setelah normalisasi satuan, sehingga
`Persen`, `persen`, dan `%` menghasilkan selisih dalam poin persentase.
Persentase perubahan relatif tetap dihitung terhadap nilai awal dan tidak
terdefinisi ketika nilai awal nol. Catatan status sementara tahun observasi
ditampilkan pada konteks bila tersedia dalam bukti.
