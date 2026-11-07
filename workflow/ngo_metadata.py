"""Source-anchored NGO metadata. No model-generated place facts or inherited geography.

All positions refer to the original page-part text; unknown values stay unknown.
GADM names are a versioned reference, not evidence of a report's current boundary.
"""
from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

SCHEMA = 'ngo-context-v3.4'
KIND = {'provinsi':'province','province':'province','kabupaten':'regency','kab.':'regency',
        'kota':'city','kecamatan':'subdistrict','desa':'village','kelurahan':'urban_village',
        'pulau':'island','island':'island','regency':'regency','district':'district_unspecified',
        'village':'village','dusun':'hamlet','jorong':'hamlet','kampung':'hamlet'}
STOP = {'dan','and','dalam','the','di','of','kecil','small','ini','itu','yang','tersebut',
        'adalah','negara','kepulauan','atau','dengan','untuk','seluruh','selatan','utara',
        'timur','barat','pada','oleh','ke','pesisir','indonesia','province','kabupaten',
        'total','tabel','table','tahun','year','sumber','source','tidak','hutan','forest','pltu','sektor',
        'pemerintah','kawasan','area','besar','ada','kecil','air','water','laut','daratan','data','penduduk',
        'negeri','nasional','national','in','on','at','from','to','as','by','a','an'}
NAME = r"[A-ZÀ-Ý][\w’'-]+(?:[ \t]+[A-ZÀ-Ý][\w’'-]+){0,3}"
PREFIX = re.compile(r'\b(?P<kind>(?i:provinsi|province|kabupaten|kab\.|kota|kecamatan|desa|kelurahan|pulau|dusun|jorong|kampung))\s+(?P<name>'+NAME+r')')
SUFFIX = re.compile(r'\b(?P<name>'+NAME+r')\s+(?P<kind>Island|Regency|Province|Village|District)\b')
TOPICS = {
 'nickel_mining':r'nikel|nickel', 'coal':r'batubara|batu bara|coal',
 'mining':r'pertambangan|penambangan|tambang|mining|mine', 'palm_oil':r'sawit|palm oil|oil palm',
 'forests':r'hutan|forest|deforestasi|deforestation|tree.cover',
 'biomass_energy':r'biomassa|biomass|co.?firing|kebun energi|hutan tanaman energi',
 'food_estate':r'food estate|ketahanan pangan|food security', 'indigenous_rights':r'masyarakat adat|orang asli|indigenous|customary',
 'human_rights':r'hak asasi|human rights|pembela ham|human rights defenders',
 'land_conflict':r'konflik agraria|perampasan lahan|land grab|land conflict|konflik lahan',
 'water':r'air bersih|pencemaran air|water pollution|clean water|sungai|river',
 'livelihoods':r'mata pencaharian|pendapatan|livelihood|income',
 'health':r'kesehatan|health|sakit|disease', 'climate_carbon':r'iklim|climate|karbon|carbon|emisi|emission',
 'peat_mangrove':r'gambut|peat|mangrove', 'fire':r'kebakaran|karhutla|wildfire|forest fire',
 'gender':r'perempuan|women|gender', 'energy_transition':r'transisi energi|energy transition|renewable|terbarukan',
 'biodiversity':r'keanekaragaman hayati|biodiversity|orangutan|habitat',
}
TOPIC_RE = {k:re.compile(r'\b(?:'+v+r')\b',re.I) for k,v in TOPICS.items()}
STATUS_RE = {
 'projection':re.compile(r'\b(?:rencana|direncanakan|proyeksi|diproyeksi\w*|projected|planned|planning|scenario|skenario|target)\b',re.I),
 'model_result':re.compile(r'\b(?:pemodelan|modelling|modeling|simulasi|simulation|IRIO|model ekonometrika|econometric model)\b',re.I),
 'threat_or_potential':re.compile(r'\b(?:terancam|ancaman|mengancam|berpotensi|potensi|threat\w*|potential|could|would)\b',re.I),
 'estimate':re.compile(r'\b(?:sekitar|diperkirakan|perkiraan|kurang lebih|approximately|about|around|estimated|roughly)\b',re.I),
 'survey_response':re.compile(r'\b(?:survei|survey|responden|respondents?|rumah tangga|households?|wawancara|interview\w*)\b',re.I),
 'allegation':re.compile(r'\b(?:diduga|dugaan|alleged|allegedly|suspected)\b',re.I),
 'recommendation':re.compile(r'\b(?:merekomendasikan|rekomendasi|recommend\w*|menuntut|mendesak)\b',re.I),
}
YEAR = re.compile(r'(?<![\w.,/])(?:19|20)\d{2}(?![\w.,/])')
QUANTITY = re.compile(r'(?<![\w.,])(?P<value>\d+(?:[.,]\d+)*)(?:[ \t]+(?P<magnitude>ribu|juta|miliar|thousand|million|billion))?\s*(?P<unit>%|persen|percent(?:age)?|hektare?|hectares?|ha|rumah tangga|households?|responden|respondents?|orang|people|tonnes?|tons?|ton|mw|gw|km2|km²)(?!\w)',re.I)


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def spans(text):
    """Sentence boundaries without splitting decimals, abbreviations or PDF lines."""
    start=0
    for match in re.finditer(r'(?<=[!?])\s+|(?<=[.])\s+(?=[A-ZÀ-Ý])|\n[ \t]*\n',text):
        # Short abbreviations are not sentence ends.
        preceding=text[max(0,match.start()-12):match.start()]
        if re.search(r'\b(?:PT|Kab|Prov|No|Dr|Mr|Ms|Jl|Vol|Fig|e\.g)\.$',preceding,re.I):continue
        if text[start:match.start()].strip():
            a=start+len(text[start:match.start()])-len(text[start:match.start()].lstrip())
            yield a,match.start()
        start=match.end()
    if text[start:].strip():
        yield start+len(text[start:])-len(text[start:].lstrip()),len(text.rstrip())


def anchor(page,start,end,**extra):
    return {'pdf_page':page['pdf_page'],'page_side':page['page_side'],
            'start':start,'end':end,'quote':page['text'][start:end],**extra}


def explicit_places(text):
    hits=[]
    for regex in (PREFIX,SUFFIX):
        for m in regex.finditer(text):
            raw=m.group('name');words=raw.split();kept=[]
            for word in words:
                if normalized(word) in STOP and not (kept and normalized(word) in {'utara','selatan','timur','barat','besar','kecil'}):break
                kept.append(word)
            if not kept:continue
            name=' '.join(kept).strip('.,:;')
            if len(name)<3:continue
            # Preserve actual source spelling and offsets, even after trimming title words.
            a=m.start('name');b=a+len(name)
            hits.append({'name':text[a:b],'kind':KIND[m.group('kind').casefold()],
                         'start':a,'end':b,'recognition':'explicit_type'})
    return hits


class Gazetteer:
    def __init__(self,entries=()):
        self.entries=list(entries)
        self.aliases=defaultdict(list)
        for entry in self.entries:
            for alias in entry['aliases']:
                key=normalized(alias)
                if key and entry not in self.aliases[key]:self.aliases[key].append(entry)
        self.pattern=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k).replace(r'\ ',r'\s+') for k in sorted(self.aliases,key=len,reverse=True))+r')(?!\w)',re.I) if self.aliases else None

    @classmethod
    def local(cls,data_root,learned=()):
        data_root=Path(data_root);entries=[]
        paths=[data_root/'gfw/raw/provinces.json',data_root/'gfw-adm2/raw/districts.json']
        for path in paths:
            if not path.exists():continue
            for row in json.loads(path.read_text()):
                if row.get('gid_2'):
                    kind='city' if row.get('type_2')=='Kota' else 'regency'
                    name=re.sub(r'^(?:Kota|Kabupaten)\s+','',row['name_2'])
                    aliases=[name,('Kota ' if kind=='city' else 'Kabupaten ')+name]
                    entries.append({'name':name,'kind':kind,'id':row['gid_2'],'parent_id':row['gid_1'],
                                    'parent_name':row['name_1'],'aliases':aliases,'reference':'GADM 4.1 / local GFW boundary snapshot'})
                else:
                    entries.append({'name':row['name_1'],'kind':'province','id':row['gid_1'],
                                    'parent_id':'IDN','parent_name':'Indonesia','aliases':[row['name_1']],
                                    'reference':'GADM 4.1 / local GFW boundary snapshot'})
        entries.append({'name':'Indonesia','kind':'country','id':'IDN','parent_id':None,'parent_name':None,
                        'aliases':['Indonesia'],'reference':'local GFW country catalogue'})
        known={(normalized(e['name']),e['kind']) for e in entries}
        for name,kind in sorted(set(learned)):
            if (normalized(name),kind) not in known:
                entries.append({'name':name,'kind':kind,'id':None,'parent_id':None,'parent_name':None,
                                'aliases':[name],'reference':'explicitly typed name in local NGO corpus; not independently verified'})
        return cls(entries)

    def resolve(self,name,kind=None):
        entries=self.aliases.get(normalized(name),[])
        if kind:entries=[e for e in entries if e['kind']==kind]
        # A name shared by multiple types or administrative units stays ambiguous.
        ids={(e.get('id'),e['kind'],e['name']) for e in entries}
        if len(ids)!=1:return None
        return entries[0]

    def mentions(self,text,page,offset=0,query=False):
        explicit=explicit_places(text);hits=list(explicit)
        if self.pattern:
            for m in self.pattern.finditer(text):
                overlaps=[p for p in explicit if m.start()<p['end'] and m.end()>p['start']]
                if overlaps:
                    for p in overlaps:
                        if m.start()==p['start'] and m.end()>p['end']:
                            p.update(name=m.group(),end=m.end())
                    continue
                key=normalized(m.group())
                candidates=self.aliases.get(key,[])
                if not query:
                    if not m.group()[0].isupper():continue
                    if not any(e.get('id') for e in candidates):
                        before=text[max(0,m.start()-60):m.start()]
                        if not re.search(r'\b(?:di|ke|dari|in|at|on|from|of|wilayah|area|island|pulau|desa|kecamatan)\s+$',before,re.I):continue
                hits.append({'name':m.group(),'kind':candidates[0]['kind'] if len({e['kind'] for e in candidates})==1 else 'ambiguous',
                             'start':m.start(),'end':m.end(),'recognition':'name_reference_match'})
        result=[]
        for hit in sorted(hits,key=lambda x:x['start']):
            ref=self.resolve(hit['name'],hit['kind'])
            a,b=hit['start']+offset,hit['end']+offset
            sentence=next((page['text'][s:e] for s,e in spans(page['text']) if s<=a<e),text)
            role='mentioned'
            if re.search(r'\b(?:penelitian|survei|kajian|study|research|survey)\b.{0,90}\b(?:di|in|at|meliputi|mencakup|conducted|located)\b',sentence,re.I):role='study_area_candidate'
            if re.search(r'\b(?:misalnya|contohnya|for example|such as)\b',sentence,re.I):role='example_or_background'
            result.append({**hit,'canonical_name':ref['name'] if ref else None,
                           'reference_id':ref.get('id') if ref else None,
                           'reference_parent_id':ref.get('parent_id') if ref else None,
                           'reference_parent_name':ref.get('parent_name') if ref else None,
                           'reference':ref.get('reference') if ref else None,
                           'resolution':'reference_match' if ref and ref.get('id') else 'typed_name_unverified' if ref else 'unresolved_or_ambiguous',
                           'role':role,'evidence':anchor(page,a,b), 'start':a,'end':b})
        return result


def headings(page):
    found=[]
    for m in re.finditer(r'(?m)^\s*([^\n]{4,110})\s*$',page['text']):
        line=m.group(1).strip();words=line.split()
        if len(words)>14 or re.search(r'[.,;!?]$',line) or re.fullmatch(r'[\d\W]+',line):continue
        letters=[c for c in line if c.isalpha()]
        title_words=[w for w in words if w.casefold() not in {'dan','and','di','in','of','the','terhadap','untuk','dengan','on'}]
        capitals=sum(w[0].isupper() for w in title_words if w)
        if not letters:continue
        if (len(words)>=2 and capitals/max(len(title_words),1)>=.8) or line.isupper() or re.match(r'^(?:\d+(?:\.\d+)*[.)]?|[IVX]+\.|[a-z][.)])\s+[A-Z]',line):
            a=m.start(1);found.append({'text':line,'evidence':anchor(page,a,a+len(line)),
                                       'recognition':'heading_candidate_not_layout_verified'})
    return found


def statuses(text):
    return [key for key,pattern in STATUS_RE.items() if pattern.search(text)]


def metadata(page,start,end,gazetteer):
    text=page['text'][start:end]
    locations=gazetteer.mentions(text,page,start)
    periods=[];quantities=[];topics=[];actors=[]
    for s,e in spans(text):
        sentence=text[s:e];status=statuses(sentence)
        for match in YEAR.finditer(sentence):
            role=('projection_year' if 'projection' in status else
                  'observation_year_candidate' if re.search(r'(?:survei|survey|penelitian|research|pengamatan|observed|data)\b.{0,70}'+re.escape(match.group()),sentence,re.I) else 'mentioned_year')
            if re.search(r'\b(?:undang.undang|peraturan|nomor|law|regulation|copyright|ISBN)\b',sentence,re.I):role='legal_or_reference_year'
            periods.append({'year':int(match.group()),'role':role,'evidence':anchor(page,start+s+match.start(),start+s+match.end())})
        for match in QUANTITY.finditer(sentence):
            a=start+s+match.start();b=start+s+match.end()
            population=re.search(r'\b(?:rumah tangga|kepala rumah tangga|households?|responden|respondents?|perempuan|women|petani|farmers?)\b',sentence,re.I)
            quantities.append({'value_text':match.group('value'),'unit_text':match.group('unit'),
                               'magnitude_text':match.group('magnitude'),'status':status or ['reported_quantity'],
                               'population_text':population.group() if population else None,
                               'measure_context':sentence[:1400], 'context_complete':len(sentence)<=1400,
                               'evidence':anchor(page,a,b),'numeric_table_verified':False})
    for key,pattern in TOPIC_RE.items():
        m=pattern.search(text)
        if m:topics.append({'id':key,'evidence':anchor(page,start+m.start(),start+m.end())})
    for m in re.finditer(r'\b(?:PT\.?|CV\.?)\s+'+NAME,text):
        actors.append({'name':m.group(),'kind':'company_name_candidate','evidence':anchor(page,start+m.start(),start+m.end())})
    lower=normalized(text[:500])
    content_kind=('bibliography' if re.search(r'\b(?:daftar pustaka|bibliography|references)\b',lower) else
                  'table_of_contents' if 'daftar isi' in lower or 'table of contents' in lower else
                  'table_or_figure_candidate' if re.match(r'^(?:tabel|table|gambar|figure)\s+\d',lower) else 'prose_or_unclassified')
    return {'locations':locations,'periods':periods,'quantities':quantities,'topics':topics,'actors':actors,
            'claim_status':statuses(text),'content_kind':content_kind,
            'observation_period':None, 'observation_period_status':'see_anchored_period_mentions_not_inferred',
            'language':language(text),'unknown_fields':['verified_authorship','verified_causal_attribution','verified_table_cells']}


def language(text):
    words=re.findall(r'\b\w+\b',text.casefold())
    id_score=sum(w in {'yang','dan','di','dengan','pada','untuk','dari','dalam','ini','adalah','masyarakat'} for w in words)
    en_score=sum(w in {'the','and','of','in','with','for','from','this','that','are','was','were','their'} for w in words)
    code='und' if max(id_score,en_score)<3 else 'id' if id_score>en_score*2 else 'en' if en_score>id_score*2 else 'mixed'
    return {'code':code,'method':'stopword_heuristic','verified':False}


def location_names(metadata):
    return list(dict.fromkeys(normalized(loc['canonical_name'] or loc['name']) for loc in metadata['locations']))


def document_metadata(document,pages):
    authors=[]
    for page in pages[:10]:
        for m in re.finditer(r'(?im)^(?:penulis|authors?|written by|disusun oleh|penyusun)\s*[:\-]\s*([^\n]{3,250})',page['text']):
            authors.append({'text':m.group(1),'status':'explicit_credit_line_not_identity_verified','evidence':anchor(page,m.start(),m.end())})
    return {'document_id':document['id'],'sha256':document['sha256'],'provider':document['provider'],
            'host_organization':document['host_organization'],'title':document['title'],
            'source_url':document['source_url'],'download_url':document['download_url'],
            'publication_date_listed':document.get('publication_date_listed'),
            'publication_year_listed':document.get('publication_year_listed'),
            'publication_date_basis':document.get('publication_date_basis','publisher_listing'),
            'observation_period':None,'observation_period_status':'not_inferred_from_publication',
            'authorship_mentions':authors,'verified_authors':None,'source_independence':'not_verified',
            'language_version_group':None,'language_version_status':'not_verified',
            'page_parts':len(pages),'readable_parts':sum(p['status']=='readable' for p in pages),
            'unreadable_parts':[{'pdf_page':p['pdf_page'],'page_side':p['page_side'],'status':p['status']} for p in pages if p['status']!='readable'],
            'schema_version':SCHEMA}
