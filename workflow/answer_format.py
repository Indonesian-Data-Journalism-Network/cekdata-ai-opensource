"""Structured, complete evidence tables and concise explanations for answer rendering."""
from decimal import Decimal, localcontext
import re


def rounded(value):
    from flow import number
    with localcontext() as ctx:
        ctx.prec = 60
        original=Decimal(value)
        shown=original.quantize(Decimal('0.01'))
        # Do not visually convert a small recorded amount into an exact zero.
        if original and not shown:
            shown=original.quantize(Decimal(1).scaleb(original.adjusted()-1))
        return number(shown.copy_abs() if not shown else shown)


def evidence_table(state, records, aggregates):
    from flow import observation_period, readable_indicator, requests_difference
    primary = {r.id for r in state.assessment.primary}
    units = {r.unit for r in records}
    concepts = {(r.indicator_id, r.population, r.source, r.definition, r.method) for r in records}
    areas = list(dict.fromkeys(r.area for r in records))
    # Pivot only unambiguous, comparable annual observations; never drop conflicting records.
    pivot = (bool(records) and len(concepts) == len(units) == 1 and len(areas) > 1
             and len({(r.area, r.year) for r in records}) == len(records)
             and all(r.month is None and not r.period_text and r.id in primary for r in records)
             and all({r.year for r in records if r.area == a} == {r.year for r in records} for a in areas))
    unit = next(iter(units)) if len(units) == 1 else ''
    if pivot:
        headers = ['Tahun'] + [f'{a} ({unit})' for a in areas]
        lookup = {(r.area,r.year):r for r in records}
        rows = [[str(year)] + [rounded(lookup[a,year].value) for a in areas]
                for year in sorted({r.year for r in records})]
        for kind,label in [('total','Total'),('annual_mean','Rata-rata tahunan')]:
            values = {c['area']:c for c in aggregates if c['kind'] == kind}
            if set(values) == set(areas): rows.append([label] + [rounded(values[a]['value']) for a in areas])
    else:
        varied = len(concepts) > 1
        contextual = any(r.id not in primary for r in records)
        headers = (['Indikator / cakupan / sumber'] if varied else []) + ['Wilayah','Periode',f'Nilai ({unit})' if unit else 'Nilai','Satuan']
        if unit: headers.pop()
        if contextual: headers.append('Keterangan')
        rows = []
        for r in records:
            label = f'{readable_indicator(r)} · {r.population_label or r.population} · {r.source_name or r.source}'
            cells = ([label] if varied else []) + [r.area,observation_period(r),rounded(r.value)] + ([] if unit else [r.unit])
            if contextual: cells.append('Bukti langsung' if r.id in primary else 'Pembanding tersedia; bukan periode/lingkup yang diminta')
            rows.append(cells)
        for c in aggregates:
            if c['kind'] not in ('total','annual_mean'): continue
            cells = ([c.get('indicator','')] if varied else []) + [c['area'], 'Total' if c['kind']=='total' else 'Rata-rata tahunan',rounded(c['value'])] + ([] if unit else [c['unit']])
            if contextual: cells.append('Hasil perhitungan')
            rows.append(cells)
    calculations = []
    by_id = {r.id:r for r in records}
    if not (set(state.assessment.gaps)-{'relative_baseline_invalid'}) and not aggregates:
        for c in state.assessment.calculations:
            a,b = by_id.get(c.baseline_id),by_id.get(c.target_id)
            if not a or not b: continue
            # Annual transitions stay in the observations for trends; expose requested endpoint/percentage calculations.
            if len(records)>2 and c.kind=='time': continue
            if c.kind=='scope' and not requests_difference(state.question): continue
            label = ('Persentase perubahan' if c.kind=='relative' else 'Selisih '+b.area+' − '+a.area if c.kind=='scope' else 'Perubahan '+observation_period(a)+'–'+observation_period(b))
            calculations.append({'label':label,'value':rounded(c.value),'unit':c.unit})
    for c in aggregates:
        if c['kind']=='mean_difference': calculations.append({'label':'Selisih rata-rata','value':rounded(c['value']),'unit':c['unit']})
    caption = ' · '.join(dict.fromkeys(readable_indicator(r) + (f' ({r.population_label or r.population})' if r.population_label or r.population != 'total' else '') for r in records))
    return {'caption':caption,'headers':headers,'rows':rows,'calculations':calculations}


def markdown_table(table):
    def cell(v): return str(v).replace('|','\\|').replace('\n',' ')
    headers=table['headers']
    lines=[table.get('caption',''),'', '| '+' | '.join(map(cell,headers))+' |','| '+' | '.join('---' for _ in headers)+' |']
    lines += ['| '+' | '.join(map(cell,row))+' |' for row in table['rows']]
    if table.get('calculations'):
        lines += ['', '| Perhitungan | Nilai |', '| --- | ---: |']
        lines += [f"| {cell(c['label'])} | {c['value']} {c['unit']} |" for c in table['calculations']]
    return '\n'.join(lines).strip()
