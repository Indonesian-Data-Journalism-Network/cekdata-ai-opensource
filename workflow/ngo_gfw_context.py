"""Bounded GFW context for narrative questions, with exact geography and periods."""
import re
from decimal import Decimal

def finer_scope(question, evidence=()):
    """Recognize requested subdistrict/island names from source text, not a place list."""
    explicit = re.search(r'\b(pulau|kecamatan|desa|kelurahan)\s+([\w-]+(?:\s+[A-Z][\w-]+){0,2})', question, re.I)
    if explicit:
        # Only the type is needed for the guard; use actual source spelling below.
        return explicit.group(1).casefold()
    # An explicitly named administrative level resolves an otherwise ambiguous
    # bare name (e.g. a province and an island sharing a name).
    remaining = re.sub(r'\b(?i:kabupaten|kota|provinsi)\s+[A-Z][\w-]+(?:\s+[A-Z][\w-]+){0,2}', '', question)
    for page in evidence or ():
        texts = [page.get('title', ''), page.get('scope_context', ''), page.get('page_text', ''),
                 *(item['text'] for item in page.get('scope_evidence', []))]
        for text in texts:
            for match in re.finditer(r'\b(?i:pulau|kecamatan|desa|kelurahan)\s+([A-Z][\w-]+(?:\s+[A-Z][\w-]+){0,2})', text):
                words = match.group(1).split()
                for length in range(len(words), 0, -1):
                    name = ' '.join(words[:length])
                    if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', remaining, re.I):
                        return match.group(0).split()[0].casefold()
    return ''


def exact_administrative_names(question,family):
    # An explicit new/different administrative name must not collapse to a
    # shorter old name merely because it shares a prefix in the GFW catalogue.
    names=set()
    for area in family.get('areas',[]):
        names.add(re.sub(r'^(?:kabupaten|kota|provinsi)\s+','',area.split(',')[0].casefold()))
    for alias in family.get('area_aliases',{}):
        names.add(re.sub(r'^(?:kabupaten|kota|provinsi)\s+','',alias.split(',')[0].casefold()))
    # Bare compound place names need the same guard as explicitly typed ones.
    # A known prefix is not the requested administrative geography.
    for name in names:
        for match in re.finditer(r'(?<!\w)'+re.escape(name)+r'\s+(barat daya|utara|selatan|timur|barat|tengah|pegunungan)\b',question,re.I):
            if match.group(0).casefold() not in names:return False
    for match in re.finditer(r'\b(?:kabupaten|kota|provinsi)\s+([^,.;?!:]+)',question,re.I):
        phrase=match.group(1).casefold()
        if not any(re.match(re.escape(name)+r'(?!\w)',phrase) for name in names):return False
    return True


def resolve_administrative_references(question, family):
    """Resolve only a unique explicitly named antecedent of the same level."""
    pattern=r'\b(kabupaten|kota|provinsi)\s+(?:ini|tersebut)\b'
    for match in reversed(list(re.finditer(pattern,question,re.I))):
        level=match.group(1).casefold(); before=question[:match.start()]
        candidates=set()
        for area in family.get('areas',[]):
            name=area.split(',')[0]
            if level in ('kabupaten','kota') and not name.casefold().startswith(level+' '):continue
            if level=='provinsi':
                if name.casefold().startswith(('kabupaten ','kota ')) or name.casefold()=='indonesia':continue
                name='Provinsi '+re.sub(r'^provinsi\s+','',name,flags=re.I)
            if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',before,re.I):candidates.add(name)
        if len(candidates)!=1:return None
        question=question[:match.start()]+next(iter(candidates))+question[match.end():]
    return question


def plan(question, catalog, reference, evidence=()):
    from flow import SearchQuery
    original=question
    family=next((c for c in catalog if 'gfw-tree-cover-loss' in c.get('member_ids',[])),None)
    if not family:return None
    question=resolve_administrative_references(question,family)
    if question is None:return None
    q=question.casefold()
    # The contextual series below is total tree-cover loss. Do not present it
    # when a more specific loss indicator was requested, or for unrelated topics.
    if re.search(r'\b(kebakaran|hutan primer|mangrove|gambut|karbon|emisi)\b',q):
        return None
    if not re.search(r'\b(nikel|tambang|pertambangan|sawit|perkebunan|hutan|deforestasi|tutupan pohon|food estate)\b',q):
        return None
    # These are finer than the national/province/district catalogue. Never replace
    # a requested island, village or subdistrict with its enclosing district.
    if finer_scope(question, evidence):
        # A separately stated GFW request may intentionally ask for the district
        # as wider context. Require that scope to be explicit rather than infer it.
        clause = re.search(r'\b(?:gfw|global forest watch|(?:data\s+)?kehilangan tutupan pohon|(?:data\s+)?deforestasi)\b(.*)', question, re.I)
        if not clause or finer_scope(clause.group(1), evidence):return None
        q = clause.group(1).casefold()
        if not re.search(r'\b(?:kabupaten|kota|provinsi|indonesia)\b', q):return None
    if not exact_administrative_names(q,family):return None
    hits=[]
    for alias,canonical in family.get('area_aliases',{}).items():
        for match in re.finditer(r'(?<!\w)'+re.escape(alias.casefold())+r'(?!\w)',q):
            hits.append((match.start(),match.end(),canonical))
    for area in family.get('areas',[]):
        # District names include the province after a comma; accept the full
        # administrative name or the province/national name as written.
        candidates=[area,area.split(',')[0]]
        for name in candidates:
            for match in re.finditer(r'(?<!\w)'+re.escape(name.casefold())+r'(?!\w)',q):
                hits.append((match.start(),match.end(),area))
    selected=[]
    for start,end,area in sorted(hits,key=lambda hit:hit[1]-hit[0],reverse=True):
        if not any(start<e and end>s for s,e,_ in selected):selected.append((start,end,area))
    areas=list(dict.fromkeys(area for _,_,area in selected))
    if len(areas)!=1:return None
    available=sorted(int(y) for y in family.get('years',[]) if int(y)<reference.year)
    if not available:return None
    explicit=[int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b',q)]
    if len(explicit)>2:return None
    if len(explicit)==2:
        first,last=explicit
        if first>last or last-first>30:return None
        years=list(range(first,last+1))
    elif len(explicit)==1:years=explicit
    else:years=list(range(max(available)-4,max(available)+1))
    if any(y not in available for y in years):return None
    return SearchQuery(text=original,indicator_ids=[family['indicator_id']],areas=areas,years=years,population='total')

async def retrieve(question, catalog, reference, retriever, evidence=(), *, request_intent=None):
    from answer_format import rounded
    contextual_question=question
    if request_intent is not None:
        # A mixed question can give the report and the statistical series
        # different observation periods. Use the explicitly scoped statistical
        # part only when the existing geography/indicator guards can resolve it.
        scoped=[part for part in request_intent.question_parts
                if re.search(r'kehilangan tutupan pohon|deforestasi',part,re.I)]
        if len(scoped)==1 and plan(scoped[0],catalog,reference,evidence) is not None:
            contextual_question=scoped[0]
    query=plan(contextual_question,catalog,reference,evidence)
    if query is None:return None
    batch=await retriever.search(query)
    if batch.truncated:return None
    records=sorted(batch.records,key=lambda r:r.year)
    if len(records)!=len(query.years) or [r.year for r in records]!=sorted(query.years):return None
    if any(r.area.casefold()!=query.areas[0].casefold() or r.unit!='ha' or r.month is not None for r in records):return None
    values=[Decimal(r.value) for r in records]
    changes=[b-a for a,b in zip(values,values[1:])]
    direction=('tetap setiap tahun' if changes and all(x==0 for x in changes) else
               'naik setiap tahun' if changes and all(x>0 for x in changes) else
               'turun setiap tahun' if changes and all(x<0 for x in changes) else
               'tidak menurun' if changes and all(x>=0 for x in changes) else
               'tidak meningkat' if changes and all(x<=0 for x in changes) else
               'berfluktuasi' if changes else 'tersedia untuk satu tahun')
    years=f'{records[0].year}–{records[-1].year}' if len(records)>1 else str(records[0].year)
    summary=f"GFW mencatat kehilangan tutupan pohon di {records[0].area} selama {years} sebesar {rounded(str(sum(values)))} ha. Pola tahunannya {direction}." if len(records)>1 else f"GFW mencatat kehilangan tutupan pohon di {records[0].area} pada {years} sebesar {rounded(records[0].value)} ha."
    table={'caption':f'Kehilangan tutupan pohon — {records[0].area}', 'headers':['Tahun','Kehilangan (ha)'],
           'rows':[[str(r.year),rounded(r.value)] for r in records], 'calculations':[]}
    if len(records)>1:table['calculations'].append({'label':f'Total {years}','value':rounded(str(sum(values))),'unit':'ha'})
    sources=[]
    for r in records:
        s={'id':r.id,'source':r.source_name or r.source,'title':r.title,'display':r.title or r.source,
           'url':r.source_url,'download_url':r.download_url,'api_url':r.api_source_url,
           'methodology_url':r.methodology_url,'source_record_id':r.source_record_id}
        if s not in sources:sources.append(s)
    return {'summary':summary,'table':table,'parsed':{'source_items':sources,'download_records':[r.model_dump() for r in records]},
            'context':'Kehilangan tutupan pohon tidak selalu berarti deforestasi permanen; data ini tidak membuktikan penyebabnya.'}
