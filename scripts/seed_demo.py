"""Create explicitly synthetic data for a fresh local demonstration."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from settings import DATA_DIR
from pilot_data import import_exports


def make_demo(folder):
    folder.mkdir(parents=True, exist_ok=False)
    records=[]
    for area, values in [('Kota Contoh', [100, 110, 105]), ('Kota Ilustrasi', [90, 95, 100])]:
        for year, value in zip([2023,2024,2025], values):
            records.append({'id': f'demo-{area}-{year}', 'values': [0.0, 1.0], 'metadata': {
                'dataset_id': 'demo-pekerja', 'series_label': 'Jumlah pekerja',
                'title': 'DATA SIMULASI — Jumlah pekerja menurut kota',
                'source': 'BPS (SIMULASI, BUKAN DATA RESMI)', 'area_name': area,
                'year': year, 'value': str(value), 'unit': 'orang', 'synthetic': True,
                'definition': 'Data buatan untuk menguji aplikasi; bukan statistik resmi.'}})
    content=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in records)
    (folder/'records.jsonl').write_text(content)
    (folder/'manifest.json').write_text(json.dumps({'dimension':2,'files':{'records.jsonl':hashlib.sha256(content.encode()).hexdigest()}},indent=2)+'\n')
    return folder


if __name__=='__main__':
    folder=make_demo(DATA_DIR/'demo-export')
    import_exports([folder])
    print('Enam record SIMULASI siap. Ini bukan data statistik nyata.')
