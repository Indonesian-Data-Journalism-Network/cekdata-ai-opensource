# General: pencarian langsung ke Pinecone

Pembaruan 8 November 2026: runner General kini mencari Pinecone **bersama BPS
Qdrant lokal terverifikasi** melalui `workflow/general_data.py`, memakai satu
intent dan satu pemilihan indikator. Lihat `docs/bps-local.md` untuk cakupan dan
batas aktivasi. Fungsi `pinecone_data.run` tetap tersedia untuk uji Pinecone saja.

General dapat membaca Pinecone melalui backend komputer. Browser dan Netlify
tidak menerima API key Pinecone. Environment tetap memakai jalur Qdrant/GFW,
MapBiomas, dan laporan NGO yang sudah ada. Tidak ada ekspor jutaan record,
penulisan ulang index, atau penggabungan otomatis General dengan Environment.

## Koneksi

Form lokal `tools/pinecone/connect_server.py` berjalan di `127.0.0.1:8782`.
Form memeriksa index dan namespace serta mengambil maksimal 20 contoh metadata.
Koneksi disimpan di `.local/pinecone-connection.json` dengan izin 0600 dan awalnya
`enabled=false`. File ini tidak masuk Git. Namespace dipertahankan persis,
termasuk bila bernama `__default__`.

Sebelum mengaktifkan, operator harus memeriksa metadata dan model embedding
index, mengisi `embedding_model`, lalu menguji pencarian dan angka jawabannya.
Set `enabled=true` hanya setelah validasi; `false` menahan permintaan General,
bukan diam-diam mengalihkannya ke data pilot. Hapus konfigurasi hanya bila memang
ingin memakai BPS lokal saja (atau pilot lama bila snapshot BPS belum tersedia).
Restart backend publik setelah perubahan kode.

Konfigurasi uji 7 November 2026 menggunakan `text-embedding-3-small`, dimensi
1536. Ini mengikuti model default retriever lama dan berhasil dalam uji pencarian
langsung; bukan audit bahwa setiap vektor dalam index dibuat dengan model yang
sama. Dimensi diperiksa setiap permintaan. Penggantian model memerlukan validasi
ulang, walaupun dimensinya sama.

## Jalur jawaban

1. Baca maksud pertanyaan untuk menemukan wilayah, tanpa memberi angka jawaban.
2. Buat embedding pertanyaan, lalu cari kandidat tabel per wilayah, maksimum
   200 kandidat bermetadata satuan dan jendela tambahan maksimal 200 kandidat
   tanpa satuan, masing-masing untuk enam wilayah. Permintaan bulan tertentu
   juga membatasi penemuan kandidat, sehingga tabel tahunan tidak menggantikan
   tabel bulanan hanya karena judulnya mirip.
3. Petakan metadata numerik menjadi kontrak Evidence yang sudah dipakai mesin.
4. Pilih indikator dari katalog kandidat; cari lagi dengan filter identitas
   tabel, seri, kategori, wilayah, tahun, dan bulan.
5. Periksa ulang setiap hasil setelah pencarian. Maksimum 500 hasil per seri;
   jendela penuh ditandai terbatas, bukan dianggap seluruh seri sudah ditemukan.
6. Jalankan perhitungan, penilaian klaim, tabel jawaban, dan sumber melalui mesin
   yang sama. Angka dibaca sebagai desimal, bukan dari elemen vektor embedding.

Pencarian semantik merupakan penemuan kandidat, bukan bukti bahwa seluruh
indikator di index telah ditelusuri. Tidak ditemukannya bukti tidak membuktikan
ketiadaan data di BPS. Gangguan API diteruskan sebagai gangguan layanan, bukan
diubah menjadi jawaban “data tidak ada”.

## Data yang diterima dan ditahan

Diterima: record `atomic` dengan `record_type=statistics_table_cell`, atau
metadata atomic lama tanpa record_type, selama memiliki wilayah, tahun, angka
teramati, satuan, judul, identitas dataset/seri, penerbit, dan tautan HTTPS sumber.
Kategori tambahan dan perkotaan/perdesaan/total tidak boleh bercampur.
Kabupaten dan kota diberi identitas berbeda bila levelnya tersedia di metadata.

Ditahan: contoh/simulasi, nilai hilang atau tidak valid, satuan yang tidak dapat
dipastikan atau sumber kosong,
tautan berkas lokal, periode yang belum didukung, dan `publication_table_cell`.
Sel PDF memerlukan adapter tersendiri: contoh nyata memiliki judul terpotong
yang menghilangkan cakupan perkotaan/perdesaan dan banyak unit kosong. Jangan
memulihkan cakupan dari angka yang kebetulan sama dengan tabel lain.

Tautan sumber berasal dari metadata. Pemeriksaan format URL tidak membuktikan
halaman masih bisa diakses atau setiap baris telah diverifikasi terhadap situs
asal. Beberapa `download_url` adalah halaman tabel BPS, bukan berkas langsung.
Pada General, tautan unduh mengikuti metadata tersebut; jangan menyebutnya
sebagai unduhan CSV langsung bila alamatnya masih halaman tabel.

## Cara baca satuan tambahan

`workflow/unit_reading.py` mempertahankan `unit` yang sudah terisi, termasuk
ejaan dan nilai asli. Jika kosong, adapter boleh membaca label satuan eksplisit
pada record yang sama: tanda kurung/kurung siku dalam judul tabel atau seri,
`unit_label`, atau keterangan `Satuan: ...`. Nama indikator, kemiripan tabel,
angka, dan pertanyaan pengguna tidak dijadikan tebakan satuan. Label yang
bertentangan ditahan sebagai `conflicting_unit_labels`; label yang tidak tersedia
atau belum dikenali ditahan sebagai `missing_unit`.

Pencarian tambahan dipisahkan agar record tanpa satuan tidak menggeser jendela
kandidat lama. Filter seri, wilayah, periode, sumber, dan pemeriksaan identitas
setelah pencarian tetap berlaku. Adapter tidak menulis kembali ke Pinecone.

Nilai `12.22` dengan label `(Ribu Jiwa)` menjadi evidence `12.22 ribu jiwa`;
angka mentah tetap sama. `source_locator.unit_reading` mencatat kolom dan label
asal, satuan dasar `jiwa`, serta skala `1000`. Metadata lengkap tidak ditambahi
provenance fallback. Perbandingan klaim dapat menyamakan satuan berskala yang
dikenali secara eksak dengan Decimal. Persen dan poin persentase tetap berbeda;
orang/jiwa tidak dipertukarkan dengan rumah tangga. Tidak ada aturan khusus
untuk ID tabel, wilayah, atau jawaban benchmark.

### Validasi tambahan pembacaan satuan — 7 November 2026

Hasil final di `docs/test-evidence/20261107/general-bps-unit-fallback-v3/`:

- Audit metadata seluruh 115 kasus jumlah penduduk miskin kabupaten/kota:
  197 record sumber, seluruh nilai acuan dapat dipetakan melalui label satuan
  eksplisit; data asli Pinecone tidak ditulis ulang.
- Uji ulang 115 pertanyaan yang sama: 112 akurat (97,39%), tiga bermasalah karena
  lingkup wilayah (Mamuju Tengah, Konawe Kepulauan, Buton Selatan).
- Sepuluh kontrol bermetadata lengkap: 10/10 akurat. Pemeriksaan 601 record
  bermetadata lengkap dari benchmark lama mempertahankan angka, satuan,
  identitas indikator dan sumber; delapan ejaan wilayah berbeda kapitalisasi
  karena penyesuaian label pertanyaan di tahap pencarian.
- 85 perhitungan diperiksa tanpa kesalahan aritmetika; 129 tes offline lulus.
- Dua kontrol konversi langsung dan melalui HTTP lokal: 12.220 jiwa sesuai
  dengan 12,22 ribu jiwa (Benar); 12,22 jiwa tidak setara (Salah). Pemahaman
  klaim mempertahankan angka beserta satuan literal, termasuk jika model
  sebelumnya mengeluarkan dimensi generik `count`.
- Kode/model tetap selama putaran final; tidak ada pengulangan selektif.
  Versi v1 menyimpan uji awal sebelum pengaman satuan klaim lengkap; v2 dihentikan
  untuk melengkapi pengaman tersebut. Keduanya bukan hasil final.

Ini pengujian ulang terarah, bukan pembaruan akurasi seluruh benchmark 500.
Backend publik dimuat ulang, dan backend lokal dimuat ulang karena proses lama
masih menjalankan jalur sebelumnya. Sesi lokal di RAM berakhir saat restart;
akun dan sesi publik tetap tersimpan.

## Klaim arah perubahan dan besaran perubahan

Penilaian klaim sederhana naik/turun pada seri persentase dapat membandingkan
tanda selisih poin persentase dengan nol meskipun predicate model menyebut
`persen`. Pengecualian sempit ini hanya berlaku untuk operator arah (`gt/lt`),
ambang nol, dan pertanyaan tanpa angka perubahan, besaran tertulis, atau klaim
gabungan. Tahun pengamatan tidak dianggap sebagai besaran perubahan. Pemeriksaan
kelengkapan bukti, kesebandingan indikator/metode, dan sebab-akibat tetap berjalan
sebelum penilaian. Predicate awal tetap tersimpan; penyesuaian memakai salinan.

Klaim eksplisit seperti `turun 0,36 poin persentase` memakai perubahan bertanda
negatif dan operator sama dengan. `Turun 0,36 persen` memakai perubahan relatif,
bukan selisih poin persentase. Pengaman literal mengikat angka, satuan, tanda,
dan operator pada kata pengguna, sehingga model tidak mengubahnya menjadi
`kurang dari -0,36` atau `+0,36`. Klaim bersyarat/berkualifikasi tetap melalui
interpretasi biasa; pemeriksaan satuan tidak dimatikan secara umum.

### Uji prioritas 1 dan 2 — 7 November 2026

Artefak final: `docs/test-evidence/20261107/general-bps-priority12-v2/`.
Seluruh 85 pertanyaan dijalankan ulang pada kode yang tetap selama putaran:
8/8 klaim arah perubahan akurat, 22/67 kasus pencarian akurat (satu parsial),
dan 10/10 kontrol akurat. Ada 45 kasus pencarian yang masih bermasalah:
33 tanpa satuan/label eksplisit yang dapat dibaca, 8 tertolak kontrak dimensi
indeks versus satuan persen, 3 belum ditemukan dalam query identitas yang
diperiksa, dan 1 masih gagal memilih/memperoleh bukti Kabupaten Gorontalo.
Tidak ditemukannya kandidat pada query tersebut bukan bukti ketiadaan data
di seluruh Pinecone atau BPS.

Pemeriksaan metadata read-only: 88 query untuk 67 kasus, nilai acuan lengkap
ditemukan pada 63 kasus. Kasus 47 ditinjau manual: angka, satuan, wilayah,
tahun, tabel dan kategori sawit tepat; penanda otomatis berasal dari perbedaan
penyimpanan kategori komoditas di `population` versus `category_label`.
Keputusan dan flag otomatis asli disimpan terpisah. Acuan pertanyaan tidak diubah.

105 tes offline lulus; 27 perhitungan hasil uji tanpa selisih aritmetika.
Lima pemeriksaan HTTP setelah layanan dimuat ulang berhasil: satu kontrol GFW,
dua klaim arah, klaim turun 0,36 poin persentase (Benar), serta turun 0,36 persen
(Salah) pada pasangan pengamatan yang sama. Versi v1 menyimpan uji sebelum
pengaman tanda/operator besaran eksplisit; v2 adalah hasil final.

Rekap gabungan benchmark 500, pengujian unit fallback, dan putaran ini:
422 akurat (84,4%), 78 bermasalah (15,6%). Ini bukan uji ulang seluruh 500
pertanyaan pada satu versi. Backend publik/lokal telah dimuat ulang; sesi
lokal di RAM berakhir, akun/sesi publik tetap tersimpan.

## Validasi integrasi 7 November 2026

Namespace yang dipilih melaporkan **8.611.485 record**. Ini jumlah record,
bukan jumlah indikator maupun jumlah record yang sudah lolos pemeriksaan.

Delapan pertanyaan berbeda dijalankan langsung melalui OpenAI dan Pinecone:

| Uji | Hasil setelah perbaikan |
| --- | --- |
| Kemiskinan Timor Tengah Selatan 2025 | 24,50 persen |
| Kemiskinan Jawa Barat Maret 2025 | 7,02 persen |
| Tren kemiskinan Timor Tengah Selatan 2023–2025 | 25,18; 24,68; 24,50 persen, menurun |
| Timor Tengah Selatan vs Melawi 2025 | 24,50 vs 10,51 persen |
| Klaim Timor Tengah Selatan 24,5 persen | Benar |
| Klaim Timor Tengah Selatan 100 persen | Salah setelah perbaikan alias percent/persen |
| Pengangguran Bali Agustus 2025 | 1,49 persen |
| IPM Aceh 2025 | Ditahan: hasil relevan berbentuk sel PDF, tanpa unit lengkap |

Angka dibandingkan dengan metadata hasil Pinecone. Ini uji integrasi terbatas,
bukan benchmark akurasi keseluruhan atau audit sumber BPS secara independen.
Paket lokal uji tersimpan di `tmp/pinecone-validation/` (tidak masuk Git).

130 pemeriksaan otomatis lulus: 13 client/adapter Pinecone, 14 alat koneksi dan
ekspor, 17 adapter web, 35 workflow utama, serta 51 regresi pemilihan data,
integritas bukti, penilaian, format, perubahan tahunan, dan GFW.

Uji website pertama menemukan pemilihan tabel tahunan untuk permintaan Maret.
Filter bulan kemudian diterapkan sejak penemuan kandidat, bukan hanya pada
pencarian angka setelah indikator dipilih. Kasus ini masuk uji regresi.
Uji ulang melalui `https://cekdata-ai-pilot.netlify.app/`, topik General,
berhasil menampilkan tabel Jawa Barat, Maret 2025, 7,02 persen, dan tautan BPS.
Bukti layar lokal: `tmp/pinecone-validation/online-general.png`.

Masalah metadata yang perlu dikerjakan terpisah: memulihkan header, satuan,
periode, dan cakupan sel publikasi PDF dari sumber aslinya; mengaudit tautan
sumber/download; dan menguji lebih banyak indikator serta variasi wilayah.
Penyajian nama tabel masih dapat mengulang judul/seri/kategori; ini belum
dirapikan dalam perubahan koneksi ini.

## Uji General: 100 pertanyaan sederhana, 7 November 2026

Jalur yang diuji adalah `web.server.run_workflow` dengan konfigurasi Pinecone
aktif dan model nyata `gpt-4.1-mini-2025-04-14`. Ini pengujian backend General,
bukan browser/HTTP. Pencarian gabungan Qdrant belum diterapkan. Kode dibekukan
sepanjang pengujian dan tidak ada pengulangan selektif.

Paket berisi 50 permintaan angka, 15 tren, 10 perbandingan tahun, 10 perbandingan
wilayah, dan 15 klaim naik/turun; mencakup 38 provinsi, 15 kabupaten/kota, serta
nasional. Angka acuan ditetapkan dari arsip API BPS sebelum uji dan tidak
diberikan kepada model. Bukti tidak ditemukan tidak dianggap otomatis akurat,
karena seluruh soal memiliki angka acuan yang tersedia.

Hasil: **81 akurat (81%), 19 bermasalah (19%), tanpa gangguan eksekusi**.
Sebanyak 79 hasil akurat menjawab lingkup angka yang diminta; dua lainnya hanya
menjawab satu wilayah tanpa menarik kesimpulan perbandingan yang tidak didukung.
Keduanya tetap akurat sesuai kriteria pengguna bahwa data benar yang kurang
lengkap dapat diterima. Kriteria harus lengkap menghasilkan 79/100.

Masalah utama, satu kategori per soal: delapan pencarian wilayah tanpa kandidat,
enam indikator/bukti tidak berhasil diperoleh, empat label klaim keliru akibat
pemeriksaan persen versus poin persentase, dan satu indikator kelompok usia
tertukar (rata-rata lama sekolah). Penyebab rinci enam kegagalan pemilihan/filter
belum diaudit seluruhnya; jangan menganggap seluruhnya berarti data tidak ada
di index. Dua jawaban parsial juga memiliki persoalan pencarian wilayah.

Seluruh 219 sel bukti dan konteks diperiksa kembali melalui fetch 197 rekaman
Pinecone unik: tidak ada selisih nilai, unit, tahun/bulan, sumber, identitas
indikator, atau kategori terhadap metadata sumber. Ini audit pemindahan bukti;
kesesuaian pertanyaan dinilai terpisah terhadap acuan BPS. Angka yang tersalin
benar tetap bisa berasal dari indikator yang salah atau mendapat label klaim
yang keliru.

Laporan lengkap, jawaban asli, acuan sebelum uji, penilaian manual untuk seri
setara, dan jejak audit tersimpan pada
`docs/test-evidence/20261107/general-bps-100-v1/rekap.html`.
Hasil ini tidak dibandingkan langsung dengan paket delapan soal Pinecone lama
atau 34 soal BPS lokal karena distribusi pertanyaannya berbeda.

## Perluasan menjadi 500 pertanyaan, 7 November 2026

100 soal dan jawaban awal dipertahankan; 400 soal baru ditambahkan dengan kode
dan model yang sama. Sampel berstrata mencakup 38 provinsi, 208 kabupaten/kota,
dan 23 tabel indikator. Acuan ditetapkan sebelum uji. Tidak ada pengulangan
selektif, pergantian provider, perbaikan mesin, atau pengujian browser/HTTP.

Hasil keseluruhan: **280/500 akurat (56%), 220/500 bermasalah (44%)**, tanpa
gangguan eksekusi. Dari 280 hasil akurat, 275 memenuhi cakupan angka dan lima
parsial dengan angka benar. 400 soal tambahan menghasilkan 199/400 akurat
(49,75%). Persentase berubah karena komposisi soal diperluas; kode tidak berubah.

Rincian: permintaan angka 112/200; tren 56/90; perbandingan tahun 35/70;
perbandingan wilayah 32/50; klaim naik/turun 33/65; klaim angka 12/25.
220 kasus bermasalah terdiri dari 203 tanpa bukti langsung yang diminta
(182 pemilihan/pencarian indikator dan 21 pencarian wilayah tanpa kandidat),
delapan indikator/kategori tertukar, serta sembilan penilaian klaim keliru.
Delapan dari sembilan masalah penilaian terkait persen versus poin persentase.

Pemeriksaan diagnostik terpisah terhadap soal 101, 102, 181, 209, 40, dan 41
menemukan rekaman indikator/wilayah/periode terkait di Pinecone, tetapi field
`unit` tidak ada sehingga adapter menolak `missing_metadata`. Contoh mencakup
jumlah penduduk miskin Aceh Jaya 2023 dan IPM nasional 2024. Jangan menyamakan
hasil ini dengan audit bahwa seluruh 203 kegagalan memiliki penyebab identik.
Pada soal 213 dan 218, P1/P2 memiliki unit `Persen`, sedangkan intent meminta
dimensi `index`; reproduksi offline `compatible_candidates` menolak kandidat
karena dimensi unit `percentage`. Bukti diagnostik tersimpan bersama laporan.

690 sel bukti/konteks dari 601 rekaman Pinecone unik dibaca ulang: tidak ada
selisih terhadap metadata sumber. Audit 238 perhitungan juga tidak menemukan
kesalahan aritmetika. Kesesuaian indikator dan penilaian klaim tetap diperiksa
terpisah; data yang tersalin benar dapat menjawab indikator yang salah.

Laporan lengkap, 500 soal, jawaban, acuan, penilaian, dan audit:
`docs/test-evidence/20261107/general-bps-500-v1/rekap.html`.
Hasil perluasan ini belum mencapai sasaran 80%; angka 81% dari 100 soal awal
tetap merupakan hasil paket awal, bukan gambaran seluruh cakupan yang baru diuji.

## Pembacaan indeks dalam satuan persen, 7 November 2026

Kontrak permintaan sekarang mengenali indeks yang ditulis sumber dalam satuan
persen, jika nama indeks lengkap pada ukuran data cocok dengan konsep yang
diminta. Ini tambahan pembacaan, bukan perubahan unit, nilai, skala, atau metadata
Pinecone. Pengecualian tidak berlaku hanya karena topik sama, tidak menggunakan
ID tabel/lokasi/jawaban tertentu, dan tetap menjalankan pengecualian indikator.
Nama kolom ukuran digunakan sebelum judul tabel induk yang lebih luas.

Delapan kegagalan kontrak indeks diuji ulang dengan pertanyaan dan acuan lama:
**8/8 akurat**, terdiri dari lima permintaan angka, satu tren, dan dua perbandingan
tahun. Sepuluh kontrol juga **10/10 akurat**. Sebanyak 108 pengujian kode lolos,
12 rekaman lama diterima dengan kontrak permintaan lama, serta empat perhitungan
tidak menunjukkan selisih aritmetika. Tidak ada pengulangan selektif atau
pengiriman acuan ke model. Bukti dan laporan lengkap tersedia pada
`docs/test-evidence/20261107/general-bps-index-contract-v1/rekap.html`.

Rekap gabungan berubah dari 422/500 menjadi **430/500 akurat (86%)**, dengan
70/500 belum berhasil (14%). Ini gabungan benchmark awal, uji tambahan pembacaan
satuan, perbaikan klaim arah perubahan, dan uji indeks; bukan pengujian ulang
seluruh 500 soal pada satu versi. Sebanyak 33 kasus yang belum memiliki metadata
satuan memadai tetap dicatat belum berhasil, bukan dinyatakan data BPS tidak ada
atau otomatis dinilai akurat.
