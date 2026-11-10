"""Inspect archived BPS source text in Qdrant; never turn raw table text into numbers."""
import json,math,re
from pathlib import Path
from collections import Counter
from qdrant_client import models
from tools.bps.ingest import DEFAULT_DIR

STOP=set('apa apakah berapa bagaimana bandingkan menurut yang dan di ke dari pada dengan untuk tahun bulan indonesia data bps ini itu terakhir saya ingin tahu jumlah'.split())
def tokens(text):return {w for w in re.findall(r'[a-z0-9]+',text.casefold()) if len(w)>2 and w not in STOP and not w.isdigit()}

def search(client,question,*,manifest=None,limit=5):
 manifest=manifest or json.loads((DEFAULT_DIR/'bundle/manifest.json').read_text())
 words=tokens(question)
 if not words:return []
 conditions=[models.FieldCondition(key=field,match=models.MatchText(text=w)) for w in sorted(words) for field in ['title','text']]
 points,offset=client.scroll(manifest['document_collection'],scroll_filter=models.Filter(
  must=[models.FieldCondition(key='record_type',match=models.MatchValue(value='text_chunk'))],should=conditions),limit=1000,with_payload=True,with_vectors=False)
 scored=[]
 for point in points:
  p=point.payload;title=tokens(p['title']);body=tokens(p['text'])
  score=4*len(words&title)+len(words&body)
  if score:scored.append((score,p))
 chosen=[];seen=set()
 for score,p in sorted(scored,key=lambda x:(-x[0],x[1]['document_id'],x[1]['chunk_index'])):
  if p['document_id'] in seen:continue
  seen.add(p['document_id']);chosen.append({**p,'retrieval_score':score,'candidate_search_truncated':offset is not None})
  if len(chosen)>=limit:break
 return chosen
