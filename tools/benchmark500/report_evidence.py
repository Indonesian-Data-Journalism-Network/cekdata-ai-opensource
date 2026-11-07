import json,pathlib,re,collections
ROOT=pathlib.Path(__file__).resolve().parents[2];P=ROOT/'docs/test-evidence/20261106/benchmark500-v1';out=P/'reference-reports';out.mkdir(exist_ok=True)
docs={d['id']:d for d in json.load((ROOT/'data/ngo/manifest.json').open())['documents']}
plan=json.load((P/'plan.json').open());seen=set();index=[]
for q in plan:
 id=q.get('reference_document')
 if not id or id in seen:continue
 seen.add(id);d=docs[id];p=ROOT/'data/ngo/extractions/ngo-pdf-v3'/d['provider']/id/'pages.json'
 if not p.exists():index.append({'id':id,'missing':True});continue
 pages=json.load(p.open());words=set(re.findall(r'\w+',q.get('report_focus','').lower()))-{'dan','di','terhadap','warga','kehidupan','hak','atas'}
 ranked=sorted(pages,key=lambda p:sum(min(3,p.get('text','').lower().count(w)) for w in words),reverse=True)[:8]
 packet={'document':d,'question_ids':[x['id'] for x in plan if x.get('reference_document')==id],'pages':sorted(ranked,key=lambda p:p['pdf_page'])}
 (out/f'{id}.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2))
 index.append({'id':id,'title':d['title'],'provider':d['provider'],'page_count':len(pages),'review_pages':[p['pdf_page'] for p in packet['pages']]})
(P/'reference-reports/index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2));print('Reference reports',len(index),'missing',sum(x.get('missing',False) for x in index))
