REFERENSI WILAYAH CEK DATA AI

geography.json: referensi yang digunakan aplikasi.
geography.tsv: tabel yang dapat ditinjau di editor atau aplikasi tabel.
Pembentuk tabel: workflow/build_geography.py. Jalankan dengan PYTHONPATH=workflow dan Python lingkungan proyek, memakai arsip sumber lokal yang hash-nya tercantum pada JSON.

Cakupan awal
- Nasional: Indonesia.
- Provinsi: 38 nama yang dikenali katalog lokal.
- Kabupaten/kota: 498 geometri administratif dalam direktori GADM 4.1 lokal (400 kabupaten, 98 kota). Bukan daftar administratif terkini yang lengkap. Empat Water Body dikeluarkan. Koleksi angka GFW lokal memiliki 497 wilayah kabupaten/kota; keberadaan nama dalam referensi tidak berarti semua indikator/tahun tersedia.
- Tujuh kelompok pulau: anggota diambil dari workbook MapBiomas lokal; misalnya Sumatera dan Wilayah Papua (6 provinsi). Ini agregat provinsi, bukan batas fisik sebuah pulau.
- Enam belas nama pulau fisik untuk pengenalan cakupan awal. Belum merupakan gazeter seluruh pulau Indonesia. Tidak otomatis diberi angka provinsi atau diagregasi tanpa batas yang sesuai.

Identitas dan batas
ID GADM, nama asli filter, provider, dan versi batas tetap disimpan. Relasi kabupaten ke provinsi GFW mengikuti GADM 4.1, khususnya Papua sebelum pemekaran. Relasi ini tidak diklaim sebagai hubungan induk administratif terbaru. Papua Selatan, Papua Tengah, Papua Pegunungan, dan Papua Barat Daya dikenali sebagai provinsi tersendiri, tanpa substitusi angka provinsi induk GFW.
Tidak ada penyuntingan nilai observasi atau pembangunan ulang koleksi Qdrant.

Alias
Alias memuat ejaan sumber, nama umum, singkatan provinsi, serta ekspansi terkurasi Tanjung Jabung T/B menjadi Timur/Barat dan Tanjabtim/Tanjabbar. Resolver menghasilkan bentuk Kab./Kabupaten, Prov./Provinsi, alamat dengan nama induk/singkatan, serta Sumatra/Sumatera. Singkatan ini merupakan alias pencarian, bukan kode resmi BPS/Kemendagri.
Nama ambigu seperti Bandung, Bogor, Malang tidak otomatis dipilih sebagai kabupaten atau kota. Nama yang identik dengan provinsi seperti Jambi mengacu provinsi jika tanpa penanda kota/kabupaten; penanda Kota Jambi mengacu kotanya.
Alias yang belum ada tidak dibuat dengan menebak huruf awal. Tambahkan ke pembentuk tabel dengan rujukan dan tes, lalu bangun ulang referensi.

Perilaku
Kota Jambi, Provinsi Jambi -> Kota Jambi saja.
Bandingkan Kota Jambi dengan Provinsi Jambi -> dua wilayah.
Kab. Bandung, Jabar -> Kabupaten Bandung, Jawa Barat.
Tanjabtim -> nama filter sumber Kabupaten Tanjung Jabung T, Jambi.
Pulau Papua -> pulau fisik; tidak menggunakan angka Provinsi Papua.
Wilayah Papua / Tanah Papua -> kelompok enam provinsi MapBiomas jika seri tersebut tersedia.
Wilayah yang sudah dikenal tetapi tidak memiliki seri tetap dinyatakan belum tersedia; tidak diganti induknya.

Sumber
Direktori GADM 4.1 yang diarsipkan dari GFW: data/gfw/raw/provinces.json dan data/gfw-adm2/raw/districts.json.
https://gadm.org/download_country.html
Workbook MapBiomas: data/mapbiomas/raw/landcover-4.1.xlsx.
https://platform.indonesia.mapbiomas.org/
Jenis lima wilayah Kalimantan Utara:
https://jdih.kaltaraprov.go.id/
Ekspansi nama Tanjung Jabung:
https://tanjabtimkab.go.id/
https://tanjabbarkab.go.id/

Validasi 6 November 2026
293 tes kode lulus. Termasuk resolusi seluruh 498 nama kabupaten/kota sumber dan pengulangan pembacaan wilayah untuk 100 pertanyaan uji sebelumnya. Ini bukan pengulangan penuh 100 jawaban model.
12 pertanyaan diuji melalui browser: klaim Kota Jambi, singkatan Kab. Bandung/Jabar, Tanjabtim, Tarakan/Kaltara, ambiguitas Bandung, perbandingan eksplisit kota-provinsi, Sumatra MapBiomas, Papua Selatan, Sumatra Selatan, Pulau Papua, dan nasional; ditambah pemeriksaan akhir Kota Jambi dengan penulisan Provinsi Jambi.
Bukti browser: tmp/geography-20261106/browser-results.json.
Kegagalan format angka model dan audit kelengkapan seri pada uji sebelumnya merupakan pekerjaan terpisah, belum dinyatakan selesai oleh perbaikan wilayah ini.
