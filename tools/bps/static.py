"""Archive topic-selected BPS static HTML tables losslessly, with a span-aware grid.

Discovery keywords are not answer-routing rules. A year in a title/update date
never establishes observation coverage. Raw tables and download links are kept;
no PDF or Excel is downloaded, and no unreviewed cell enters active Qdrant.
"""
import argparse
import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata
from bs4 import BeautifulSoup
from tools.bps.brs import plain_text, safe_download_url
from tools.bps.client import BPSClient, BPSError
from tools.bps.ingest import Archive, DEFAULT_DIR, ROOT, now, write_json

TOPICS = {
 'kemiskinan_ketimpangan':r'kemiskinan|penduduk miskin|gini|ketimpangan|distribusi pendapatan',
 'pekerjaan_pendapatan':r'penganggur|penduduk bekerja|angkatan kerja|upah|tenaga kerja|pekerja|buruh|pendapatan bersih',
 'ekonomi_daerah':r'pdrb|produk domestik regional|pertumbuhan ekonomi|produk domestik bruto',
 'harga_daya_beli':r'inflasi|nilai tukar petani',
 'pembangunan_manusia':r'pembangunan manusia|harapan hidup|air minum|sanitasi',
 'pertanian_perkebunan':r'luas.*(?:areal|panen|tanam|perkebunan)|produksi.*(?:padi|beras|jagung|kedelai|kacang|ubi|sawit|kelapa|karet|kopi|kakao|teh|tebu|tembakau|perkebunan|tanaman)|produktivitas.*(?:tanaman|padi|jagung|perkebunan)|komoditas.*perkebunan',
 'konsumsi':r'pengeluaran.*(?:kapita|makanan|rumah tangga)|konsumsi.*(?:kalori|protein|makanan|rumah tangga)|kalori|protein|distribusi pengeluaran',
 'pendidikan':r'sekolah|pendidikan|melek huruf|buta huruf|baca tulis|melek aksara|ujian nasional|perguruan tinggi',
 'politik_demokrasi':r'demokrasi|pemilu|pemilihan umum|parlemen|legislatif|dprd|dpr\b|politik',
 'kriminalitas':r'kejahatan|kriminal|pidana|korban.*(?:kekerasan|pencurian)|melapor.*polisi',
}
YEAR = re.compile(r'^(?:19|20)\d{2}(?:\s*(?:\*+|[a-zA-Z]|\d+\)|\([a-zA-Z]\)))?$')


def classify(title):
 return [name for name,pattern in TOPICS.items() if re.search(pattern,plain_text(title),re.I)]


def grids(markup):
 soup=BeautifulSoup(markup or '', 'html.parser')
 results=[]
 for table in soup.find_all('table'):
  if table.find_parent('table') is not None: continue
  slots={}; cells=[]; row_count=0
  for ri,tr in enumerate(table.find_all('tr')):
   if tr.find_parent('table') is not table: continue
   row_count=max(row_count,ri+1); col=0
   for node in tr.find_all(['td','th'],recursive=False):
    while (ri,col) in slots:col+=1
    try:rs,cs=int(node.get('rowspan',1)),int(node.get('colspan',1))
    except (TypeError,ValueError):raise BPSError('Span tabel tidak valid.') from None
    if not (1<=rs<=1000 and 1<=cs<=1000):raise BPSError('Span tabel di luar batas.')
    text=plain_text(node.decode_contents())
    origin=len(cells)
    cells.append({'row':ri,'column':col,'rowspan':rs,'colspan':cs,'tag':node.name,'text':text})
    for r in range(ri,ri+rs):
     for c in range(col,col+cs):
      if (r,c) in slots:raise BPSError('Sel tabel saling menimpa.')
      slots[r,c]=origin
    col+=cs
  height=max([row_count]+[r+1 for r,c in slots]); width=max([0]+[c+1 for r,c in slots])
  if height*width>2000000:raise BPSError('Ukuran tabel di luar batas.')
  results.append({'cells':cells,'grid':[[slots.get((r,c)) for c in range(width)] for r in range(height)],'rows':height,'columns':width})
 return results


def make_document(body,saved,topics,start,end,domain='0000'):
 ident=str(body['table_id']);title=plain_text(body.get('title',''))
 markup=body.get('table') or ''; tables=grids(markup)
 year_cells=[]
 for ti,t in enumerate(tables):
  for ci,cell in enumerate(t['cells']):
   if YEAR.fullmatch(cell['text']):
    year=int(cell['text'][:4])
    if start<=year<=end:year_cells.append({'table':ti,'cell':ci,'year':year})
 token=base64.b64encode(f'{ident}#1'.encode()).decode()
 slug=re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',title).encode('ascii','ignore').decode().lower()).strip('-')
 return {'id':f'bps-static-{domain}-{ident}','table_id':ident,'publisher':'Badan Pusat Statistik',
  'publisher_domain_id':domain,'source_type':'bps_static_table','title':title,'topics':topics,
  'updated_at':body.get('updt_date'),'created_at':body.get('cr_date'),'retrieved_at':saved['retrieved_at'],
  'requested_years':[start,end],'year_cell_candidates':year_cells,
  'years_with_label_candidates':sorted({x['year'] for x in year_cells}),
  'observation_coverage_verified':False,'coverage_status':'requires_dimension_review',
  'source_url':f'https://www.bps.go.id/id/statistics-table/1/{token}/{slug}.html',
  'source_url_origin':'constructed_from_official_table_id','source_url_verified':False,
  'download_url':safe_download_url(body.get('excel')),'download_file_fetched':False,
  'subject':body.get('subcsa') or body.get('subj'),'html':markup,'text':plain_text(markup),'tables':tables,
  'source_snapshot_sha256':saved['sha256'],'html_sha256':hashlib.sha256(markup.encode()).hexdigest(),
  'ready_for_numeric_answers':False,'qdrant_ingested':False}


def collect(archive,start,end):
 rows,provenance=archive.list('list/model/statictable/domain/0000',{'lang':'ind'})
 write_json(archive.root/'catalog.json',{'domain':'0000','rows':rows,'provenance':provenance})
 all_candidates=[{'table_id':str(r['table_id']),'title':plain_text(r['title']),'updated_at':r.get('updt_date'),'topics':classify(r['title'])} for r in rows if classify(r['title'])]
 excluded=[]; candidates=[]
 for row in all_candidates:
  years=[int(x) for x in re.findall(r'\b(?:19|20)\d{2}\b',row['title'])]
  updated=str(row.get('updated_at') or '')[:4]
  if years and max(years)<start and updated.isdigit() and int(updated)<start:
   excluded.append({**row,'reason':'Both title period and last update precede requested start year'})
  else:candidates.append(row)
 if len({r['table_id'] for r in rows})!=len(rows):raise BPSError('Katalog memiliki ID berulang.')
 write_json(archive.root/'plan.json',{'start_year':start,'end_year':end,'topics':TOPICS,'candidates':candidates,'excluded_before_period':excluded,
  'note':'Title keywords discover candidates only. All candidate bodies are inspected; update year is not a data-year filter.'})
 documents=[];errors=[]
 for i,row in enumerate(candidates,1):
  ident=row['table_id']
  try:
   data,saved=archive.get(f'view/domain/0000/model/statictable/lang/ind/id/{ident}')
   body=data.get('data')
   if data.get('data-availability')!='available' or not isinstance(body,dict) or str(body.get('table_id'))!=ident:raise BPSError('Detail tabel tidak tersedia atau identitas berbeda.')
   doc=make_document(body,saved,row['topics'],start,end)
   write_json(archive.root/'documents'/(doc['id']+'.json'),doc)
   documents.append({k:doc[k] for k in ['id','table_id','title','topics','updated_at','years_with_label_candidates','source_url','download_url']})
  except (BPSError,ValueError,TypeError,KeyError) as exc:
   errors.append({'table_id':ident,'error':str(exc)})
   if isinstance(exc,BPSError) and any(x in str(exc) for x in ['429','Batas permintaan','Koneksi']):
    write_json(archive.root/'errors.json',errors);raise
  if i==1 or i%10==0 or i==len(candidates):print(json.dumps({'completed':i,'total':len(candidates),'saved':len(documents),'errors':len(errors)}),flush=True)
  write_json(archive.root/'progress.json',{'completed':i,'total':len(candidates),'documents':documents,'errors':errors})
 manifest={'status':'archived' if not errors else 'partial','completed_at':now(),'requested_years':[start,end],
  'catalog_tables':len(rows),'candidates':len(candidates),'topic_candidates':len(all_candidates),'excluded_before_period':excluded,'archived_tables':len(documents),'errors':errors,
  'topics':{t:sum(t in d['topics'] for d in documents) for t in TOPICS},
  'tables_with_requested_year_labels':sum(bool(d['years_with_label_candidates']) for d in documents),
  'note':'Year labels are candidate evidence only, not verified numeric observations. Full source tables retain out-of-range context.',
  'qdrant_ingested':False,'pdf_downloads':0,'documents':documents}
 write_json(archive.root/'manifest.json',manifest)
 return manifest


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--start-year',type=int,default=2019);p.add_argument('--end-year',type=int,default=2026)
 p.add_argument('--directory',type=Path,default=DEFAULT_DIR/'static');p.add_argument('--max-requests',type=int,default=800);p.add_argument('--refresh',action='store_true')
 args=p.parse_args()
 if not 1900<=args.start_year<=args.end_year<=2100:p.error('Rentang tahun tidak valid.')
 key=os.environ.get('BPS_API_KEY') or json.loads((ROOT/'.local/bps-connection.json').read_text())['api_key']
 c=BPSClient(key)
 try:
  m=collect(Archive(args.directory,c,refresh=args.refresh,max_requests=args.max_requests),args.start_year,args.end_year)
  print(json.dumps({k:v for k,v in m.items() if k!='documents'},ensure_ascii=False),flush=True)
 except BPSError as exc:p.exit(2,str(exc)+'\n')
 finally:c.close()

if __name__=='__main__':main()
