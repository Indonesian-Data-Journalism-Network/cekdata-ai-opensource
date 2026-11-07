"""Merge public WALHI PDFs downloaded through the browser into the resumable manifest."""
import sys,shutil,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from ngo_corpus import ROOT, read, save, record, allowed
m=read(ROOT/'manifest.json');by_url={d['download_url']:d for d in m['documents']}
failures=[]
for article in read(ROOT/'walhi-browser-documents.json',[]):
 if not article['documents']:
  failures.append({'provider':'walhi','stage':'browser_article','url':article['source_url'],'error':'no_direct_pdf_link'})
 for file in article['documents']:
  if not allowed(file['url']):
   failures.append({'provider':'walhi','stage':'browser_download','url':file['url'],'error':'external_host_needs_review'});continue
  d=by_url.get(file['url']) or record('walhi',article['title'],article['source_url'],file['url'],article.get('date',''), 'position_paper' if 'kertas' in article['title'].lower() else 'report')
  d['source_url']=article['source_url'];by_url[file['url']]=d
  if file.get('file'):
   p=Path(file['file'])
   if not p.is_file() or p.stat().st_size>100*1024*1024 or p.read_bytes()[:5]!=b'%PDF-':
    failures.append({'provider':'walhi','stage':'browser_download','url':file['url'],'error':'not_valid_pdf'});continue
   dest=ROOT/'walhi'/d['id']/'original.pdf';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
  else:failures.append({'provider':'walhi','stage':'browser_download','url':file['url'],'error':file.get('error','not_downloaded')})
m['documents']=list(by_url.values());m['browser_failures']=failures
save(ROOT/'manifest.json',m)
print('Manifest documents:',len(by_url),'WALHI:',sum(d['provider']=='walhi' for d in by_url.values()),'browser pending:',len(failures))
