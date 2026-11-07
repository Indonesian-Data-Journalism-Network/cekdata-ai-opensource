"""Resumable public NGO PDF ingestion; source URLs are mandatory, never LLM-generated.

CLI: python workflow/ngo_corpus.py discover|ingest|index|status
Raw PDFs, page extraction, crawl failures and model files stay under ignored data/ngo.
"""
from __future__ import annotations
import argparse, hashlib, json, re, time, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
import httpx
from bs4 import BeautifulSoup
from settings import DATA_DIR, QDRANT_URL

ROOT = DATA_DIR / 'ngo'
MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
VERSION = 'ngo-pdf-v3'
SOURCES = {
 'auriga': ('Auriga Nusantara', ['https://auriga.or.id/resources/report']),
 'trendasia': ('Trend Asia', ['https://trendasia.org/category/publikasi/laporan/studi/']),
 'satyabumi': ('Satya Bumi', ['https://satyabumi.org/en/category/publikasi/laporan/']),
 'walhi': ('WALHI', ['https://www.walhi.or.id/category/kertas-posisi', 'https://www.walhi.or.id/category/laporan-tahunan']),
}
HOSTS = {'auriga.or.id','trendasia.org','satyabumi.org','walhi.or.id','www.walhi.or.id'}
# Observed public PDF links retained when a publisher's listing rejects automated reads.
WALHI_SEEDS = [
 ('Tinjauan Lingkungan Hidup 2026 — Membayar Mahal Ambisi Pertumbuhan', '2026', 'https://www.walhi.or.id/membayar-mahal-ambisi-pertumbuhan-dari-konflik-bencana-ekologis-hingga-krisis-lain', 'https://www.walhi.or.id/uploads/WALHI%202025-2029/Dokumen/TLH%202026%20Membayar%20Mahal%20Ambisi%20Pertumbuhan_compressed.pdf'),
 ('Tinjauan Lingkungan Hidup 2025 — Melanjutkan Tersesat, atau Kembali ke Jalan yang Benar', '2025', 'https://www.walhi.or.id/melanjutkan-tersesat-atau-kembali-ke-jalan-yang-benar', 'https://www.walhi.or.id/uploads/2024-Rilis/TLH%202025%20rev.pdf'),
 ('Tiga Alasan Mencabut Undang-Undang Kehutanan', '2025', 'https://www.walhi.or.id/kertas-posisi-uu-kehutanan-terkait-revisi-uu-kehutanan', 'https://www.walhi.or.id/uploads/blogs/Foto%20Rilis/Rilis/Content%20Menu%20/JTA%202025/Kertas%20Posisi%20-%20UU%20Kehutanan_Rev2%20%281%29.pdf'),
 ('Perdagangan Karbon: Jalan Sesat Atasi Krisis Iklim', '2023', 'https://www.walhi.or.id/category/kertas-posisi?page=8', 'https://walhi.or.id/uploads/buku/Kertas_Posisi_Perdagangan_Karbon_2023_rev_compressed.pdf'),
 ('Food Estate di Papua: Perampasan Ruang Berkedok Ketahanan Pangan?', '2021', 'https://www.walhi.or.id/category/kertas-posisi?page=11', 'https://www.walhi.or.id/uploads/buku/KertasPosisi%20food%20estate%20Papua_EDIT_25062021.pdf'),
 ('PSEL: Solusi Palsu yang Mengancam', '2026', 'https://www.walhi.or.id/kertas-posisi-psel-solusi-palsu-yang-mengancam', 'https://www.walhi.or.id/uploads/WALHI%202025-2029/Dokumen/Kertas%20Posisi%20PSEL.pdf'),
]

def now(): return datetime.now(timezone.utc).isoformat()
def save(path, value):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+'.tmp'); temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)); temp.replace(path)
def read(path, default=None): return json.loads(path.read_text()) if path.exists() else default

def source_pages(config,provider,document_id):
 root=config.get('pages_root') or config.get('source_pages_root') or ''
 from pathlib import PurePosixPath
 if root and (PurePosixPath(root).is_absolute() or '..' in PurePosixPath(root).parts):raise ValueError('invalid_pages_root')
 return read(ROOT/root/provider/document_id/'pages.json',[])

def allowed(url):
 u=urlsplit(url)
 return u.scheme=='https' and u.hostname in HOSTS and not u.username and not u.password and u.port in (None,443)

def get(url, *, pdf=False):
 if not allowed(url): raise ValueError('outside_publisher_allowlist')
 limit=100*1024*1024 if pdf else 4*1024*1024
 # Validate EVERY redirect before contacting it, not just the final URL.
 with httpx.Client(timeout=httpx.Timeout(60,connect=15), follow_redirects=False,
                   headers={'User-Agent':'CekDataAI-report-indexer/1.0 (public NGO reports)'}) as client:
  for _ in range(6):
   with client.stream('GET',url) as response:
    if response.is_redirect:
     url=urljoin(url,response.headers['location'])
     if not allowed(url): raise ValueError('external_redirect_needs_review')
     continue
    response.raise_for_status(); chunks=[]; size=0
    for chunk in response.iter_bytes():
     size+=len(chunk)
     if size>limit: raise ValueError('file_size_limit')
     chunks.append(chunk)
    content=b''.join(chunks)
    if pdf and not content.startswith(b'%PDF-'): raise ValueError('not_a_pdf')
    return content,url
 raise ValueError('redirect_limit')

def record(provider,title,page,pdf,date='',kind='report'):
 year=re.search(r'\b(20\d{2}|19\d{2})\b',date)
 return {'id':hashlib.sha256(pdf.encode()).hexdigest()[:20], 'provider':provider,
  'host_organization':SOURCES[provider][0], 'title':title, 'source_url':page,'download_url':pdf,
  'publication_date_listed':date, 'publication_year_listed':int(year[0]) if year else None,
  'document_kind':kind,'publication_date_basis':'publisher_listing','retrieved_at':now()}

def listing(provider,html,url):
 soup=BeautifulSoup(html,'html.parser'); reports=[]; articles=[]; pages=[]
 if provider=='auriga':
  for li in soup.select('li[date-publish]'):
   title=li.select_one('h2.title')
   if not title:continue
   for a in li.select('a[href]'):
    href=urljoin(url,a['href'])
    if '/report/download/' in href:
     suffix=' — Lampiran' if 'append' in a.get_text().lower() else ''
     reports.append(record(provider,title.get_text(' ',strip=True)+suffix,url,href,li.get('date-publish',''), 'appendix' if suffix else 'report'))
 else:
  selector='.t-entry-title a' if provider=='trendasia' else '.elementor-widget-archive-posts .elementor-post__title a' if provider=='satyabumi' else 'h2 a, h3 a, h5 a'
  for a in soup.select(selector):
   href=urljoin(url,a.get('href',''))
   if allowed(href) and '/category/' not in href:
    articles.append({'provider':provider,'source_url':href,'title':a.get_text(' ',strip=True)})
  for a in soup.select('a[href]'):
   href=urljoin(url,a['href'])
   if allowed(href) and any(href.startswith(base) for base in SOURCES[provider][1]) and ('page/' in href or 'page=' in href):
    pages.append(href)
 return reports,articles,list(dict.fromkeys(pages))

def article(entry,html):
 if isinstance(html,bytes):html=html.decode('utf-8',errors='replace')
 soup=BeautifulSoup(html,'html.parser'); scope=soup.select_one('main') or soup
 # Exclude navigation/footer/sidebar links and related publications.
 for e in scope.select('header,footer,nav,script,style,.related-posts,.related-content'):e.decompose()
 links=[]
 for a in scope.select('a[href],iframe[src],embed[src],object[data]'):
  url=urljoin(entry['source_url'],a.get('href') or a.get('src') or a.get('data') or '')
  if '.pdf' in urlsplit(url).path.lower() and allowed(url):links.append(urldefrag(url)[0])
 dates=soup.select_one('meta[property="article:published_time"]')
 date=dates.get('content','') if dates else ''
 kind='position_paper' if 'kertas-posisi' in html or 'Kertas Posisi' in entry['title'] else 'report'
 return [record(entry['provider'],entry['title'],entry['source_url'],u,date,kind) for u in dict.fromkeys(links)]

def discover():
 found={}; failures=[]; articles={}
 for provider,(_,starts) in SOURCES.items():
  queue=list(starts);seen=set()
  while queue and len(seen)<60:
   url=queue.pop(0)
   if url in seen:continue
   seen.add(url)
   try:
    data,final=get(url); pdfs,posts,pages=listing(provider,data,final)
    for r in pdfs:found[r['download_url']]=r
    for r in posts:articles[r['source_url']]=r
    queue.extend(p for p in pages if p not in seen)
    print('catalog',provider,len(seen),len(posts),flush=True)
   except Exception as e:failures.append({'url':url,'provider':provider,'stage':'listing','error':type(e).__name__})
   time.sleep(.15)
 for entry in articles.values():
  try:
   data,_=get(entry['source_url']); docs=article(entry,data)
   if not docs:failures.append({**entry,'stage':'article','error':'no_direct_publisher_pdf'})
   for r in docs:
    # Same PDF on a release and report page is ONE source, retain aliases.
    if r['download_url'] in found:
     found[r['download_url']].setdefault('alternate_source_urls',[]).append(r['source_url'])
    else:found[r['download_url']]=r
  except Exception as e:failures.append({**entry,'stage':'article','error':type(e).__name__})
  time.sleep(.12)
 for title,year,page,pdf in WALHI_SEEDS:
  found.setdefault(pdf,record('walhi',title,page,pdf,year))
 # Preserve previously verified links; a temporary crawl failure cannot erase them.
 previous=read(ROOT/'manifest.json',{'documents':[]})
 for old in previous['documents']:
  found.setdefault(old['download_url'],old)
 result={'created_at':now(),'sources':SOURCES,'documents':list(found.values()),'failures':failures,
         'catalog_status':'partial' if failures else 'discovered'}
 save(ROOT/'manifest.json',result)
 print(json.dumps({'documents':len(found),'failures':len(failures),'providers':dict(Counter(r['provider'] for r in found.values()))}),flush=True)
 return result


def clean(text):
 text=text.replace('\x00','').replace('\u00ad','')
 return re.sub(r'[ \t]+',' ',text).strip()

def extract(path):
 import pdfplumber
 pages=[]
 with pdfplumber.open(path) as doc:
  for number,page in enumerate(doc.pages,1):
   # Some exported PDFs retain text from a neighbouring page outside the visible
   # media box. Exclude it before reading, otherwise citations point to invisible text.
   page=page.within_bbox(page.bbox)
   x0,top,x1,bottom=page.bbox
   spread=page.width/page.height>1.3
   midpoint=(x0+x1)/2
   halves=[('left',(x0,top,midpoint,bottom)),('right',(midpoint,top,x1,bottom))] if spread else [('full',None)]
   for side,bbox in halves:
    crop=page.crop(bbox) if bbox else page
    from ngo_pdf_layout import read_columns
    layout=read_columns(crop)
    text=clean(layout['text'] if layout else crop.extract_text(x_tolerance=2,y_tolerance=3) or '')
    # Printed labels are detected only at the bottom and are never substituted for PDF indexes.
    tail=crop.crop((crop.bbox[0],top+(bottom-top)*.92,crop.bbox[2],bottom)).extract_text() or ''
    labels=re.findall(r'(?m)^\s*(\d{1,4})\s*$',tail)
    status='readable' if len(re.findall(r'[^\W\d_]',text))>=70 else 'needs_ocr_or_visual_review'
    pages.append({'pdf_page':number,'page_side':side,'printed_page':labels[-1] if len(labels)==1 else '',
      'text':text,'status':status,'reading_order':layout['reading_order'] if layout else 'original_lines',
      'layout':{k:v for k,v in (layout or {}).items() if k!='text'},
      'numeric_tables_verified':False,'visual_content_verified':False})
 return pages

def prepare_document(d):
  base=ROOT/d['provider']/d['id'];base.mkdir(parents=True,exist_ok=True)
  pdf=base/'original.pdf'; state=base/'document.json'; extracted=base/'pages.json'
  existing=read(state,{})
  try:
   if not pdf.exists():
    data,final=get(d['download_url'],pdf=True)
    tmp=pdf.with_suffix('.part');tmp.write_bytes(data);tmp.replace(pdf)
   digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
   if extracted.exists() and existing.get('sha256')==digest and existing.get('extractor_version')==VERSION:
    pages=read(extracted)
   else:
    pages=extract(pdf);save(extracted,pages)
   readable=sum(p['status']=='readable' for p in pages)
   status={**d,'sha256':digest,'extractor_version':VERSION,'pages':max((p['pdf_page'] for p in pages),default=0),
     'readable_parts':readable,'review_parts':len(pages)-readable,
     'status':'extracted' if readable else 'needs_ocr','numeric_tables_verified':False,
     'language_version_group':'not_verified','authors':'see_publication','updated_at':now()}
   status.pop('error',None)
  except Exception as e:
   status={**d,'status':'failed','error':type(e).__name__,'updated_at':now()}
  save(state,status)
  return status

def ingest(limit=0):
 from concurrent.futures import ProcessPoolExecutor
 manifest=read(ROOT/'manifest.json')
 if not manifest:raise RuntimeError('Run discover first')
 results=[]; checksums={}
 groups=[[d for d in manifest['documents'] if d['provider']==p] for p in SOURCES]
 docs=[g[i] for i in range(max(map(len,groups),default=0)) for g in groups if i<len(g)]
 if limit:docs=docs[:limit]
 # Independent extraction workers; only the parent writes the report/dedup state.
 with ProcessPoolExecutor(max_workers=3) as pool:
  for status in pool.map(prepare_document,docs):
   digest=status.get('sha256')
   if digest:
    if digest in checksums:
     status.update(status='duplicate',duplicate_of=checksums[digest])
     save(ROOT/status['provider']/status['id']/'document.json',status)
    else:checksums[digest]=status['id']
   results.append(status)
   print(status['status'],status['provider'],status['title'][:55],flush=True)
   save(ROOT/'ingest-report.json',{'updated_at':now(),'documents':results,'discovery_failures':manifest['failures'],'browser_failures':manifest.get('browser_failures',[])})
 return results

_model=None

def model(threads=2):
 global _model
 if _model is None:
  from fastembed import TextEmbedding
  _model=TextEmbedding(MODEL,cache_dir=str(ROOT/'models'),threads=threads,local_files_only=True)
 return _model

def chunks(text, max_chars=360, overlap=60):
 """Small overlapping passages keep the local multilingual encoder under its token window.
 A token-based safety check is also applied in index_documents."""
 text=clean(text)
 start=0
 while start<len(text):
  end=min(start+max_chars,len(text))
  if end<len(text):
   boundary=text.rfind(' ',start+max_chars//2,end)
   if boundary>start:end=boundary
  value=text[start:end].strip()
  if len(value)>=40:yield value
  if end==len(text):break
  start=max(start+1,end-overlap)

def index_documents_legacy():
 from qdrant_client import QdrantClient,models
 report=read(ROOT/'ingest-report.json',{})
 if not report.get('documents'):raise RuntimeError('No extracted documents')
 m=model(threads=6);points=[];docs=[]
 from tokenizers import Tokenizer
 tokenizer=Tokenizer.from_str(m.model.tokenizer.to_str())
 tokenizer.no_truncation();tokenizer.no_padding()
 def bounded(text):
  if len(tokenizer.encode(text).ids)<=126:
   yield text
  else:
   middle=text.rfind(' ',0,len(text)//2)
   if middle<1:middle=len(text)//2
   yield from bounded(text[:middle])
   yield from bounded(text[middle:].strip())
 for d in report['documents']:
  if d['status']!='extracted':continue
  docs.append(d)
  pages=read(ROOT/d['provider']/d['id']/'pages.json')
  for p in pages:
   if p['status']!='readable':continue
   for n,text in enumerate(part for chunk in chunks(p['text']) for part in bounded(chunk)):
    ident=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{VERSION}:{d['sha256']}:{p['pdf_page']}:{p['page_side']}:{n}"))
    payload={k:d.get(k) for k in ('id','provider','host_organization','title','source_url','download_url','publication_year_listed','publication_date_listed','document_kind','sha256')}
    payload.update({'document_id':payload.pop('id'),'text':text,
     'pdf_page':p['pdf_page'],'page_side':p['page_side'],'printed_page':p['printed_page'],
     'numeric_tables_verified':False,'visual_content_verified':False,
     'text_extraction':p.get('extraction_method','pdf_text'),'ocr_verified':p.get('ocr_verified'),
     'model':MODEL,'schema_version':VERSION})
    if not allowed(payload['source_url']) or not allowed(payload['download_url']):raise ValueError('Missing publisher source')
    points.append((ident,payload))
 if not points:raise RuntimeError('No readable passages')
 fingerprint=hashlib.sha256((MODEL+VERSION).encode())
 for ident,payload in points:
  fingerprint.update(json.dumps([ident,payload],sort_keys=True,ensure_ascii=False).encode())
 signature=fingerprint.hexdigest()[:12]
 collection='cekdata_ngo_'+signature
 client=QdrantClient(url=QDRANT_URL,timeout=60)
 if not client.collection_exists(collection):
  client.create_collection(collection,vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
  client.create_payload_index(collection,'provider',models.PayloadSchemaType.KEYWORD)
  client.create_payload_index(collection,'document_id',models.PayloadSchemaType.KEYWORD)
 existing=client.count(collection,exact=True).count
 if existing!=len(points):
  # An interrupted run may already have successfully written some batches.
  # Reuse only IDs actually present; never infer completeness from a count.
  existing_ids=set();offset=None
  while existing:
   records,offset=client.scroll(collection,offset=offset,limit=1000,with_payload=False,with_vectors=False)
   existing_ids.update(str(record.id) for record in records)
   if offset is None:break
  for start in range(0,len(points),128):
   batch=[point for point in points[start:start+128] if point[0] not in existing_ids]
   if batch:
    vectors=list(m.embed([payload['text'] for _,payload in batch],batch_size=64))
    client.upsert(collection,points=[models.PointStruct(id=i,vector=v.tolist(),payload=p) for (i,p),v in zip(batch,vectors)],wait=True)
   if start%1280==0:print('indexed',min(start+128,len(points)),'/',len(points),flush=True)
 count=client.count(collection,exact=True).count
 if count!=len(points):raise RuntimeError('Count mismatch')
 # Save candidate only; activation follows retrieval and citation tests.
 result={'collection':collection,'model':MODEL,'schema_version':VERSION,'points':count,
  'documents':len(docs),'providers':dict(Counter(d['provider'] for d in docs)),
  'created_at':now(),'status':'candidate','catalog':[{k:d.get(k) for k in ('id','title','provider','source_url','download_url','publication_year_listed','sha256')} for d in docs]}
 save(ROOT/'candidate.json',result);client.close();print(json.dumps({k:v for k,v in result.items() if k!='catalog'}),flush=True)
 return result

def index_documents():
 # New imports and rebuilds always use source-anchored parent/child metadata.
 from ngo_reindex import build
 return build()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['discover','ingest','index','status']);p.add_argument('--limit',type=int,default=0);args=p.parse_args()
 if args.command=='discover':discover()
 elif args.command=='ingest':ingest(args.limit)
 elif args.command=='index':index_documents()
 else:
  for name in ('manifest','ingest-report','candidate','active'):
   r=read(ROOT/(name+'.json'),{});print(name,json.dumps({k:(len(v) if isinstance(v,list) else v) for k,v in r.items() if k not in ('catalog','sources')},ensure_ascii=False))
