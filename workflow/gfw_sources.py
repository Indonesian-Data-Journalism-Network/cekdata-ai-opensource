"""Public reading links for archived GFW evidence; never alter its numeric source."""
import json
from pathlib import Path
import re

REGISTRY = Path(__file__).resolve().parents[1] / 'web/frontend/src/config/gfwPublicSources.json'
DATASET_PAGE = 'https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html'
IDENTITY = re.compile(r'^gfw:gadm__tcl__(iso|adm1|adm2)_change:(v\d+):IDN:(None|\d+(?:\.\d+)?):(\d{4}):t30:(tree-cover-loss|tree-cover-loss-fire|primary-forest-loss)$')
PUBLIC_NOTE = ('Tautan sumber membuka halaman publik GFW. Halaman tersebut dapat diperbarui; '
    'angka jawaban memakai versi arsip yang tercantum, ambang tajuk 30%, dan tahun yang diminta. '
    'Pilih indikator dan periode yang sama saat membandingkan dengan dashboard.')
_registry = None
_registry_stamp = None


def public_sources():
    global _registry, _registry_stamp
    stamp = REGISTRY.stat().st_mtime_ns if REGISTRY.exists() else None
    if _registry is None or stamp != _registry_stamp:
        _registry = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}
        _registry_stamp = stamp
    return _registry


def public_evidence(payload):
    match = IDENTITY.fullmatch(payload.get('source_record_id',''))
    if not match:
        return payload
    level,version,code,_,_ = match.groups()
    if (level=='iso' and code!='None') or (level=='adm1' and not code.isdigit()) or (level=='adm2' and '.' not in code):
        return payload
    metadata_url=f'https://data-api.globalforestwatch.org/dataset/gadm__tcl__{level}_change/{version}'
    if payload.get('source_url') != metadata_url:
        return payload
    key = 'iso:IDN' if level=='iso' else level+':'+code
    entry = public_sources().get(key,{})
    url=entry.get('url',DATASET_PAGE)
    # The registry is a reviewed presentation layer, not a new numeric source.
    if not re.fullmatch(r'https://www\.globalforestwatch\.org/dashboards/country/IDN/(?:\d+/){0,2}',url):
        url=DATASET_PAGE
    note=PUBLIC_NOTE
    if url==DATASET_PAGE:
        note+=' Halaman wilayah belum terverifikasi; tautan membuka penjelasan dataset resmi.'
    return {**payload,'source_url':url,'api_source_url':metadata_url,
        'methodology_url':DATASET_PAGE,
        'source_note':payload.get('source_note','')+' '+note}
