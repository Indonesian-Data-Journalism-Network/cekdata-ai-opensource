"""OCR low-text PDF pages locally. Low-confidence output remains pending review."""
import sys, tempfile, subprocess, csv, io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from ngo_corpus import ROOT, read, save, now
import pypdfium2 as pdfium

def process_document(d):
  if d['status'] not in ('extracted','needs_ocr'):return d
  base=ROOT/d['provider']/d['id'];pages=read(base/'pages.json',[])
  todo=[p for p in pages if p['status']!='readable' and not p.get('ocr_attempted')]
  if not todo:return d
  pdf=pdfium.PdfDocument(base/'original.pdf');changed=False
  for p in todo:
   page=pdf[p['pdf_page']-1];bitmap=page.render(scale=2);image=bitmap.to_pil()
   if p['page_side']=='left':image=image.crop((0,0,image.width//2,image.height))
   elif p['page_side']=='right':image=image.crop((image.width//2,0,image.width,image.height))
   with tempfile.TemporaryDirectory(prefix='cekdata-ocr-') as tmp:
    file=Path(tmp)/'page.png';image.save(file)
    try:
     proc=subprocess.run(['tesseract',str(file),'stdout','-l','eng','tsv'],capture_output=True,timeout=90,check=True)
     rows=list(csv.DictReader(io.StringIO(proc.stdout.decode('utf-8')),delimiter='\t'))
     lines={};conf=[]
     for r in rows:
      if not r.get('text','').strip():continue
      lines.setdefault((r['block_num'],r['par_num'],r['line_num']),[]).append(r['text'])
      if float(r['conf'])>=0:conf.append(float(r['conf']))
     text='\n'.join(' '.join(words) for words in lines.values());score=sum(conf)/len(conf) if conf else 0
     p.update(ocr_attempted=True,ocr_language='eng',ocr_mean_confidence=round(score,2))
     if score>=80 and len(text)>180:
      p.update(text=text,status='readable',extraction_method='tesseract_ocr',ocr_verified=False)
     else:p['ocr_status']='needs_visual_review'
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError):p.update(ocr_attempted=True,ocr_status='failed')
   image.close();bitmap.close();page.close();changed=True
  pdf.close()
  if changed:
   save(base/'pages.json',pages)
   d.update(readable_parts=sum(p['status']=='readable' for p in pages),review_parts=sum(p['status']!='readable' for p in pages))
   if d['readable_parts']:d['status']='extracted'
   save(base/'document.json',d)
   print('ocr',d['provider'],d['title'][:45],d['readable_parts'],d['review_parts'],flush=True)
  return d

def run():
 from concurrent.futures import ProcessPoolExecutor
 report=read(ROOT/'ingest-report.json',{})
 documents=report.get('documents',[])
 with ProcessPoolExecutor(max_workers=3) as pool:
  for i,d in enumerate(pool.map(process_document,documents)):
   documents[i]=d
   save(ROOT/'ingest-report.json',{**report,'updated_at':now()})
if __name__=='__main__':run()
