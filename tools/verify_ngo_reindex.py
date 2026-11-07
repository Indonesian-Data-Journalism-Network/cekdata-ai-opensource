"""Audit all rebuilt source spans, token bounds, IDs and search results before publication."""
import argparse,json,hashlib,re,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from ngo_corpus import ROOT,MODEL,read,save,now,allowed,model,source_pages
from ngo_metadata import SCHEMA
from ngo_answer import search
from ngo_reindex import parent_for
from settings import QDRANT_URL
from qdrant_client import QdrantClient,models
from tokenizers import Tokenizer

CASES=[
 ('auriga','Apa temuan Auriga tentang pertambangan nikel di Raja Ampat?',['Raja Ampat nickel mining'],['raja ampat']),
 ('trendasia','Apa temuan Trend Asia tentang cofiring biomassa di Jawa Timur?',['cofiring biomass East Java'],['biomassa','cofiring','co-firing']),
 ('satyabumi','Apa dampak tambang nikel pada masyarakat di Kabaena menurut Satya Bumi?',['Kabaena livelihoods nickel mining'],['kabaena']),
 ('walhi','Bagaimana pandangan WALHI tentang food estate di Papua?',['food estate Papua indigenous'],['food estate','papua']),
 (None,'Bagaimana dampak pertambangan nikel terhadap masyarakat dan hutan di Kabaena?',['Kabaena nickel mining household environment'],['kabaena']),
 (None,'Apa risiko food estate terhadap hutan dan masyarakat adat di Merauke?',['Merauke food estate forest indigenous'],['merauke','food estate']),
]


def check_anchor(evidence,page):
    assert evidence['pdf_page']==page['pdf_page'] and evidence['page_side']==page['page_side'],'Wrong metadata page locator'
    a,b=evidence['start'],evidence['end']
    assert 0<=a<b<=len(page['text']) and page['text'][a:b]==evidence['quote'],'Unanchored metadata'


def verify(pilot=False,publish=False):
    cfg=read(ROOT/('pilot-candidate.json' if pilot else 'candidate.json'),{})
    assert cfg.get('schema_version')==SCHEMA and cfg.get('model')==MODEL,'Wrong schema/model'
    assert cfg.get('pilot')==pilot,'Wrong candidate scope'
    if publish:assert not pilot,'Pilot cannot be published'
    from ngo_editions import finalize
    cfg=finalize(cfg)
    folder=ROOT/cfg['context_root'];tokenizer=Tokenizer.from_str(model().model.tokenizer.to_str());tokenizer.no_truncation();tokenizer.no_padding()
    totals=Counter();expected_ids=set();client=QdrantClient(url=QDRANT_URL,timeout=90)
    try:
        for d in cfg['catalog']:
            local=read(folder/(d['id']+'.json'));pages=source_pages(cfg,d['provider'],d['id'])
            pdf=ROOT/d['provider']/d['id']/'original.pdf'
            with pdf.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==d['sha256'],'Changed original PDF'
            by_page={(p['pdf_page'],p['page_side']):p for p in pages};parents={p['parent_id']:p for p in local['parents']}
            for credit in local['document']['authorship_mentions']:
                e=credit['evidence'];check_anchor(e,by_page[(e['pdf_page'],e['page_side'])])
            coverage=defaultdict(list);expected={}
            for parent in parents.values():
                page=by_page[(parent['pdf_page'],parent['page_side'])]
                assert parent['text']==page['text'][parent['start']:parent['end']],'Wrong parent source span'
                for category in ('locations','periods','quantities','topics','actors'):
                    for item in parent['metadata'][category]:check_anchor(item['evidence'],page)
                if parent.get('heading'):check_anchor(parent['heading']['evidence'],by_page[(parent['heading']['evidence']['pdf_page'],parent['heading']['evidence']['page_side'])])
                for key in ('previous_parent_id','next_parent_id'):
                    if parent[key]:assert parent[key] in parents,'Broken parent link'
            for point in (json.loads(line) for line in (folder/(d['id']+'.jsonl')).open()):
                p=point['payload'];ident=point['id'];page=by_page[(p['pdf_page'],p['page_side'])]
                assert ident not in expected_ids,'Duplicate child ID';expected_ids.add(ident)
                assert p['text']==page['text'][p['start']:p['end']],'Wrong child source span'
                assert page['status']=='readable' and p['parent_id'] in parents,'Invalid searchable page/parent'
                parent=parents[p['parent_id']]
                assert parent['start']<=p['start']<p['end']<=parent['end'],'Child escapes parent'
                assert p['document_id']==d['id'] and p['sha256']==d['sha256'],'Source identity mismatch'
                assert p['source_url']==d['source_url'] and p['download_url']==d['download_url'],'Changed source URLs'
                assert allowed(p['source_url']) and allowed(p['download_url'])
                assert p['schema_version']==SCHEMA and not p['numeric_tables_verified'] and not p['visual_content_verified']
                assert p['observation_period'] is None,'Publication inferred as observation period'
                assert len(tokenizer.encode(point['embedding_text']).ids)<=126,'Silent embedding truncation'
                assert point['embedding_text'].endswith(p['text']),'Embedding loses child text'
                for category in ('locations','periods','quantities','topics','actors'):
                    for item in p['metadata'][category]:
                        check_anchor(item['evidence'],page)
                        assert p['start']<=item['evidence']['start'] and item['evidence']['end']<=p['end'],'Inherited metadata mislabeled as direct'
                coverage[(p['pdf_page'],p['page_side'])].append((p['start'],p['end']))
                expected[ident]=p
                totals.update(points=1,with_direct_locations=bool(p['location_names']),with_parent_locations=bool(p['context_location_names']),with_quantities=bool(p['metadata']['quantities']))
            for key,page in by_page.items():
                if page['status']!='readable':totals['unreadable_parts']+=1;continue
                intervals=sorted(coverage[key]);cursor=0
                for a,b in intervals:
                    assert not page['text'][cursor:a].strip(),'Missing source text between children'
                    cursor=max(cursor,b)
                assert not page['text'][cursor:].strip(),'Missing page tail'
                totals['readable_parts']+=1
            actual={};offset=None
            while True:
                rows,offset=client.scroll(cfg['collection'],scroll_filter=models.Filter(must=[models.FieldCondition(key='document_id',match=models.MatchValue(value=d['id']))]),limit=256,offset=offset,with_payload=True,with_vectors=False)
                for row in rows:actual[str(row.id)]=row.payload
                if offset is None:break
            assert set(actual)==set(expected),'Qdrant IDs incomplete or extra'
            for ident in expected:
                assert actual[ident]==expected[ident],'Qdrant payload differs from source-verified candidate'
                p=expected[ident]
                for key in ('previous_chunk_id','next_chunk_id'):
                    if p[key]:assert p[key] in expected,'Broken child link'
            totals.update(documents=1,parents=len(parents))
            print('PASS document',totals['documents'],'/',cfg['documents'],d['provider'],len(expected),flush=True)
        assert totals['points']==cfg['points']==client.count(cfg['collection'],exact=True).count,'Wrong collection count'
    finally:client.close()
    results=[]
    old=read(ROOT/'active.json',{})
    for provider,question,queries,terms in CASES:
        found=search(question,queries,config=cfg)
        assert found,'No retrieval hits'
        if provider:assert all(p['provider']==provider for p in found),'Publisher filter failed'
        assert any(any(term in (p['title']+' '+p['page_text']).casefold() for term in terms) for p in found[:4]),'Relevant document missing'
        for p in found:
            assert p['text'] in p['page_text'],'Retrieved passage absent from page'
            for parent in p['context_parents']:assert parent['text'] in p['page_text'],'Parent context mislocated'
        baseline=search(question,queries,config=old) if old and old['collection']!=cfg['collection'] else []
        results.append({'question':question,'provider':provider,'new':[{'document_id':p['document_id'],'title':p['title'],'pdf_page':p['pdf_page'],'provider':p['provider']} for p in found],
                        'previous':[{'document_id':p['document_id'],'title':p['title'],'pdf_page':p['pdf_page'],'provider':p['provider']} for p in baseline]})
        print('PASS search',provider or 'general',question,flush=True)
    report={'verified_at':now(),'collection':cfg['collection'],'schema_version':SCHEMA,'totals':dict(totals),'cases':results,
            'scope':'source-span, coverage, token, citation and retrieval checks; metadata rules and reports are not independently fact-verified'}
    save(folder/'verification.json',report)
    if publish:
        ingest=read(ROOT/'ingest-report.json');eligible={d['id'] for d in ingest['documents'] if d['status']=='extracted'}
        assert {d['id'] for d in cfg['catalog']}==eligible,'Full corpus not represented'
        if old and old['collection']!=cfg['collection']:
            save(ROOT/'previous-active.json',old)
            save(ROOT/'active-history'/(old['collection']+'.json'),old)
        save(ROOT/'active.json',{**cfg,'status':'published','verified_at':report['verified_at']})
        print('ACTIVATED',cfg['collection'],cfg['documents'],cfg['points'],flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pilot',action='store_true');parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    verify(pilot=args.pilot,publish=args.publish)
