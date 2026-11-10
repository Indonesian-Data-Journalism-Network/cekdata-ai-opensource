"""Acquire reviewed national BPS series, keeping five source dimensions intact.

This is a separate store: no regional observations or active collection are replaced.
Scope review belongs to the acquisition plan, not to question-specific answer rules.
"""
import argparse,base64,csv,hashlib,json,os,re,shutil,sqlite3,unicodedata
from collections import Counter
from pathlib import Path
from tools.bps.client import BPSClient,BPSError
from tools.bps.ingest import Archive,Store,normalize,ROOT,DEFAULT_DIR,now,write_json,digest
from tools.bps.brs import plain_text
from tools.bps.observation import period_fields

COUNTRY_LABELS={'indonesia','nasional','indonesia/indonesia'}


def label(value):
 return re.sub(r'\s+',' ',plain_text(str(value or ''))).strip().casefold()


class ReusingArchive(Archive):
 def __init__(self,*args,cache_roots=(),**kwargs):
  super().__init__(*args,**kwargs);self.cache_roots=[Path(p) for p in cache_roots]
 def get(self,path,params=None):
  request={'path':path,'params':params or {}};name=digest(json.dumps(request,sort_keys=True).encode())
  target=self.root/'requests'/(name+'.json')
  if not self.refresh and not target.exists():
   for root in self.cache_roots:
    src=root/'requests'/(name+'.json')
    if not src.exists():continue
    saved=json.loads(src.read_text())
    if saved.get('retrieved_at','')[:10]!=now()[:10]:continue
    raw=(root/'raw'/(saved['sha256']+'.json')).read_bytes()
    if digest(raw)!=saved['sha256']:raise BPSError('Checksum cache tidak cocok.')
    (self.root/'raw').mkdir(exist_ok=True)
    (self.root/'raw'/(saved['sha256']+'.json')).write_bytes(raw);write_json(target,saved);break
  return super().get(path,params)


def public_url(variable,title):
 token=base64.b64encode(f'{variable}#2'.encode()).decode()
 slug=re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',plain_text(title)).encode('ascii','ignore').decode().lower()).strip('-')
 return f'https://www.bps.go.id/id/statistics-table/2/{token}/{slug}.html'


def country_scope(data,table):
 """Use an explicit country member, or a reviewed non-geographic source table."""
 candidates=[]
 for axis in ['vervar','turvar']:
  ids={str(x['val']) for x in data.get(axis,[]) if label(x.get('label')) in COUNTRY_LABELS}
  if ids:candidates.append((axis,ids,'explicit_country_member'))
 if len(candidates)==1:return candidates[0]
 if len(candidates)>1:raise BPSError('Lebih dari satu sumbu memuat Indonesia; perlu tinjauan.')
 review=table.get('national_scope_review') or {}
 if review.get('mode')=='member' and review.get('reviewed') is True and review.get('evidence'):
  axis=review.get('axis')
  if axis not in {'vervar','turvar'}:raise BPSError('Sumbu tinjauan anggota tidak valid.')
  if label(data.get('labelvervar'))!=label(review.get('vertical_axis')):raise BPSError('Sumbu geografis berubah dari tinjauan.')
  actual={str(x['val']):x['label'] for x in data[axis]};members=review.get('members') or []
  if not members or any(actual.get(str(m['id']))!=m['label'] for m in members):raise BPSError('Anggota nasional berubah dari tinjauan.')
  return axis,{str(m['id']) for m in members},'reviewed_source_country_member'
 if review.get('mode')=='whole_table' and review.get('reviewed') is True:
  if label(data.get('labelvervar')) != label(review.get('vertical_axis')):
   raise BPSError('Sumbu sumber berubah dari tinjauan nasional.')
  expected=review.get('vertical_members')
  actual=[{'id':str(x['val']),'label':x['label']} for x in data.get('vervar',[])]
  if actual not in review.get('vertical_member_variants',[expected]):raise BPSError('Kategori sumber berubah dari tinjauan nasional.')
  if not review.get('evidence'):raise BPSError('Tinjauan cakupan nasional belum memiliki dasar.')
  return 'whole_table',set(),'reviewed_national_table'
 raise BPSError('Tidak ditemukan baris Indonesia; cakupan tabel perlu ditinjau.')


def national_rows(rows,data,table,saved,url):
 axis,ids,origin=country_scope(data,table)
 output=[]
 for r in rows:
  if axis=='vervar' and r['vertical_id'] not in ids:continue
  if axis=='turvar' and r['derived_id'] not in ids:continue
  row=dict(r)
  year=int(r['year_label'])
  row.update(area='Indonesia',geographic_level='adm0',area_code='IDN',area_code_system='ISO3166-1',
    national_scope_origin=origin,national_filter_axis=axis,source_url=url,
    population_scope=table.get('population_scope_review','see_source_categories'),
    source_url_origin='constructed_from_official_variable_id',source_url_verified=False,
    source_name='Badan Pusat Statistik',source_snapshot_sha256=saved['sha256'],retrieved_at=saved['retrieved_at'],
    topics=table['topics'],year=year,
    categories=[{'axis':a,'id':r[i],'label':r[l]} for a,i,l in [('vervar','vertical_id','vertical_label'),('turvar','derived_id','derived_label')]
                if a!=axis],
    usable_for_answers=False,source_dimensions_preserved=True)
  # Keep source unit as given; heterogeneous or absent units stay held.
  if label(r['unit']) in {'satuan komoditas','tidak ada satuan',''} and row['status']=='observed':row['status']='missing_unit'
  if row['status']=='missing_unit':
   # Only explicit unit suffixes in source categories, never inferred from values.
   units={'ha':'Hektar','ku/ha':'Kuintal/Hektar','ton':'Ton','kg':'Kilogram','gram':'Gram','liter':'Liter','ons':'Ons','butir':'Butir','buah':'Buah','batang':'Batang','bungkus':'Bungkus','porsi':'Porsi','gelas':'Gelas','kalori':'Kalori','kkal':'Kilokalori'}
   candidates=[]
   for field in ['vertical_label','derived_label']:
    match=re.search(r'\(([^()]*)\)\s*$',plain_text(r[field]))
    if match and label(match[1]) in units:candidates.append((units[label(match[1])],field))
   if candidates and len({u for u,f in candidates})==1:
    row.update(unit=candidates[0][0],unit_origin='explicit_source_category_suffix',unit_source_field=candidates[0][1],status='observed')
  override=table.get('unit_review') or {}
  if row['status']=='missing_unit' and override.get('reviewed') and override.get('evidence') and override.get('unit'):
   row.update(unit=override['unit'],unit_origin='reviewed_source_concept',unit_review_evidence=override['evidence'],status='observed')
  try:
   row.update(period_fields(year,r['subperiod_label']));row['period_status']='mapped'
  except BPSError:
   row.update(period_text=f"{r['subperiod_label']} {year}",period_status='unmapped_source_label')
  retrieval_date=saved['retrieved_at'][:10]
  row['period_ended_at_retrieval']=(row['period_end']<=retrieval_date if row.get('period_end') and re.fullmatch(r'\d{4}-\d{2}-\d{2}',retrieval_date) else None)
  notes=plain_text(r.get('notes') or '')
  note=re.search(r'(?:Tahun\s+)?'+str(year)+r'\s*:\s*([^\n]+)',notes,re.I)
  year_note=note[1].strip() if note else ''
  row.update(data_status='provisional' if re.search(r'\bsementara\b',year_note,re.I) else 'published_status_unspecified',data_status_note=year_note)
  if row.get('temporal_basis')=='month':
   month_name=row['period_text'].rsplit(' ',1)[0]
   month_note=re.search(r'\b'+re.escape(month_name)+r'\s+'+str(year)+r'\s+(?:adalah\s+)?(angka\s+(?:(?:sangat\s+)*sementara|tetap))\b',notes,re.I)
   if month_note:
    row.update(data_status='provisional' if 'sementara' in month_note[1].casefold() else 'final',data_status_note=month_note[0])
   # Unqualified notes can be shared across API years. Apply a reviewed month
   # range only to its reviewed observation year and exact source wording.
   status_review=table.get('period_status_review') or {}
   if status_review.get('reviewed') and status_review.get('evidence'):
    for rule in status_review.get('rules',[]):
     if rule['year']==year and rule['first_month']<=row['month']<=rule['last_month']:
      if rule['source_note'] not in notes:raise BPSError('Catatan status periode berubah dari tinjauan.')
      if rule['status'] not in {'provisional','potential','final'}:raise BPSError('Status periode tinjauan tidak valid.')
      row.update(data_status=rule['status'],data_status_note=rule['source_note'])
  output.append(row)
 return output


def acquire(archive,plan):
 db=Store(archive.root/'bps.sqlite3');results=[];holds=[];period_catalog={}
 tables=[t for t in plan['tables'] if t.get('selected',True)]
 try:
  for index,table in enumerate(tables,1):
   var=str(table['variable_id']);url=public_url(var,table['title'])
   periods,_=archive.list('list/model/th/domain/0000',{'var':var})
   available=[p for p in periods if re.fullmatch(r'\d{4}',str(p.get('th','')))]
   period_catalog[var]=available
   wanted=sorted([p for p in available if plan['start_year']<=int(p['th'])<=plan['end_year']],key=lambda p:int(p['th']),reverse=True)
   if not wanted:holds.append({'variable_id':var,'title':table['title'],'reason':'No requested year in source period catalogue'})
   for period in wanted:
    pid=str(period['th_id']);year=int(period['th'])
    data,saved=archive.get(f'list/model/data/domain/0000/var/{var}/th/{pid}')
    try:
     rows,summary=normalize(data,'0000',var,pid,max_combinations=2000000)
     if not rows:
      results.append({'variable_id':var,'year':year,'national_rows':0,**summary});continue
     if any(str(r['year_label'])!=str(year) for r in rows):raise BPSError('Label tahun berbeda dari katalog.')
     selected=national_rows(rows,data,table,saved,url)
     summary.update(national_rows=len(selected),excluded_non_national=len(rows)-len(selected),national_statuses=dict(Counter(r['status'] for r in selected)),year_label=str(year))
     db.put('0000',var,pid,selected,summary,saved,url,False)
     results.append({'variable_id':var,'year':year,**summary})
    except BPSError as exc:
     holds.append({'variable_id':var,'year':year,'title':table['title'],'reason':str(exc),'source_snapshot_sha256':saved['sha256']})
   write_json(archive.root/'progress.json',{'tables_completed':index,'tables_total':len(tables),'results':results,'holds':holds})
   write_json(archive.root/'period-catalog.json',period_catalog)
   print(json.dumps({'tables_completed':index,'tables_total':len(tables),'variable_id':var,'national_rows':sum(r.get('national_rows',0) for r in results),'holds':len(holds)}),flush=True)
 finally:db.close()
 manifest={'status':'acquired_with_review_holds' if holds else 'acquired','completed_at':now(),'requested_years':[plan['start_year'],plan['end_year']],
  'tables_requested':len(tables),'national_rows':sum(r.get('national_rows',0) for r in results),'holds':holds,'results':results,'qdrant_ingested':False,'public_provider_changed':False}
 write_json(archive.root/'manifest.json',manifest);return manifest


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--directory',type=Path,default=DEFAULT_DIR/'national-2019-2026');p.add_argument('--max-requests',type=int,default=1000)
 args=p.parse_args();plan=json.loads(args.plan.read_text())
 c=BPSClient(os.environ.get('BPS_API_KEY') or json.loads((ROOT/'.local/bps-connection.json').read_text())['api_key'])
 try:
  a=ReusingArchive(args.directory,c,max_requests=args.max_requests,cache_roots=[DEFAULT_DIR,DEFAULT_DIR/'national-discovery'])
  acquire(a,plan)
 except BPSError as exc:p.exit(2,str(exc)+'\n')
 finally:c.close()

if __name__=='__main__':main()
