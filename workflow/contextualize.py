"""Explain the evidence and arithmetic used in an answer, independently of source notes."""
from decimal import Decimal, localcontext
import re


def explain(state):
    from flow import number, observation_period, readable_indicator, requests_difference
    out = state.assessment
    rows = {r.id:r for r in out.primary}
    lines, calculations = [], []
    conclusion = ''
    if set(out.gaps)=={'relative_baseline_invalid'}:
        # The main answer already states both the absolute change and why
        # dividing by this baseline is invalid; avoid another generic formula.
        return {'lines':[],'conclusion':'','calculations':[]}
    from environment_data import cross_source_limit
    mixed_limit=cross_source_limit(state)
    if mixed_limit:
        return {'lines':[mixed_limit],'conclusion':'','calculations':[]}
    def shown(value):
        from answer_format import rounded
        return rounded(value)

    with localcontext() as ctx:
        ctx.prec = 60
        if rows and not out.gaps and all(r.temporal_basis == 'land_transition' for r in rows.values()):
            from environment_data import source_context
            return {'lines':[source_context(list(rows.values()))],
                    'conclusion':'', 'calculations':[]}
        if rows and not out.gaps and all(r.temporal_basis == 'model_period' for r in rows.values()):
            for start,end in sorted({(r.period_start,r.period_end) for r in rows.values()}):
                first,last=int(start[:4]),int(end[:4])
                kinds={r.aggregation_kind for r in rows.values() if (r.period_start,r.period_end)==(start,end)}
                if 'period_total' in kinds:lines.append(f'Total mencakup seluruh periode {first}–{last}.')
                if 'period_mean' in kinds:lines.append(f'Rata-rata tahunan adalah total periode {first}–{last} dibagi {last-first+1} tahun; bukan pengamatan untuk satu tahun tertentu.')
            net = [r for r in rows.values() if ':carbon-net-flux-' in r.source_record_id]
            if net:
                lines.append('Neraca positif berarti sumber emisi bersih; negatif berarti penyerap bersih.')
                statuses=[]
                for r in net:
                    status = 'sumber emisi bersih' if Decimal(r.value)>0 else 'penyerap karbon bersih' if Decimal(r.value)<0 else 'seimbang antara emisi dan penyerapan'
                    statuses.append(f'Dalam periode model {r.period_start[:4]}–{r.period_end[:4]}, hutan di {r.area} merupakan {status}.')
                conclusion=' '.join(dict.fromkeys(statuses))
            return {'lines':lines,'conclusion':conclusion,'calculations':[]}
        average = re.search(r'\brata[\s-]+rata\b', state.question, re.I)
        total_request = re.search(r'\b(?:total|akumulasi|kumulatif|jumlahkan)\b', state.question, re.I)
        if (average or total_request) and state.intent.kind != 'claim':
            years = sorted(set(int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b',state.question)))
            if len(years) == 2:
                expected = set(range(years[0],years[1]+1))
            elif state.intent.baseline_year and state.intent.year:
                expected = set(range(state.intent.baseline_year,state.intent.year+1))
            else:
                expected = set()
            groups = {}
            for r in rows.values():
                groups.setdefault(r.series,[]).append(r)
            valid = bool(expected and groups and not out.gaps) and all(
                {r.year for r in group} == expected and len(group) == len(expected)
                and all(r.month is None and not r.period_text for r in group) for group in groups.values())
            if total_request and not average:
                valid = valid and all(r.source_record_id.startswith('gfw:gadm__tcl__') or r.aggregation_kind=='annual_flow' for r in rows.values())
            if valid:
                means = []
                for group in groups.values():
                    group.sort(key=lambda r:r.year)
                    sample=group[0]
                    total=sum((Decimal(r.value) for r in group),Decimal(0))
                    mean=total/len(expected)
                    means.append((sample,mean))
                    if sample.aggregation_kind != 'annual_stock':
                        calculations.append({'kind':'total','area':sample.area,'indicator':sample.indicator,
                            'evidence_ids':[r.id for r in group],'value':str(total),'unit':sample.unit})
                    if average:
                        calculations.append({'kind':'annual_mean','area':sample.area,'indicator':sample.indicator,
                            'evidence_ids':[r.id for r in group],'total':str(total),'count':len(expected),'value':str(mean),'unit':sample.unit})
                if not average:
                    conclusion=' '.join(f"Total {c['area']} selama {min(expected)}–{max(expected)} adalah {shown(c['value'])} {c['unit']}." for c in calculations)
                    return {'lines':[f'Total dihitung dengan menjumlahkan nilai tahunan selama {min(expected)}–{max(expected)}. Perhitungan memakai angka asli sebelum pembulatan.'], 'conclusion':conclusion, 'calculations':calculations}
                conclusion=' '.join(f'Rata-rata tahunan di {r.area} adalah {shown(v)} {r.unit}.' for r,v in means)
                if len(means)==2:
                    a,b=means[0][0],means[1][0]
                    compatible = (a.indicator_id,a.population,a.source,a.unit,a.definition,a.method)==(
                        b.indicator_id,b.population,b.source,b.unit,b.definition,b.method)
                    if compatible and a.area!=b.area:
                        (low,lv),(high,hv)=sorted(means,key=lambda item:item[1])
                        difference=hv-lv
                        comparison=(f'Rata-rata {high.area} lebih tinggi daripada {low.area}, dengan selisih '
                            f'{shown(difference)} {high.unit}.' if difference else f'Rata-rata kedua wilayah sama, yaitu {shown(hv)} {high.unit}.')
                        conclusion+=' '+comparison
                        calculations.append({'kind':'mean_difference','value':str(difference),'unit':high.unit,
                            'evidence_ids':list(rows)})
                lines=[f'Rata-rata dihitung dari total selama {len(expected)} tahun dibagi {len(expected)}. Seluruh seri memiliki data lengkap untuk periode yang sama.']
                return {'lines':lines,'conclusion':conclusion,'calculations':calculations}
            lines.append('Perhitungan agregat belum dilakukan karena kelengkapan periode, kesetaraan seri, atau kesesuaian indikator belum dapat dipastikan. Tahun tanpa data tidak dianggap nol.')
            return {'lines':lines,'conclusion':'Hasil agregat belum dapat disimpulkan dari bukti yang tersedia.','calculations':[]}

        if any(g in out.gaps for g in ('source_conflict','incompatible_definitions','retrieval_truncated')):
            return {'lines':[],'conclusion':'','calculations':[]}
        kinds={c.kind for c in out.calculations}
        if 'relative' in kinds:
            lines=['Selisih dihitung dari nilai akhir dikurangi nilai awal. Persentase perubahan menggunakan nilai awal sebagai pembagi, lalu dikalikan 100%.']
        elif 'scope' in kinds:
            lines=['Perbandingan menggunakan periode dan satuan yang sebanding.' + (' Selisih dihitung dari perbedaan nilai kedua wilayah atau kategori.' if requests_difference(state.question) else '')]
        elif 'time' in kinds:
            if state.intent.kind=='trend' or state.intent.continuous:
                groups={}
                for r in rows.values(): groups.setdefault(r.series,[]).append(r)
                endpoints=[]
                for group in groups.values():
                    group.sort(key=lambda r:r.period)
                    first,last=group[0],group[-1]
                    direction='lebih tinggi' if Decimal(last.value)>Decimal(first.value) else 'lebih rendah' if Decimal(last.value)<Decimal(first.value) else 'sama'
                    if len(group)>1: endpoints.append(f'{last.area}: nilai {observation_period(last)} {direction} daripada {observation_period(first)}')
                changes=[Decimal(c.value) for c in out.calculations if c.kind=='time']
                pattern=('Rangkaian ini memuat kenaikan dan penurunan.' if any(v>0 for v in changes) and any(v<0 for v in changes)
                         else 'Arah perubahan dibaca dari seluruh pasangan periode yang tersedia.')
                lines=[('; '.join(endpoints)+'. '+pattern) if endpoints else pattern]
            elif (state.intent.predicate is not None or state.intent.endpoint_difference
                  or state.intent.relative_change or re.search(r'perubahan|kenaikan|penurunan|selisih',state.question,re.I)):
                lines=['Perubahan dihitung dari nilai akhir dikurangi nilai awal pada indikator dan wilayah yang sama.']
        elif len(rows)==1:
            sample=next(iter(rows.values()))
            if sample.source_record_id.startswith('mapbiomas:'):
                from environment_data import source_context
                lines = [source_context(list(rows.values()))]
            elif sample.source_record_id.endswith(':tree-cover-loss-fire'):
                lines=['Angka ini mengukur kehilangan tutupan pohon yang dikaitkan dengan kebakaran, bukan seluruh luas lahan yang terbakar.']
            elif sample.aggregation_kind=='extent':
                if sample.temporal_basis=='map_version':
                    lines=['Angka berasal dari peta gabungan berbagai tahun. Tahun versi peta tidak menunjukkan tahun pengamatan.']
                elif ':sdpt-' in sample.source_record_id:
                    lines=['Angka menunjukkan luas kelas tanaman pada peta acuan 2020, dengan tahun sumber lokal beragam; bukan luas izin konsesi. Kelas campuran disajikan terpisah.']
                else:
                    lines=['Angka menunjukkan luas mangrove yang dipetakan pada tahun acuan 2020; tidak menggambarkan perubahan setelah tahun tersebut.']
            elif sample.source_record_id.startswith('gfw:carbonflux_'):
                lines=['Emisi bruto hutan dihitung dari gangguan tegakan menurut model karbon GFW; angka ini bukan seluruh emisi wilayah.']
            elif sample.source_record_id.startswith('gfw:'):
                lines=['Kehilangan tutupan pohon tidak otomatis berarti deforestasi permanen atau luas hutan yang tersisa.']
        if (state.intent.continuous and out.verdict=='Salah' and re.search(r'\b(?:meningkat|naik)\b',state.question,re.I)
                and state.intent.predicate and state.intent.predicate.operator in ('gt','ge')
                and not state.intent.predicate.negated and Decimal(state.intent.predicate.threshold)==0
                and any(Decimal(c.value)<0 for c in out.calculations if c.kind=='time')):
            lines=['Klaim meningkat setiap tahun mensyaratkan kenaikan pada seluruh pasangan tahun berturut-turut. Adanya penurunan pada salah satu pasangan tahun membantah klaim tersebut.']
    return {'lines':lines,'conclusion':conclusion,'calculations':calculations}
