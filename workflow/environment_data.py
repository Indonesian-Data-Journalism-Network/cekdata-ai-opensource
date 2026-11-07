"""Compose independently published numeric sources at request time.

The application reloads flow between requests. An atomic MapBiomas pointer can
therefore add a source without restarting the server or losing its RAM key.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from flow import SearchBatch
from settings import ROOT

DIRECTORY = ROOT / 'data/mapbiomas'


LOSS_MEMBERS = {'gfw-tree-cover-loss', 'gfw-primary-forest-loss', 'gfw-tree-cover-loss-fire'}


def requested_loss_members(question):
    """Resolve loss categories from the original request, never its paraphrase.

    Return None for other measurements. Availability, place and year must not
    influence which concept is requested.
    """
    q = question.casefold()
    # These qualify a different measurement or spatial subset, not one of the
    # three loss families below. Leave them to their own catalogue matcher.
    if re.search(r'\b(?:emisi|karbon|mangrove|gambut|konsesi|perkebunan)\b|hutan tanaman', q):
        return None
    loss = re.search(r'kehilangan|\bhilang\b|tree[ -]cover loss|forest loss', q)
    forest = re.search(r'hutan|tutupan pohon|tree[ -]cover|forest', q)
    if not (loss and forest):
        return None
    requested = set()
    primary = re.search(r'hutan primer|primary forest', q)
    fire = re.search(r'kebakaran|karhutla|\bfire\b|fires', q)
    # Primary-forest loss caused by fire is an intersection, not two totals.
    if primary and fire and not re.search(r'bandingkan|perbandingan|masing-masing', q):
        return None
    if primary:
        requested.add('gfw-primary-forest-loss')
    if fire:
        requested.add('gfw-tree-cover-loss-fire')
    if not requested or re.search(r'(?:kehilangan tutupan pohon|tree[ -]cover loss)\s+total|kehilangan total', q):
        requested.add('gfw-tree-cover-loss')
    return requested


def preserve_loss_selection(selected, catalog, question, sources=()):
    """An exact requested loss family cannot be replaced by an available subset."""
    requested = requested_loss_members(question)
    if requested is None:
        return selected
    # This guard is for the GFW loss taxonomy; other explicitly named providers
    # retain their own concept matching rather than silently becoming GFW.
    named_map = re.search(r'\bmap\s*biomas\b', question, re.I)
    named_gfw = re.search(r'\bgfw\b|global (?:forest|nature) watch', question, re.I)
    if named_map and not named_gfw:
        return selected
    matches = [c for c in catalog if requested.intersection(c.get('member_ids', [c['indicator_id']]))
               and (not sources or c.get('source') in sources)]
    if not matches:
        return [c for c in selected if not LOSS_MEMBERS.intersection(c.get('member_ids', [c['indicator_id']]))]
    # A compound request may legitimately include another measure. Preserve it
    # only if the question asks for more than the loss measurement.
    compound = bool(re.search(r'\bluas (?:hutan|sawit|mangrove|gambut)\b|\b(?:emisi|penyerapan|neraca karbon|transisi)\b', question, re.I))
    other = [c for c in selected if not LOSS_MEMBERS.intersection(c.get('member_ids', [c['indicator_id']]))] if compound else []
    return list({c['indicator_id']: c for c in matches + other}.values())


def forest_measure_clarification(question, catalog):
    """Do not turn a broad damage concept into an arbitrary primary-loss subset."""
    if not any(LOSS_MEMBERS.intersection(c.get('member_ids', [c['indicator_id']])) for c in catalog):
        return ''
    if requested_loss_members(question) is not None:
        return ''
    if not re.search(r'\bdeforestasi\b|kerusakan hutan', question, re.I):
        return ''
    if re.search(r'dampak|penyebab|karena|akibat|kebijakan|pemerintah|laporan|masyarakat|konversi|menjadi|luas hutan', question, re.I):
        return ''
    return ('Untuk mengukur perubahan hutan ini, apakah yang dimaksud kehilangan tutupan pohon '
            'atau perubahan hutan menjadi nonhutan? Keduanya berbeda; kehilangan tutupan pohon '
            'tidak otomatis berarti deforestasi permanen.')


def active():
    pointer = DIRECTORY / 'active.json'
    if not pointer.exists():
        return {}
    config = json.loads(pointer.read_text())
    if config.get('status') != 'published' or config.get('schema_version') != 'landy-statistics-v1':
        return {}
    directory = (DIRECTORY / config['directory']).resolve()
    if directory.parent != DIRECTORY.resolve() or not (directory / 'catalog.json').is_file():
        raise ValueError('Invalid published MapBiomas directory')
    return {**config, 'catalog_path': directory / 'catalog.json'}


class EnvironmentRetriever:
    def __init__(self, primary, secondary, primary_ids, secondary_ids):
        self.primary, self.secondary = primary, secondary
        self.primary_ids, self.secondary_ids = set(primary_ids), set(secondary_ids)

    async def search(self, query):
        # Never send another provider's IDs through a collection-wide scan.
        records, truncated = {}, False
        for retriever, allowed in [(self.primary, self.primary_ids), (self.secondary, self.secondary_ids)]:
            ids = [i for i in query.indicator_ids if i in allowed]
            if not ids:
                continue
            batch = await retriever.search(query.model_copy(update={'indicator_ids': ids}))
            records.update((r.id, r) for r in batch.records)
            truncated |= batch.truncated
        return SearchBatch(records=list(records.values()), truncated=truncated)


def augment(ai, retriever, catalog):
    # Only the production Environment adapter, not General or scripted tests.
    if not hasattr(ai, 'llm') or not hasattr(retriever, 'client') or not any(
            str(m).startswith('gfw-') for c in catalog for m in c.get('member_ids', [])):
        return ai, retriever, catalog
    config = active()
    if not config:
        return ai, retriever, catalog
    from pilot_data import PilotAI, group_catalog
    from storage import QdrantEvidenceRetriever
    extra = group_catalog(json.loads(config['catalog_path'].read_text()))
    merged = catalog + extra
    secondary = QdrantEvidenceRetriever(retriever.client, config['collection'],
        usable_only=True, catalog=extra, limit=2000)
    combined = EnvironmentRetriever(retriever, secondary,
        [c['indicator_id'] for c in catalog], [c['indicator_id'] for c in extra])
    return PilotAI(ai.llm, merged), combined, merged


def prioritize(candidates, question):
    """Rank matching concepts, retaining the explicit source and measurement type."""
    q = question.casefold()
    named_map = 'mapbiomas' in q or 'map biomas' in q
    named_gfw = bool(re.search(r'\bgfw\b|global (?:forest|nature) watch', q))
    def is_map(c):
        return any(m.startswith('mapbiomas-') for m in c.get('member_ids', [c['indicator_id']]))
    if named_map and not named_gfw:
        candidates = [c for c in candidates if is_map(c)]
    elif named_gfw and not named_map:
        candidates = [c for c in candidates if not is_map(c)]
    transition = bool(re.search(r'\b(?:transisi|menjadi|beralih|dikonversi|konversi)\b|berubah (?:jadi|ke)', q))
    stock = bool(re.search(r'\bluas\b|tutupan lahan', q)) and not re.search(r'kehilangan|deforestasi', q)
    years = sorted(set(map(int, re.findall(r'\b(?:19|20)\d{2}\b', q))))
    direct = transition and len(years) == 2 and years[-1] - years[0] > 1 and not re.search(
        r'tahunan|setiap tahun|masing-masing|selama|rata[ -]rata|total|akumulasi|kumulatif', q)
    def score(c):
        members = c.get('member_ids', [c['indicator_id']])
        if transition:
            preferred = 'mapbiomas-transition-' if direct else 'mapbiomas-annual-transition-'
            path=re.search(r'\btransisi\s+(.+?)\s+(?:tahunan|antarperiode)\b',c.get('label',''),re.I)
            direction_match=path is not None and path[1].casefold() in q
            return (0 if any(m.startswith(preferred) for m in members) else 1,
                    0 if direction_match else 1)
        if stock:
            return (0 if any(m.startswith('mapbiomas-extent-') for m in members) else 1,0)
        return (0,0)
    return sorted(candidates, key=score)


def cross_source_limit(state):
    """Two regional aggregates cannot establish a pixel-level transition.

    Detect the measurement types from source records, not a place or commodity
    exception, and never describe a retrieved second source as unavailable.
    """
    rows=state.assessment.primary
    loss=[r for r in rows if r.source_record_id.startswith('gfw:gadm__tcl__')]
    transitions=[r for r in rows if r.source_record_id.startswith('mapbiomas:')
                 and r.aggregation_kind in ('annual_flow','direct_transition')]
    if not loss or not transitions:return ''
    return ('GFW mengukur kehilangan tutupan pohon, sedangkan MapBiomas memetakan perubahan kelas tutupan lahan. '
            'Angka agregat kedua sumber tidak membuktikan bahwa seluruh area kehilangan pada GFW '
            'merupakan area konversi yang dicatat MapBiomas; diperlukan pencocokan lokasi, periode, dan definisi.')


def prefer_requested_transitions(selected, question):
    """Do not add a component when the requested aggregate path is explicit."""
    def path(c):
        if c.get('source')!='MapBiomas Indonesia':return ''
        found=re.search(r'\btransisi\s+(.+?)\s+(?:tahunan|antarperiode)\b',c.get('label',''),re.I)
        return found[1].casefold() if found else ''
    q=re.sub(r'\b(?:jadi|ke)\b','menjadi',question.casefold())
    requested={path(c) for c in selected if path(c) and path(c) in q}
    if not requested or re.search(r'\b(?:rincian|rinci|komponen|pecahan|termasuk|masing-masing kelas)\b',q):return selected
    return [c for c in selected if not path(c) or path(c) in requested]


def source_context(records):
    """Short interpretation relevant to these observations, never a boilerplate wall."""
    rows = [r for r in records if r.source_record_id.startswith('mapbiomas:')]
    if not rows:
        return ''
    if any(r.source_record_id.startswith('gfw:') for r in records) and any(r.area in {'Papua', 'Papua Barat'} for r in rows):
        return 'Cakupan Papua/Papua Barat berbeda: MapBiomas memakai pembagian 38 provinsi, sedangkan seri GFW lokal memakai 34 provinsi sumber. Angka kedua sumber tidak dibandingkan langsung.'
    if any(r.temporal_basis == 'land_transition' for r in rows):
        return 'Transisi membandingkan kelas lahan pada peta awal dan akhir. Angkanya bukan penjumlahan perubahan setiap tahun di antaranya.'
    if any(r.aggregation_kind == 'annual_flow' for r in rows):
        return 'Tahun menunjukkan akhir pasangan peta: angka 2024 membandingkan peta 2023 dan 2024. Akumulasi tahunan dapat menghitung lokasi yang berubah kembali.'
    if any(':extent:forest:' in r.source_record_id for r in rows):
        return 'Hutan mencakup formasi hutan, mangrove, dan hutan rawa gambut; kebun kayu dihitung terpisah.'
    if any(':oil-palm:' in r.source_record_id for r in rows):
        return 'Angka menunjukkan tutupan sawit yang dipetakan dari citra, bukan luas izin konsesi atau sensus seluruh petani sawit.'
    return 'Angka menunjukkan luas kelas tutupan lahan yang dipetakan, bukan luas izin atau kawasan administratif.'


def gfw_boundary_context(records):
    """Show the boundary caveat only when the cited GFW metadata establishes it."""
    old = [r for r in records if r.source_record_id.startswith('gfw:')
           and r.area in {'Papua', 'Papua Barat'}
           and re.search(r'34 provinsi|sebelum pemekaran', r.method+' '+r.source_note, re.I)]
    if not old:
        return ''
    return ('Data Papua dan Papua Barat mengikuti batas wilayah sumber sebelum pemekaran. '
            'Angka untuk provinsi hasil pemekaran belum tersedia secara terpisah dalam seri ini.')


def explain_unavailable(result, state, catalog, config=None):
    """Explain a known local coverage limit without inventing an observation."""
    if state.assessment.primary:
        return result
    gfw = [c for c in catalog if any(str(m).startswith('gfw-')
           for m in c.get('member_ids', [c['indicator_id']]))]
    named_gfw = re.search(r'\bgfw\b|global (?:forest|nature) watch', state.question, re.I)
    selected_gfw = any(c['indicator_id'] in state.intent.indicator_ids for c in gfw)
    new_provinces = ('Papua Selatan', 'Papua Tengah', 'Papua Pegunungan', 'Papua Barat Daya')
    requested = [a for a in new_provinces if re.search(r'\b'+re.escape(a)+r'\b', state.question, re.I)]
    available = {a.casefold() for c in gfw for a in c.get('areas', [])}
    if gfw and (named_gfw or selected_gfw) and requested and all(a.casefold() not in available for a in requested):
        from presentation import render_answer
        note = ('Seri GFW lokal masih mengikuti batas wilayah sebelum pemekaran Papua. '
                'Data '+', '.join(requested)+' belum tersedia secara terpisah; angka wilayah lama tidak digunakan sebagai pengganti.')
        parsed = result['parsed']
        previous = parsed.get('konteks_penting', '')
        parsed['konteks_penting'] = '\n\n'.join(x for x in (previous, note) if x)
        result['answer'] = parsed['raw_answer'] = render_answer(parsed)
        return result
    selected = [c for c in catalog if c['indicator_id'] in state.intent.indicator_ids
                and c.get('source') == 'MapBiomas Indonesia']
    # The language model may decline every indicator when the requested
    # geography is absent. Explicitly naming the provider still permits a
    # factual explanation of its local catalog coverage, without numeric proof.
    if not selected and re.search(r'\bmap\s*biomas\b', state.question, re.I):
        selected = [c for c in catalog if c.get('source') == 'MapBiomas Indonesia']
    if not selected:
        return result
    config = active() if config is None else config
    if not config:
        return result
    years = {y for c in selected for y in c.get('years', [])}
    areas = {a.casefold() for c in selected for a in c.get('areas', [])}
    target = state.reference_date.year if state.intent.temporal == 'this_year' else state.intent.year
    notes = []
    if target and years and target > max(years):
        notes.append(f'Data MapBiomas Koleksi {config["dataset_version"]} yang terhubung baru tersedia hingga {max(years)}; data {target} belum tersedia dalam seri lokal ini.')
    missing = [a for a in state.intent.areas if a.casefold() not in areas]
    if missing and config.get('district_count') == 0 and any(re.search(
            r'\b(?:kabupaten|kota|kecamatan|desa|kelurahan)\b', a, re.I) for a in missing):
        notes.append(f'Tabel MapBiomas yang terhubung mencakup {config["province_count"]} provinsi serta agregat pulau dan nasional. Rincian kabupaten/kota belum tersedia dalam koleksi lokal ini.')
    if not notes:
        return result
    from mapbiomas_data import PAGE, DOWNLOAD, SOURCE, VERSION
    from presentation import render_answer
    parsed = result['parsed']
    detail = ' '.join(notes)
    parsed['jawaban_utama'] = detail
    if state.intent.kind == 'claim':
        parsed['alasan'] = detail + ' Data yang tersedia belum cukup untuk menilai klaim pada wilayah dan periode tersebut.'
        result['reason'] = parsed['alasan']
    if missing:
        parsed['konteks_penting'] = 'Angka untuk wilayah lain tidak digunakan sebagai pengganti wilayah yang diminta. Data yang belum tersedia tidak dianggap nol.'
    if not any(s.get('source') == SOURCE for s in parsed.get('source_items', [])):
        item = {'source': SOURCE, 'title': f'Tutupan dan transisi lahan — Koleksi {VERSION}',
                'display': f'{SOURCE} — Koleksi {VERSION}', 'url': PAGE, 'download_url': DOWNLOAD,
                'provider': 'mapbiomas', 'dataset_version': VERSION,
                'source_record_id': f'mapbiomas:landy:{VERSION}:catalog:coverage',
                'source_role': 'coverage_metadata'}
        parsed.setdefault('source_items', []).append(item)
        parsed['sumber'] = item['display']
        parsed['link_sumber'] = PAGE
        parsed['unduh_data'] = DOWNLOAD
    result['answer'] = parsed['raw_answer'] = render_answer(parsed)
    return result
