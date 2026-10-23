# Kontrak data pilot

Qdrant menyimpan payload bukti dengan `id`, `indicator_id`, `indicator`, `area`, `year`, `value` (teks desimal), `unit`, `source`, serta konteks opsional: `month`, `population`, `definition`, `method`, `title`, `source_url`, dan `download_url`.

Satu record harus mewakili satu observasi. Nilai nol bukan nilai hilang. Teks desimal disimpan agar tidak membulat melalui float. Kategori/populasi dipisahkan dan nilai dari seri yang tidak sebanding tidak boleh dihitung bersama.

Importer Pinecone membaca `metadata.value`, `year`, `area_name`, `unit`, `title`, `source`, `dataset_id`, `series_label`, dan kategori tambahan. `period` berisi nama bulan atau penjelasan periode. URL singular `source_url`/`download_url` dipertahankan. Metadata asli disimpan di `original_metadata`. Record yang tidak dapat dipetakan ditandai `usable=false`; tidak dibuatkan angka pengganti.

File ekspor memerlukan manifest dengan dimensi dan checksum SHA-256 `records.jsonl`; eksportir yang disertakan menghasilkan format ini. Model pembuat embedding asli belum diverifikasi, sehingga vektor tidak digunakan untuk pencarian semantik.

## Canonical di MySQL

Jika Pinecone hanya berisi metadata string dan `mysql_reference`, nilainya memang bisa berada di MySQL. Prototipe ini belum melakukan pengambilan canonical tersebut. Jangan menganggap angka tidak ada dalam sumber hanya karena tidak berada dalam metadata pencarian. Jangan mengubah vektor `values` menjadi nilai statistik. Dukungan MySQL perlu pengambilan record lengkap berdasarkan ID dan pemeriksaan versi sebelum dipakai sebagai bukti.
