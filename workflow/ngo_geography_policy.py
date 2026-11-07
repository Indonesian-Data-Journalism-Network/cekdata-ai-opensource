"""Geographic scope must come from the cited event, not the question or title."""
from functools import lru_cache
import re
from geography import Geography, normalize
from ngo_metadata import explicit_places, spans, STOP


@lru_cache(maxsize=1)
def reference():
    geo = Geography([])
    # A unique archipelago short name is an alias, never a substring match.
    for entity in geo.entities.values():
        short=re.sub(r'^(?:Kabupaten|Kota)\s+Kepulauan\s+', '', entity['name'])
        if short != entity['name'] and len(short)>3:
            geo.aliases[normalize(short)].add(entity['id'])
    geo.pattern=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(a) for a in sorted(geo.aliases,key=lambda a:(-len(a),a)))+r')(?!\w)')
    return geo


def ancestor(parent, child):
    geo = reference()
    return geo.ancestor(parent, child) or any(
        member == child or geo.ancestor(member, child)
        for member in geo.entities.get(parent, {}).get('member_ids', []))


def translated(text):
    # English reports commonly use cardinal directions before province names.
    directions = {'West': 'Barat', 'East': 'Timur', 'North': 'Utara',
                  'South': 'Selatan', 'Central': 'Tengah'}
    for english, indonesian in directions.items():
        text = re.sub(r'\b'+english+r'\s+(Kalimantan|Sulawesi|Sumatra|Sumatera|Papua|Java|Maluku)\b',
                      lambda m: ('Jawa' if m[1] == 'Java' else m[1])+' '+indonesian, text, flags=re.I)
    return text


def places(text):
    text = ' '.join(translated(text).split())
    geo = reference()
    result = {}
    normalized = normalize(text)
    typed=explicit_places(text)
    for match in geo.pattern.finditer(normalized):
        if re.match(r'\s+(?:utara|selatan|barat|timur|tengah)\b', normalized[match.end():]):
            continue  # An unindexed new district is not its name-prefix parent.
        if re.search(r'\b(?:sungai|river|danau|lake)\s*$', normalized[:match.start()]) or re.match(r'\s+(?:rivers?|lakes?)\b', normalized[match.end():]):
            continue
        # A short administrative alias embedded in a longer typed locality
        # does not relocate that locality to the homonymous district.
        if any(match[0] != normalize(p['name']) and
               re.search(r'(?<!\w)'+re.escape(match[0])+r'(?!\w)', normalize(p['name']))
               for p in typed):
            continue
        if match[0] in {'baru','lama'} and not re.search(
                r'\b(?:kabupaten|kab|kota|provinsi|prov)\s+$',normalized[:match.start()]):
            continue
        ids = geo.aliases[match[0]]
        if len(ids) != 1: continue
        identity = next(iter(ids)); entity = geo.entities[identity]
        result[identity] = {'id': identity, 'name': entity['name'], 'level': entity['level']}
    candidates = explicit_places(text)
    # Unindexed villages/islands remain names, never invented administrative IDs.
    name_pattern=r'[A-Z][\w-]+(?:[ \t]+[A-Z][\w-]+){0,3}'
    list_pattern=name_pattern+r'(?:(?:,\s*(?:(?:and|dan)\s+)?|\s+(?:and|dan)\s+)'+name_pattern+r')*'
    for match in re.finditer(r'\b(?i:di|in|on|from|dari|sekitar)\s+('+list_pattern+r')',text):
        for raw in re.split(r',\s*(?:(?:and|dan)\s+)?|\s+(?:and|dan)\s+',match[1]):
            words=[]
            for word in raw.split():
                if normalize(word) in STOP:break
                words.append(word)
            name=' '.join(words)
            # All-capital organization/program acronyms are not unknown places.
            if name and not name.isupper():
                candidates.append({'name':name,'kind':'unknown'})
    for place in candidates:
        name = place['name']; key = normalize(name)
        if re.match(r'^(?:PT|CV|PLTU|PLTS|PLTP|WALHI)\b', name): continue
        if not key or key in {'indonesia', 'nasional'}: continue
        ids=geo.aliases.get(key,set())
        if len(ids)==1:
            identity=next(iter(ids));entity=geo.entities[identity]
            result[identity]={'id':identity,'name':entity['name'],'level':entity['level']}
            continue
        if any(key in normalize(p['name']) or normalize(p['name']) in key for p in result.values()): continue
        result[key] = {'id': key, 'name': name, 'level': place['kind'], 'parents': []}
    order={'hamlet':0,'village':1,'urban_village':1,'subdistrict':2,'unknown':2,'island':2,'pulau':2,
           'regency':3,'city':3,'kabupaten':3,'kota':3,'province':4,'provinsi':4,'kelompok_pulau':4,'nasional':5}
    for child in result.values():
        child.setdefault('parents', [])
        child.setdefault('parent_levels', {})
        for parent in result.values():
            if child is parent: continue
            # A comma-separated list is not an administrative address. An
            # untyped sibling must never become the parent of a typed village.
            if parent['level'] not in ('subdistrict','village','urban_village',
                                       'regency','city','kabupaten','kota','province','provinsi'):
                continue
            # An address cannot reverse a relationship already established by
            # the reference (e.g. make a large island part of a regency).
            if child['id'] in geo.entities and parent['id'] in geo.entities and ancestor(child['id'],parent['id']):
                continue
            if order.get(parent['level'],2)<=order.get(child['level'],2):continue
            short = re.sub(r'^(?:Kabupaten|Kota|Provinsi)\s+', '', parent['name'])
            intermediate=r'(?:(?:Kecamatan|Desa|Kelurahan)\s+[A-Z][\w-]+(?:\s+[A-Z][\w-]+){0,3}\s*,\s*){0,2}'
            admin=r'(?:(?:Kabupaten|Kota|Provinsi|Kecamatan|Desa|Kelurahan)\s+)'
            # Physical islands have no automatic administrative hierarchy.
            # Require an explicitly typed address, not a comma between clauses.
            if child['level'] not in ('island','pulau'):admin+='?'
            if re.search(re.escape(child['name'])+r'\s*(?:,|di|in)\s*'+intermediate+admin+re.escape(short), text):
                child['parents'].append(parent['id'])
                child['parent_levels'][parent['id']]=parent['level']
    # A complete address is one location; keep the finest identified place.
    return [p for p in result.values() if not any(
        ancestor(p['id'], other['id']) or p['id'] in other.get('parents', []) for other in result.values())]


def document_addresses(pages):
    """Only explicit addresses from original report sentences, with page trace."""
    result=[]
    for page in pages:
        for a,b in spans(page.get('text','')):
            sentence=page['text'][a:b]
            for place in places(sentence):
                if place.get('parents'):
                    result.append({**place,'pdf_page':page['pdf_page'],'evidence':sentence})
    return result


def project_links(pages):
    """Original nearby sentences explicitly connecting a facility and localities.

    These are event links, never administrative parent boundaries. They can
    support an impact question about that named project, not area aggregation.
    """
    from ngo_source_facts import named_facilities
    result=[]
    for page in pages:
        text=page.get('text','');sentences=[text[a:b] for a,b in spans(text)]
        for i,sentence in enumerate(sentences):
            facilities=named_facilities(sentence)
            if len(facilities)!=1:continue
            name=next(iter(facilities));window=' '.join(sentences[i:i+3])
            if len(window)>2400 or named_facilities(window)!={name}:continue
            if not re.search(r'warga|masyarakat|petani|nelayan|residents?|communities|farmers?',window,re.I):continue
            local=[p for p in places(window) if p['level'] in ('hamlet','village','urban_village','subdistrict')]
            if local:result.append({'facility':name,'locations':local,'text':window,'pdf_page':page['pdf_page']})
    return result


def project_relation(question, finding, actual, links):
    # Require a named project question, preserve local names, and never replace
    # a known conflicting administrative place with a facility association.
    if not re.search(r'proyek|PLT\w*|panas bumi|pembangkit',question,re.I):return False
    q=normalize(question);retained={p['id'] for p in places(finding)}
    if not actual or any(p['level'] not in ('hamlet','village','urban_village','subdistrict') for p in actual):return False
    for link in links:
        name=re.sub(r'^plt\w*\s+','',link['facility'],flags=re.I)
        name=re.sub(r'\s+(?:tahap|phase|stage)$','',name,flags=re.I)
        if not re.search(r'(?<!\w)'+re.escape(normalize(name))+r'(?!\w)',q):continue
        ids={p['id'] for p in link['locations']}
        if all(p['id'] in ids and p['id'] in retained for p in actual):return True
    return False


def address_supports(location, proof, addresses):
    """An added parent is supported only by an explicit address of this child."""
    target=places('di '+location)
    if len(target)!=1:return False
    target_id=target[0]['id']
    local={p['id'] for p in places(proof)}
    relevant=[a for a in addresses if a['id'] in local]
    if conflicting_addresses(relevant):return False
    parents={parent for a in relevant for parent in a.get('parents',[])}
    known=parents & reference().entities.keys()
    if any(a!=b and not ancestor(a,b) and not ancestor(b,a) for a in known for b in known):return False
    return target_id in parents


def conflicting_addresses(addresses):
    levels={}
    for address in addresses:
        for parent,level in address.get('parent_levels',{}).items():
            levels.setdefault(level,set()).add(parent)
    return any(len(ids)>1 for ids in levels.values())


def measurement_clauses(finding, sentence):
    """Separate explicitly assigned measurements; never split a shared total."""
    from ngo_source_facts import quantities, same_quantity
    clauses=re.split(r';\s*|\b(?:sedangkan|sementara|semetara|whereas|while)\b',sentence,flags=re.I)
    if len(clauses)<2 or not all(places(c) and quantities(c) for c in clauses):return sentence
    wanted=quantities(finding)
    selected=[c for c in clauses if any(same_quantity(a,b) for a in wanted for b in quantities(c))]
    return ' '.join(selected) if selected else sentence


def source_scope(finding, proof, page='', continuation='', addresses=()):
    """Use the substantive sentence and its preceding local scope only."""
    sentences = [proof[a:b] for a, b in spans(proof)]
    substantive = [s for s in sentences if not re.match(r'\s*(?:foto|photo|caption|gambar|figure)\b', s, re.I)]
    if not substantive: return []
    stop = {'yang','dengan','untuk','dalam','dari','pada','laporan','menurut','warga','tersebut'}
    words = lambda s: set(re.findall(r'\w{4,}', s.casefold())) - stop
    scored = [(len(words(finding) & words(s)), s) for s in substantive]
    best = max(score for score, _ in scored)
    core = [s for score, s in scored if score == best]
    direct = [p for s in core for p in places(measurement_clauses(finding,s))]
    if direct:
        address_map = {}
        original_addresses=list(addresses)+[p for a,b in spans(page) for p in places(page[a:b]) if p.get('parents')]
        for p in original_addresses:
            address_map.setdefault(p['id'],set()).update(p.get('parents',[]))
        return list({p['id']: {**p, 'parents': sorted(address_map.get(p['id'],p.get('parents',[]))),
                              'ambiguous_address':conflicting_addresses([a for a in original_addresses if a['id']==p['id']])} for p in direct}.values())
    # Follow the most recent explicit scope before the selected passage. A
    # later caption or another chapter cannot retrospectively locate an event.
    active = places(continuation) if continuation else []
    for a, b in spans(page):
        sentence = page[a:b]
        if any(normalize(s) in normalize(sentence) for s in core): return active
        if re.match(r'\s*(?:foto|photo|caption|gambar|figure)\b', sentence, re.I): continue
        here = places(sentence)
        # A regional description after a precise address does not move the
        # project out of that address. A different locality starts a new scope.
        if here and not (active and all(any(ancestor(p['id'],old['id']) for old in active) for p in here)):
            active = here
    return []


def scope_decision(question, finding, proof, page='', continuation='', addresses=(), event_links=()):
    """Return proven relation and original scope; unknown is not a match."""
    requested = places(question)
    if not requested: return 'unscoped', []
    actual = source_scope(finding, proof, page, continuation, addresses)
    if not actual: return 'unknown', []
    for place in actual:
        if place.get('ambiguous_address'):return 'unknown',actual
        parents=[p for p in place.get('parents',[]) if p in reference().entities]
        if any(a!=b and not ancestor(a,b) and not ancestor(b,a) for a in parents for b in parents):
            return 'unknown',actual  # Homonymous places need a disambiguated address.
    geo = reference()
    def relation(a, b):
        if a['id'] == b['id']: return 'same'
        if ancestor(a['id'], b['id']) or a['id'] in b.get('parents', []): return 'within_requested_area'
        if ancestor(b['id'], a['id']) or b['id'] in a.get('parents',[]): return 'broader_context'
        return 'different'
    priority = {'same': 0, 'within_requested_area': 1, 'broader_context': 2, 'different': 3}
    relations = [min((relation(a, b) for a in requested), key=priority.get) for b in actual]
    if all(r == 'different' for r in relations):
        if project_relation(question,finding,actual,event_links):return 'within_requested_area',actual
        return 'different', actual
    # A multi-region observation must retain every region, including verbal
    # quantities ("ribuan hektare") that digit-only validation cannot catch.
    retained = {p['id'] for p in places(finding)}
    if any(r=='within_requested_area' and p['id'] not in retained for p,r in zip(actual,relations)):
        return 'narrowed',actual
    if any(p['id'] in retained and not any(relation(p, b) in ('same', 'within_requested_area')
                                         for b in actual) for p in requested):
        return 'narrowed', actual
    if len(actual) > 1 and not all(p['id'] in retained for p in actual): return 'narrowed', actual
    if 'different' in relations or 'broader_context' in relations: return 'broader_context', actual
    return ('same' if 'same' in relations else 'within_requested_area'), actual
