"""Source-backed quantities and local prose scopes, independent of any case/place.

These checks preserve source semantics; they never infer causation or a parent
administrative area from a matching word elsewhere in a report.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from ngo_metadata import spans, explicit_places, normalized

BOUND = (r'lebih\s+dari|lebih\s+besar\s+dari|kurang\s+dari|setidaknya|sedikitnya|'
         r'paling\s+sedikit|minimal|maksimal|paling\s+banyak|hingga|sampai|'
         r'sekitar|kira-kira|diperkirakan|hampir|nearly|almost|more\s+than|over|less\s+than|under|'
         r'at\s+least|at\s+most|up\s+to|approximately|about|around|[<>]=?')
AMOUNT = r'\d+(?:[.,]\d+)*'
QUANTITY = re.compile(r'(?<![\w.,])(?:(?P<bound>'+BOUND+r')\s*)?'
    r'(?:(?P<currency>Rp\.?|IDR)\s*)?(?P<value>'+AMOUNT+r')'
    r'(?:\s*(?:–|—|-|sampai\s+dengan|to)\s*(?P<upper>'+AMOUNT+r'))?\s*'
    r'(?P<unit>(?:(?:ribu|juta|miliar|triliun|thousand|million|billion|trillion)\s+)?'
    r'(?:persen|percent|%|hektare|hektar|hectares?|ha|rumah\s+tangga|households?|'
    r'orang|jiwa|warga|penduduk|people|pasien|patients?|hari|days?|kasus|cases?|kematian|deaths?|kunjungan|visits?|narasumber|responden|respondents?|interviewees?|sampel|samples?)|'
    r'ribu|juta|miliar|triliun|thousand|million|billion|trillion)?(?!\w)',re.I)


def operator(raw):
    raw=' '.join((raw or '').casefold().split())
    if raw in ('lebih dari','lebih besar dari','more than','over','>'):return 'gt'
    if raw in ('kurang dari','less than','under','<'):return 'lt'
    if raw in ('setidaknya','sedikitnya','paling sedikit','minimal','at least','>='):return 'ge'
    if raw in ('maksimal','paling banyak','hingga','sampai','at most','up to','<='):return 'le'
    if raw in ('hampir','nearly','almost'):return 'near'
    if raw:return 'approx'
    return 'eq'


def decimal(raw):
    try:
        if ',' in raw and '.' in raw:raw=raw.replace('.','').replace(',','.')
        elif re.fullmatch(r'\d{1,3}(?:\.\d{3})+',raw):raw=raw.replace('.','')
        else:raw=raw.replace(',','.')
        return Decimal(raw)
    except InvalidOperation:return None


def quantities(text):
    result=[]
    for m in QUANTITY.finditer(text):
        unit=' '.join((m['unit'] or '').casefold().split())
        if not unit and not m['currency']:continue # years, footnotes and page numbers
        if unit in ('ribu','juta','miliar','triliun','thousand','million','billion','trillion') and not m['currency']:continue
        canonical=('percent' if unit in ('%','persen','percent') else
                   'ha' if unit in ('ha','hektar','hektare','hectare','hectares') else
                   'households' if unit in ('rumah tangga','household','households') else
                   'people' if unit in ('orang','jiwa','warga','penduduk','people','narasumber','responden','respondent','respondents','interviewee','interviewees') else
                   'cases' if unit in ('kasus','case','cases') else
                   'deaths' if unit in ('kematian','death','deaths') else
                   'visits' if unit in ('kunjungan','visit','visits') else
                   'patients' if unit in ('pasien','patient','patients') else
                   'days' if unit in ('hari','day','days') else
                   'samples' if unit in ('sampel','sample','samples') else unit)
        if m['currency']:canonical='IDR'+(' '+unit if unit else '')
        result.append({'value':m['value'],'upper':m['upper'], 'operator':'range' if m['upper'] else operator(m['bound']),
                       'unit':canonical,'unit_literal':m['unit'] or '', 'literal':m.group().strip(),'start':m.start(),'end':m.end()})
    # Counts such as "35 dari 877 warga" have an implicit numerator unit.
    # Keep both values and their original spans; the population is not a
    # second outcome and must not be silently dropped from numeric checks.
    ratio=re.compile(r'(?<![\w.,])(?:(?P<bound>'+BOUND+r')\s*)?(?P<n>'+AMOUNT+r')\s*(?:(?:orang|jiwa|warga|penduduk|people)\s+)?(?:dari|of|out of)\s+(?P<d>'+AMOUNT+r')\s+(?:orang|jiwa|warga|penduduk|people)\b',re.I)
    for m in ratio.finditer(text):
        denominator=next((q for q in result if q['start']==m.start('d')),None)
        if not denominator:continue
        denominator['role']='population_basis'
        numerator=next((q for q in result if q['start']<=m.start('n')<q['end']),None)
        if numerator is None:
            numerator={'value':m['n'],'upper':None,'operator':operator(m['bound']),'unit':'people',
                'unit_literal':'orang','literal':m.group(),'start':m.start(),'end':m.end()}
            result.append(numerator)
        numerator['population_basis']=m['d']
    return sorted(result,key=lambda q:q['start'])


def same_quantity(a,b):
    return (decimal(a['value'])==decimal(b['value']) and a['unit']==b['unit']
            and (decimal(a['upper']) if a['upper'] else None)==(decimal(b['upper']) if b['upper'] else None))


def source_quantity(finding,proof):
    """One table metric, retaining bounds AND the original respondent basis."""
    reported=quantities(finding);source=quantities(proof)
    # Counts accompanying a percentage are its basis, not another metric.
    primary=[q for q in reported if q['unit']=='percent'] or [q for q in reported if q.get('role')!='population_basis']
    if len(primary)!=1:return None
    q=primary[0]
    matches=[s for s in source if same_quantity(q,s)]
    if not matches:return None
    semantics={(s['operator'],s['upper']) for s in matches}
    if len(semantics)!=1:return None
    s=matches[0]
    names={'gt':'Lebih dari','lt':'Kurang dari','ge':'Setidaknya','le':'Hingga','approx':'Sekitar','near':'Hampir','eq':'','range':''}
    value=(names[s['operator']]+' '+q['value']).strip()
    if s['upper']:value+='–'+s['upper']
    unit={'percent':'persen','ha':q['unit_literal'],'households':'rumah tangga','people':'orang','samples':'sampel','cases':'kasus','deaths':'kematian','visits':'kunjungan','patients':'pasien','days':'hari'}.get(q['unit'],q['unit'])
    if q['unit'].startswith('IDR'):
        value=value.replace(q['value'],'Rp'+q['value'],1)
        if s['upper']:value=value.replace('–'+s['upper'],'–Rp'+s['upper'],1)
        scale=q['unit'][3:].strip()
        if scale:value+=' '+scale
    else:value+=' '+unit
    basis=(s['population_basis']+' orang' if s.get('population_basis') else '')
    if s['unit']=='percent':
        # Keep the source's literal count/population, rather than making an
        # interview sample into a household census through a generated label.
        nearby=proof[max(0,s['start']-220):min(len(proof),s['end']+240)]
        b=re.search(r'\b(?:dari|of|among|out of)\s+(\d+)\s*(?:orang\s+)?'
                    r'(narasumber|responden|rumah tangga|households?|respondents?|interviewees?)',nearby,re.I)
        if b:basis=b.group(1)+' '+b.group(2)
    return {**s,'display':value,'basis':basis}


def quantity_errors(text,proof):
    """Do not turn source bounds/estimates into exact figures (or vice versa)."""
    errors=[]
    source=quantities(proof)
    for q in quantities(text):
        matches=[s for s in source if same_quantity(q,s)]
        if matches and not any(q['operator']==s['operator'] for s in matches):
            errors.append('Pertahankan batas, rentang, atau perkiraan pada angka sumber: '+matches[0]['literal'])
    return errors


SCOPE_KINDS=('province','regency','city','subdistrict','village','urban_village','hamlet','island')


def named_facilities(text):
    # Technology is part of the entity: a waste-to-energy facility cannot be
    # substituted for a coal plant just because both discuss air pollution.
    pattern=r'\b((?i:PLTSa|PLTGU|PLTU|PLTP|PLTB|PLTS|PLTA|PLTG|PLTD))\s+([A-Z][a-zA-Z-]+(?:\s+[A-Z][a-zA-Z-]+){0,2})'
    return {' '.join((kind+' '+name).casefold().split()) for kind,name in re.findall(pattern,text)}


def facility_names_grounded(text,proof):
    return all(name in ' '.join(proof.casefold().split()) for name in named_facilities(text))


def different_named_facility(question,proof):
    requested=named_facilities(question);actual=named_facilities(proof)
    return bool(requested and actual and requested.isdisjoint(actual))

def prose_blocks(text):
    """Split at an explicit change of local subject, never by query location."""
    sections=re.split(r'\n(?=[ \t]*\d+(?:\.\d+){1,}[ \t]+[A-Za-z])',text)
    if len(sections)>1:return [block for section in sections for block in prose_blocks(section)]
    sentences=[text[a:b] for a,b in spans(text)]
    blocks=[];current=[];active={}
    for sentence in sentences:
        here={kind:{normalized(p['name']) for p in explicit_places(sentence) if p['kind']==kind}
              for kind in SCOPE_KINDS}
        changed=any(names and active.get(kind) and names.isdisjoint(active[kind]) for kind,names in here.items())
        if changed:
            blocks.append(current);current=[];active={}
        current.append(sentence)
        active.update({kind:names for kind,names in here.items() if names})
    if current:blocks.append(current)
    return blocks


def event_scope_valid(question,finding,proof,page):
    """A neighboring project's place must not supply an unnamed event's scope."""
    requested=explicit_places(question)
    requested+=[p for p in boundary_gazetteer().mentions(question,{'text':question,'pdf_page':0,'page_side':'query'},query=True) if p.get('reference_id')]
    wanted={kind:{normalized(p['name']) for p in requested if p['kind']==kind} for kind in SCOPE_KINDS}
    if not any(wanted.values()) or not page:return True
    retained=explicit_places(finding)+boundary_gazetteer().mentions(finding,{'text':finding,'pdf_page':0,'page_side':'finding'})
    active={}
    for a,b in spans(page):
        sentence=page[a:b]
        located=explicit_places(sentence)
        for index,place in enumerate(located):
            # A line break may truncate the typed-name parser. Expand only
            # when the full retained name is literally present at that offset.
            for named in retained:
                if named['kind']!=place['kind'] or not normalized(named['name']).startswith(normalized(place['name'])+' '):continue
                match=re.match(r'\s+'.join(re.escape(w) for w in named['name'].split())+r'(?!\w)',sentence[place['start']:],re.I)
                if match and '\n' in match.group():place={**place,'name':named['name']};break
            # Keep the normalized identity without changing source offsets.
            located[index]=place
        for kind in wanted:
            here={normalized(p['name']) for p in located if p['kind']==kind}
            here={name for name in here if not any(other.startswith(name+' ') for other in here)}
            if here:active[kind]=here
        if len(sentence)<35 or normalized(sentence) not in normalized(proof):continue
        for kind,names in wanted.items():
            local=active.get(kind,set())
            if names and local and local.isdisjoint(names):
                # Use the most recent explicit event subject. An introductory
                # list of several districts cannot locate a later project.
                if not local & {normalized(p['name']) for p in retained if p['kind']==kind}:return False
    return True


def population_supported(text,proof):
    metric=source_quantity(text,proof)
    if not metric or not metric['basis']:return True
    individual=bool(re.search(r'narasumber|interviewees?',metric['basis'],re.I))
    household_subject=bool(re.search(r'(?:persen|%)\s+(?:dari\s+)?(?:seluruh\s+)?rumah tangga',text,re.I))
    return not (individual and household_subject)


def table_label(label,metric,finding=''):
    """A sample of individuals must not become a percentage of households."""
    basis=metric.get('basis','')
    # A count of tested samples is not a concentration measurement. Keep the
    # already-grounded finding rather than inventing a short measurement label.
    if metric.get('unit')=='samples':
        label=finding or 'Jumlah sampel'
    if re.search(r'narasumber|interviewees?',basis,re.I):
        label=re.sub(r'^(?:Persentase\s+)?rumah tangga(?=\s+yang\b)',
                     'Narasumber' if re.search('narasumber|interviewee',basis,re.I) else 'Responden',label,flags=re.I)
    if basis:label+=' — basis: '+basis
    return label


def report_relative_period(text):
    """Relative source periods do not move forward with the application's date."""
    amount=r'(?:\d+|satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|dua belas)'
    return re.sub(r'\b(?:dalam|selama)\s+('+amount+r'\s+(?:hari|minggu|bulan|tahun))\s+terakhir\b',
                  r'dalam periode \1 yang dibahas laporan',text,flags=re.I)


def qualified_numeric_excerpts(text,question):
    """Original projection sentences, excluding a prior footnoted incident."""
    wanted=quantities(question)
    for a,b in spans(text):
        for sentence in re.split(r'(?<=[.!?])\d{1,3}\s+(?=[A-Z])',text[a:b]):
            sentence=sentence.strip()
            if not 45<=len(sentence)<=1000 or not re.search(r'estimasi|pemodelan|simulasi|diproyeksi|berisiko',sentence,re.I):continue
            if any(same_quantity(q,s) for q in wanted for s in quantities(sentence)):yield sentence


def report_count_excerpts(text,question):
    """Recover source counts for report-content checks, including counterevidence.

    Values need not equal the user's number. These are only candidates; the
    normal grounding, scope, outcome and numeric matching checks still apply.
    """
    if not re.search(r'laporan|studi|survei|penelitian',question,re.I):return
    wanted={q['unit'] for q in quantities(question) if q.get('role')!='population_basis'}
    if not wanted:return
    stop={'benarkah','laporan','menyebut','menurut','sekitar','tentang','dari','yang','dengan','pada','orang','warga'}
    words=set(re.findall(r'\w{4,}',question.casefold()))-stop
    sentences=[text[a:b] for a,b in spans(text)]
    for i,sentence in enumerate(sentences):
        if not any(q['unit'] in wanted for q in quantities(sentence)):continue
        excerpt=' '.join(sentences[max(0,i-1):i+1])
        if 45<=len(excerpt)<=1000 and len(words & set(re.findall(r'\w{4,}',excerpt.casefold())))>=2:
            yield excerpt


def unbacked_outcome(text,proof):
    if re.search(r'memerintahkan|perintah|direkomendasikan|merekomendasikan',proof,re.I) and re.search(r'pencabutan|mencabut|dicabut',proof,re.I):
        if re.search(r'telah\s+(?:mencabut|dicabut)|sudah\s+(?:mencabut|dicabut)',text,re.I) and not re.search(r'telah\s+(?:mencabut|dicabut)|sudah\s+(?:mencabut|dicabut)',proof,re.I):
            return True
    # Prohibits an invented opposition to an economic claim from being added
    # to a source passage that contains no such measured/claimed outcome.
    dimensions=[r'kesejahteraan|sejahtera|welfare|well-being|prosperity',
                r'pendapatan|penghasilan|income|earnings?',r'produktivitas|productivity']
    for dim in dimensions:
        if re.search(r'(?:bukan|tidak|belum)[^.!?]{0,45}(?:'+dim+')',text,re.I) and not re.search(dim,proof,re.I):return True
    return False


def restore_quantity_bounds(text,proof):
    """Restore an omitted source qualifier only for an unambiguous same value/unit.

    This never changes a numeric value or repairs an explicitly conflicting
    bound. It is analogous to preserving a unit during translation.
    """
    labels={'gt':'lebih dari','ge':'setidaknya','lt':'kurang dari','le':'hingga','approx':'sekitar','near':'hampir'}
    source=quantities(proof);replacements=[]
    for q in quantities(text):
        matches=[s for s in source if same_quantity(q,s)]
        ops={s['operator'] for s in matches}
        if q['operator']=='eq' and len(ops)==1 and next(iter(ops)) in labels:
            replacements.append((q['start'],q['end'],labels[next(iter(ops))]+' '+q['literal']))
    for a,b,new in reversed(replacements):text=text[:a]+new+text[b:]
    return re.sub(r'\b(?:Sebanyak|Terdapat|Ada)\s+(?=sekitar|hampir|lebih dari|kurang dari|setidaknya|hingga)','',text,flags=re.I)


from functools import lru_cache
@lru_cache(maxsize=1)
def boundary_gazetteer():
    from ngo_metadata import Gazetteer
    from settings import DATA_DIR
    return Gazetteer.local(DATA_DIR)

ACTIVITIES = {
    'perkebunan sawit':r'\bsawit\b|oil[ -]?palm',
    'hutan tanaman/perkebunan kayu':r'hutan tanaman|\bHTI\b|perkebunan kayu|pulp|timber plantation|wood plantation',
    'pertambangan nikel':r'\bnikel\b|\bnickel\b',
    'batu bara':r'batu\s*bara|\bcoal\b',
    'panas bumi':r'panas bumi|geothermal|geotermal|\bPLTP\b',
    'proyek pangan/energi':r'food estate|ketahanan pangan|swasembada pangan|\btebu\b|sugarcane|kebun energi|bioetanol|proyek pangan',
}


def activity_conflict(question, proof, local_context=''):
    """Reject an explicitly different activity in the cited prose.

    Titles and neighboring paragraphs cannot override the activity of the
    evidence sentence. A sentence with both activities can establish a link;
    a pronoun-only sentence still uses its local passage and semantic review.
    """
    requested = {key for key, pattern in ACTIVITIES.items() if re.search(pattern, question, re.I)}
    if not requested:
        return False
    actual = {key for key, pattern in ACTIVITIES.items() if re.search(pattern, proof, re.I)}
    if not actual:
        actual = {key for key, pattern in ACTIVITIES.items() if re.search(pattern, local_context, re.I)}
    return bool(actual and actual.isdisjoint(requested))


def activity_context(question,proof,local_context,title=''):
    """A subject elsewhere on a page cannot identify this passage's commodity."""
    requested=[key for key,pattern in ACTIVITIES.items() if re.search(pattern,question,re.I)]
    if not requested:return ''
    # The nearest original prose takes precedence over the report title.
    original = next((text for text in (proof, local_context, title)
                     if any(re.search(pattern, text, re.I) for pattern in ACTIVITIES.values())),
                    ' '.join((proof, local_context)))
    if any(re.search(ACTIVITIES[key],original,re.I) for key in requested):return ''
    actual=[key for key,pattern in ACTIVITIES.items() if re.search(pattern,original,re.I)]
    if actual:return 'Konteks '+', '.join(actual)+': '
    if re.search(r'\bPSN\b|proyek strategis nasional',original,re.I):return 'Konteks proyek strategis nasional (PSN): '
    # Missing a commodity token is not positive evidence of another activity;
    # the sentence-level semantic fit still controls such pronoun continuations.
    return ''


def activity_supported(question, finding, proof, local_context='', title='', fit_activity='same'):
    """Keep specific-activity answers grounded, including the displayed noun.

    Generic PSN/other-sector context may be useful for a broad question, but
    must not replace evidence about a specifically requested commodity.
    """
    requested = {key for key, pattern in ACTIVITIES.items() if re.search(pattern, question, re.I)}
    if not requested:
        return True
    if fit_activity != 'same':
        return False
    if activity_conflict(question, proof, local_context):
        return False
    if activity_context(question, proof, local_context, title):
        return False
    original = proof + ' ' + local_context
    added = {key for key, pattern in ACTIVITIES.items() if re.search(pattern, finding, re.I)
             and not re.search(pattern, original, re.I)}
    return not added


def quantity_relation_supported(text,proof):
    """A stock-area number is not automatically an area already converted."""
    completed=r'dialihfungsikan|dikonversi|dibuka|digunduli|ditebang|berubah menjadi|converted|cleared'
    if not re.search(completed,text,re.I):return True
    # Explicit plans/risks keep their status; this guard addresses an unqualified
    # assertion that a measured stock area has already undergone a change.
    if re.search(r'\b(?:akan|rencana|direncanakan)\b',text,re.I):return True
    for q in quantities(text):
        if q['unit']!='ha' and not re.search(r'hektar|hectare|\bha\b',q['unit']):continue
        originals=[proof[a:b] for a,b in spans(proof) if any(same_quantity(q,s) for s in quantities(proof[a:b]))]
        if originals and not any(re.search(completed+r'|membuka|mengalihfungsikan|mengonversi|menebang',s,re.I) for s in originals):return False
    return True


def local_geography_supported(text,proof):
    """Resolve a local finding against its own sentence, not a province list.

    If the sentence naming a village/district explicitly gives its province,
    another province mentioned elsewhere on the page cannot be added to that
    local finding. Unknown parent relations remain unknown.
    """
    gaz=boundary_gazetteer()
    def places(s):
        return explicit_places(s)+[p for p in gaz.mentions(s,{'text':s,'pdf_page':0,'page_side':'evidence'}) if p.get('reference_id')]
    finding_places=places(text)
    local=[p for p in finding_places if p['kind'] in ('village','urban_village','subdistrict','regency','city')]
    if not local:return True
    sentences=[proof[a:b] for a,b in spans(proof)]
    for parent_kind in ('province',):
        stated={normalized(p['name']) for p in finding_places if p['kind']==parent_kind}
        if not stated:continue
        anchored=[s for s in sentences if any(re.search(r'(?<!\w)'+re.escape(p['name'])+r'(?!\w)',s,re.I) for p in local)]
        original={normalized(p['name']) for s in anchored for p in places(s) if p['kind']==parent_kind}
        if original and not stated<=original:return False
    return True
