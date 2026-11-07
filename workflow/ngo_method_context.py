"""Locate original methodology passages without treating an entire PDF as a model."""
import re

METHOD=re.compile(r'\b(?:pemodelan|modelling|modeling|simulasi|simulation|IRIO|model ekonometrika|econometric model)\b',re.I)
DESCRIBES_METHOD=re.compile(r'metodologi|metode|methodolog|asumsi|assumptions?|menggunakan|using|digunakan|disajikan|presented|estimasi dampak|impact estimat',re.I)
INTRODUCES_METHOD=re.compile(r'metodologi|methodology|(?:menggunakan|using|used)\b.{0,120}\b(?:model|IRIO|simulation|simulasi)|model dan asumsi',re.I|re.S)


def method_evidence(document,page):
    candidates=[]
    for parent in document.get('parents',[]):
        distance=page-parent['pdf_page']
        text=parent['text']
        foundational=bool(INTRODUCES_METHOD.search(text))
        if ((distance<0 or distance>12) and not foundational) or not METHOD.search(text) or not DESCRIBES_METHOD.search(text):continue
        if parent['metadata'].get('content_kind') in ('bibliography','table_of_contents'):continue
        # Keep a bounded contiguous source quote, with its original offsets.
        hit=METHOD.search(text);start=max(0,hit.start()-450);end=min(len(text),hit.end()+1150)
        candidates.append({'pdf_page':parent['pdf_page'],'page_side':parent['page_side'],
            'start':parent['start']+start,'end':parent['start']+end,'text':text[start:end],
            'parent_id':parent['parent_id'],'method_introduction':foundational,
            'applicability':'must_be_matched_to_result_not_document_wide'})
    # Executive summaries can precede the method; conclusions may follow it
    # much later. Neither position proves applicability without source review.
    # Include original method introductions as candidates for semantic review,
    # never as automatic evidence that every later result uses that method.
    nearest=sorted(candidates,key=lambda p:(abs(page-p['pdf_page']),p['start']))
    selected=nearest[:2]
    for item in [p for p in nearest if p['method_introduction']][:3]:
        if item not in selected:selected.append(item)
    return [{'method_id':'M'+str(i+1),**p} for i,p in enumerate(selected)]
