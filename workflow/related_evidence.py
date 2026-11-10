"""Optional, non-decisive statistical context. Never feeds back into assessment.

Queries retain the requested geography and use explicit catalogue indicator
relationships. Historical observations and provincial examples are labelled,
never summed into a substitute for a missing national/current-year figure.
"""
import asyncio
import re


def plans(question, intent, catalog, reference):
    from flow import SearchQuery
    from geography import Geography
    from ngo_gfw_context import finer_scope, exact_administrative_names
    if finer_scope(question):
        return []
    fire = bool(re.search(r'\b(?:karhutla|kebakaran|terbakar|titik panas|hotspot)\b', question, re.I))
    forest = bool(re.search(r'\b(?:hutan|deforestasi|tutupan pohon|tambang|pertambangan|sawit)\b', question, re.I))
    selected = set(getattr(intent, 'indicator_ids', []) or [])
    member = 'gfw-tree-cover-loss-fire' if fire else 'gfw-tree-cover-loss' if forest else ''
    candidates = [c for c in catalog if c['indicator_id'] in selected or member in c.get('member_ids', [c['indicator_id']])]
    if fire:
        # A fire claim must not acquire unrelated forest/peat stock merely
        # because the initial selector chose those catalogue neighbours.
        candidates = [c for c in candidates if member in c.get('member_ids', [c['indicator_id']])]
    # Topic relationships are explicit, not arbitrary semantic neighbours.
    if member:
        candidates.sort(key=lambda c: member not in c.get('member_ids', [c['indicator_id']]))
    output = []
    for family in candidates[:2]:
        # Words like "tiga provinsi terdampak" or "kabupaten dengan luas
        # terbesar" describe a level, not a proper administrative name.
        scope_text = re.sub(r'\b(?:provinsi|kabupaten|kota)\s+(?=[a-z])', '', question)
        if not exact_administrative_names(scope_text, family):
            continue
        geo = Geography([family])
        resolution = geo.resolve(question)
        if resolution.clarification:
            continue
        areas = [a for a in resolution.areas if a in family.get('areas', [])]
        national = any(geo.entities[i]['level'] == 'nasional' for i in resolution.ids)
        if not areas and not national:
            continue
        available = {int(y) for y in family.get('years', []) if int(y) < reference.year}
        years = sorted(available)[-5:]
        if not years:
            continue
        claim_text = re.split(r'Pernyataan disampaikan', question, flags=re.I)[0]
        explicit_years = {int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b', claim_text)}
        if explicit_years:
            requested = set(range(min(explicit_years), max(explicit_years) + 1))
            matching = sorted(requested.intersection(available))[-5:]
            if matching:
                years = matching
        if areas:
            output.append((SearchQuery(text=question, indicator_ids=[family['indicator_id']],
                areas=areas[:6], years=years, population=getattr(intent, 'population', 'total'),
                rationale='Konteks terpisah; bukan bukti untuk menentukan label klaim.'), family, False))
        # National queries can fall back to a small reproducible set of provinces.
        # Order is alphabetical, never selected by their numeric results.
        if national:
            provinces = sorted({geo.destination(i) for i, e in geo.entities.items()
                if e['level'] == 'provinsi' and geo.destination(i) in family.get('areas', [])})[:3]
            if provinces:
                output.append((SearchQuery(text=question, indicator_ids=[family['indicator_id']],
                    areas=provinces, years=years, population=getattr(intent, 'population', 'total'),
                    rationale='Contoh provinsi menurut abjad, bukan total nasional.'), family, True))
    return output


def group_records(records, query, family, subset):
    from answer_format import rounded
    members = family.get('member_ids', [family['indicator_id']])
    rows = sorted(records, key=lambda r: (r.area, r.year, r.month or 0))
    # Validate every dimension again: retrieval can return broad candidates.
    rows = [r for r in rows if r.indicator_id == family['indicator_id'] and r.area in query.areas
            and r.year in query.years and r.population == query.population
            and r.month is None and r.quarter is None and r.temporal_basis == 'annual'
            and r.source_url and not r.synthetic]
    if not rows:
        return None
    # Conflicting duplicate observations must not be silently selected.
    seen = {}
    for r in rows:
        key = (r.area, r.year)
        if key in seen and (seen[key].value, seen[key].unit, seen[key].series) != (r.value, r.unit, r.series):
            return None
        seen[key] = r
    rows = list(seen.values())
    note = ('Data berikut adalah konteks pada wilayah dan tahun yang tercantum; '
            'bukan pengganti angka atau periode yang diminta dan tidak menentukan penilaian klaim.')
    if subset:
        note += ' Contoh provinsi dipilih menurut abjad dari katalog yang tersedia; bukan total atau gambaran seluruh Indonesia.'
    if 'gfw-tree-cover-loss-fire' in members:
        note += ' Kehilangan tutupan pohon akibat kebakaran berbeda dari seluruh luas karhutla, jumlah titik panas, dan penyebab kebakaran.'
    elif 'gfw-tree-cover-loss' in members:
        note += ' Kehilangan tutupan pohon tidak otomatis berarti deforestasi permanen dan tidak membuktikan penyebabnya.'
    expected = {(a, y) for a in query.areas for y in query.years}
    missing = sorted(expected - set(seen))
    if missing:
        note += ' Seri tidak lengkap; nilai yang tidak ditemukan tidak dianggap nol. Tidak dihitung total atau tren.'
    sources = []
    for r in rows:
        item = {'display': r.source_name or r.source, 'source': r.source_name or r.source,
                'title': r.title or r.indicator, 'url': r.source_url, 'download_url': r.download_url,
                'dataset_version': r.dataset_version, 'source_record_id': r.source_record_id}
        if item not in sources:
            sources.append(item)
    return {'role': 'related', 'reason': 'provincial_examples' if subset else 'related_series',
            'summary': 'Data pendamping yang tersedia: ' + rows[0].indicator + '.', 'context': note,
            'table': {'caption': rows[0].indicator, 'headers': ['Wilayah', 'Tahun', 'Nilai', 'Satuan'],
                      'rows': [[r.area, str(r.year), rounded(r.value), r.unit] for r in rows], 'calculations': []},
            'parsed': {'source_items': sources, 'download_records': [r.model_dump() for r in rows]}}


async def attach(result, question, intent, catalog, reference, retriever):
    """Append context after a verdict has been finalized; never change evidence/label."""
    parsed = result.get('parsed')
    if not parsed or parsed.get('gfw_context') or parsed.get('related_evidence'):
        return result
    # Successful statistical answers already have their full evidence table.
    if result.get('evidence') and not result.get('gaps') and not parsed.get('document_answer'):
        return result
    from presentation import render_answer
    groups = []
    # Existing numeric context may already contain the same observations.
    used = {r.get('id') for r in parsed.get('download_records', [])}
    last_family_with_data = None
    try:
        async with asyncio.timeout(15):
            for query, family, subset in plans(question, intent, catalog, reference):
                if subset and last_family_with_data == family['indicator_id']:
                    continue
                batch = await retriever.search(query)
                if batch.truncated:
                    continue
                group = group_records([r for r in batch.records if r.id not in used], query, family, subset)
                if group:
                    groups.append(group)
                    used.update(r['id'] for r in group['parsed']['download_records'])
                    last_family_with_data = family['indicator_id']
                if len(groups) >= 2:
                    break
    except Exception:
        # Optional context failure must not erase an already valid primary answer
        # or be described as data absence. Do not log credentials/response bodies.
        parsed['related_evidence_status'] = 'service_unavailable'
    if groups:
        parsed['related_evidence'] = groups
    if groups or parsed.get('related_evidence_status'):
        result['answer'] = parsed['raw_answer'] = render_answer(parsed)
    return result
