"""Interactive secret setup. Never pass API keys as CLI arguments or print them."""
from getpass import getpass
from pathlib import Path
import json,os,secrets,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from public_server import Config

def main():
    path=ROOT/'.local/public-server.json'
    if path.exists():
        raise SystemExit('Konfigurasi sudah ada. Tidak ditimpa; gunakan pengelolaan konfigurasi lokal untuk perubahan.')
    origin=input('Alamat website Netlify/domain (https://…, tanpa / di akhir): ').strip().rstrip('/')
    key=getpass('API key model (disembunyikan): ').strip()
    gateway=getpass('Rahasia gateway minimal 32 karakter (kosong untuk buat otomatis): ').strip() or secrets.token_urlsafe(48)
    db=ROOT/'.local/public/accounts.sqlite3'
    Config(database=db,origin=origin,gateway_secret=gateway,model_key=key)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    obj={'database':str(db),'origin':origin,'gateway_secret':gateway,'model_key':key}
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(obj,f,indent=2)
    print('Konfigurasi tersimpan lokal dengan izin 600. Kunci tidak ditampilkan.')
    print('Salin hanya gateway_secret ke variabel runtime CEKDATA_GATEWAY_SECRET di Netlify; jangan unggah berkas ini.')
if __name__=='__main__':main()
