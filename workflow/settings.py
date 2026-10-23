from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get('CEKDATA_DATA_DIR', str(ROOT / 'data'))).resolve()
COLLECTION = os.environ.get('CEKDATA_COLLECTION', 'cekdata_opensource_pilot')
QDRANT_URL = os.environ.get('QDRANT_URL', 'http://127.0.0.1:6333')
CATALOG_PATH = DATA_DIR / 'catalog.json'
REPORT_PATH = DATA_DIR / 'import-report.json'
