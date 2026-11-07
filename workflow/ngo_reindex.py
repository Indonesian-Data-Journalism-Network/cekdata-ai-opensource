"""Versioned, resumable rebuild of NGO child vectors and source-anchored parent contexts.

python workflow/ngo_reindex.py --pilot | (full corpus by default)
No download, remote model call, deletion, or activation is performed here.
"""
from __future__ import annotations
import argparse
import math
import hashlib
import json
import re
import uuid
from collections import Counter,defaultdict
from pathlib import Path
from functools import lru_cache
from ngo_corpus import ROOT, MODEL, read, save, now, model, allowed, source_pages
from ngo_metadata import SCHEMA, Gazetteer, explicit_places, metadata, document_metadata, headings, spans, location_names, normalized
from settings import DATA_DIR,QDRANT_URL


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,':'.join(str(x) for x in (SCHEMA,*parts))))


def parent_spans(text,target=1700):
    """Group adjacent source sentences without inventing or rewriting text."""
    pieces=list(spans(text))
    if not pieces:return
    start=pieces[0][0];end=start
    for a,b in pieces:
        if end>start and b-start>target:
            yield start,end
            start=a
        end=b
    if end>start:yield start,end


def child_spans(text,tokenizer,max_tokens=100,overlap_words=12):
    words=list(re.finditer(r'\S+',text));i=0
    while i<len(words):
        a=words[i].start();lo=i+1;hi=len(words);best=i
        while lo<=hi:
            mid=(lo+hi)//2
            if len(tokenizer.encode(text[a:words[mid-1].end()]).ids)<=max_tokens:
                best=mid;lo=mid+1
            else:hi=mid-1
        if best==i:
            # Pathological no-space strings are still covered without truncating tokens.
            end=words[i].end();cursor=a
            while cursor<end:
                low=cursor+1;high=end;chosen=cursor
                while low<=high:
                    mid=(low+high)//2
                    if len(tokenizer.encode(text[cursor:mid]).ids)<=max_tokens:chosen=mid;low=mid+1
                    else:high=mid-1
                if chosen==cursor:raise ValueError('single_character_exceeds_embedding_budget')
                yield cursor,chosen;cursor=chosen
            i+=1;continue
        b=words[best-1].end()
        # Prefer a full sentence boundary when it retains most of this child.
        if best<len(words):
            cuts=[e for s,e in spans(text[a:b]) if e>len(text[a:b])*.6 and e<len(text[a:b])]
            if cuts:
                b=a+cuts[-1];best=next((n for n in range(i+1,best+1) if words[n-1].end()>=b),best)
        yield a,b
        if best>=len(words):break
        i=max(i+1,best-overlap_words)


def direct_metadata(parent,a,b):
    result={}
    for key in ('locations','periods','quantities','topics','actors'):
        result[key]=[item for item in parent[key] if a<=item['evidence']['start'] and item['evidence']['end']<=b]
    result['claim_status']=list(dict.fromkeys(x for q in result['quantities'] for x in q['status']))
    result['content_kind']=parent['content_kind'];result['language']=parent['language']
    return result


def contextual_embedding(text,heading,context,tokenizer):
    # All hints are derived from an anchored heading or names on this parent;
    # the complete child text always remains inside the encoder's true window.
    names=[item['name'] for item in context['locations'][:3]]
    hints=[heading['text'] if heading else '',', '.join(dict.fromkeys(names))]
    prefix=' | '.join(x for x in hints if x)
    while prefix and len(tokenizer.encode(prefix+'\n'+text).ids)>126:
        prefix=' '.join(prefix.split()[:-1])
    value=prefix+'\n'+text if prefix else text
    if len(tokenizer.encode(value).ids)>126:raise ValueError('embedding_truncation')
    return value


def prepare_document(document,pages,gazetteer,tokenizer):
    docmeta=document_metadata(document,pages);parents=[];points=[];last_heading=None
    for page in pages:
        if page['status']!='readable':continue
        # A title from a previous page is not proof that this page still
        # describes the same project. Continuations keep explicit page links.
        last_heading=None
        heads=headings(page)
        for start,end in parent_spans(page['text']):
            local_heads=[h for h in heads if h['evidence']['start']<=start]
            if local_heads:last_heading=local_heads[-1]
            context=metadata(page,start,end,gazetteer)
            ident=uid(document['sha256'],page['pdf_page'],page['page_side'],start,end,'parent')
            parent={'parent_id':ident,'pdf_page':page['pdf_page'],'page_side':page['page_side'],
                    'printed_page':page.get('printed_page'),'start':start,'end':end,'text':page['text'][start:end],
                    'heading':last_heading,'metadata':context,'previous_parent_id':None,'next_parent_id':None}
            parents.append(parent)
            for a,b in child_spans(parent['text'],tokenizer):
                a+=start;b+=start;text=page['text'][a:b]
                if not text.strip():continue
                direct=direct_metadata(context,a,b)
                ident_child=uid(document['sha256'],page['pdf_page'],page['page_side'],a,b,'child')
                payload={k:document.get(k) for k in ('provider','host_organization','title','source_url','download_url','publication_year_listed','publication_date_listed','document_kind','sha256')}
                payload.update({'document_id':document['id'],'text':text,'pdf_page':page['pdf_page'],
                  'page_side':page['page_side'],'printed_page':page.get('printed_page'),'start':a,'end':b,
                  'parent_id':parent['parent_id'],'section_heading':last_heading,
                  'previous_chunk_id':None,'next_chunk_id':None,
                  'metadata':direct,'context_metadata':context,
                  'location_names':location_names(direct),'context_location_names':location_names(context),
                  'location_ids':list(dict.fromkeys(x['reference_id'] for x in direct['locations'] if x.get('reference_id'))),
                  'topic_ids':[x['id'] for x in context['topics']],
                  'mentioned_years':list(dict.fromkeys(x['year'] for x in context['periods'])),
                  'model':MODEL,'schema_version':SCHEMA,'metadata_method':'local_source_anchored_rules_v1',
                  'numeric_tables_verified':False,'visual_content_verified':False,
                  'text_extraction':page.get('extraction_method','pdf_text'),
                  'ocr_verified':page.get('ocr_verified'),'ocr_mean_confidence':page.get('ocr_mean_confidence'),
                  'ocr_language':page.get('ocr_language'),'ocr_status':page.get('ocr_status'),
                  'observation_period':None,'authorship_status':'see_document_credit_lines_not_inferred_from_host',
                  'source_independence':'not_verified'})
                embedding=contextual_embedding(text,last_heading,context,tokenizer)
                points.append({'id':ident_child,'payload':payload,'embedding_text':embedding})
    for i,parent in enumerate(parents):
        parent['previous_parent_id']=parents[i-1]['parent_id'] if i else None
        parent['next_parent_id']=parents[i+1]['parent_id'] if i+1<len(parents) else None
    for i,point in enumerate(points):
        point['payload']['previous_chunk_id']=points[i-1]['id'] if i else None
        point['payload']['next_chunk_id']=points[i+1]['id'] if i+1<len(points) else None
    docmeta.update(parent_count=len(parents),child_count=len(points),
                   document_topic_ids=sorted(set(t for p in parents for t in [x['id'] for x in p['metadata']['topics']])),
                   scope_evidence=[{'pdf_page':p['pdf_page'],'page_side':p['page_side'],
                                    'text':p['text'],'parent_id':p['parent_id']}
                                   for p in parents if any(x['role']=='study_area_candidate' for x in p['metadata']['locations'])][:20])
    return docmeta,parents,points


def load_corpus(pages_root=''):
    report=read(ROOT/'ingest-report.json',{})
    docs=[d for d in report.get('documents',[]) if d['status']=='extracted']
    if not docs:raise ValueError('no_extracted_documents')
    corpus=[];learned=[]
    for d in docs:
        if not allowed(d['source_url']) or not allowed(d['download_url']):raise ValueError('untrusted_source')
        pages=source_pages({'pages_root':pages_root},d['provider'],d['id'])
        if not pages:raise ValueError('missing_source_pages')
        for page in pages:
            for hit in explicit_places(page['text']):learned.append((hit['name'],hit['kind']))
        corpus.append((d,pages))
    return corpus,Gazetteer.local(DATA_DIR,learned)


def build(pilot=False,threads=4,reuse_context=None,pages_root=''):
    from tokenizers import Tokenizer
    from qdrant_client import QdrantClient,models
    corpus,gazetteer=load_corpus(pages_root)
    if pilot:
        chosen=[]
        for provider,terms in [('auriga',['raja ampat']),('trendasia',['biomassa','cofiring']),('satyabumi',['kabaena']),('walhi',['food estate','tinjauan lingkungan hidup 2026'])]:
            matches=[item for item in corpus if item[0]['provider']==provider and any(term in item[0]['title'].casefold() for term in terms)]
            chosen.extend(matches[:2] or [item for item in corpus if item[0]['provider']==provider][:2])
        corpus=chosen
    signature=hashlib.sha256((SCHEMA+MODEL+pages_root+json.dumps(gazetteer.entries,sort_keys=True,ensure_ascii=False)).encode())
    for doc,pages in corpus:signature.update(json.dumps([doc,pages],sort_keys=True,ensure_ascii=False).encode())
    build_id=signature.hexdigest()[:14];folder=ROOT/'v3'/build_id;folder.mkdir(parents=True,exist_ok=True)
    collection='cekdata_ngo_v3_'+build_id
    encoder=model(threads=threads);tokenizer=Tokenizer.from_str(encoder.model.tokenizer.to_str())
    tokenizer.no_truncation();tokenizer.no_padding()
    save(folder/'gazetteer.json',gazetteer.entries)
    client=QdrantClient(url=QDRANT_URL,timeout=90)
    if not client.collection_exists(collection):
        client.create_collection(collection,vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
        for key in ('provider','document_id','parent_id','location_names','context_location_names','location_ids','topic_ids'):
            client.create_payload_index(collection,key,models.PayloadSchemaType.KEYWORD,wait=True)
        client.create_payload_index(collection,'mentioned_years',models.PayloadSchemaType.INTEGER,wait=True)
    reuse_folder=None;reuse_collection=None
    if reuse_context:
        if not re.fullmatch(r'v3/[a-f0-9]{14}',reuse_context):raise ValueError('invalid_reuse_context')
        reuse_folder=ROOT/reuse_context
        reuse_collection='cekdata_ngo_v3_'+reuse_folder.name
        if not client.collection_exists(reuse_collection):raise ValueError('missing_reuse_collection')
    totals=Counter();inventory=[];coverage=[]
    try:
        for d,pages in corpus:
            path=folder/(d['id']+'.json')
            if path.exists():
                cached=read(path);docmeta,parents=cached['document'],cached['parents']
                pointpath=folder/(d['id']+'.jsonl')
                points=[json.loads(line) for line in pointpath.open()]
            else:
                docmeta,parents,points=prepare_document(d,pages,gazetteer,tokenizer)
                pointpath=folder/(d['id']+'.jsonl')
                with pointpath.with_suffix('.jsonl.tmp').open('w') as stream:
                    for point in points:stream.write(json.dumps(point,ensure_ascii=False)+'\n')
                pointpath.with_suffix('.jsonl.tmp').replace(pointpath)
                save(path,{'document':docmeta,'parents':parents})
            # Always check real IDs, not just counts, when resuming.
            present=set();offset=None
            while True:
                rows,offset=client.scroll(collection,scroll_filter=models.Filter(must=[models.FieldCondition(key='document_id',match=models.MatchValue(value=d['id']))]),limit=1000,offset=offset,with_payload=False,with_vectors=False)
                present.update(str(row.id) for row in rows)
                if offset is None:break
            reusable={}
            if reuse_folder and (reuse_folder/(d['id']+'.jsonl')).exists():
                for line in (reuse_folder/(d['id']+'.jsonl')).open():
                    item=json.loads(line)
                    if item['payload']['model']==MODEL:reusable[item['embedding_text']]=item
            for start in range(0,len(points),128):
                batch=[point for point in points[start:start+128] if point['id'] not in present]
                if not batch:continue
                vectors=[None]*len(batch)
                reuse_ids=list(dict.fromkeys(reusable[point['embedding_text']]['id'] for point in batch if point['embedding_text'] in reusable))
                if reuse_ids:
                    records=client.retrieve(reuse_collection,ids=reuse_ids,with_payload=['model','text'],with_vectors=True)
                    old={str(record.id):record for record in records}
                    for index,point in enumerate(batch):
                        previous=reusable.get(point['embedding_text'])
                        record=old.get(previous['id']) if previous else None
                        if record and record.payload.get('model')==MODEL and record.payload.get('text')==point['payload']['text']:
                            vector=record.vector
                            if isinstance(vector,list) and len(vector)==384 and all(math.isfinite(x) for x in vector):
                                vectors[index]=vector;totals['vectors_reused_identical_input']+=1
                missing=[i for i,vector in enumerate(vectors) if vector is None]
                if missing:
                    fresh=encoder.embed([batch[i]['embedding_text'] for i in missing],batch_size=64)
                    for index,vector in zip(missing,fresh):vectors[index]=vector.tolist()
                    totals['vectors_computed']+=len(missing)
                client.upsert(collection,points=[models.PointStruct(id=p['id'],vector=v,payload=p['payload']) for p,v in zip(batch,vectors)],wait=True)
            totals.update(documents=1,points=len(points),parents=len(parents),readable_parts=docmeta['readable_parts'],unreadable_parts=len(docmeta['unreadable_parts']))
            for p in parents:
                totals.update(parents_with_locations=bool(p['metadata']['locations']),parents_with_quantities=bool(p['metadata']['quantities']),parents_with_years=bool(p['metadata']['periods']))
            inventory.append({k:d.get(k) for k in ('id','title','provider','source_url','download_url','publication_year_listed','sha256')})
            coverage.append({'document_id':d['id'],'provider':d['provider'],'children':len(points),'parents':len(parents),'readable_parts':docmeta['readable_parts'],'unreadable_parts':len(docmeta['unreadable_parts'])})
            save(folder/'progress.json',{'updated_at':now(),'collection':collection,'status':'building','totals':dict(totals),'completed_document_ids':[x['id'] for x in inventory]})
            print(json.dumps({'documents':totals['documents'],'of':len(corpus),'provider':d['provider'],'points':totals['points'],'title':d['title'][:65]}),flush=True)
        actual=client.count(collection,exact=True).count
        if actual!=totals['points']:raise ValueError('candidate_count_mismatch')
    finally:client.close()
    result={'collection':collection,'model':MODEL,'schema_version':SCHEMA,'build_id':build_id,'points':totals['points'],
            'documents':len(inventory),'providers':dict(Counter(d['provider'] for d in inventory)),
            'created_at':now(),'status':'candidate','pilot':pilot,'catalog':inventory,'totals':dict(totals),
            'context_root':str(folder.relative_to(ROOT)), 'pages_root':pages_root, 'embedding_limit':126,'child_target_tokens':100,
            'boundary_reference':'GADM 4.1 / existing local GFW snapshot; not current administrative equivalence'}
    save(folder/'coverage.json',coverage);save(folder/'candidate.json',result)
    save(ROOT/('pilot-candidate.json' if pilot else 'candidate.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k!='catalog'}),flush=True)
    return result


@lru_cache(maxsize=32)
def context_document(context_root,document_id):
    # Configuration paths are local relative build IDs, not values generated by a model.
    relative=Path(context_root)
    if relative.is_absolute() or '..' in relative.parts or not re.fullmatch(r'[a-f0-9]{20}',document_id):return {}
    return read(ROOT/relative/(document_id+'.json'),{})


def parent_for(config,payload):
    doc=context_document(config['context_root'],payload['document_id'])
    return next((p for p in doc.get('parents',[]) if p['parent_id']==payload.get('parent_id')),None)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pilot',action='store_true');parser.add_argument('--threads',type=int,default=4);parser.add_argument('--reuse-context');parser.add_argument('--pages-root',default='')
    args=parser.parse_args();build(pilot=args.pilot,threads=args.threads,reuse_context=args.reuse_context,pages_root=args.pages_root)
