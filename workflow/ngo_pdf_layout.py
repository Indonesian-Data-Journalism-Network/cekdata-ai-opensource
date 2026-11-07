"""Read prose columns in page order while retaining full-width headings/tables."""
from collections import Counter
import re


def word_lines(words):
    lines=[]
    for word in sorted(words,key=lambda w:(w['top'],w['x0'])):
        if not lines or abs(word['top']-lines[-1][0]['top'])>3:lines.append([])
        lines[-1].append(word)
    merged=[]
    for line in lines:
        previous=merged[-1] if merged else []
        # Font variants can have shifted bounding boxes on the same baseline.
        # Rejoin only nearby rows whose horizontal spans do not overlap.
        close=previous and line[0]['top']-previous[0]['top']<=max(w['height'] for w in line+previous)*.65
        overlap=any(min(a['x1'],b['x1'])-max(a['x0'],b['x0'])>1 for a in line for b in previous)
        if close and not overlap:previous.extend(line)
        else:merged.append(line)
    return [sorted(line,key=lambda w:w['x0']) for line in merged]


def prose(words):
    return len(words)>=4 and sum(bool(re.search(r'[A-Za-zÀ-ÿ]{3}',w['text'])) for w in words)>=len(words)*.65


def read_columns(page):
    """Conservative repeated prose gutter detection; returns None if ambiguous.

    A table's isolated cell gaps do not suffice. Full-width lines split the
    reading bands so headings and tables retain their position in the page.
    """
    lines=word_lines(page.extract_words(x_tolerance=2,y_tolerance=3))
    x0,_,x1,_=page.bbox;width=x1-x0;gap_min=width*.025
    votes=Counter()
    for line in lines:
        for a,b in zip(line,line[1:]):
            if b['x0']-a['x1']<gap_min:continue
            left=[w for w in line if w['x1']<=a['x1']]
            right=[w for w in line if w['x0']>=b['x0']]
            if not (prose(left) and prose(right)):continue
            for step in range(30,71):
                x=x0+width*step/100
                if a['x1']+3<x<b['x0']-3:votes[step]+=1
    if not votes:return None
    best=max(votes.values())
    if best<5:return None
    choices=[s for s,n in votes.items() if n==best]
    split=x0+width*sorted(choices)[len(choices)//2]/100
    def crossing(line):
        if any(w['x0']<split<w['x1'] for w in line):return True
        left=[w for w in line if w['x1']<=split];right=[w for w in line if w['x0']>=split]
        return bool(left and right and right[0]['x0']-left[-1]['x1']<width*.016)
    bands=[];block=[];previous_bottom=None
    for line in lines:
        top=min(w['top'] for w in line)
        if block and previous_bottom is not None and top-previous_bottom>width*.045:
            bands.append(block);block=[]
        if crossing(line):
            if block:bands.append(block);block=[]
            bands.append([line])
        else:block.append(line)
        previous_bottom=max(w['bottom'] for w in line)
    if block:bands.append(block)
    ordered=[];column_bands=0
    for band in bands:
        paired=sum(prose([w for w in line if w['x1']<=split]) and
                   prose([w for w in line if w['x0']>=split]) for line in band)
        if paired>=4:
            column_bands+=1
            for side in ('left','right'):
                for line in band:
                    words=[w for w in line if (w['x1']<=split if side=='left' else w['x0']>=split)]
                    if words:ordered.append(' '.join(w['text'] for w in words))
                ordered.append('')
        else:
            ordered.extend(' '.join(w['text'] for w in line) for line in band)
    if not column_bands:return None
    text='\n'.join(ordered).strip()
    # Every extracted word must survive reordering, including numbers.
    before=Counter(w['text'] for line in lines for w in line)
    if Counter(text.split())!=before:return None
    return {'text':text,'reading_order':'prose_columns_v1','column_bands':column_bands,
            'gutter_x':round(split,2)}
