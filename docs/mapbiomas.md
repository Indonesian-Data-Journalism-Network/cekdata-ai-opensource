# MapBiomas Indonesia di Environment

Sumber resmi: <https://landy.mapbiomas.id/en/statistics>.
Lisensi: CC-BY-SA, <https://landy.mapbiomas.id/en/termsofuse>.

Integrasi memakai berkas statistik LANDY Koleksi 4.1. Akses Google Earth Engine
dan kredensial tambahan tidak diperlukan untuk berkas ini. Berkas, waktu unduh,
URL, dan SHA-256 disimpan di `data/mapbiomas/raw/`. Angka dibaca langsung dari
teks desimal OOXML, tanpa konversi ke float atau pembulatan nilai tersimpan.

## Cakupan yang benar-benar ada di berkas

- `COVERAGE`: 441 baris kelas/provinsi, 1990–2024, hektare.
- `TRANSITION`: 4.718 pasangan kelas/provinsi; 34 pasangan tahun berturut-turut
  dan 16 interval langsung pilihan, termasuk 1990–2024.
- 38 provinsi dan tujuh kelompok pulau. Tidak ada baris kabupaten/kota.
  Keterangan umum situs yang menyebut kabupaten tidak digunakan sebagai bukti
  bahwa berkas ini mempunyai cakupan tersebut.
- Tiga belas kelas daun: formasi hutan, mangrove, hutan rawa gambut, vegetasi
  alami nonhutan, sawah, sawit, kebun kayu, pertanian lainnya, lubang tambang,
  permukiman, nonvegetasi lainnya, tambak, serta sungai/danau/laut.
- Nasional dan pulau dijumlahkan dari provinsi yang saling terpisah, bukan
  dicampur dengan subtotal sumber. Total hutan menjumlahkan baris formasi
  hutan, mangrove dan hutan rawa gambut yang tercantum; kebun kayu terpisah.
- Tahun 2025–2026 tidak diisi, diproyeksikan atau dianggap nol.

Terdapat 322.225 observasi sumber dan turunan: 20.475 stok tahunan, 205.190
transisi tahunan, serta 96.560 transisi langsung. Ini bukan jumlah pengamatan
independen: agregat dan kelas induk berasal dari sel sumber yang sama.

## Makna angka

Stok tahunan boleh dibandingkan atau dirata-ratakan, tetapi tidak dijumlahkan
lintas tahun menjadi luas hutan/sawit unik. Transisi tahunan memakai tahun akhir
pasangan peta: 2024 berarti peta 2023 → 2024. Akumulasi transisi tahunan dapat
menghitung lokasi yang berubah kembali. Transisi langsung membandingkan kelas
pada dua peta ujung interval dan bukan jumlah seluruh perubahan di antaranya.
Mesin hanya menerima transisi langsung bila kedua tahun yang diminta cocok
dengan interval sumber. Satu tahun tidak boleh menggantikan interval panjang.

Setelah sesi API disambungkan kembali, pengujian model live melalui chat lokal
berhasil untuk lookup sawit tanpa menyebut penerbit, tren hutan lima tahun,
transisi hutan menjadi sawit antarperiode, penilaian klaim naik, serta penolakan
pengganti angka untuk tahun/wilayah yang belum tersedia. Hasil dan bukti layar
uji tersimpan di `tmp/mapbiomas-live/`. Pengujian ini melengkapi audit seluruh
angka dan pemeriksaan dengan intent terkontrol; bukan ukuran akurasi seluruh
jenis pertanyaan. Regresi live GFW kebakaran Aceh 2025 juga berhasil.
Pengulangan konteks transisi sudah dihapus. Batas tahun dan
wilayah dijelaskan dari katalog lokal, bahkan jika model tidak memilih indikator.

Sawit merupakan kelas tutupan yang dikenali dari citra, bukan izin konsesi atau
sensus petani. Hutan rawa gambut bukan seluruh bentang gambut. Lubang tambang
bukan batas konsesi. Definisi tutupan MapBiomas berbeda dari kehilangan tutupan
pohon GFW; angka tidak digabung menjadi satu seri. Cakupan 38 provinsi MapBiomas
juga tidak otomatis sebanding dengan GADM 4.1/34 provinsi sumber GFW, terutama
wilayah Papua. Nama sumber asli dan cakupan tetap tercatat.

## Penyimpanan, aktivasi dan verifikasi

`workflow/mapbiomas_data.py` membangun snapshot terpisah berdasarkan skema dan
checksum sumber. `source_locator` menunjuk sheet, baris fisik dan kolom asli
setiap angka; agregat mempertahankan seluruh sel penyusunnya.

```sh
.venv/bin/python workflow/mapbiomas_data.py --publish
```

Sebelum publikasi, `tools/verify_mapbiomas.py` memeriksa setiap nilai terhadap
sel aslinya, cakupan geografis, tanggal, identitas dan checksum. Sebanyak 44.100
kontrol marginal tabel transisi terhadap tabel stok mempunyai selisih maksimum
0,0000012492159 ha (toleransi 0,01 ha). Nilai kosong membatalkan agregat terkait;
baris kelas yang tidak ada tidak menghasilkan observasi nol buatan.

Publikasi menggunakan koleksi Qdrant terpisah dengan payload numerik, tanpa
embedding baru yang tidak diperlukan untuk pencarian terstruktur. Seluruh
payload Qdrant dibandingkan dengan snapshot sebelum `active.json` diganti
secara atomik. Aktivasi tidak menghapus koleksi GFW/NGO. Untuk menonaktifkan,
pindahkan `data/mapbiomas/active.json` ke arsip, atau pulihkan pointer sebelumnya.

`environment_data.py` menambahkan katalog dan retriever pada pembuatan workflow
Environment setiap permintaan. Kunci API dalam RAM tidak perlu dipindah atau
server dimulai ulang. General tidak berubah. UI menampilkan sumber dan satu
tautan unduhan XLSX untuk berkas/versi yang sama, tanpa mengulang setiap tahun.

## Pertanyaan pemeriksaan

- Berapa luas sawit di Riau pada 2024?
- Bagaimana tren luas hutan di Aceh selama 2020–2024 menurut MapBiomas?
- Bandingkan luas mangrove di Aceh dan Sumatera Utara pada 2024.
- Berapa luas hutan yang berubah menjadi sawit di Riau antara 1990 dan 2024 menurut MapBiomas?
- Berapa luas sawit di Aceh pada 2026? (harus menyatakan periode belum tersedia)
- Berapa luas sawit di Kabupaten Bombana pada 2024 menurut MapBiomas?
  (harus mempertahankan ketidaktersediaan kabupaten, bukan menggantinya provinsi)

Tabel transisi Koleksi 3.0 pernah diunduh saat eksplorasi dan tetap sebagai
arsip; tidak masuk indeks aktif, karena berkas 4.1 sudah mencakup transisi.

Untuk pertanyaan lintas sumber, pencocokan katalog dilakukan terpisah menurut
penerbit, dengan ruang kandidat untuk setiap sumber sebelum pemotongan hasil.
Pilihan transisi mempertahankan arah kelas asal–tujuan; kelas komponen tidak
ditambahkan jika jalur agregat diminta secara eksplisit. Permintaan “selama”
atau angka masing-masing tahun menggunakan transisi tahunan. Daftar tahun
eksplisit dipertahankan, termasuk jika tidak berurutan.

Klaim yang menghubungkan seluruh kehilangan GFW dengan transisi MapBiomas
tidak diputuskan hanya dengan membandingkan total wilayah. Alasan penilaian
dan catatan editorial sama-sama mensyaratkan kecocokan lokasi, periode dan
definisi; angka agregat berbeda metode tidak membuktikan hubungan spasial.
