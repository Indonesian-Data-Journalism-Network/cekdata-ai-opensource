"""Verify candidate retrieval/citation integrity; optionally activate locally.

This verifies indexing and citations, not the truth of the reports' claims.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from ngo_corpus import ROOT, MODEL, read, save, now, allowed
from ngo_answer import search
from settings import QDRANT_URL
from qdrant_client import QdrantClient

CASES=[
 ('auriga','Menurut Auriga, apa dampak pertambangan nikel di Raja Ampat?', ['Raja Ampat nickel mining impacts'], ['raja ampat']),
 ('trendasia','Apa temuan Trend Asia mengenai cofiring biomassa PLTU?', ['cofiring biomassa hutan energi'], ['cofiring','co-firing','biomassa']),
 ('satyabumi','Apa temuan Satya Bumi tentang tambang nikel di Kabaena?', ['Kabaena nickel mining impacts'], ['kabaena']),
 ('walhi','Apa pandangan WALHI mengenai food estate di Papua?', ['food estate Papua'], ['papua','food estate']),
]

def verify(publish=False):
 cfg=read(ROOT/'candidate.json',{})
 if cfg.get('schema_version','').startswith('ngo-context-v3'):
  from verify_ngo_reindex import verify as verify_enriched
  return verify_enriched(publish=publish)
 assert cfg.get('model')==MODEL,'Embedding model mismatch'
 documents={d['id']:d for d in cfg['catalog']}
 client=QdrantClient(url=QDRANT_URL,timeout=60)
 offset=None;count=0
 while True:
  rows,offset=client.scroll(cfg['collection'],offset=offset,limit=512,with_payload=True,with_vectors=False)
  for row in rows:
   p=row.payload;d=documents[p['document_id']]
   assert p['source_url']==d['source_url'] and allowed(p['source_url'])
   assert p['download_url']==d['download_url'] and allowed(p['download_url'])
   assert p['sha256']==d['sha256'] and p['pdf_page']>=1 and p['text'].strip()
   assert p['model']==MODEL
   count+=1
  if offset is None:break
 assert count==cfg['points'],'Passage count mismatch'
 client.close()
 results=[]
 for provider,question,queries,terms in CASES:
  found=search(question,queries,config=cfg)
  assert found and all(p['provider']==provider for p in found),f'Publisher filter failed: {provider}'
  assert any(any(t in (p['title']+' '+p['page_text']).casefold() for t in terms) for p in found[:3]),f'Topic retrieval failed: {provider}'
  for p in found:
   assert p['text'] in p['page_text'] or len(p['page_text'])==14000,'Passage absent from local cited page'
  results.append({'provider':provider,'question':question,'hits':[{'title':p['title'],'pdf_page':p['pdf_page'],'source_url':p['source_url']} for p in found[:3]]})
  print('PASS retrieval',provider,flush=True)
 report={'verified_at':now(),'collection':cfg['collection'],'checked_points':count,'cases':results,'scope':'retrieval and citation integrity; not factual validation'}
 save(ROOT/'verification.json',report)
 if publish:
  previous=read(ROOT/'active.json')
  if previous:save(ROOT/'previous-active.json',previous)
  save(ROOT/'active.json',{**cfg,'status':'published','verified_at':report['verified_at']})
  print('Activated',cfg['collection'],cfg['documents'],'documents',count,'passages',flush=True)
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true')
 verify(parser.parse_args().publish)
