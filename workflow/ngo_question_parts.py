"""Bounded evidence coverage, independent of publisher, project or place names."""
import re

FACETS = {
    'water': r'air bersih|sumber air|\bair\b|irigasi|sungai|water|irrigation|river',
    'health': r'kesehatan|penyakit|sakit|ISPA|bronkitis|asma|kematian|prematur|pernapasan|morbiditas|keselamatan|kecelakaan|health|disease|illness|safety|injur',
    'livelihood': r'penghidupan|kehidupan (?:warga|masyarakat|penduduk)|mata pencaharian|pendapatan|sejahtera|keuntungan|kerugian|ekonomi|nelayan|petani|upah|pekerjaan|biaya hidup|livelihood|income|fisher|farmer|welfare|wage|employment|cost of living',
    'land_rights': r'hak|tanah|lahan|adat|ruang hidup|relokasi|penggusuran|land|rights|customary|displace|relocation',
    'environment': r'lingkungan|hutan|pencemaran|banjir|environment|forest|pollution|flood',
    'energy': r'akses energi|akses listrik|kebutuhan listrik|pasokan listrik|elektrifikasi|\bRE\s+(?:PLN|di)\b|electricity|electrification|energy access',
}
SEARCH_TERMS = {
    'water':'sumber air irigasi water', 'health':'kesehatan penyakit health',
    'livelihood':'pendapatan upah pekerjaan biaya hidup hasil panen tangkapan naik turun income wages livelihoods', 'land_rights':'hak tanah warga land rights',
    'environment':'lingkungan pencemaran forest pollution', 'energy':'akses listrik electrification',
}

def facets(text):
    return {k for k,p in FACETS.items() if re.search(p,text,re.I)}

def requested_facets(question):
    # Separate an explicit statistics request from the documentary question.
    narrative=re.split(r'\b(?:tambahkan|tampilkan)\b.*?kehilangan tutupan',question,flags=re.I)[0]
    wanted=facets(narrative)
    if not wanted and re.search(r'dampak|masalah|kerugian|kehidupan warga',narrative,re.I):
        wanted={'livelihood','environment'}
    return wanted

def missing_facets(question,findings,fits=None):
    # Keyword presence is a search hint, not proof that an aspect was answered.
    # In production, use the source-grounded review's explicit coverage only.
    if fits is None:
        covered=set().union(*(facets(f.text) for f in findings)) if findings else set()
    else:
        covered=set().union(*(set(fit.answered_aspects) for fit in fits
            if fit.geography in ('same','within_requested_area') and fit.activity=='same')) if fits else set()
    return requested_facets(question)-covered


def aspect_queries(question):
    """Search outcomes in both directions; never require a claim to be true."""
    narrative=re.split(r'\b(?:tambahkan|tampilkan)\b.*?kehilangan tutupan',question,flags=re.I)[0]
    return [narrative+' '+SEARCH_TERMS[k] for k in sorted(requested_facets(question))][:2]


def source_candidates(question,findings,fits,evidence,limit=4):
    """Original sentences for a second review, never automatically approved facts.

    Extraction can omit numbers while returning a qualitative recommendation.
    Try a bounded set of already retrieved sentences before searching elsewhere.
    All candidates still require the normal source, geography and fit checks.
    """
    from ngo_metadata import spans,language
    from ngo_source_facts import quantities,activity_supported
    from ngo_geography_policy import scope_decision
    from ngo_evidence_status import status_tags
    wanted=requested_facets(question)
    response_language='en' if language(question)['code']=='en' else 'id'
    missing=missing_facets(question,findings,fits)
    data_request=bool(re.search(r'\b(?:data|angka|berapa|persentase|rasio|jumlah|luas)\b',question,re.I))
    measured=set().union(*(set(fit.answered_aspects) for f,fit in zip(findings,fits)
        if fit.geography in ('same','within_requested_area') and fit.activity=='same'
        and quantities(f.text))) if findings else set()
    numeric_missing=wanted-measured if data_request else set()
    if not missing and not numeric_missing:return []
    pool=[];seen=set()
    for page in evidence:
        for passage in page.get('passages',[]):
            for a,b in spans(passage['text']):
                raw=passage['text'][a:b];text=' '.join(raw.split())
                key=(page['sha256'],text.casefold())
                if key in seen or len(text)<40 or len(text)>1200:continue
                seen.add(key)
                # This fallback copies rather than translates. Other-language
                # pages still go through the normal model extraction path.
                source_language=language(text)['code']
                if source_language in ('id','en') and source_language!=response_language:continue
                if not re.search(r'[.!?]["”’\']?$',text):continue
                # PDF captions/headings can be joined to the next sentence.
                # Do not inject those as findings; ordinary extraction still
                # has the complete page and can separate their actual prose.
                if re.match(r'^(?:Lembar Fakta|Kronologi\b|(?:Gambar|Figure|Tabel|Table)\s+\d)',text,re.I):continue
                hits=facets(text)&wanted
                numeric=bool(quantities(text))
                if not (hits & missing or (numeric and hits & numeric_missing)):continue
                if any(text in f.text or f.text in text for f in findings):continue
                relation,_=scope_decision(question,text,raw,page.get('page_text',''),
                    (page.get('continued_scope') or {}).get('continuation_text',''),
                    page.get('source_addresses',[]),page.get('project_links',[]))
                if relation in ('unknown','different','narrowed','broader_context'):continue
                if not activity_supported(question,text,raw,passage.get('context',''),page.get('title','')):continue
                pool.append({'page':page,'text':text,'quote':raw,'aspects':hits,
                             'qualified':bool(status_tags(text)),
                             'numeric_aspects':hits & numeric_missing if numeric else set()})
    result=[];covered=set()
    while pool and len(result)<limit:
        row=max(pool,key=lambda r:(bool(r['numeric_aspects']),len(r['aspects']-covered),
                                  not r['qualified'],len(r['aspects']),-len(r['text'])))
        pool.remove(row);result.append(row);covered.update(row['aspects'])
    return result
