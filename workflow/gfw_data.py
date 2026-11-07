"""Pinned, auditable GFW annual statistics; originals retained before publication."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

import httpx
from qdrant_client import QdrantClient, models
from flow import Evidence
from settings import ROOT, QDRANT_URL

BASE = 'https://data-api.globalforestwatch.org'
VERSION = 'v20260424'
BOUNDARY_VERSION = 'v4.1'
DIRECTORY = ROOT / 'data/gfw'
COLLECTION = 'cekdata_gfw_idn_20260424_t30'
YEAR = 'umd_tree_cover_loss__year'
THRESHOLD = 'umd_tree_cover_density_2000__threshold'
PRIMARY = 'is__umd_regional_primary_forest_2001'
SOURCE = 'Global Forest Watch / UMD GLAD'
METRICS = {
    'loss_ha': ('tree-cover-loss', 'Kehilangan tutupan pohon', 'umd_tree_cover_loss__ha'),
    'fire_loss_ha': ('tree-cover-loss-fire', 'Kehilangan tutupan pohon akibat kebakaran', 'umd_tree_cover_loss_from_fires__ha'),
    'primary_loss_ha': ('primary-forest-loss', 'Kehilangan tutupan pohon dalam hutan primer tropis basah tahun acuan 2001', 'umd_tree_cover_loss__ha'),
}

def sql_for(level, primary=False, *, adm1=None, adm2=None, year=None, metric=None):
    if level not in ('iso', 'adm1', 'adm2'):
        raise ValueError('Unsupported level')
    dims = ['iso'] + (['adm1'] if level != 'iso' else []) + (['adm2'] if level == 'adm2' else []) + [YEAR]
    fields = [metric] if metric else (['primary_loss_ha'] if primary else ['loss_ha', 'fire_loss_ha'])
    if any(f not in METRICS for f in fields):
        raise ValueError('Unsupported metric')
    where = ["iso = 'IDN'", f'{THRESHOLD} = 30', f'{YEAR} >= {2002 if primary else 2001}', f'{YEAR} <= 2025']
    if primary:
        where.append(f'{PRIMARY} = true')
    if adm1 is not None:
        if level not in ('adm1', 'adm2') or type(adm1) is not int or adm1 <= 0:
            raise ValueError('Invalid province')
        where.append(f'adm1 = {adm1}')
    if adm2 is not None:
        if level != 'adm2' or adm1 is None or type(adm2) is not int or adm2 <= 0:
            raise ValueError('Invalid district')
        where.append(f'adm2 = {adm2}')
    if year is not None:
        if type(year) is not int or not (2002 if primary else 2001) <= year <= 2025:
            raise ValueError('Invalid year')
        where.append(f'{YEAR} = {year}')
    return ('SELECT ' + ', '.join(dims + [f'SUM({METRICS[f][2]}) AS {f}' for f in fields])
        + ' FROM data WHERE ' + ' AND '.join(where)
        + ' GROUP BY ' + ', '.join(dims) + ' ORDER BY ' + ', '.join(dims) + ' LIMIT 2001')

def province_directory(rows):
    result = {}
    for row in rows:
        match = re.fullmatch(r'IDN\.(\d+)_\d+', row.get('gid_1', ''))
        if row.get('gid_0') != 'IDN' or str(row.get('adm_level')) != '1' or not match or not row.get('name_1'):
            raise ValueError('Invalid boundary record')
        code = int(match[1])
        if code in result:
            raise ValueError('Duplicate province')
        result[code] = {'name': row['name_1'], 'gid': row['gid_1']}
    if not result:
        raise ValueError('Empty boundary directory')
    return result

def normalize(rows, level, primary, provinces, provenance, districts=None):
    if not isinstance(rows, list) or len(rows) >= 2001:
        raise ValueError('Invalid or possibly truncated response')
    result, seen = [], set()
    dataset = f'gadm__tcl__{level}_change'
    for row in rows:
        year, code = row.get(YEAR), row.get('adm1') if level != 'iso' else None
        district_code = row.get('adm2') if level == 'adm2' else None
        if row.get('iso') != 'IDN' or type(year) is not int or not (2002 if primary else 2001) <= year <= 2025:
            raise ValueError('Country/year mismatch')
        if level != 'iso' and (type(code) is not int or code not in provinces):
            raise ValueError('Unmapped province; publication stopped')
        district = None
        if level == 'adm2':
            if type(district_code) is not int or not districts or (code,district_code) not in districts:
                raise ValueError('Unmapped district; publication stopped')
            district = districts[(code,district_code)]
        if (code, district_code, year) in seen:
            raise ValueError('Duplicate observation')
        seen.add((code, district_code, year))
        area = district['name'] if district else provinces[code]['name'] if code is not None else 'Indonesia'
        for metric in (['primary_loss_ha'] if primary else ['loss_ha', 'fire_loss_ha']):
            if row.get(metric) is None:
                raise ValueError('Missing value is not zero')
            value = Decimal(str(row[metric]))
            if not value.is_finite() or value < 0:
                raise ValueError('Invalid area value')
            metric_id, label, field = METRICS[metric]
            area_id = f'{code}.{district_code}' if district else code
            identity = f'gfw:{dataset}:{VERSION}:IDN:{area_id}:{year}:t30:{metric_id}'
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
            record_sql = sql_for(level, primary, adm1=code, adm2=district_code, year=year, metric=metric)
            url = str(httpx.URL(f'{BASE}/dataset/{dataset}/{VERSION}/download/json', params={'sql': record_sql}))
            definition = ('Luas kehilangan tutupan pohon tahunan; ambang kerapatan tajuk 30% pada tahun 2000. '
                'Kehilangan tutupan pohon tidak otomatis berarti deforestasi permanen atau luas hutan tersisa. '
                + ('Dibatasi pada hutan primer tropis basah tahun acuan 2001. ' if primary else '')
                + ('Dibatasi pada kehilangan akibat kebakaran. ' if metric == 'fire_loss_ha' else ''))
            note = ('Batas wilayah GADM 4.1; 34 provinsi sumber, bukan pemekaran terbaru. '
                    'Papua dan Papua Barat mengikuti cakupan sumber sebelum pemekaran terbaru. '
                    'Perbandingan seri sebelum/sesudah 2011 dan 2015 perlu memperhatikan perubahan metode deteksi. '
                    'Angka luas satelit, bukan statistik luas kawasan hutan administratif.')
            evidence = Evidence(id=point_id, indicator_id='gfw-'+metric_id, indicator=label+' tahunan menurut provinsi dan nasional',
                area=area, year=year, value=str(value), unit='ha', source=SOURCE,
                title=label+' — GFW '+VERSION, source_name=SOURCE,
                source_url=f'{BASE}/dataset/{dataset}/{VERSION}', download_url=url,
                definition=definition, method=f'GFW {VERSION}; GADM {BOUNDARY_VERSION}; threshold 30%; annual SUM; '+note,
                source_record_id=identity, source_note=definition + note)
            result.append({**evidence.model_dump(), 'usable': True, 'area_key': area.casefold(),
                'provider': 'gfw', 'dataset': dataset, 'dataset_version': VERSION,
                'boundary_version': BOUNDARY_VERSION, 'boundary_gid': district['gid'] if district else provinces[code]['gid'] if code else 'IDN',
                **({'adm2':district_code, 'geographic_level':'adm2', 'boundary_type':district['type'],
                    'province_context':provinces[code]['name']} if district else {}),
                'adm1': code, 'metric': metric, 'canopy_threshold': 30, 'source_field': field,
                'source_sql': record_sql, 'source_provenance': provenance,
                'original_row': row, 'coverage_note': note, 'data_status': 'annual_published',
                'period_start': f'{year}-01-01', 'period_end': f'{year}-12-31'})
    return result

class ArchiveClient:
    def __init__(self, directory, key):
        self.directory = directory
        self.client = httpx.Client(headers={'x-api-key': key, 'Origin': 'http://localhost'}, timeout=90, follow_redirects=False)
    def get(self, name, path, sql=None):
        target = self.directory / 'raw' / (name+'.json')
        receipt = target.with_suffix('.receipt.json')
        url = str(httpx.URL(BASE+path, params={'sql': sql} if sql else None))
        if target.exists() and receipt.exists():
            info = json.loads(receipt.read_text())
            raw = target.read_bytes()
            if info['url'] != url or info['sha256'] != hashlib.sha256(raw).hexdigest():
                raise ValueError('Archive checksum or request mismatch')
        else:
            response = self.client.get(url)
            if response.status_code != 200:
                raise RuntimeError(f'GFW HTTP {response.status_code} for {name}; no publication')
            raw = response.content
            if len(raw) > 12*1024*1024:
                raise ValueError('Unexpected response size')
            info = {'url': url, 'sql': sql, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'file': str(target.relative_to(self.directory))}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            receipt.write_text(json.dumps(info,indent=2)+'\n')
        payload = json.loads(raw, parse_float=Decimal)
        if isinstance(payload, dict):
            if payload.get('status') != 'success':
                raise ValueError('GFW payload not successful')
            payload = payload['data']
        return payload, info

def build_catalog(records):
    catalog = {}
    for r in records:
        c = catalog.setdefault(r['indicator_id'], {'indicator_id': r['indicator_id'], 'label': r['indicator'],
            'source': SOURCE, 'unit': 'ha', 'definition': r['definition'], 'areas': set(), 'years': set(), 'populations': ['total']})
        c['areas'].add(r['area']); c['years'].add(r['year'])
    return [{k: sorted(v) if isinstance(v,set) else v for k,v in c.items()} for c in catalog.values()]

def reconcile(records):
    totals, provincial = {}, defaultdict(Decimal)
    with localcontext() as ctx:
        ctx.prec = 60
        for r in records:
            if r.get('adm2') is not None:
                continue
            key = (r['metric'], r['year'])
            if r['adm1'] is None:
                totals[key] = Decimal(r['value'])
            else:
                provincial[key] += Decimal(r['value'])
        differences = {f'{m}:{y}':str(abs(v-provincial[(m,y)])) for (m,y),v in totals.items()}
        if any(Decimal(v) > Decimal('0.01') for v in differences.values()):
            raise ValueError('National/province reconciliation exceeds 0.01 ha: '+str(differences))
    return differences

def main(publish=False):
    key = os.environ.get('GFW_API_KEY')
    if not key:
        key = json.loads((ROOT/'.local/gfw-credentials.json').read_text())['api_key']
    client = ArchiveClient(DIRECTORY, key)
    try:
        client.get('loss-metadata', '/dataset/umd_tree_cover_loss')
        client.get('boundary-version', f'/dataset/gadm_administrative_boundaries/{BOUNDARY_VERSION}')
        sql = "SELECT gid_0,gid_1,name_1,adm_level FROM data WHERE gid_0='IDN' AND adm_level='1' ORDER BY gid_1 LIMIT 100"
        directory, boundary_receipt = client.get('provinces', f'/dataset/gadm_administrative_boundaries/{BOUNDARY_VERSION}/download/json', sql)
        provinces = province_directory(directory)
        records = []
        for level in ('iso','adm1'):
            dataset = f'gadm__tcl__{level}_change'
            version, _ = client.get(level+'-version', f'/dataset/{dataset}/{VERSION}')
            if version.get('status') != 'saved' or version.get('is_mutable') is not False:
                raise ValueError('Version must be saved and immutable')
            for primary in (False,True):
                name = level+('-primary' if primary else '-loss-fire')
                rows, receipt = client.get(name, f'/dataset/{dataset}/{VERSION}/download/json',sql_for(level,primary))
                normalized = normalize(rows, level, primary, provinces, {'data':receipt,'boundaries':boundary_receipt})
                records.extend(normalized)
                print(name, len(rows), 'rows;',len(normalized),'observations',flush=True)
    finally:
        client.client.close()
    diffs = reconcile(records)
    ids = [r['id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate IDs')
    catalog = build_catalog(records)
    present = {(r['metric'],r['area'],r['year']) for r in records}
    missing = [{'metric':metric,'area':area,'years':[y for y in range(2002 if metric=='primary_loss_ha' else 2001,2026)
                if (metric,area,y) not in present]}
               for metric in METRICS for area in ['Indonesia']+[p['name'] for p in provinces.values()]]
    missing = [m for m in missing if m['years']]
    report = {'provider':'gfw','collection':COLLECTION,'dataset_version':VERSION,'boundary_version':BOUNDARY_VERSION,
        'province_count':len(provinces),'records':len(records),'searchable_records':len(records),'catalog_entries':len(catalog),
        'years':{c['indicator_id']:c['years'] for c in catalog}, 'province_names':[p['name'] for p in provinces.values()],
        'canopy_threshold':30,'national_province_absolute_differences_ha':diffs,
        'missing_observations_not_assumed_zero':missing,
        'publication_status':'validated','source_links_required':True,
        'note':'GADM 4.1 source geography; no missing observations filled as zero; primary forest series starts 2002.'}
    (DIRECTORY/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,default=str)+'\n' for r in records))
    (DIRECTORY/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    (DIRECTORY/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if publish:
        db = QdrantClient(url=QDRANT_URL,timeout=60)
        try:
            if db.collection_exists(COLLECTION) and db.count(COLLECTION,exact=True).count:
                raise ValueError('Collection already populated; not overwritten')
            if not db.collection_exists(COLLECTION):
                db.create_collection(COLLECTION,vectors_config={})
            for offset in range(0,len(records),100):
                batch = json.loads(json.dumps(records[offset:offset+100],default=str))
                db.upsert(COLLECTION,points=[models.PointStruct(id=r['id'],vector={},payload=r) for r in batch],wait=True)
            for field,kind in [('indicator_id','keyword'),('area_key','keyword'),('source','keyword'),('population','keyword'),('year','integer'),('usable','bool')]:
                db.create_payload_index(COLLECTION,field_name=field,field_schema=kind,wait=True)
            if db.count(COLLECTION,exact=True).count != len(records):
                raise ValueError('Qdrant count mismatch')
        finally:
            db.close()
        report['publication_status']='published'
        (DIRECTORY/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['records','province_count','catalog_entries','publication_status']}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    main(parser.parse_args().publish)
