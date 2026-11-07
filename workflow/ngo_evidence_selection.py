"""Select only after source checks; relevance outranks publisher rotation."""
from collections import Counter
import re
from ngo_question_parts import requested_facets
from ngo_evidence_policy import decisive_fit


def select_findings(question,findings,fits,by_id,limit=10):
    if len(findings)!=len(fits):
        raise ValueError('finding_fit_alignment')
    wanted=requested_facets(question)
    data_request=bool(re.search(r'\b(?:data|angka|berapa|persentase|rasio|jumlah|luas)\b',question,re.I))
    pool=[];seen=set()
    for finding,fit in zip(findings,fits):
        source=by_id[finding.evidence_id]
        edition=source.get('document_context',{}).get('language_version_group')
        key=(edition or source['sha256'],finding.text.casefold())
        if key not in seen:
            seen.add(key);pool.append((finding,fit))
    chosen=[];covered=set();docs=Counter()
    def priority(pair):
        finding,fit=pair
        local=fit.geography in ('same','within_requested_area') and fit.activity=='same'
        aspects=set(fit.answered_aspects)&wanted if local else set()
        decisive=any(decisive_fit(fit,relation) for relation in ('direct_support','direct_contradiction'))
        from ngo_source_facts import quantities
        measured=data_request and bool(aspects) and bool(quantities(finding.text))
        return (int(decisive),int(bool(aspects-covered)),int(bool(aspects)),int(local),
                int(measured),-docs[by_id[finding.evidence_id]['sha256']])
    while pool and len(chosen)<limit:
        pair=max(pool,key=priority)
        pool.remove(pair);chosen.append(pair)
        finding,fit=pair
        if fit.geography in ('same','within_requested_area') and fit.activity=='same':
            covered.update(fit.answered_aspects)
        docs[by_id[finding.evidence_id]['sha256']]+=1
    for n,(_,fit) in enumerate(chosen,1):fit.finding_id='F'+str(n)
    return [f for f,_ in chosen],[fit for _,fit in chosen]
