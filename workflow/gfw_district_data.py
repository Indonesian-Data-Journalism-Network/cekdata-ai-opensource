"""Add GADM source districts in an isolated, reconciled GFW snapshot."""
import argparse
from collections import defaultdict
from decimal import Decimal, localcontext
import json
import os
import re

from qdrant_client import QdrantClient, models
from gfw_data import (ArchiveClient, BASE, BOUNDARY_VERSION, DIRECTORY as PARENT_DIRECTORY,
    METRICS, ROOT, QDRANT_URL, VERSION, build_catalog, normalize, province_directory,
    reconcile, sql_for)

DIRECTORY = ROOT / 'data/gfw-adm2'
COLLECTION = 'cekdata_gfw_idn_adm2_20260424_t30'
DIRECTORY_SQL = ("SELECT gid_0,gid_1,name_1,gid_2,name_2,type_2,engtype_2,adm_level "
    "FROM data WHERE gid_0='IDN' AND adm_level='2' ORDER BY gid_1,gid_2 LIMIT 1001")


def district_directory(rows, provinces):
    if not isinstance(rows,list) or not rows or len(rows) >= 1001:
        raise ValueError('Empty or truncated district directory')
    result = {}
    for row in rows:
        match = re.fullmatch(r'IDN\.(\d+)\.(\d+)(?:_\d+)?', row.get('gid_2',''))
        if not match or row.get('gid_0') != 'IDN' or str(row.get('adm_level')) != '2':
            raise ValueError('Invalid district boundary')
        p,d = map(int,match.groups())
        if p not in provinces or row['gid_1'] != provinces[p]['gid'] or row['name_1'] != provinces[p]['name']:
            raise ValueError('District/province mismatch')
        if (p,d) in result or not row.get('name_2'):
            raise ValueError('Duplicate or unnamed district')
        kind, short = row.get('type_2'), row['name_2']
        if kind not in ('Kabupaten','Kota','NA','Water Body'):
            raise ValueError('Unknown boundary type')
        if kind in ('Kabupaten','Kota') and not short.casefold().startswith(kind.casefold()+' '):
            short = kind+' '+short
        result[p,d] = {'name':short+', '+row['name_1'], 'short':short, 'original_name':row['name_2'],
            'gid':row['gid_2'], 'type':kind, 'province':row['name_1'], 'original_row':row}
    if len({d['name'].casefold() for d in result.values()}) != len(result):
        raise ValueError('Non-unique full district names')
    return result


def district_aliases(districts, provinces):
    candidates = defaultdict(set)
    reserved = {p['name'].casefold() for p in provinces.values()} | {'indonesia'}
    for d in districts.values():
        if d['type'] == 'Water Body':
            continue
        bare = re.sub(r'^(?:Kabupaten|Kota)\s+', '', d['short'], flags=re.I)
        for alias in (d['short'],bare,bare+', '+d['province'],d['short']+' '+d['province']):
            candidates[alias.casefold()].add(d['name'])
    # Never guess between a city and regency, or names shared by provinces.
    return {a:next(iter(names)) for a,names in candidates.items() if len(names)==1 and a not in reserved}


def reconcile_districts(parents, children):
    totals, sums = {}, defaultdict(Decimal)
    with localcontext() as ctx:
        ctx.prec = 60
        for r in parents:
            if r['adm1'] is not None:
                totals[r['adm1'],r['metric'],r['year']] = Decimal(r['value'])
        for r in children:
            sums[r['adm1'],r['metric'],r['year']] += Decimal(r['value'])
        differences = {f'{p}:{m}:{y}':str(abs(totals.get((p,m,y),Decimal(0))-sums.get((p,m,y),Decimal(0))))
            for p,m,y in sorted(totals.keys() | sums.keys())}
        bad = {k:v for k,v in differences.items() if Decimal(v)>Decimal('0.01')}
        if bad:
            raise ValueError('Province/district reconciliation exceeds 0.01 ha: '+str(bad))
    return differences


def publish(records, report):
    db = QdrantClient(url=QDRANT_URL,timeout=60)
    try:
        if db.collection_exists(COLLECTION) and db.count(COLLECTION,exact=True).count:
            raise ValueError('Snapshot already populated; not overwritten')
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
    target = DIRECTORY/'import-report.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(target)


def main(do_publish=False):
    # Do not rewrite a catalog already serving requests.
    if (DIRECTORY/'import-report.json').exists():
        raise ValueError('Published snapshot exists; no files overwritten')
    parent_report = json.loads((PARENT_DIRECTORY/'import-report.json').read_text())
    parents = [json.loads(line) for line in (PARENT_DIRECTORY/'records.jsonl').read_text().splitlines()]
    if parent_report['publication_status']!='published' or len(parents)!=parent_report['records']:
        raise ValueError('Parent snapshot is not published or count differs')
    reconcile(parents)
    key = os.environ.get('GFW_API_KEY') or json.loads((ROOT/'.local/gfw-credentials.json').read_text())['api_key']
    client = ArchiveClient(DIRECTORY,key)
    parent_client = ArchiveClient(PARENT_DIRECTORY,key)
    children = []
    try:
        directory, _ = parent_client.get('provinces',f'/dataset/gadm_administrative_boundaries/{BOUNDARY_VERSION}/download/json',
            "SELECT gid_0,gid_1,name_1,adm_level FROM data WHERE gid_0='IDN' AND adm_level='1' ORDER BY gid_1 LIMIT 100")
        provinces = province_directory(directory)
        rows,boundary_receipt = client.get('districts',f'/dataset/gadm_administrative_boundaries/{BOUNDARY_VERSION}/download/json',DIRECTORY_SQL)
        districts = district_directory(rows,provinces)
        version,_ = client.get('adm2-version',f'/dataset/gadm__tcl__adm2_change/{VERSION}')
        if version.get('status')!='saved' or version.get('is_mutable') is not False:
            raise ValueError('Version must be saved and immutable')
        client.get('adm2-fields',f'/dataset/gadm__tcl__adm2_change/{VERSION}/fields')
        for primary in (False,True):
            for year in range(2002 if primary else 2001,2026):
                name=f'adm2-{year}-'+('primary' if primary else 'loss-fire')
                rows,receipt = client.get(name,f'/dataset/gadm__tcl__adm2_change/{VERSION}/download/json',sql_for('adm2',primary,year=year))
                if any(r.get('umd_tree_cover_loss__year') != year for r in rows):
                    raise ValueError('Year partition mismatch')
                children.extend(normalize(rows,'adm2',primary,provinces,{'data':receipt,'boundaries':boundary_receipt},districts))
                print(name,len(rows),'source rows',flush=True)
    finally:
        client.client.close(); parent_client.client.close()
    differences = reconcile_districts(parents,children)
    excluded = [r for r in children if r['boundary_type']=='Water Body']
    added = [r for r in children if r['boundary_type']!='Water Body']
    for r in added:
        r['source_note'] += ' Kabupaten/kota mengikuti nama dan batas GADM 4.1, bukan daftar pemekaran terbaru.'
        if r['boundary_type']=='NA':
            r['source_note'] += ' Jenis kabupaten/kota tidak diisi oleh sumber untuk wilayah ADM2 ini.'
    records = parents+added
    for r in records:
        r['indicator'] = r['indicator'].replace('menurut provinsi dan nasional','menurut kabupaten/kota, provinsi dan nasional')
    if len({r['id'] for r in records})!=len(records):
        raise ValueError('Duplicate snapshot IDs')
    catalog = build_catalog(records)
    aliases = district_aliases(districts,provinces)
    for c in catalog:
        c['area_aliases'] = {a:target for a,target in aliases.items() if target in c['areas']}
    present = {(r['metric'],r['area'],r['year']) for r in added}
    missing = [{'area':d['name'],'metric':metric,'years':[y for y in range(2002 if metric=='primary_loss_ha' else 2001,2026)
        if (metric,d['name'],y) not in present]} for d in districts.values() if d['type']!='Water Body' for metric in METRICS]
    report = {**parent_report,'collection':COLLECTION,'records':len(records),'searchable_records':len(records),
        'district_records':len(added),'district_directory_count':sum(d['type']!='Water Body' for d in districts.values()),
        'districts_with_observations':len({r['area'] for r in added}),
        'district_boundary_types':{kind:sum(d['type']==kind for d in districts.values()) for kind in ('Kabupaten','Kota','NA','Water Body')},
        'province_district_absolute_differences_ha':differences,'excluded_water_body_records':len(excluded),
        'district_missing_observations_not_assumed_zero':[m for m in missing if m['years']],
        'publication_status':'validated','parent_directory':str(PARENT_DIRECTORY),
        'note':'GADM 4.1 source districts; water bodies archived but not searchable; NA type retained without guessing; missing rows never filled as zero.'}
    for name,rows in [('records',records),('excluded-water-bodies',excluded)]:
        (DIRECTORY/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False,default=str)+'\n' for r in rows))
    (DIRECTORY/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    (DIRECTORY/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if do_publish:
        publish(records,report)
    print(json.dumps({k:report[k] for k in ('records','district_records','district_directory_count','districts_with_observations','publication_status')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--publish',action='store_true')
    main(parser.parse_args().publish)
