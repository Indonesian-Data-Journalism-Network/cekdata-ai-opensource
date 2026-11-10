"""Explicit observation periods shared by intent, retrieval and assessment.

Language normalization is source/indicator/location independent. A quarter is
not a month, and a comparison carries both complete period identities.
"""
import re

MONTHS = ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember']
ROMAN = {'i':1,'ii':2,'iii':3,'iv':4}


def key(p):
    quarter = getattr(p,'quarter',None)
    if quarter:
        return ('quarter',p.year,quarter)
    if p.month:
        return ('month',p.year,p.month)
    return ('annual',p.year,0)


def matches(record, periods):
    return not periods or key(record) in {key(p) for p in periods}


def normalize(intent, question):
    from flow import ObservationPeriod
    years = sorted({int(v) for v in re.findall(r'\b(?:19|20)\d{2}\b',question)})
    pattern = r'\b(?P<month>'+'|'.join(MONTHS)+r')\b|\b(?:triwulan|kuartal)\s+(?P<quarter>IV|III|II|I|[1-4])\b'
    found = list(re.finditer(pattern,question,re.I))
    if not found:
        return  # Relative/implicit periods remain the model's explicit contract.
    refs=[]
    abbreviated_quarters=False
    for hit in found:
        number = MONTHS.index(next(m for m in MONTHS if m.casefold()==hit['month'].casefold()))+1 if hit['month'] else ROMAN.get(hit['quarter'].casefold()) or int(hit['quarter'])
        basis = 'month' if hit['month'] else 'quarter'
        following = re.match(r'\s*(?:tahun\s+)?((?:19|20)\d{2})\b',question[hit.end():],re.I)
        if following:
            target_years=[int(following[1])]
        elif len(years)==1:
            target_years=years
        elif len(found)==1 and len(years)>=2:
            target_years=years
        else:
            continue  # Do not invent a year for an ambiguous fragment.
        # A month followed by a year range retains that month in each year.
        if len(found)==1 and len(years)>=2 and re.search(r'\b\d{4}\s*(?:[–—-]|sampai|hingga|s/d)\s*\d{4}\b',question,re.I):
            target_years=list(range(years[0],years[-1]+1))
        for year in target_years:
            refs.append(ObservationPeriod(year=year, **{basis:number}))
        # "triwulan I dan II 2026" abbreviates the repeated frequency.
        if basis=='quarter':
            more=re.match(r'\s*(dan|ke|hingga|sampai|[–—-])\s*(IV|III|II|I|[1-4])\b',question[hit.end():],re.I)
            if more and len(years)==1:
                abbreviated_quarters=True
                last=ROMAN.get(more[2].casefold()) or int(more[2])
                refs.append(ObservationPeriod(year=years[0],quarter=last))
    if not refs:
        return
    refs=sorted({key(p):p for p in refs}.values(),key=lambda p:(p.year,p.quarter*3 if p.quarter else p.month))
    same_frequency=len({key(p)[0] for p in refs})==1
    # For an explicit continuous interval, enumerate periods, including across years.
    continuous=bool(re.search(r'\b(?:tren|setiap bulan|setiap triwulan|terus|selama)\b',question,re.I))
    interval=bool(re.search(r'\b(?:hingga|sampai|ke)\b|[–—-]',question))
    if len(refs)>1 and same_frequency and continuous and interval and (len(found)>1 or abbreviated_quarters):
        freq=key(refs[0])[0];size=4 if freq=='quarter' else 12
        start=refs[0].year*size+key(refs[0])[2]-1
        end=refs[-1].year*size+key(refs[-1])[2]-1
        if end-start<=1200:
            refs=[ObservationPeriod(year=n//size,**{freq:n%size+1}) for n in range(start,end+1)]
    intent.requested_periods=refs
    intent.temporal='explicit'
    intent.year=refs[-1].year
    intent.month=refs[-1].month  # Compatibility for older source adapters only.
    intent.baseline_year=refs[0].year if len(refs)>1 else None
    if len(refs)>1:
        intent.requires_series = intent.kind=='trend' or continuous
        intent.endpoint_difference = not intent.requires_series and not intent.relative_change
    else:
        # A lookup at one quarter must not accidentally request an annual change.
        if intent.kind=='lookup':intent.requires_series=False


def label(p):
    if p.quarter:
        return f'Triwulan {("I","II","III","IV")[p.quarter-1]} {p.year}'
    if p.month:
        return f'{MONTHS[p.month-1]} {p.year}'
    return str(p.year)
