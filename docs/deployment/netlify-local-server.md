# Netlify dengan server data lokal

Website publik dibangun menggunakan `npm run build:public` di `web/frontend`.
Mode lokal dan server 8765/8767 tetap terpisah. Backend publik menggunakan port
loopback 8780, satu proses, satu antrean pekerja. Jangan mengekspos Qdrant atau
server lokal 8765 langsung ke internet.

## Alur

Browser → Netlify `/api/*` → Function `api` → HTTPS tunnel → komputer 8780 →
Qdrant lokal dan penyedia model. Submit pertanyaan mengembalikan ID pekerjaan;
browser mengecek status sampai jawaban selesai, sehingga koneksi HTTP tidak
perlu menunggu seluruh durasi pencarian.

## Data dan akun

- Nama, email, organisasi/media, bidang liputan, persetujuan, hash kata sandi,
  hash sesi, dan jumlah pemakaian disimpan di SQLite lokal berizin 600.
- Pendaftaran tidak memerlukan verifikasi email. Identitas yang diisikan belum
  diverifikasi. Kata sandi minimal 12 karakter; sesi 7 hari.
- Pertanyaan/jawaban tidak ditulis ke database akun. Pekerjaan berada sementara
  di RAM; hasil dibersihkan sesudah 5 menit dan saat logout. Antrean maksimal
  8, satu pertanyaan aktif per pengguna, 3 permintaan/menit dan 20/hari/akun.
- Riwayat chat disimpan di browser, dipisahkan menurut ID akun. Logout tidak
  menghapus riwayat perangkat. Perangkat/browser lain tidak otomatis memiliki
  riwayat tersebut. Gunakan tombol hapus riwayat untuk membersihkannya.
- Pertanyaan dan bukti dikirim ke penyedia model. Ketentuan penyimpanan penyedia
  model berlaku terpisah; jangan menjanjikan bahwa tidak ada pihak yang menerima
  pertanyaan. Netlify/Cloudflare juga menangani lalu lintas dan metadata jaringan.
- Belum ada pemulihan kata sandi mandiri atau dashboard admin akun. Cadangkan
  database akun secara privat; jangan memasukkannya ke Git atau folder publik.

## Konfigurasi rahasia

Jalankan `.venv/bin/python scripts/setup_public_server.py` untuk pengaturan
terminal. Alternatif untuk pengaturan awal pilot:
`.venv/bin/python scripts/setup_public_web.py`, lalu buka `http://127.0.0.1:8781/`.
Formulir web hanya untuk loopback dan sekali pakai; hentikan setelah selesai.
Jangan pernah men-tunnel port 8781.

Kunci model dan rahasia gateway berada di `.local/public-server.json` (600).
File ini diabaikan Git. Jangan mencetak, mengunggah, atau memasukkan kunci dalam
argumen perintah. Model key tidak dikirim ke Netlify atau browser.

Di proyek Netlify, simpan sebagai environment variables konteks production,
scope **Functions**:

- `CEKDATA_API_ORIGIN`: origin HTTPS tunnel, tanpa path.
- `CEKDATA_GATEWAY_SECRET`: rahasia acak yang sama dengan konfigurasi lokal;
  tandai secret. Jangan gunakan awalan `VITE_`.

Redeploy setelah mengubah environment variables. Origin website dalam konfigurasi
lokal harus sama persis dengan alamat yang digunakan pengunjung; URL preview
lain tidak otomatis dapat melakukan login. Permintaan langsung ke tunnel tanpa
rahasia gateway ditolak.

## Menjalankan server

Manual: `.venv/bin/python web/public_server.py`.
`scripts/public_service.py` menghasilkan berkas LaunchAgent di `.local/services`;
script tersebut hanya membuat berkas, tidak mengaktifkannya. Untuk Mac pengguna:

```sh
mkdir -p "$HOME/Library/LaunchAgents"
cp .local/services/org.idjnetwork.cekdata.public.plist "$HOME/Library/LaunchAgents/"
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/org.idjnetwork.cekdata.public.plist"
launchctl print gui/$(id -u)/org.idjnetwork.cekdata.public
```

LaunchAgent menjaga proses hidup setelah pengguna masuk. Ini bukan layanan
sebelum login; setelah reboot, FileVault/login pengguna tetap perlu diperhatikan.
Qdrant harus hidup, komputer tidak tidur, listrik dan internet harus tersedia.

## Tunnel sementara vs 24 jam

`cloudflared tunnel --url http://127.0.0.1:8780 --no-autoupdate` menghasilkan
alamat Quick Tunnel untuk uji coba. URL berubah bila proses dijalankan ulang.
Perbarui `CEKDATA_API_ORIGIN` dan redeploy jika URL berubah. Quick Tunnel bukan
jaminan layanan produksi 24 jam.

Untuk produksi, gunakan named Cloudflare Tunnel dengan hostname stabil dan
konfigurasi seperti `scripts/cloudflared.example.yml`; lalu jalankan
`scripts/public_service.py --tunnel-config /path/privat/config.yml` untuk membuat
LaunchAgent tunnel. Kredensial tunnel tidak boleh masuk repo. Website tetap
boleh memakai `*.netlify.app`; hostname tunnel backend dikelola terpisah.

## Deploy dan pemeriksaan

Netlify membaca `netlify.toml`: base `web/frontend`, publish `dist-public`,
functions `../../netlify/functions`. Paket deploy hanya memerlukan source frontend,
aset publik, function dan konfigurasi build. Jangan upload workspace mentah yang
mengandung `.local`, PDF, data Qdrant, atau hasil tes mentah.

```sh
PYTHONPATH=web:workflow .venv/bin/python -m unittest web/test_public_server.py web/test_server.py -q
node --test netlify/tests/*.test.mjs
cd web/frontend
npm test
npm run build:public
```

Uji online: pendaftaran/masuk, satu pertanyaan nyata, tabel dan unduhan, logout,
akses tanpa login, dan respons saat komputer offline. Hasil tes fixture membuktikan
perilaku aplikasi, bukan validitas jawaban model pada semua pertanyaan.
