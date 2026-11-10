# Pemahaman pertanyaan yang diteruskan — 7 November 2026

Perubahan ini memperbaiki pemilihan ukuran dan kelengkapan permintaan pada jalur
General/Pinecone, Environment, serta laporan NGO. Tidak mengubah isi Pinecone,
Qdrant, atau membangun ulang chunk laporan.

## Perubahan

- `Intent` membawa daftar ukuran yang diminta, dimensi satuan, ukuran berdekatan
  yang tidak menjawab pertanyaan, dan seluruh bagian pertanyaan. AI memahami
  konsep sebelum melihat kandidat. Definisi ukuran berbeda dari judul publikasi.
- Pinecone meneruskan Intent awal ke pemilih katalog; tidak memanggil pemahaman
  kedua. Embedding memakai pertanyaan asli ditambah konsep dan istilah pencarian
  dari pemahaman tersebut. Wilayah/bulan tetap menjadi batas pencarian.
- Pemilih katalog memeriksa dimensi dan kolom pengukuran sebelum memotong daftar
  kandidat, setelah pemilihan, dan saat pencarian alternatif. Indikator bersatuan
  rupiah tidak menjawab permintaan persentase hanya karena judulnya menyebut
  kemiskinan. Frasa pengecualian yang lebih umum tidak boleh menghapus konsep
  spesifik yang memang diminta.
- Laporan NGO menerima pemahaman yang sama pada perencanaan pencarian,
  pengambilan temuan, pemeriksaan bukti, dan penyusunan jawaban. Perencana
  pencarian tidak boleh mengubah jenis klaim. Pengambilan temuan mempertahankan
  kata seperti “semua” dan seluruh pertanyaan setelah tanda tanya pertama.
- Jika sebagian ukuran sudah dijawab katalog tetapi ukuran lain belum,
  Environment melanjutkan pencarian laporan. Periode laporan dan periode seri
  GFW yang disebutkan secara terpisah dipertahankan melalui bagian pertanyaan.
- Semua pemeriksaan kutipan, angka, wilayah, status bukti, dan kelayakan label
  penilaian tetap berlaku. Acuan pertanyaan tidak menjadi bukti fakta.

Kamus yang ditambahkan berupa dimensi satuan umum (persentase, jumlah, uang,
luas, indeks, massa); rincian konsep berasal dari pemahaman pertanyaan. Tidak ada
angka jawaban, nama wilayah, perusahaan, atau ID tabel yang dipatok dalam aturan
baru. Ini belum merupakan kamus lengkap seluruh indikator statistik.

## Hasil uji

**431 uji workflow dan 17 uji server lulus (448 total).** Uji baru memeriksa:
pemahaman hanya dibuat sekali, indikator rupiah/persen dipisahkan, judul induk
tidak menutupi kolom yang berbeda, pertanyaan kedua dan pengkuantifikasi tetap
terbawa, jenis klaim tidak diubah perencana, serta periode laporan tidak menimpa
periode statistik. Uji lama yang mengharuskan NGO melewati pemahaman awal telah
diubah untuk memeriksa bahwa pemahaman awal kini diteruskan.

Enam pertanyaan berbeda diuji melalui layanan model dan data nyata:

| Pertanyaan | Hasil setelah perbaikan |
| --- | --- |
| Tren kemiskinan Jawa Barat, tanpa tahun | Memilih persentase penduduk miskin; seri Maret 2024–2026; tidak memakai garis kemiskinan |
| Tren garis kemiskinan Jawa Barat, Maret 2021–2023 | Memilih garis kemiskinan dengan satuan rupiah |
| Jumlah penduduk miskin Jawa Barat, Maret 2025 | Belum terjawab; tidak diganti persentase. Dalam kandidat bulanan yang diperiksa belum ditemukan ukuran jumlah yang sesuai |
| Tren kehilangan tutupan pohon Aceh 2021–2025 | Menampilkan lima tahun GFW; turun pada awal seri kemudian meningkat |
| Dua pertanyaan tentang persentase rumah tangga Kabaena | Menampilkan angka penurunan produksi 45,8 persen dan penurunan pendapatan 38,2 persen, dengan sumber Satya Bumi |
| Pendapatan rumah tangga Kabaena serta tren kehilangan tutupan pohon Bombana | Menampilkan temuan Satya Bumi dan tabel GFW 2021–2025; tidak menyamakan cakupan pulau dengan seluruh kabupaten |

Uji gabungan awal masih hanya menjawab bagian GFW. Setelah penambahan pemeriksaan
ukuran yang belum terjawab, uji ulang berhasil menampilkan kedua sumber.
Uji jumlah penduduk miskin mengungkap frasa pengecualian terlalu umum; setelah
penanganannya diperbaiki, permintaan tersebut tetap belum terjawab karena kandidat
ukuran jumlah yang sesuai belum ditemukan dalam pencarian bulanan.

Hasil rinci lokal: `tmp/intent-contract-validation/`. Angka dibandingkan dengan
bukti yang dipakai mesin; ini bukan audit ulang independen seluruh publikasi.
Lima pertanyaan menghasilkan jawaban dengan ukuran yang diminta; satu masih
terbatas. Sampel kecil ini tidak menggantikan benchmark akurasi 500 pertanyaan.

Backend publik dimuat ulang setelah pemeriksaan. Uji browser di
`https://cekdata-ai-pilot.netlify.app/` dengan pertanyaan “Bagaimana tren kemiskinan
di Jawa Barat?” menampilkan tabel persentase Maret 2024, 2025, dan 2026 dengan
tautan BPS. Bukti layar: `tmp/intent-contract-validation/online-poverty-trend.png`.

## Batas yang masih perlu diuji

Pemahaman awal tetap dapat keliru. Filter dimensi tidak membedakan semua konsep
yang satuannya sama, dan satuan yang belum dikenali belum dipaksa menjadi satuan
lain. Metadata PDF dan periode pada tabel Pinecone masih memiliki keterbatasan.
Penyajian judul, tautan berulang, serta kelengkapan kesimpulan singkat masih dapat
ditingkatkan terpisah. Perubahan ini memperkuat konsistensi maksud dan bukti;
tidak menjamin setiap pertanyaan sudah dapat dijawab.
