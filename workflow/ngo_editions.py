"""Conservative edition candidates from publisher filenames, not translated title guesses."""
import hashlib,re
from collections import defaultdict
from pathlib import PurePosixPath
from urllib.parse import unquote,urlsplit
from ngo_corpus import ROOT,read,save
from ngo_pages import source_pages
from ngo_metadata import explicit_places,normalized
from settings import DATA_DIR

LANG={'eng':'en','en':'en','english':'en','ind':'id','id':'id','indo':'id','indonesian':'id','jp':'ja','ja':'ja','japanese':'ja'}


def edition_candidates(documents):
    buckets=defaultdict(list)
    for document in documents:
        stem=PurePosixPath(unquote(urlsplit(document['download_url']).path)).stem
        tokens=[s for s in re.split(r'[\s_\-]+',stem.casefold()) if s]
        hints=[LANG[s] for s in tokens if s in LANG]
        if len(set(hints))!=1:continue
        # Strip language markers only; retain dates, version numbers and all other words.
        core=' '.join(s for s in tokens if s not in LANG)
        if len(core)<12:continue
        buckets[(document['provider'],core)].append((document,hints[0]))
    groups=[]
    for (provider,core),members in sorted(buckets.items()):
        if len({lang for doc,lang in members})<2:continue
        ident='edition:'+hashlib.sha256((provider+':'+core).encode()).hexdigest()[:16]
        groups.append({'group_id':ident,'basis':'identical publisher filename stem after removing explicit language tokens',
                       'status':'possible_translation_not_independently_verified','independent_corroboration':False,
                       'members':[{'document_id':d['id'],'language_hint':lang,'download_url':d['download_url']} for d,lang in members]})
    return groups


def finalize(config):
    groups=edition_candidates(config['catalog']);by_id={m['document_id']:group for group in groups for m in group['members']}
    folder=ROOT/config['context_root']
    for doc in config['catalog']:
        path=folder/(doc['id']+'.json');value=read(path)
        group=by_id.get(doc['id'])
        value['document']['language_version_group']=group['group_id'] if group else None
        value['document']['language_version_status']=group['status'] if group else 'not_verified'
        value['document']['source_independence']='possible_translation_do_not_count_as_independent' if group else 'not_verified'
        save(path,value)
    # Preserve the source trail behind learned (non-GADM) names. A name alone
    # remains unverified, especially when its origin is a sparse/OCR page.
    origins=defaultdict(list);occurrences=defaultdict(int)
    for doc in config['catalog']:
        for page in source_pages(config,doc['provider'],doc['id']):
            for hit in explicit_places(page['text']):
                key=normalized(hit['name'])+'|'+hit['kind'];occurrences[key]+=1
                if len(origins[key])>=5:continue
                origins[key].append({'document_id':doc['id'],'provider':doc['provider'],
                    'source_url':doc['source_url'],'pdf_page':page['pdf_page'],'page_side':page['page_side'],
                    'page_status':page['status'],'start':hit['start'],'end':hit['end'],
                    'quote':page['text'][hit['start']:hit['end']]})
    reference_files=[]
    for relative in ('gfw/raw/provinces.json','gfw-adm2/raw/districts.json'):
        path=DATA_DIR/relative
        reference_files.append({'relative_path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    save(folder/'gazetteer-origins.json',{'method_version':'typed-name-origins-v1',
         'reference_files':reference_files,'names':{key:{'occurrences':occurrences[key],'example_origins':value} for key,value in origins.items()},
         'note':'Typed source occurrences explain recognition, not verified real-world location identity or current boundaries.'})
    save(folder/'document-relations.json',{'method_version':'filename-editions-v1','groups':groups,
          'unknown_documents':[d['id'] for d in config['catalog'] if d['id'] not in by_id]})
    config={**config,'document_relations_method':'filename-editions-v1','possible_translation_groups':len(groups),'gazetteer_origins_method':'typed-name-origins-v1'}
    save(folder/'candidate.json',config)
    save(ROOT/('pilot-candidate.json' if config.get('pilot') else 'candidate.json'),config)
    return config


def colophon_identity(pages):
    """Independent of translated filenames: same credited authors and edition date."""
    text='\n'.join(p.get('text','') for p in pages[:4])
    authors=re.search(r'(?im)^\s*(?:Penulis|Authors?|Writers?)\s*:\s*\n(.+?)(?=\n\s*(?:Penyelaras|Penyunting|Editors?|Desain|Design|Edisi|[^\n]*edition)\b)',text,re.S)
    if not authors:return None
    names=tuple(sorted(normalized(line) for line in authors[1].splitlines() if len(line.split())>=2))
    if len(names)<2 or len(names)>12:return None
    months={'januari':1,'january':1,'februari':2,'february':2,'maret':3,'march':3,'april':4,
            'mei':5,'may':5,'juni':6,'june':6,'juli':7,'july':7,'agustus':8,'august':8,
            'september':9,'oktober':10,'october':10,'november':11,'desember':12,'december':12}
    date=re.search(r'(?im)^.*(?:edisi|edition)[^\n]*?(\d{1,2})\s+('+ '|'.join(months)+r')\s+(20\d{2})',text)
    if not date:return None
    return names,(int(date[3]),months[date[2].casefold()],int(date[1]))


def content_numbers(pages):
    # Exclude ubiquitous years, small integers, figure numbers and pagination.
    nums=set(re.findall(r'(?<![\w.,])\d+(?:[.,]\d+)*(?![\w.,])',' '.join(p.get('text','') for p in pages)))
    return {n.replace(',','.') for n in nums if ('.' in n or ',' in n or len(n)>=3)
            and not re.fullmatch(r'(?:19|20)\d{2}',n)}


def verified_content_groups(documents,load_pages):
    """Require matching colophon AND substantial shared numerical body content.

    Matching names/date alone never merges two reports. Different publishers
    also remain separate. This is an edition relation, not extra corroboration.
    """
    buckets=defaultdict(list)
    for d in documents:
        pages=load_pages(d)
        ident=colophon_identity(pages)
        if ident:buckets[(d['provider'],ident)].append((d,content_numbers(pages)))
    groups=[]
    for key,members in buckets.items():
        clusters=[]
        for d,nums in members:
            linked=next((cluster for cluster in clusters if any(
                len(nums & other)>=8 and len(nums & other)/max(1,len(nums | other))>=.55 for _,other in cluster)),None)
            if linked is None:clusters.append([(d,nums)])
            else:linked.append((d,nums))
        for cluster in clusters:
            if len(cluster)<2:continue
            ids=sorted(d['id'] for d,_ in cluster)
            groups.append({'group_id':'edition-content:'+hashlib.sha256('|'.join(ids).encode()).hexdigest()[:16],
                'status':'matching_colophon_and_numeric_content', 'independent_corroboration':False,
                'basis':'same publisher, credited author list, edition date; >=8 shared nontrivial numbers and >=0.55 numerical Jaccard',
                'members':[{'document_id':d['id'],'download_url':d['download_url'],'source_url':d.get('source_url')} for d,_ in cluster]})
    return groups


from functools import lru_cache
@lru_cache(maxsize=4)
def content_groups(context_root):
    config=read(ROOT/context_root/'candidate.json',{})
    return verified_content_groups(config.get('catalog',[]),lambda d:source_pages(config,d['provider'],d['id']))


def collapse_retrieved_editions(evidence,config):
    """Keep one actual PDF per verified edition group; its page locators stay intact."""
    groups=content_groups(config['context_root']) if config.get('context_root') else []
    by_id={m['document_id']:g for g in groups for m in g['members']}
    for p in evidence:
        group=by_id.get(p.get('document_id'))
        if group:
            p['document_context']={**p.get('document_context',{}),'language_version_group':group['group_id'],
                'language_version_status':group['status'],'source_independence':'translation_not_independent'}
            p['related_editions']=group['members']
    verified_ids={g['group_id'] for g in groups}
    chosen={}
    for p in evidence:
        group=p.get('document_context',{}).get('language_version_group')
        if group in verified_ids and group not in chosen:chosen[group]=p['document_id']
    return [p for p in evidence if p.get('document_context',{}).get('language_version_group') not in chosen
            or p['document_id']==chosen[p['document_context']['language_version_group']]]
