"""Import all downloaded BPS evidence without pretending documents are numeric cells.

Build immutable numeric and source-document collections, verify every payload,
then publish a local trial pointer. No public provider or existing collection is deleted.
"""
import argparse,hashlib,json,sqlite3,uuid
from collections import Counter,defaultdict
from pathlib import Path
from qdrant_client import QdrantClient,models
from tools.bps.ingest import DEFAULT_DIR,normalize,write_json,now,BPSError
from tools.bps.national import national_rows
from tools.bps.observation import SCHEMA,unit_fields
from tools.bps.qdrant_import import fingerprint,verify,public_source,build_catalog
from tools.bps.brs import plain_text


def uid(text):return str(uuid.uuid5(uuid.NAMESPACE_URL,text))

def national_payload(r):
    """A commodity/sector is a measurement category, never a geographic member."""
    extra=[c for c in r['categories'] if c['axis']=='vervar']
    parts=[r['domain'],r['variable_id'],r['derived_id'],r['unit']]
    if extra:parts.append([(c['axis'],c['id']) for c in extra])
    indicator_id='bps-'+fingerprint(parts)[:24]
    meaningful=[c for c in r['categories'] if c['label'].strip().casefold() not in {'','tidak ada'}]
    indicator=r['variable']+''.join(' — '+plain_text(c['label']) for c in meaningful)
    pop={'urban':'urban','rural':'rural','urban_and_rural':'total'}.get(r.get('population_scope'))
    if pop is None:pop={'perkotaan':'urban','perdesaan':'rural'}.get(r['derived_label'].casefold(),'total')
    held=[]
    if r['status']!='observed':held.append(r['status'])
    if r['period_status']!='mapped':held.append(r['period_status'])
    if r.get('data_status')=='potential':held.append('potential_not_observed')
    if r.get('period_ended_at_retrieval') is False:held.append('period_not_ended_at_retrieval')
    try:units=unit_fields(r['unit'])
    except BPSError:units={'unit':r['unit'],'unit_source':r['unit'],'unit_code':'source_native','unit_scale':'1'}
    return {**r,**units,'id':uid('cekdata:bps:observation:'+r['id']),'source_record_id':r['id'],
        'schema_version':SCHEMA,'record_type':'observation' if not held else 'held_observation',
        'provider':'bps_api','indicator_id':indicator_id,'indicator':indicator,'title':r['variable'],
        'source':'Badan Pusat Statistik','source_name':'Badan Pusat Statistik','area':'Indonesia','area_key':'indonesia',
        'vertical_key':'indonesia','boundary_type':'Negara','province_context':'','population':pop,
        'population_label':{'urban':'Perkotaan','rural':'Perdesaan'}.get(pop,''),
        'category_id':'|'.join(c['axis']+':'+c['id'] for c in meaningful),
        'category_label':' — '.join(c['label'] for c in meaningful),
        'source_note':plain_text(r.get('notes','')),'method':'','synthetic':False,'usable':not held,
        'hold_reasons':held,'source_sha256':r['source_snapshot_sha256'],'download_url':'',
        'original_row':r,'source_locator':{k:r[k] for k in ['domain','variable_id','vertical_id','derived_id','period_id','subperiod_id','source_cell']}}


def read_national(root):
    plan=json.loads((root/'plan.json').read_text());tables={t['variable_id']:t for t in plan['tables']}
    db=sqlite3.connect(f'file:{root / "bps.sqlite3"}?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN')
        for imp in db.execute('select * from imports order by variable_id,period_id'):
            raw=(root/'raw'/(imp['sha256']+'.json')).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=imp['sha256']:raise BPSError('National raw checksum differs')
            d=json.loads(raw,parse_float=str);decoded,_=normalize(d,imp['domain'],imp['variable_id'],imp['period_id'],max_combinations=2000000)
            expected=national_rows(decoded,d,tables[imp['variable_id']],dict(imp),imp['source_url'])
            actual=[json.loads(x['record']) for x in db.execute('select record from observations where variable_id=? and period_id=?',(imp['variable_id'],imp['period_id']))]
            if {r['id']:r for r in expected}!={r['id']:r for r in actual}:raise BPSError('National SQLite differs from raw source')
            if not public_source(imp['source_url']):raise BPSError('Unsafe source URL')
            yield from (national_payload(r) for r in actual)
    finally:db.close()


def scroll_all(client,collection,**kwargs):
    offset=None
    while True:
        points,offset=client.scroll(collection,offset=offset,limit=256,with_payload=True,with_vectors=False,**kwargs)
        yield from (p.payload for p in points)
        if offset is None:break


def source_chunks(doc):
    """Exact reversible slices; original HTML retains all table cells and spans."""
    common={k:doc[k] for k in ['id','title','source_url','source_snapshot_sha256','source_type','retrieved_at']}
    common['document_id']=common.pop('id');common['publisher']='Badan Pusat Statistik'
    common.update(download_url=doc.get('download_url',''),source_url_verified=doc.get('source_url_verified',False),
                  ready_for_numeric_answers=False,usable=False)
    metadata={k:v for k,v in doc.items() if k not in {'html','text','search_text','tables'}}
    bodies={'metadata':json.dumps(metadata,ensure_ascii=False,sort_keys=True),'text':doc['text']}
    if 'html' in doc:bodies['html']=doc['html']
    for body_kind,text in bodies.items():
        size=40000 if body_kind!='text' else 12000
        for i,start in enumerate(range(0,max(1,len(text)),size)):
            fragment=text[start:start+size]
            point_id=uid(f"cekdata:bps:document:{doc['id']}:{body_kind}:{i}")
            yield {**common,'id':point_id,'record_type':body_kind+'_chunk','chunk_index':i,
                   'start_char':start,'end_char':start+len(fragment),('text' if body_kind=='text' else 'content'):fragment,
                   'text_sha256':hashlib.sha256(fragment.encode()).hexdigest(),
                   'body_sha256':hashlib.sha256(text.encode()).hexdigest()}


def verified_documents(root):
    for kind in ['brs','static']:
        directory=root/kind
        manifest=json.loads((directory/('manifest.json' if kind=='static' else 'brs-0000-2026-manifest.json')).read_text())
        expected=set(manifest['document_ids'] if kind=='brs' else [d['id'] for d in manifest['documents']])
        files={p.stem:p for p in (directory/'documents').glob('*.json')}
        if set(files)!=expected:raise BPSError('Document inventory differs from archive manifest')
        for ident in sorted(expected):
            doc=json.loads(files[ident].read_text());raw=(directory/'raw'/(doc['source_snapshot_sha256']+'.json')).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=doc['source_snapshot_sha256']:raise BPSError('Document raw checksum differs')
            body=json.loads(raw)['data']
            if kind=='static':
                if doc['html']!=body.get('table','') or doc['text']!=plain_text(doc['html']):raise BPSError('Static table differs from source')
            elif doc['text']!=plain_text(body.get('abstract')) or doc['title']!=plain_text(body['title']):raise BPSError('BRS text differs from source')
            if not public_source(doc['source_url']):raise BPSError('Unsafe document URL')
            yield doc


def import_file(client,path,name,hashes,indexes):
    existing=0
    if client.collection_exists(name):existing=verify(client,name,hashes,complete=False)
    else:client.create_collection(name,vectors_config={},on_disk_payload=True,
                                 optimizers_config=models.OptimizersConfigDiff(max_optimization_threads=1))
    batch=[];size=0;count=0
    def flush():
        nonlocal batch,size,count
        if batch:
            client.upsert(name,points=[models.PointStruct(id=p['id'],vector={},payload=p) for p in batch],wait=True)
            count+=len(batch);batch=[];size=0
    if existing!=len(hashes):
        with open(path) as f:
            for line in f:
                p=json.loads(line)
                if size+len(line)>1800000 or len(batch)>=256:flush()
                batch.append(p);size+=len(line)
            flush()
    existing_indexes=client.get_collection(name).payload_schema
    index_types={'keyword':models.KeywordIndexParams,'integer':models.IntegerIndexParams,
                 'bool':models.BoolIndexParams,'text':models.TextIndexParams}
    for field,schema in indexes:
        if field not in existing_indexes:
            client.create_payload_index(name,field_name=field,field_schema=index_types[schema](type=schema,on_disk=True),wait=True)
    verified=verify(client,name,hashes,complete=True)
    if client.count(name,exact=True).count!=verified:raise BPSError('Collection count differs')
    return verified


def build(root=DEFAULT_DIR,url='http://127.0.0.1:6333',activate=False):
    root=Path(root);out=root/'bundle';out.mkdir(exist_ok=True)
    client=QdrantClient(url=url,timeout=120)
    try:
        base_manifest_path=out/'base-manifest.json'
        if not base_manifest_path.exists():write_json(base_manifest_path,json.loads((root/'qdrant-current-manifest.json').read_text()))
        base=json.loads(base_manifest_path.read_text());rows=list(scroll_all(client,base['collection']))
        if len(rows)!=base['records'] or fingerprint({p['id']:fingerprint(p) for p in rows})!=base['snapshot_sha256']:raise BPSError('Base snapshot differs from verified manifest')
        merged={p['source_record_id']:p for p in rows};base_count=len(merged);overrides=0;national_count=0
        for p in read_national(root/'national-2019-2026'):
            national_count+=1;overrides+=p['source_record_id'] in merged;merged[p['source_record_id']]=p
        rows=sorted(merged.values(),key=lambda p:p['id']);numeric_hashes={p['id']:fingerprint(p) for p in rows}
        numeric_name='cekdata_bps_all_'+fingerprint(numeric_hashes)[:14]
        with open(out/'observations.jsonl','w') as f:
            for p in rows:f.write(json.dumps(p,ensure_ascii=False)+'\n')
        catalog=build_catalog([p for p in rows if p.get('usable')]);by_id={p['indicator_id']:p for p in rows if p.get('usable')}
        for e in catalog:e['label']=by_id[e['indicator_id']]['indicator']
        catalog_path=root/(numeric_name+'-catalog.json');write_json(catalog_path,catalog)
        doc_hashes={};inventory=[]
        with open(out/'documents.jsonl','w') as f:
            for doc in verified_documents(root):
                counts=Counter()
                for p in source_chunks(doc):
                    doc_hashes[p['id']]=fingerprint(p);f.write(json.dumps(p,ensure_ascii=False)+'\n');counts[p['record_type']]+=1
                inventory.append({'id':doc['id'],'title':doc['title'],'source_type':doc['source_type'],'source_url':doc['source_url'],'download_url':doc.get('download_url',''),'chunks':dict(counts),'source_snapshot_sha256':doc['source_snapshot_sha256']})
        doc_name='cekdata_bps_documents_'+fingerprint(doc_hashes)[:14]
        write_json(out/'document-inventory.json',inventory)
        indexes=[(k,'keyword') for k in ['indicator_id','area_key','variable_id','source','population','record_type']]+[('year','integer'),('usable','bool')]
        print(json.dumps({'stage':'importing','numeric_points':len(rows),'document_points':len(doc_hashes),'documents':len(inventory)}),flush=True)
        n=import_file(client,out/'observations.jsonl',numeric_name,numeric_hashes,indexes)
        print(json.dumps({'stage':'numeric_verified','points':n}),flush=True)
        d=import_file(client,out/'documents.jsonl',doc_name,doc_hashes,[(k,'keyword') for k in ['document_id','source_type','record_type']]+[('text','text'),('title','text')])
        manifest={'schema':SCHEMA,'status':'verified','collection':numeric_name,'catalog_file':catalog_path.name,
            'records':n,'snapshot_sha256':fingerprint(numeric_hashes),'verified_payloads':n,'years':sorted({p['year'] for p in rows}),
            'base_records':base_count,'national_records':national_count,'overlapping_source_records_replaced':overrides,
            'usable_records':sum(bool(p.get('usable')) for p in rows),'held_records':sum(not p.get('usable') for p in rows),
            'hold_reasons':dict(Counter(x for p in rows for x in p.get('hold_reasons',[]))),
            'source_tables':len({(p['domain'],p['variable_id']) for p in rows}),'catalog_entries':len(catalog),
            'document_collection':doc_name,'document_points':d,'document_snapshot_sha256':fingerprint(doc_hashes),
            'documents':len(inventory),'document_types':dict(Counter(x['source_type'] for x in inventory)),
            'document_retrieval':'full text and original source reconstruction; not numeric observations',
            'completed_at':now(),'chat_provider_activated':False,'public_provider_changed':False}
        write_json(out/'manifest.json',manifest)
        if activate:
            previous=json.loads((root/'qdrant-current-manifest.json').read_text());write_json(root/(previous['collection']+'-manifest.json'),previous)
            write_json(root/'qdrant-current-manifest.json',manifest)
        print(json.dumps(manifest,ensure_ascii=False),flush=True);return manifest
    finally:client.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--activate-trial',action='store_true');args=p.parse_args()
    build(activate=args.activate_trial)
