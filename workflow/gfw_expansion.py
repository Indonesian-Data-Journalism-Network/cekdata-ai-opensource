"""Auditable Indonesia carbon, habitat and planted-tree statistics from pinned GFW tables.

Fetch/validate before publication. Original API responses and receipts remain on disk.
No concession data, alerts, inferred 2026 values, or interpolated annual habitat areas.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, localcontext
import json
from pathlib import Path
import uuid
from collections import defaultdict
from datetime import datetime, timezone
import shutil
import httpx
import hashlib
import os

from flow import Evidence

from gfw_data import ArchiveClient, BASE, ROOT, province_directory
from gfw_district_data import district_directory, district_aliases

DIRECTORY = ROOT / 'data/gfw-expansion'
CARBON_VERSION = 'v20260327'
TABLE_VERSION = 'v20260424'
TREE_TYPES = {
    'Oil palm': ('oil-palm', 'Luas tanaman sawit yang dipetakan'),
    'Oil palm mix': ('oil-palm-mix', 'Luas tanaman campuran sawit yang dipetakan'),
    'Wood fiber or timber': ('planted-forest', 'Luas hutan tanaman kayu dan serat yang dipetakan'),
    'Wood fiber or timber mix': ('planted-forest-mix', 'Luas campuran hutan tanaman kayu dan serat yang dipetakan'),
    'Rubber': ('rubber', 'Luas tanaman karet yang dipetakan'),
    'Rubber mix': ('rubber-mix', 'Luas tanaman campuran karet yang dipetakan'),
    'Fruit': ('fruit', 'Luas tanaman buah yang dipetakan'),
    'Fruit mix': ('fruit-mix', 'Luas tanaman campuran buah yang dipetakan'),
    'Other': ('other-planted-trees', 'Luas tanaman pohon lainnya yang dipetakan'),
    'Unknown': ('unknown-planted-trees', 'Luas tanaman pohon dengan jenis tidak diketahui'),
}
CARBON_FIELDS = {
    'emissions': 'gfw_full_extent_gross_emissions_biomass_soil__Mg_CO2e',
    'removals': 'gfw_full_extent_gross_removals__Mg_CO2',
    'net': 'gfw_full_extent_net_flux__Mg_CO2e',
}


def dims(level):
    return ['iso'] + (['adm1'] if level != 'iso' else []) + (['adm2'] if level == 'adm2' else [])


def query(kind, level, province=None):
    columns = dims(level)
    where = ["iso = 'IDN'", 'umd_tree_cover_density_2000__threshold = 30']
    if province is not None:
        where.append(f"adm1 = '{int(province)}'")
    if kind == 'summary':
        dataset, version = f'carbonflux_{level}_summary', CARBON_VERSION
        sums = [f'SUM(CASE WHEN is__flux_model_extent THEN "{field}" ELSE 0 END) AS {alias}' for alias,field in CARBON_FIELDS.items()]
        # Keep the full land partition, including non-forest cells, for habitat extent.
        sums += ['SUM(area__ha) AS total_area_ha',
                 'SUM(CASE WHEN is__gfw_peatlands THEN area__ha ELSE 0 END) AS peat_ha',
                 'SUM(CASE WHEN is__gmw_global_mangrove_extent_2020 THEN area__ha ELSE 0 END) AS mangrove_ha']
    elif kind == 'annual':
        dataset, version = f'carbonflux_{level}_change', CARBON_VERSION
        columns += ['umd_tree_cover_loss__year']
        where += ['is__flux_model_extent = true', 'umd_tree_cover_loss__year >= 2001', 'umd_tree_cover_loss__year <= 2025']
        sums = [f'SUM("{CARBON_FIELDS["emissions"]}") AS emissions']
    elif kind == 'plantations':
        dataset, version = f'gadm__tcl__{level}_summary', TABLE_VERSION
        sums = ['SUM(area__ha) AS total_area_ha'] + [
            f"SUM(CASE WHEN gfw_planted_forests__type = '{name}' THEN area__ha ELSE 0 END) AS type_{i}"
            for i,name in enumerate(TREE_TYPES)]
    else:
        raise ValueError('Unknown dataset kind')
    sql = ('SELECT '+', '.join(columns+sums)+' FROM data WHERE '+' AND '.join(where)
           +' GROUP BY '+', '.join(columns)+' ORDER BY '+', '.join(columns)+' LIMIT 20001')
    return dataset,version,sql


def fetch(kind, level, province=None):
    key=json.loads((ROOT/'.local/gfw-credentials.json').read_text())['api_key']
    client=ArchiveClient(DIRECTORY,key)
    ds,v,sql=query(kind,level,province)
    name=f'{kind}-{level}'+(f'-{province}' if province is not None else '')
    try:
        rows,receipt=client.get(name,f'/dataset/{ds}/{v}/download/json',sql)
        if not isinstance(rows,list) or not rows or len(rows)>=20001:
            raise ValueError('Empty or truncated table: '+name)
        print(f'{name}: {len(rows)} rows',flush=True)
        return {'kind':kind,'level':level,'dataset':ds,'version':v,'rows':rows,'receipt':receipt}
    finally:
        client.client.close()


def download():
    results,failed=[],[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks={pool.submit(fetch,k,l):(k,l) for k in ['summary','annual','plantations'] for l in ['iso','adm1','adm2']}
        for future in as_completed(tasks):
            k,l=tasks[future]
            try: results.append(future.result())
            except RuntimeError as exc:
                if l=='iso' or 'HTTP 504' not in str(exc): raise
                failed.append((k,l))
                print(f'{k}-{l}: splitting request by province after timeout',flush=True)
    if failed:
        with ThreadPoolExecutor(max_workers=3) as pool:
            province_codes=sorted(boundaries()[0])
            tasks=[pool.submit(fetch,k,l,p) for k,l in failed for p in province_codes]
            for future in as_completed(tasks): results.append(future.result())
    path=DIRECTORY/'downloaded.json'
    path.write_text(json.dumps(results,ensure_ascii=False,default=str)+'\n')
    return results


def boundaries():
    def raw(path):
        obj=json.loads(path.read_text())
        return obj['data'] if isinstance(obj,dict) else obj
    provinces=province_directory(raw(ROOT/'data/gfw/raw/provinces.json'))
    districts=district_directory(raw(ROOT/'data/gfw-adm2/raw/districts.json'),provinces)
    return provinces,districts


def location(row, level):
    if row['iso']!='IDN': raise ValueError('Unexpected country')
    return (int(row['adm1']) if level!='iso' else None,
            int(row['adm2']) if level=='adm2' else None)


def close(a,b):
    # Source rasters use floating point. Tolerance is relative to the large gross
    # flux, never to a nearly zero net flux, and always reported in the receipt.
    return abs(a-b) <= max(Decimal('0.1'),max(abs(a),abs(b))*Decimal('0.000001'))


def validate(tables):
    groups=defaultdict(dict)
    for table in tables:
        kind,level=table['kind'],table['level']
        for row in table['rows']:
            p,d=location(row,level)
            year=int(row['umd_tree_cover_loss__year']) if kind=='annual' else None
            key=(p,d,year)
            if key in groups[kind,level]: raise ValueError('Duplicate statistical cell')
            for field,value in row.items():
                if field in ('iso','adm1','adm2','umd_tree_cover_loss__year'): continue
                if value is None or not Decimal(str(value)).is_finite(): raise ValueError('Missing/nonfinite statistic')
                if field not in ('net','removals') and Decimal(str(value))<0: raise ValueError('Unexpected negative statistic')
            groups[kind,level][key]=row
    checks=[]
    with localcontext() as ctx:
        ctx.prec=60
        for kind in ['summary','annual','plantations']:
            for child,parent in [('adm2','adm1'),('adm1','iso')]:
                sums=defaultdict(lambda:defaultdict(Decimal))
                for (p,d,y),row in groups[kind,child].items():
                    key=(p,None,y) if parent=='adm1' else (None,None,y)
                    for field,value in row.items():
                        if field not in ('iso','adm1','adm2','umd_tree_cover_loss__year'):
                            sums[key][field]+=Decimal(str(value))
                if set(sums)!=set(groups[kind,parent]): raise ValueError('Parent/child coverage mismatch: '+kind)
                worst=Decimal(0)
                for key,row in groups[kind,parent].items():
                    for field,value in sums[key].items():
                        expected=Decimal(str(row[field]));worst=max(worst,abs(expected-value))
                        if not close(expected,value): raise ValueError(f'Hierarchy mismatch {kind} {key} {field}')
                checks.append({'kind':kind,'child':child,'parent':parent,'max_absolute_difference':str(worst)})
        for level in ['iso','adm1','adm2']:
            annual=defaultdict(Decimal)
            for (p,d,y),row in groups['annual',level].items():
                if not 2001<=y<=2025: raise ValueError('Unexpected carbon year')
                annual[p,d]+=Decimal(str(row['emissions']))
            for (p,d,_),row in groups['summary',level].items():
                e,r,n=[Decimal(str(row[k])) for k in ['emissions','removals','net']]
                if abs(e-r-n)>max(Decimal('.1'),max(abs(e),abs(r))*Decimal('.000001')):
                    raise ValueError('Net carbon does not reconcile with gross fluxes')
                if not close(e,annual[p,d]): raise ValueError(f'Annual/cumulative emissions mismatch {level} {p} {d}')
                area=Decimal(str(row['total_area_ha']))
                if any(Decimal(str(row[k]))>area for k in ['peat_ha','mangrove_ha']):
                    raise ValueError('Habitat area exceeds land area')
                planted=groups['plantations',level].get((p,d,None))
                if not planted or not close(area,Decimal(str(planted['total_area_ha']))):
                    raise ValueError('Habitat table is not the complete land partition')
                if sum((Decimal(str(planted[f'type_{i}'])) for i in range(len(TREE_TYPES))),Decimal(0))>area+Decimal('.01'):
                    raise ValueError('Plantation classes exceed land area')
    return checks


CARBON_PAGE='https://globalnaturewatch.org/blog/data-and-tools/whats-new-carbon-flux-monitoring/'
SDPT_PAGE='https://www.wri.org/research/spatial-database-planted-trees-sdpt-version-2'
BOUNDARY_NOTE='Batas GADM 4.1, 34 provinsi sumber; tidak mengikuti pemekaran provinsi terbaru.'


def normalize(tables):
    provinces,districts=boundaries()
    records=[]
    def add(table,row,metric,label,value,unit,year,definition,source,page,*,basis='annual',kind='annual_flow',period='',start='',end='',upstream=None):
        p,d=location(row,table['level'])
        district=districts[p,d] if d is not None else None
        area=district['name'] if district else provinces[p]['name'] if p else 'Indonesia'
        ds,v=table['dataset'],table['version']
        identity=f'gfw:{ds}:{v}:IDN:{p}.{d}:{year}:t30:{metric}'
        api=f'{BASE}/dataset/{ds}/{v}'
        evidence=Evidence(id=str(uuid.uuid5(uuid.NAMESPACE_URL,identity)),indicator_id='gfw-'+metric,
            indicator=label,area=area,year=year,value=str(value),unit=unit,source=source,source_name=source,
            title=label+' — GFW '+v,source_url=page,methodology_url=page,api_source_url=api,
            download_url=table['receipt']['url'],definition=definition,method=f'GFW {v}; GADM 4.1; '+definition,
            source_record_id=identity,source_note=definition+' '+BOUNDARY_NOTE,
            province_context=provinces[p]['name'] if p else '',period_text=period,
            temporal_basis=basis,aggregation_kind=kind,period_start=start,period_end=end)
        records.append({**evidence.model_dump(), 'provider':'gfw', 'usable':not district or district['type']!='Water Body',
            'area_key':area.casefold(),'adm1':p,'adm2':d,'geographic_level':table['level'],
            'boundary_gid':district['gid'] if district else provinces[p]['gid'] if p else 'IDN',
            'boundary_version':'v4.1','dataset':ds,'dataset_version':v,'upstream_dataset':upstream,
            'source_sql':table['receipt']['sql'],'source_provenance':table['receipt'],'original_row':row,
            'data_status':'annual_published' if basis=='annual' else basis,'canopy_threshold':30 if metric.startswith('carbon-') else None})
    with localcontext() as ctx:
        ctx.prec=60
        for table in tables:
            for row in table['rows']:
                if table['kind']=='annual':
                    y=int(row['umd_tree_cover_loss__year'])
                    add(table,row,'carbon-emissions','Emisi gas rumah kaca hutan tahunan',row['emissions'],'ton CO2e',y,
                        'Emisi bruto terkait gangguan pengganti tegakan; semua gas dan karbon biomassa serta tanah. Model hutan, ambang tajuk 30%; bukan seluruh emisi wilayah.',
                        'Global Forest Watch / WRI',CARBON_PAGE,start=f'{y}-01-01',end=f'{y}-12-31')
                elif table['kind']=='summary':
                    labels={'emissions':('emissions','emisi gas rumah kaca hutan','ton CO2e'),
                            'removals':('removals','penyerapan karbon hutan','ton CO2'),
                            'net':('net-flux','neraca bersih gas rumah kaca hutan','ton CO2e')}
                    for field,(slug,label,unit) in labels.items():
                        definition=('Model karbon 2001–2025, ambang tajuk 30%. Emisi bruto dikurangi penyerapan menghasilkan neraca bersih; '
                            'neraca positif berarti sumber emisi bersih, negatif berarti penyerap bersih. Penyerapan ditampilkan sebagai besaran positif. '
                            'Nilai penyerapan dan neraca tidak tersedia sebagai pengamatan tahun tunggal.')
                        for mean in [False,True]:
                            metric='carbon-'+slug+('-period-mean' if mean else '-period-total')
                            add(table,row,metric,('Rata-rata tahunan ' if mean else 'Total ')+label+' periode 2001–2025',
                                Decimal(str(row[field]))/(25 if mean else 1),unit+('/tahun' if mean else ''),2025,
                                definition+(' Rata-rata dihitung dari total dibagi 25 tahun.' if mean else ''),
                                'Global Forest Watch / WRI',CARBON_PAGE,basis='model_period',kind='period_mean' if mean else 'period_total',
                                period='2001–2025'+(' (rata-rata tahunan)' if mean else ' (total periode)'),start='2001-01-01',end='2025-12-31')
                    add(table,row,'mangrove-extent','Luas mangrove yang dipetakan',row['mangrove_ha'],'ha',2020,
                        'Luas area berlabel mangrove GMW v3, acuan 2020; agregasi raster GFW menurut GADM 4.1 mencakup seluruh area, bukan hanya tajuk pohon 30%. Bukan pengamatan 2025/2026.',
                        'Global Forest Watch / Global Mangrove Watch','https://zenodo.org/records/6894273',basis='baseline',kind='extent',
                        period='2020 (tahun acuan peta)',upstream={'dataset':'gmw_global_mangrove_extent','version':'v3'})
                    add(table,row,'peatland-extent','Luas gambut dalam peta gabungan',row['peat_ha'],'ha',2023,
                        'Luas peta gambut gabungan berbagai tahun, versi v20230315. Indonesia memakai Miettinen 2016 (peta lahan 2015) dan Gumbricht 2017. Tahun 2023 adalah versi peta, bukan pengamatan 2023. Agregasi seluruh area raster menurut GADM 4.1.',
                        'Global Forest Watch / penyedia peta gambut','https://globalnaturewatch.org/map/?modalMeta=gfw_peatlands',basis='map_version',kind='extent',
                        period='Peta gabungan berbagai tahun (versi 2023)',upstream={'dataset':'gfw_peatlands','version':'v20230315'})
                else:
                    for i,(category,(slug,label)) in enumerate(TREE_TYPES.items()):
                        add(table,row,'sdpt-'+slug,label,row[f'type_{i}'],'ha',2020,
                            f'Kelas SDPT "{category}"; acuan global 2020, tahun dan metode sumber lokal beragam. Luas kelas raster dalam ringkasan GFW, bukan luas izin konsesi atau statistik perkebunan tahunan. Kelas campuran disajikan terpisah dan tidak seluruhnya merupakan tanaman tunggal.',
                            'Global Forest Watch / WRI (SDPT)',SDPT_PAGE,basis='baseline',kind='extent',period='2020 (acuan SDPT; tahun sumber beragam)',
                            upstream={'dataset':'gfw_planted_forests','version':'v20231128'})
    if len({r['id'] for r in records})!=len(records): raise ValueError('Duplicate evidence ID')
    flagged={(r['adm1'],r['adm2']) for r in records
             if r['indicator_id']=='gfw-carbon-removals-period-total' and Decimal(r['value'])<0}
    for r in records:
        if r['indicator_id'].startswith(('gfw-carbon-removals-','gfw-carbon-net-flux-')):
            if (r['adm1'],r['adm2']) in flagged:
                r['usable']=False
                r['unusable_reason']='Nilai penyerapan sumber negatif; penyerapan dan neraca ditahan untuk pemeriksaan. Angka asli tidak diubah.'
            elif r['adm2'] is None and (r['adm1'] is None or any(p==r['adm1'] for p,d in flagged)):
                r['source_note']+=' Total resmi sumber mencakup dua kabupaten Papua dengan anomali penyerapan negatif; observasi kabupaten terkait ditahan dari pencarian.'
    return records


def build():
    report_path=DIRECTORY/'import-report.json'
    if report_path.exists() and json.loads(report_path.read_text()).get('publication_status')=='published':
        raise ValueError('Published expansion cannot be rebuilt in place')
    tables=json.loads((DIRECTORY/'downloaded.json').read_text())
    checks=validate(tables)
    records=normalize(tables)
    provinces,districts=boundaries()
    aliases=district_aliases(districts,provinces)
    catalog={}
    for r in records:
        if not r['usable']:continue
        c=catalog.setdefault(r['indicator_id'],{'indicator_id':r['indicator_id'],'label':r['indicator'],
            'source':r['source'],'unit':r['unit'],'definition':r['definition'],'areas':set(),'years':set(),
            'populations':['total'],'area_aliases':aliases})
        c['areas'].add(r['area']);c['years'].add(r['year'])
    catalog=[{k:sorted(v) if isinstance(v,set) else v for k,v in c.items()} for c in catalog.values()]
    (DIRECTORY/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,default=str)+'\n' for r in records))
    (DIRECTORY/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    report={'publication_status':'validated','records':len(records),'searchable_records':sum(r['usable'] for r in records),
        'catalog_entries':len(catalog),'province_count':len(provinces),'district_count':len(districts),
        'validated_at':datetime.now(timezone.utc).isoformat(),'reconciliation':checks,
        'temporal_notes':'Emissions 2001–2025; carbon period 2001–2025; mangrove baseline 2020; peat mixed-year map version 2023; SDPT nominal baseline 2020. No 2026 observations.',
        'excluded':'Restricted Indonesia concessions; near-real-time alerts.',
        'quarantined_observations':[{'id':r['id'],'area':r['area'],'indicator':r['indicator'],'value':r['value'],'reason':r['unusable_reason']}
                                   for r in records if r.get('unusable_reason')],
        'missing_annual_policy':'No row is created for missing years. Missing observations are not assumed to be zero.',
        'indicators':[{k:c[k] for k in ['indicator_id','label','years','unit']} for c in catalog]}
    (DIRECTORY/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['records','searchable_records','catalog_entries','publication_status']}),flush=True)
    return records,catalog,report


def publish():
    from qdrant_client import QdrantClient, models
    from gfw_district_data import DIRECTORY as active, COLLECTION
    from settings import QDRANT_URL
    report=json.loads((DIRECTORY/'import-report.json').read_text())
    if report['publication_status']=='published':
        print('Expansion already published; no changes.',flush=True)
        return
    if report['publication_status']!='validated': raise ValueError('Validation required')
    records=[json.loads(line) for line in (DIRECTORY/'records.jsonl').read_text().splitlines()]
    extra_catalog=json.loads((DIRECTORY/'catalog.json').read_text())
    lock=DIRECTORY/'publication.lock'
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.close(fd)
    client=QdrantClient(url=QDRANT_URL,timeout=60)
    try:
        backup=DIRECTORY/'base-backup';backup.mkdir(exist_ok=True)
        for name in ['records.jsonl','catalog.json','import-report.json']:
            if not (backup/name).exists():shutil.copy2(active/name,backup/name)
        base_report=json.loads((backup/'import-report.json').read_text())
        base_catalog=json.loads((backup/'catalog.json').read_text())
        base_ids=set()
        with (backup/'records.jsonl').open() as src:
            for line in src:base_ids.add(json.loads(line)['id'])
        if len(base_ids)!=base_report['records'] or base_ids & {r['id'] for r in records}:
            raise ValueError('Original snapshot count/ID collision')
        current_report=json.loads((active/'import-report.json').read_text())
        if current_report.get('expansion_import') not in (None,str(DIRECTORY)):
            raise ValueError('Unexpected concurrent import')
        for offset in range(0,len(records),100):
            client.upsert(COLLECTION,points=[models.PointStruct(id=r['id'],vector={},payload=r) for r in records[offset:offset+100]],wait=True)
        total=len(base_ids)+len(records)
        if client.count(COLLECTION,exact=True).count!=total:raise ValueError('Qdrant count mismatch')
        # Verify complete persisted payloads, not just collection counts.
        for offset in range(0,len(records),200):
            batch=records[offset:offset+200]
            found={str(p.id):p.payload for p in client.retrieve(COLLECTION,ids=[r['id'] for r in batch],with_payload=True,with_vectors=False)}
            if any(found.get(r['id'])!=r for r in batch):raise ValueError('Qdrant payload mismatch')
        merged=active/'records.jsonl.tmp'
        with merged.open('wb') as dest:
            for path in [backup/'records.jsonl',DIRECTORY/'records.jsonl']:
                with path.open('rb') as src:shutil.copyfileobj(src,dest)
        merged.replace(active/'records.jsonl')
        combined_catalog=base_catalog+extra_catalog
        if len({c['indicator_id'] for c in combined_catalog})!=len(combined_catalog):raise ValueError('Catalog collision')
        combined_report={**base_report,'records':total,
            'searchable_records':base_report.get('searchable_records',base_report['records'])+report['searchable_records'],
            'catalog_entries':len(combined_catalog),'expansion_import':str(DIRECTORY),
            'base_records':base_report['records'],'expansion_records':len(records),
            'publication_status':'published','updated_at':datetime.now(timezone.utc).isoformat(),
            'base_snapshot_sha256':hashlib.sha256((backup/'records.jsonl').read_bytes()).hexdigest(),
            'years':{c['indicator_id']:c['years'] for c in combined_catalog},
            'dataset_versions':['v20260424','v20260327'],'temporal_notes':report['temporal_notes']}
        for name,value in [('import-report.json',combined_report),('catalog.json',combined_catalog)]:
            temp=active/(name+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(active/name)
        report.update(publication_status='published',collection=COLLECTION,published_at=combined_report['updated_at'])
        (DIRECTORY/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'added':len(records),'searchable_added':report['searchable_records'],'total':total,'indicators_added':len(extra_catalog)}),flush=True)
    finally:
        client.close();lock.unlink()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    publish() if args.publish else build() if args.build else download()
