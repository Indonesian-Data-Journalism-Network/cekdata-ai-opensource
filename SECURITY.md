# Keamanan

Versi ini hanya untuk penggunaan lokal pada loopback. API key dimasukkan melalui formulir lokal dan tidak boleh dimasukkan ke issue, screenshot, commit, atau dataset. Key OpenAI disimpan dalam memori sesi server; key Pinecone diteruskan ke host Pinecone yang diizinkan. Metadata sumber dan pertanyaan merupakan input tak tepercaya.

Pertanyaan dan bukti terpilih dikirim ke OpenAI untuk pemahaman dan penyusunan jawaban. Riwayat chat disimpan oleh browser. Jangan memasukkan data yang tidak boleh dikirim ke penyedia model.

Data ekspor, katalog, penyimpanan Qdrant, dan `.env` dikecualikan oleh `.gitignore`. Periksa perubahan sebelum commit. Berkas unduhan dapat mengandung data yang tidak boleh dipublikasikan.

Untuk masalah keamanan, hubungi pengelola melalui kanal privat yang tersedia pada organisasi. Jangan mempublikasikan key atau detail eksploitasi aktif dalam issue terbuka.
