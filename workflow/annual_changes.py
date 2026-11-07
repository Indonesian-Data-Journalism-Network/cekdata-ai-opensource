"""Compare two year-on-year changes, with explicit predecessor evidence."""
from decimal import Decimal, localcontext
import re


def normalize(intent, question):
    q = question.casefold()
    years = list(dict.fromkeys(int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b', q)))
    nominal = bool(re.search(r'\b(?:kenaikan|peningkatan|penurunan|perubahan|pertumbuhan)\b', q))
    compare = bool(re.search(r'\bbandingkan\b|lebih (?:tinggi|rendah|besar|kecil|cepat|lambat)|selisih\s+(?:kenaikan|penurunan|perubahan)|sama (?:besar|tinggi)|berbeda', q))
    # "Berapa kenaikan dari A ke B?" requests ONE change, not two changes.
    interval = bool(re.search(r'dari\s+(?:tahun\s+)?\d{4}\s+(?:ke|hingga|sampai)\s+(?:tahun\s+)?\d{4}', q))
    matched = nominal and compare and len(years) == 2 and not interval
    intent.change_comparison = 'none'
    intent.change_years = []
    if not matched:
        return False
    intent.change_comparison = 'relative' if re.search(r'persen|persentase|laju', q) else 'absolute'
    intent.change_years = years
    intent.temporal = 'explicit'
    intent.requested_years = sorted({y for end in years for y in (end-1, end)})
    intent.baseline_year, intent.year = min(intent.requested_years), max(years)
    intent.requires_series = True
    intent.continuous = intent.endpoint_difference = intent.relative_change = False
    intent.predicate = None  # This compares two derived values, not a raw value against zero.
    if intent.kind != 'claim':
        intent.kind = 'comparison'
    if intent.month is not None:
        intent.clarification = 'Perbandingan perubahan ini untuk angka tahunan penuh atau bulan yang sama pada setiap tahun?'
    return True


def evaluate(state, out):
    from flow import readable_indicator
    from answer_format import rounded
    i = state.intent
    rows = {r.id:r for r in out.primary}
    result = {'groups':[], 'conclusion':'', 'context':'', 'calculations':[]}
    out.annual_changes = result
    years = i.change_years
    required = sorted({y for end in years for y in (end-1, end)})
    result['context'] = 'Perubahan tiap tahun dihitung terhadap tahun sebelumnya: ' + '; '.join(f'{y-1}→{y}' for y in sorted(years)) + '.'
    if i.change_comparison == 'relative':
        result['context'] += ' Persentasenya memakai nilai tahun sebelumnya sebagai pembagi; selisih antar-persentase dinyatakan dalam poin persentase.'
    groups = {}
    for r in out.primary:
        groups.setdefault((r.indicator_id,r.area,r.population,r.source),[]).append(r)
    with localcontext() as ctx:
        ctx.prec = 60
        for group in groups.values():
            sample = group[0]
            changes = {}
            for year in years:
                edges = [c for c in out.calculations if c.kind == 'time'
                         and c.baseline_id in {r.id for r in group}
                         and rows[c.baseline_id].year == year-1 and rows[c.target_id].year == year]
                if len(edges) != 1:
                    continue
                c = edges[0]
                a,b = rows[c.baseline_id],rows[c.target_id]
                if a.month is not None or b.month is not None or a.temporal_basis != 'annual' or b.temporal_basis != 'annual':
                    if 'incompatible_definitions' not in out.gaps: out.gaps.append('incompatible_definitions')
                    continue
                delta = Decimal(c.value)
                value,unit = delta,c.unit
                if i.change_comparison == 'relative':
                    if Decimal(a.value) <= 0:
                        if 'relative_baseline_invalid' not in out.gaps: out.gaps.append('relative_baseline_invalid')
                        continue
                    value,unit = delta/Decimal(a.value)*100,'persen'
                changes[year] = value
                result['calculations'].append({'label':f'{sample.area} · Perubahan {year-1}–{year}',
                    'value':rounded(value),'unit':unit})
            if len(changes) != 2:
                continue
            first,last = sorted(years)
            difference = changes[last]-changes[first]
            diffunit = 'poin persentase' if i.change_comparison=='relative' else c.unit
            result['groups'].append({'area':sample.area,'indicator':readable_indicator(sample),
                'changes':{str(y):str(v) for y,v in changes.items()},'unit':unit,'difference':str(difference)})
            result['calculations'].append({'label':f'{sample.area} · Selisih perubahan {last} − {first}',
                'value':rounded(difference),'unit':diffunit})
    if out.gaps or not result['groups'] or len(result['groups']) != len(groups):
        missing = []
        for group in groups.values():
            absent = sorted(set(required)-{r.year for r in group})
            if absent: missing.append(f"{group[0].area}: data {', '.join(map(str,absent))} belum ditemukan")
        result['conclusion'] = ('Belum cukup data yang sebanding untuk membandingkan kedua perubahan tahunan. '
            + ('; '.join(missing)+'. ' if missing else '') + 'Tahun tanpa data tidak dianggap nol.')
        result['calculations'] = []  # Conflicting/incomplete evidence cannot support the full comparison.
        if i.kind=='claim':
            out.verdict,out.reason = 'Tidak dapat diverifikasi',result['conclusion']
        return
    statements=[]
    for g in result['groups']:
        phrases=[]
        for y in sorted(years):
            value=Decimal(g['changes'][str(y)])
            verb='naik' if value>0 else 'turun' if value<0 else 'tidak berubah'
            phrases.append(f'{y-1}–{y} {verb}' + (f" {rounded(abs(value))} {g['unit']}" if value else ''))
        delta=Decimal(g['difference']); relation='lebih tinggi' if delta>0 else 'lebih rendah' if delta<0 else 'sama'
        first,last=sorted(years)
        diffunit='poin persentase' if i.change_comparison=='relative' else g['unit']
        statements.append(f"{g['indicator']} di {g['area']}: "+'; '.join(phrases)+f'. Perubahan {last} {relation} dibandingkan {first}'
            +(f' dengan selisih {rounded(abs(delta))} {diffunit}.' if delta else '.'))
    result['conclusion']=' '.join(statements)
    if i.kind!='claim': return
    out.verdict='Tidak dapat diverifikasi'
    out.reason=result['conclusion']
    q=state.question.casefold()
    direction=re.search(r'lebih (tinggi|besar|cepat|rendah|kecil|lambat)|(?:sama besar|sama tinggi)',q)
    # Compound/causal/numeric assertions need more than this single relational test.
    without_years=re.sub(r'\b(?:19|20)\d{2}\s+dan\s+(?:19|20)\d{2}\b','',q)
    without_years=re.sub(r'\b(?:19|20)\d{2}\b','',without_years)
    if not direction or len(result['groups'])!=1 or i.causal or re.search(r'\d|\bkarena\b|\bsehingga\b|\b(?:dan|atau)\b',without_years):
        out.reason+=' Belum cukup data untuk menilai keseluruhan klaim.'
        return
    g=result['groups'][0]
    a,b=(Decimal(g['changes'][str(y)]) for y in years)
    decline=bool(re.search(r'\bpenurunan\b',q))
    increase=bool(re.search(r'\b(?:kenaikan|peningkatan)\b',q))
    signs_ok=(a<0 and b<0) if decline else (a>0 and b>0) if increase else True
    if decline: a,b=-a,-b
    op=direction[1]
    supported=(a>b if op in ('tinggi','besar','cepat') else a<b if op in ('rendah','kecil','lambat') else a==b) and signs_ok
    if re.search(r'\b(?:tidak|tak)\s+(?:lebih|sama)',q): supported=not supported
    out.verdict='Benar' if supported else 'Salah'


def present(state, parsed):
    result=state.assessment.annual_changes
    parsed['jawaban_utama']=parsed['kesimpulan']=result.get('conclusion','')
    parsed['konteks_penting']=result.get('context','')
    parsed['alasan']=state.assessment.reason if state.intent.kind=='claim' else ''
    parsed['penilaian']=state.assessment.verdict or ''
    if parsed.get('findings_table'):
        parsed['findings_table']['calculations']=result.get('calculations',[])
