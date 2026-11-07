"""Multi-channel search over the enriched index, returning only original page evidence."""
from collections import Counter,defaultdict
from functools import lru_cache
import re
from ngo_corpus import ROOT,allowed,read,model
from ngo_pages import source_pages
from ngo_metadata import Gazetteer,normalized,TOPIC_RE,spans
from ngo_reindex import parent_for,context_document,child_spans
from settings import QDRANT_URL


@lru_cache(maxsize=4)
def gazetteer_for(context_root):
    from pathlib import Path
    path=Path(context_root)
    if path.is_absolute() or '..' in path.parts:raise ValueError('invalid_context_root')
    return Gazetteer(read(ROOT/path/'gazetteer.json',[]))


def query_mentions(question,config):
    gaz=gazetteer_for(config['context_root'])
    page={'pdf_page':0,'page_side':'query','text':question}
    return [x for x in gaz.mentions(question,page,query=True) if grounded_query_place(x,question)]


def query_scope(question,config):
    mentions=query_mentions(question,config)
    names=list(dict.fromkeys(normalized(x['canonical_name'] or x['name']) for x in mentions))
    from ngo_geography_policy import places as resolved_places, reference
    for place in resolved_places(question):
        if place['id'] in reference().entities:
            name=re.sub(r'^(?:Kabupaten|Kota|Provinsi)\s+','',place['name'])
            if normalized(name) not in names:names.append(normalized(name))
    return names,[topic for topic,pattern in TOPIC_RE.items() if pattern.search(question)]


def focused_places(question,config):
    mentions=query_mentions(question,config)
    levels={'village':0,'urban_village':0,'subdistrict':1,'island':2,'regency':2,'city':2,
            'district_unspecified':2,'province':3,'country':4,'ambiguous':5}
    if not mentions:return query_scope(question,config)[0]
    level=min(levels.get(x['kind'],5) for x in mentions)
    return list(dict.fromkeys(normalized(x['canonical_name'] or x['name']) for x in mentions
                             if levels.get(x['kind'],5)==level))


def scope_strength(payload,places):
    if set(payload.get('location_names',[])).intersection(places):return 2
    if set(payload.get('context_location_names',[])).intersection(places):return 1
    return 0


def grounded_query_place(mention,question):
    """A learned, unverified lowercase word is not a place by itself.

    Explicit geographic types and known boundary names remain usable. Bare
    learned names need an explicit locative phrase (or a leading bare place).
    Capitalization alone can also identify species, companies or common
    concepts, so it must not create a geographic filter.
    """
    if mention.get('recognition')=='explicit_type' or mention.get('reference_id'):
        return True
    name=mention.get('name','')
    if name and name[0].isupper() and mention.get('start')==0:
        return True
    before=question[max(0,mention.get('start',0)-50):mention.get('start',0)]
    return bool(re.search(r'\b(?:di|ke|dari|in|at|on|from|wilayah|area|pulau|desa|kecamatan)\s+$',before,re.I))


def bibliography(text):
    """Do not let place names in reference lists outrank the actual study."""
    if re.search(r'^\s*(?:daftar pustaka|bibliography|references)\b',text,re.I):return True
    matches=list(re.finditer(r'(?m)^\s*\[\d{1,3}\]',text))
    urls=len(re.findall(r'https?://',text))
    return len(matches)>=3 and urls>=2 and matches[0].start()<max(250,len(text)*.35)


def neutral_search_text(text):
    # A claimed amount is what is being checked, not a required source value.
    # Observation years remain intact; only amounts with explicit units go.
    return ' '.join(re.sub(r'(?<![\w.,])\d+(?:[.,]\d+)*\s*(?:persen|%|hektare?|hectares?|ha|orang|rumah tangga)(?!\w)',
                          ' ',text,flags=re.I).split())


def rank(score,payload,question,place_names,topics):
    from ngo_source_facts import activity_conflict
    words=set(re.findall(r'\w{4,}',question.casefold()))-{'laporan','menurut','apakah','bagaimana','tentang','dalam','tahun','jelaskan','temuan','sertakan'}
    overlap=len(words & set(re.findall(r'\w{4,}',payload['text'].casefold())))
    direct=set(payload.get('location_names',[]));context=set(payload.get('context_location_names',[]))
    score+=min(overlap,6)*.025
    if direct.intersection(place_names):score+=.11
    elif context.intersection(place_names):score+=.06
    if set(payload.get('topic_ids',[])).intersection(topics):score+=.025
    specific=set(topics)-{'forests','water','health','livelihoods','gender','mining'}
    if specific and not set(payload.get('topic_ids',[])).intersection(specific):score-=.10
    # Runtime prose check also covers activities missing from older index tags
    # (for example timber plantations). A broad report title is not a match.
    if activity_conflict(question,payload['text']):score-=.18
    if payload.get('metadata',{}).get('content_kind') in ('bibliography','table_of_contents'):score-=.2
    return score


def selection_body(text,title='',repeated=()):
    """Ranking text only; original source pages and citation offsets stay intact."""
    clean=lambda s:' '.join(s.casefold().split())
    repeated={clean(s) for s in repeated}
    body=' '.join(line.strip() for line in text.splitlines()
                  if clean(line) not in repeated and not re.fullmatch(r'\s*\d{1,3}\s*',line))
    if title:
        body=re.sub(re.escape(' '.join(title.split())), ' ', body, flags=re.I)
    return ' '.join(body.split())


def page_content_score(page,wanted):
    from ngo_question_parts import facets
    from ngo_source_facts import quantities
    from ngo_metadata import spans
    body=page.get('selection_text',page.get('text',''))
    # A matching cover supplies no evidence. Relevant measurements earn a
    # bounded ranking bonus, never approval as evidence or a verdict.
    if len(body)<80:return -.25
    measured=sum(bool(quantities(body[a:b])) and bool(facets(body[a:b]) & wanted)
                 for a,b in spans(body))
    return .08*min(measured,2)


def select_pages(candidates,limit=20,question='',exclude_pages=()):
    """Cover relevant documents and question aspects before spending on repeats."""
    from ngo_question_parts import requested_facets,facets
    wanted=requested_facets(question)
    if re.search(r'dampak.*bagi warga|hanya membawa keuntungan',question,re.I):
        wanted|={'health','water','land_rights'}
    # Keep document-level locality established by an already read page, but
    # exclude that page BEFORE spending the fresh-page budget.
    local_docs={p['sha256'] for p in candidates if p.get('scope_strength',0)>0}
    excluded=set(exclude_pages)
    candidates=[p for p in candidates if (p['sha256'],p['pdf_page'],p['page_side']) not in excluded]
    ordered=sorted(candidates,key=lambda p:(-int(p.get('scope_strength',0)>0),-p['score']))
    if not ordered:return []
    if local_docs:
        ordered=[p for p in ordered if p['sha256'] in local_docs]
    best=max(p['score'] for p in ordered)
    ordered=[p for p in ordered if p['score']>=best-.40]
    by_doc=defaultdict(list)
    for p in ordered:by_doc[p['sha256']].append(p)
    # Ranking is across documents, not a round-robin publisher ordering.
    docs=sorted(by_doc,key=lambda d:-max(p['score'] for p in by_doc[d]))[:6]
    selected=[];seen=set();counts=Counter();covered=defaultdict(set)
    def identity(p):return (p['sha256'],p['pdf_page'],p['page_side'])
    def hits(p):return facets(p.get('selection_text',
        ' '.join(x['text'] for x in p.get('context_parents',[])) or p.get('text',''))) & wanted
    def choose(pool):
        p=max(pool,key=lambda p:p['score']+page_content_score(p,wanted)
              +.13*len(hits(p)-covered[p['sha256']])-.045*counts[p['sha256']])
        selected.append(p);seen.add(identity(p));counts[p['sha256']]+=1;covered[p['sha256']]|=hits(p)
    for doc in docs:
        if len(selected)>=limit:break
        choose(by_doc[doc])
    while len(selected)<limit:
        pool=[p for doc in docs for p in by_doc[doc] if identity(p) not in seen and counts[doc]<5]
        if not pool:break
        choose(pool)
    return selected


def scope_evidence(document,requested_places):
    """Select already indexed scope/method evidence, keeping its source locator."""
    candidates=[]
    for parent in document.get('parents',[]):
        locs=parent['metadata']['locations']
        names={normalized(x['canonical_name'] or x['name']) for x in locs}
        geographic=bool(names.intersection(requested_places)) and bool(re.search(r'administrasi|administratif|terbagi|terletak|administrativ|jurisdiction',parent['text'],re.I))
        method=any('survey_response' in q['status'] and q.get('population_text') for q in parent['metadata']['quantities']) and bool(re.search(r'sampel|sample|wawancara|interview',parent['text'],re.I))
        if not geographic and not method:continue
        for a,b in spans(parent['text']):
            sentence=parent['text'][a:b]
            relevant=(geographic and re.search(r'administrasi|administratif|terbagi|terletak|administrativ|jurisdiction',sentence,re.I)) or (method and re.search(r'sampel|sample|wawancara|interview',sentence,re.I) and re.search(r'\d',sentence))
            if not relevant or len(sentence)>1500:continue
            candidates.append((0 if geographic else 1,{'pdf_page':parent['pdf_page'],'page_side':parent['page_side'],
                               'start':parent['start']+a,'end':parent['start']+b,'text':sentence,'parent_id':parent['parent_id']}))
    selected=[]
    for category in (0,1):
        item=next((item for kind,item in candidates if kind==category),None)
        if item:selected.append(item)
    return selected


def geographic_points(client,collection,geographic,max_points=12288):
    offset=None;read_count=0
    while read_count<max_points:
        points,following=client.scroll(collection,scroll_filter=geographic,
            offset=offset,limit=min(384,max_points-read_count),with_payload=True,with_vectors=False)
        yield from points
        read_count+=len(points)
        if following is None:return
        if not points or following==offset:raise RuntimeError('ngo_geographic_scroll_stalled')
        offset=following
    # The semantic channels still run; reaching this work budget is not absence.
    import logging
    logging.getLogger('cekdata.local').info('NGO geographic search budget reached: %d',read_count)


def search(question,queries,config,*,exclude_pages=()):
    from qdrant_client import QdrantClient,models
    from tokenizers import Tokenizer
    from ngo_answer import source_filter
    places,topics=query_scope(question,config)
    focus=focused_places(question,config)
    providers=source_filter(question)
    must=[models.FieldCondition(key='provider',match=models.MatchAny(any=providers))] if providers else []
    base=models.Filter(must=must) if must else None
    geographic=models.Filter(must=must,should=[models.FieldCondition(key=key,match=models.MatchAny(any=places)) for key in ('location_names','context_location_names')]) if places else None
    narrative=re.split(r'[?]',question,maxsplit=1)[0]
    narrative=re.sub(r'\b(?:bagaimana|apakah|benarkah|terhadap|di|dan hutan)\b',' ',narrative,flags=re.I)
    narrative=neutral_search_text(narrative)
    from ngo_question_parts import aspect_queries
    all_queries=list(dict.fromkeys([question,' '.join(narrative.split())]+list(queries or [])[:2]
                                  +aspect_queries(question)))[:6]
    encoder=model();tokenizer=Tokenizer.from_str(encoder.model.tokenizer.to_str());tokenizer.no_truncation();tokenizer.no_padding()
    # Long questions are split into bounded searches, not silently truncated.
    bounded=[]
    for query in all_queries:
        bounded.extend(query[a:b] for a,b in child_spans(query,tokenizer,max_tokens=120,overlap_words=8))
    bounded=list(dict.fromkeys(bounded))[:8]
    client=QdrantClient(url=QDRANT_URL,timeout=30);by_page={};page_cache={}
    def add(p,similarity,record_id,local_document=False):
        if not p or not allowed(p.get('source_url','')) or not allowed(p.get('download_url','')):return
        if p['document_id'] not in page_cache:
            page_cache[p['document_id']]={(page['pdf_page'],page['page_side']):page for page in
                source_pages(config,p['provider'],p['document_id'])}
        page=page_cache[p['document_id']].get((p['pdf_page'],p['page_side']))
        if not page or bibliography(page['text']):return
        parent=parent_for(config,p)
        if parent is None:raise ValueError('missing_parent_context')
        if bibliography(parent['text']):return
        # Ranking-only document context is not inherited geographic metadata.
        # The source scope passages and final fit check must prove its scope.
        p={**p,'scope_strength':max(scope_strength(p,focus),1 if local_document else 0)}
        score=rank(similarity,p,question,places,topics)+(.08 if p['scope_strength'] else -.08 if focus else 0)
        key=(p['sha256'],p['pdf_page'],p['page_side'])
        if key not in by_page or score>by_page[key]['score']:
            previous=by_page.get(key,{}).get('context_parents',[])
            by_page[key]={**p,'score':score,'passage_id':str(record_id),'context_parents':[parent]+[x for x in previous if x['parent_id']!=parent['parent_id']][:1]}
        elif parent['parent_id'] not in [x['parent_id'] for x in by_page[key]['context_parents']] and len(by_page[key]['context_parents'])<2:
            by_page[key]['context_parents'].append(parent)
    try:
        # Exact location metadata is a bounded extra channel, independent of
        # the semantic similarity of a positive/negative claim's wording.
        if geographic:
            for item in geographic_points(client,config['collection'],geographic):
                add(item.payload,.32,item.id)
        vectors=list(encoder.embed(bounded))
        for index,vector in enumerate(vectors):
            channels=[base]+([geographic] if geographic and index<2 else [])
            for filt in channels:
                hits=client.query_points(config['collection'],query=vector.tolist(),query_filter=filt,limit=32,with_payload=True).points
                for hit in hits:
                    if hit.score>=.30:add(hit.payload,hit.score,hit.id)
        # A method page can establish a study's geography while its findings
        # omit the district name. Search inside those documents for the actual
        # outcome, rather than returning only geographic introduction pages.
        local_docs=[];provider_counts=Counter()
        for p in sorted(by_page.values(),key=lambda p:-p['score']):
            if not p['scope_strength'] or p['document_id'] in local_docs or provider_counts[p['provider']]>=2:continue
            local_docs.append(p['document_id']);provider_counts[p['provider']]+=1
            if len(local_docs)==6:break
        if vectors:
            vector=vectors[min(1,len(vectors)-1)]
            for document_id in local_docs:
                filt=models.Filter(must=must+[models.FieldCondition(key='document_id',match=models.MatchValue(value=document_id))])
                for hit in client.query_points(config['collection'],query=vector.tolist(),query_filter=filt,limit=8,with_payload=True).points:
                    if hit.score>=.18:add(hit.payload,hit.score,hit.id,local_document=True)
    finally:client.close()
    # Adjacent parent evidence may sit on a different page. Keep its own locator.
    candidates=list(by_page.values());doc_cache={}
    for p in sorted(candidates,key=lambda x:-x['score'])[:6]:
        document=context_document(config['context_root'],p['document_id'])
        parents={item['parent_id']:item for item in document.get('parents',[])}
        for parent in p['context_parents'][:1]:
            for key in ('previous_parent_id','next_parent_id'):
                other=parents.get(parent.get(key))
                if not other:continue
                if bibliography(other['text']):continue
                identity=(p['sha256'],other['pdf_page'],other['page_side'])
                if identity in by_page:continue
                other_names=list(dict.fromkeys(normalized(x['canonical_name'] or x['name']) for x in other['metadata']['locations']))
                by_page[identity]={**p,'pdf_page':other['pdf_page'],'page_side':other['page_side'],
                    'printed_page':other['printed_page'],'text':other['text'],'start':other['start'],'end':other['end'],
                    'parent_id':other['parent_id'],'metadata':{},'context_metadata':other['metadata'],
                    'section_heading':other.get('heading'),'location_names':[],
                    'context_location_names':other_names,
                    'scope_strength':1 if set(other_names).intersection(focus) else 0,
                    'score':p['score']-.08,'passage_id':'adjacent-parent','context_parents':[other]}
    # Read the full page for ranking, not just the best matching chunk. Strip
    # repeated headers here only; citation text remains the original page.
    repeated_by_doc={}
    for doc,pages in page_cache.items():
        counts=Counter(line.strip() for page in pages.values()
                       for line in set(page['text'].splitlines()) if len(line.strip())>12)
        repeated_by_doc[doc]={line for line,n in counts.items() if n>=max(3,len(pages)*.4)}
    for p in by_page.values():
        page=page_cache.get(p['document_id'],{}).get((p['pdf_page'],p['page_side']))
        p['selection_text']=selection_body(page['text'] if page else p['text'],p.get('title',''),
                                          repeated_by_doc.get(p['document_id'],()))
    result=[]
    for p in select_pages(list(by_page.values()),question=question,exclude_pages=exclude_pages):
        if p['document_id'] not in doc_cache:
            doc_cache[p['document_id']]=source_pages(config,p['provider'],p['document_id'])
        page=next((x for x in doc_cache[p['document_id']] if x['pdf_page']==p['pdf_page'] and x['page_side']==p['page_side']),None)
        if page is None or page['status']!='readable':raise ValueError('missing_source_page')
        p['page_text']=page['text'];p['text_extraction']=page.get('extraction_method','pdf_text')
        p['evidence_id']='D'+str(len(result)+1)
        p['index_schema_version']=config['schema_version']
        document=context_document(config['context_root'],p['document_id'])
        p['document_context']=document.get('document',{})
        p['source_pages_root']=config.get('pages_root','')
        from ngo_method_context import method_evidence
        p['method_evidence']=method_evidence(document,p['pdf_page'])
        p['indexed_scope_evidence']=scope_evidence(document,places)
        result.append(p)
    return result
