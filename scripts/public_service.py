"""Render launchd service files for review; does not load or start services."""
import argparse,plistlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--tunnel-config',type=Path);args=p.parse_args()
    out=ROOT/'.local/services';out.mkdir(parents=True,exist_ok=True)
    env={'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'}
    app={'Label':'org.idjnetwork.cekdata.public','ProgramArguments':[str(ROOT/'.venv/bin/python'),str(ROOT/'web/public_server.py')],
         'WorkingDirectory':str(ROOT),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,'EnvironmentVariables':env}
    (out/'org.idjnetwork.cekdata.public.plist').write_bytes(plistlib.dumps(app))
    if args.tunnel_config:
        binary=shutil.which('cloudflared')
        if not binary:raise SystemExit('cloudflared belum terpasang')
        tunnel={**app,'Label':'org.idjnetwork.cekdata.tunnel',
                'ProgramArguments':[binary,'tunnel','--config',str(args.tunnel_config.resolve()),'run']}
        (out/'org.idjnetwork.cekdata.tunnel.plist').write_bytes(plistlib.dumps(tunnel))
    print('Berkas layanan siap ditinjau di',out,'; belum diaktifkan.')
if __name__=='__main__':main()
