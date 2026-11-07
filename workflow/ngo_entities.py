"""Source-anchored company aliases and conservative cross-source display merging.

An acronym is an alias only when a source explicitly pairs it with a full
name. Conflicting expansions remain unresolved. This is not entity discovery
from similarity, and never adds areas or totals across reports.
"""
import re
from collections import defaultdict


def aliases(evidence):
    candidates=defaultdict(set)
    pattern=re.compile(r'\bPT\.?\s+([A-Z][\w-]+(?:\s+[A-Z][\w-]+){1,7})\s*\(\s*(?:PT\.?\s*)?([A-Z][A-Z0-9]{1,9})\s*\)')
    for page in evidence:
        for full,short in pattern.findall(page.get('page_text','')):
            full='PT '+' '.join(full.split())
            candidates['pt '+short.casefold()].add(full)
    return {short:next(iter(names)) for short,names in candidates.items() if len(names)==1}


def canonical(text,mapping):
    result=' '.join(text.split())
    for short,full in mapping.items():
        result=re.sub(re.escape(full)+r'\s*\(\s*(?:PT\.?\s*)?'+re.escape(short[3:])+r'\s*\)',lambda _:full,result,flags=re.I)
        result=re.sub(r'\bPT\.?\s*'+re.escape(short[3:])+r'\b',lambda _:full,result,flags=re.I)
    return result


def merge_rows(rows,evidence):
    mapping=aliases(evidence);merged=[];keys={}
    for label,value,refs in rows:
        label=canonical(label,mapping)
        # Labels retain measurement, geography, period and status. Equal
        # numbers alone are never a reason to merge unrelated observations.
        key=(' '.join(re.findall(r'\w+',label.casefold())),value)
        if key in keys:
            target=merged[keys[key]]
            numbers=list(dict.fromkeys(re.findall(r'\[\d+\]',target[2]+' '+refs)))
            target[2]=''.join(numbers)
        else:
            keys[key]=len(merged);merged.append([label,value,refs])
    return merged


def merge_lines(lines,evidence):
    mapping=aliases(evidence);seen={};result=[]
    for line in lines:
        content=re.sub(r'\s*(?:\[\d+\])+\s*$','',line)
        key=canonical(content,mapping).casefold()
        if key in seen:
            i=seen[key];refs=list(dict.fromkeys(re.findall(r'\[\d+\]',result[i]+' '+line)))
            result[i]=re.sub(r'\s*(?:\[\d+\])+\s*$','',result[i])+' '+''.join(refs)
        else:seen[key]=len(result);result.append(canonical(line,mapping))
    return result
