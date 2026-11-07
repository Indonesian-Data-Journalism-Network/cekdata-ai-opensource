# Aturan editorial versi awal

- Pertanyaan data dan klaim dibedakan. Pertanyaan biasa tidak otomatis diberi Benar/Salah.
- Klaim dinilai berdasarkan indikator, wilayah, periode, kategori, satuan, dan definisi yang sebanding.
- Benar: bukti mendukung proposisi. Salah: bukti langsung bertentangan. Sebagian benar: bagian klaim didukung, tetapi kesimpulan melampaui bukti. Tidak dapat diverifikasi: bukti belum mencukupi.
- Periode tidak lengkap ditafsirkan dengan konteks dan ketersediaan data. Tahun ini mengacu tanggal Jakarta. Data tahun lama boleh ditampilkan sebagai konteks, tidak menggantikan pembuktian klaim tahun yang diminta.
- Paparkan angka dalam butir terpisah. Temuan data mendahului kesimpulan.
- Keputusan pengguna, 5 November 2026: angka bersumber tetap ditampilkan meskipun tahun berjalan belum berakhir atau sumber menandainya sementara. Sertakan catatan singkat tentang periode cakupan, tanggal acuan, dan status sesuai sumber (sementara, estimasi/proyeksi, atau pengamatan pada tanggal tertentu). Jangan menahan angka hanya karena belum final. Jangan menyebut angka parsial sebagai realisasi setahun penuh atau mengubah jenis indikatornya. Bila angka memang tidak tersedia, jangan membuat perkiraan sendiri. Ini ketentuan editorial untuk pengembangan berikutnya; penerapan otomatis pada seluruh jalur jawaban belum diverifikasi.
- Tren mempertimbangkan seluruh titik yang sebanding: naik, turun, fluktuatif, atau datar.
- Perbandingan menjelaskan hubungan, bukan selalu selisih. Selisih atau persentase dihitung sesuai permintaan.
- Keputusan pengguna, 5 November 2026: judul bagian adalah **Konteks**, bukan “Konteks penting”. Isinya menjelaskan dasar kesimpulan dari angka yang digunakan: langkah perhitungan, pembagi, titik perbandingan, pola perubahan, atau keterbatasan bukti yang relevan. Jangan mengisi bagian ini otomatis dengan paragraf metadata GFW yang sama untuk semua pertanyaan. Catatan teknis tetap tersedia di rincian sumber. Semua observasi yang dipakai tetap ditampilkan; penjelasan perhitungan tidak menggantikan data tahunan. Rata-rata memerlukan seluruh tahun yang diminta, tidak menganggap data hilang sebagai nol, dan menggunakan presisi asli sebelum pembulatan tampilan.
- Sumber di bagian akhir, dengan URL jika tersedia dalam metadata. Jangan mengarang tautan.
- Jangan membuat sebab, angka, atau bukti keberhasilan kebijakan tanpa dukungan data.

Keterbatasan saat ini: kalimat perubahan pada pertanyaan penjelasan masih bisa berada dalam Temuan data; beberapa label indikator masih panjang. Rancangan pencarian indikator pendukung ada di `why-analysis-plan.md` dan belum diimplementasikan.

Tampilan sumber GFW (keputusan pengguna, 5 November 2026): cukup `Sumber: Global Forest Watch / UMD GLAD — versi …` dengan nama sumber sebagai tautan publik dan `Unduh: <nama data>` sebagai tautan CSV. Jangan mengulang tautan per observasi atau menampilkan daftar API/metode terpisah. Metadata penelusuran tetap tersimpan di data unduhan. Label penilaian di atas jawaban dan seluruh temuan data tetap dipertahankan.

Format jawaban yang disetujui pengguna (5 November 2026):
- Pertanyaan data dimulai dengan jawaban utama, dilanjutkan Temuan Data berupa tabel seluruh observasi yang digunakan, Konteks ringkas (umumnya 1–2 kalimat), dan sumber/unduhan.
- Klaim tetap memiliki badge penilaian di atas, teks klaim, judul `Penilaian: <label>` dengan penjelasan di bawahnya, Temuan Data, Konteks, serta Peringatan editorial hanya jika relevan. Jangan menampilkan bagian Alasan terpisah yang mengulang penjelasan.
- Angka tabel ditampilkan dua desimal; bukti dan CSV menyimpan presisi asal. Hasil total/rata-rata/selisih dibedakan dari observasi tahunan. Data pembanding di luar lingkup harus ditandai dan tidak boleh dipakai sebagai pengganti data yang hilang.
- Konteks menjelaskan dasar perhitungan/pembacaan data, bukan menyalin metadata sumber. Tren menjelaskan arah perubahan dan titik balik, bukan hanya menyebut fluktuatif. Rata-rata dan total memerlukan seri lengkap; total lintas tahun hanya dilakukan untuk indikator yang boleh dijumlahkan (saat ini seri kehilangan tutupan pohon GFW).
- Frasa nama indikator `kehilangan tutupan pohon akibat kebakaran` tidak otomatis menandai klaim kausal/pengaruh program. Penilaian pengaruh program tetap membutuhkan bukti tambahan.
- Format baru berlaku pada jawaban yang diproses ulang; jawaban historis tidak diberi kesimpulan baru tanpa pemeriksaan ulang.

Tambahan karbon dan peta (5 November 2026): total lintas tahun juga dapat dihitung
untuk emisi tahunan dengan seri lengkap. Ringkasan model 2001–2025 tidak boleh
menjawab sebagai nilai satu tahun atau subperiode. Peta gabungan gambut memakai
tahun versi yang harus dibedakan dari tahun pengamatan. Neraca positif berarti
sumber emisi bersih; negatif berarti penyerap bersih. Kelas tanaman campuran
tidak digabung otomatis dengan kelas tanaman tunggal atau disamakan dengan konsesi.
