"""Resolve geographic mentions using a versioned reference, without aggregating data."""
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

REFERENCE=Path(__file__).resolve().parent/'reference/geography.json'

def normalize(text):
    return re.sub(r'[^\w]+',' ',text.casefold()).strip()

def embedded_place_alias(text, alias, aliases):
    """A known short name cannot absorb an unindexed compound proper name."""
    for match in re.finditer(r'\b[A-Z][\w-]+(?:[ \t]+[A-Z][\w-]+){1,5}', text):
        name = normalize(match[0])
        name = re.sub(r'^(?:kabupaten|kota|provinsi|kecamatan|desa|kelurahan|pulau|sungai|das)\s+', '', name)
        if name.startswith(alias + ' ') and name not in aliases:
            return True
    return False

@lru_cache(maxsize=4)
def _read(path,mtime):
    return json.loads(Path(path).read_text())

@dataclass
class Resolution:
    areas: list[str]
    clarification: str = ''
    ids: tuple[str,...] = ()

class Geography:
    def __init__(self,catalog,reference=None):
        reference=reference if reference is not None else _read(str(REFERENCE),REFERENCE.stat().st_mtime_ns)
        self.entities={e['id']:e for e in reference['entries']}
        self.available={normalize(a):a for c in catalog for a in c.get('areas',[])}
        self.aliases=defaultdict(set)
        self.province_aliases=set()
        for e in self.entities.values():
            if e['level']=='provinsi':
                self.province_aliases.update(normalize(a) for a in e['aliases'])
        for e in self.entities.values():
            names=set(e['aliases'])
            if e['level']=='provinsi':
                names.update(prefix+a for a in e['aliases'] for prefix in ['Provinsi ','Prov. '])
            if e['level'] in {'kabupaten','kota'}:
                names.update(re.sub(r'^Kabupaten\b',prefix,a,flags=re.I)
                             for a in e['aliases'] for prefix in ['Kab.','Kab'] if a.lower().startswith('kabupaten '))
                parent=self.entities[e['parent_id']]
                short=[n for n in names if ',' not in n]
                names.update(n+' '+prefix+p for n in short for p in parent['aliases'] for prefix in ['', 'Provinsi ', 'Prov. '])
            names.update(n.replace('Sumatera','Sumatra') for n in list(names) if 'Sumatera' in n)
            for name in names:
                key=normalize(name)
                # Bare province names identify the province; Kota/Kabupaten prefix
                # is required for a child sharing that name (Jambi, Gorontalo, etc.).
                if e['level'] in {'kabupaten','kota'} and key in self.province_aliases:continue
                self.aliases[key].add(e['id'])
        # Match longest mention first; full address includes the province's name.
        self.pattern=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(a) for a in sorted(self.aliases,key=lambda a:(-len(a),a)))+r')(?!\w)')

    def destination(self,id):
        e=self.entities[id]
        for binding in e['source_bindings']:
            if normalize(binding['area']) in self.available:return self.available[normalize(binding['area'])]
        # Other catalogs can use a unique short name (e.g. BPS 'Brebes').
        for alias in e['aliases']:
            key=normalize(alias)
            if key in self.available and self.aliases.get(key)=={id}:
                return self.available[key]
        # Preserve known but unavailable geography. Never substitute its parent.
        return e['name']

    def ancestor(self,parent,child):
        seen=set()
        while child not in seen:
            seen.add(child)
            child=self.entities.get(child,{}).get('parent_id')
            if not child:return False
            if child==parent:return True
        return False

    def resolve(self,question):
        q=normalize(question);mentions=[]
        for m in self.pattern.finditer(q):
            if embedded_place_alias(question, m[0], self.aliases):continue
            candidates=set(self.aliases[m[0]])
            # Explicit unsupported lower levels must not become their homonymous province.
            prefix=q[:m.start()].rstrip().split(' ')
            if prefix and prefix[-1] in {'desa','kelurahan','kecamatan','kec','kabupaten','kab','kota'}:
                candidates={i for i in candidates if self.entities[i]['level'] not in {'provinsi','kelompok_pulau','nasional'}}
            if candidates:mentions.append([m.start(),m.end(),candidates])
        # Parent in an address can disambiguate repeated district names, but cannot
        # distinguish a city and regency with the same name within that province.
        explicit={next(iter(c)) for _,_,c in mentions if len(c)==1}
        for start,end,c in mentions:
            if len(c)>1:
                within={i for i in c if self.entities[i].get('parent_id') in explicit}
                if within:c.intersection_update(within)
        ambiguous=[c for _,_,c in mentions if len(c)>1]
        if ambiguous:
            names=sorted({self.entities[i]['name'] for c in ambiguous for i in c})
            return Resolution([], 'Wilayah yang dimaksud '+ ' atau '.join(names)+'? Sebutkan kabupaten/kota dan provinsinya.')
        chosen=[]
        for start,end,c in mentions:
            id=next(iter(c))
            # Parent following a child with only address punctuation/prepositions is
            # location context. A conjunction/comparison explicitly retains both.
            if chosen:
                previous=chosen[-1]
                bridge=q[previous[1]:start].strip()
                if self.ancestor(id,previous[2]) and bridge in {'','di','dalam','wilayah'}:
                    # Extend the consumed address so another ancestor is also context.
                    chosen[-1]=(previous[0],end,previous[2])
                    continue
                if self.ancestor(previous[2],id) and bridge in {'khususnya','khususnya di','tepatnya','tepatnya di'}:
                    chosen.pop()
            chosen.append((start,end,id))
        ids=list(dict.fromkeys(i for _,_,i in chosen))
        return Resolution(list(dict.fromkeys(self.destination(i) for i in ids)),ids=tuple(ids))

    def canonical(self,area):
        ids=self.aliases.get(normalize(area),set())
        return self.destination(next(iter(ids))) if len(ids)==1 else None

    def reconcile(self,question,model_areas):
        result=self.resolve(question)
        if result.clarification or not result.areas:return result
        # The reference covers higher levels, not every village/subdistrict or
        # small island in NGO reports. Preserve their specific model scope.
        if re.search(r'\b(?:desa|kelurahan|kecamatan|kec\.)\s+',question,re.I):
            return Resolution(list(model_areas))
        unknown=[a for a in model_areas if not self.aliases.get(normalize(a))]
        # Preserve explicitly named, unindexed localities; never let a known
        # ancestor or model-invented place override the reference matches.
        unknown=[a for a in unknown if normalize(a) in normalize(question)]
        return Resolution(list(dict.fromkeys(result.areas+unknown)),ids=result.ids)
