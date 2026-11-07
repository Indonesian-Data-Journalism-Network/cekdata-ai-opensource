"""Stage new PDF text beside the live corpus. Originals and OCR remain intact."""
import sys,json,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from ngo_corpus import ROOT,read,save,extract,now,VERSION

DEST='extractions/ngo-pdf-v3'

def prepare(doc):
    base=ROOT/doc['provider']/doc['id'];target=ROOT/DEST/doc['provider']/doc['id']
    receipt=read(target/'receipt.json',{})
    if receipt.get('sha256')==doc['sha256'] and receipt.get('extractor_version')==VERSION:return receipt
    pdf=base/'original.pdf'
    with pdf.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=doc['sha256']:raise ValueError('changed_pdf')
    previous=read(base/'pages.json');old={(p['pdf_page'],p['page_side']):p for p in previous}
    fresh=extract(pdf);changed=[];preserved=0
    for n,p in enumerate(fresh):
        before=old.get((p['pdf_page'],p['page_side']))
        if before and (before.get('extraction_method','').startswith('ocr') or before.get('ocr_verified') or before.get('ocr_status')):
            fresh[n]=before;preserved+=1
        elif before and p.get('reading_order')=='original_lines':fresh[n]=before
        elif before and p['text']!=before['text']:changed.append(p['pdf_page'])
    if {(p['pdf_page'],p['page_side']) for p in fresh}!=set(old):raise ValueError('page_inventory_changed')
    save(target/'pages.json',fresh)
    receipt={'id':doc['id'],'provider':doc['provider'],'sha256':doc['sha256'],
             'extractor_version':VERSION,'changed_pages':changed,'preserved_ocr_parts':preserved,'parts':len(fresh)}
    save(target/'receipt.json',receipt);return receipt

if __name__=='__main__':
    docs=[d for d in read(ROOT/'ingest-report.json')['documents'] if d['status']=='extracted'];results=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for result in pool.map(prepare,docs):
            results.append(result);print(json.dumps({'done':len(results),'of':len(docs),**result}),flush=True)
            save(ROOT/DEST/'progress.json',{'created_at':now(),'documents':results,'status':'building'})
    save(ROOT/DEST/'progress.json',{'created_at':now(),'documents':results,'status':'complete'})
