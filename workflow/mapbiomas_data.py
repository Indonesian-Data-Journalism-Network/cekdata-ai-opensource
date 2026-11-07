"""Import the official LANDY workbook without guessing absent cells or geography.

The workbook is the authority for coverage (currently 38 provinces). Website
descriptions mentioning districts must not promote province rows to districts.
Numbers are read as original OOXML decimals, not rounded spreadsheet floats.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import re
import uuid
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import httpx
from qdrant_client import QdrantClient, models
from settings import ROOT, QDRANT_URL

DIRECTORY = ROOT / 'data/mapbiomas'
SOURCE = 'MapBiomas Indonesia'
VERSION = '4.1'
SCHEMA = 'landy-statistics-v1'
PAGE = 'https://landy.mapbiomas.id/en/statistics'
DOWNLOAD = 'https://landy.mapbiomas.id/storage/files/statistics_lulc_indonesia_col4-1%20%281%29%20%281%29.xlsx'
METHOD = 'https://landy.mapbiomas.id/en/atbd'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
CLASSES = {
    3: ('forest-formation', 'formasi hutan'),
    5: ('mangrove', 'mangrove'),
    76: ('peat-swamp-forest', 'hutan rawa gambut'),
    13: ('other-natural-vegetation', 'vegetasi alami nonhutan'),
    40: ('rice-paddy', 'sawah'),
    35: ('oil-palm', 'sawit'),
    9: ('pulpwood-plantation', 'kebun kayu'),
    21: ('other-agriculture', 'pertanian lainnya'),
    30: ('mining-pit', 'lubang tambang'),
    24: ('urban-area', 'permukiman'),
    25: ('other-non-vegetation', 'nonvegetasi lainnya'),
    31: ('aquaculture', 'tambak'),
    33: ('water', 'sungai, danau, dan laut'),
}
FOREST = {3, 5, 76}
PROVINCE_NAMES = {'DKI Jakarta': 'Jakarta Raya',
                   'Daerah Istimewa Yogyakarta': 'Yogyakarta',
                   'Kepulauan Bangka Belitung': 'Bangka Belitung'}
NOTE = ('Klasifikasi tutupan/penggunaan lahan citra Landsat 30 m, Koleksi 4.1; '
        'cakupan tabel 38 provinsi sumber. Ini bukan luas kawasan hutan administratif '
        'atau batas izin konsesi. Tahun 2025–2026 belum tercakup dalam berkas ini.')


def xlsx_rows(path, sheet_name):
    """Yield (physical row number, column -> raw value), ignoring formatting-only cells."""
    with ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in item.iterfind('.//s:t', NS))
                       for item in ET.parse(archive.open('xl/sharedStrings.xml')).getroot()]
        rels = {r.attrib['Id']: r.attrib['Target'] for r in
                ET.parse(archive.open('xl/_rels/workbook.xml.rels')).getroot()}
        sheets = ET.parse(archive.open('xl/workbook.xml')).getroot().find('s:sheets', NS)
        sheet = next(s for s in sheets if s.attrib['name'] == sheet_name)
        target = rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        for _, row in ET.iterparse(archive.open(target), events=('end',)):
            if row.tag != '{' + NS['s'] + '}row':
                continue
            values = {}
            for cell in row.findall('s:c', NS):
                value = cell.find('s:v', NS)
                text = value.text if value is not None else None
                if cell.get('t') == 's' and text is not None:
                    text = strings[int(text)]
                elif cell.get('t') == 'inlineStr':
                    text = ''.join(t.text or '' for t in cell.iterfind('.//s:t', NS))
                if cell.get('t') == 'e':
                    raise ValueError(f'Spreadsheet error at {sheet_name}!{cell.get("r")}')
                if text not in (None, ''):
                    values[re.sub(r'\d+$', '', cell.get('r'))] = text
            if values:
                yield int(row.get('r')), values
            row.clear()


def numeric(value):
    if value is None:
        return None
    number = Decimal(value)
    if not number.is_finite() or number < 0:
        raise ValueError('Invalid land area')
    return number


def island_area(island):
    # Papua and Maluku are province names as well as island groups.
    return {'Papua': 'Wilayah Papua (6 provinsi)', 'Maluku': 'Kepulauan Maluku'}.get(island, island)


def read_tables(path):
    result = {}
    for sheet, pattern in [('COVERAGE', r'y(\d{4})'), ('TRANSITION', r'p(\d{4})_(\d{4})')]:
        rows = iter(xlsx_rows(path, sheet))
        header_number, header = next(rows)
        periods = {col: tuple(map(int, re.fullmatch(pattern, name).groups()))
                   for col, name in header.items() if re.fullmatch(pattern, name)}
        if sheet == 'COVERAGE' and sorted(p[0] for p in periods.values()) != list(range(1990, 2025)):
            raise ValueError('Unexpected coverage years')
        data, seen = [], set()
        for row_number, row in rows:
            if row.get('B') != 'Indonesia' or not row.get('C') or not row.get('D'):
                raise ValueError('Unrecognized geography; no publication')
            classes = (int(row['E']),) if sheet == 'COVERAGE' else (int(row['E']), int(row['F']))
            if not set(classes) <= CLASSES.keys():
                raise ValueError('Unrecognized land-cover class')
            key = (row['D'], classes)
            if key in seen:
                raise ValueError('Duplicate province/class row')
            seen.add(key)
            data.append({'row': row_number, 'island': row['C'], 'province': row['D'],
                         'classes': classes, 'values': {c: numeric(row.get(c)) for c in periods}})
        result[sheet] = {'periods': periods, 'rows': data}
    coverage_provinces = {(r['island'], r['province']) for r in result['COVERAGE']['rows']}
    transition_provinces = {(r['island'], r['province']) for r in result['TRANSITION']['rows']}
    if len(coverage_provinces) != 38 or coverage_provinces != transition_provinces:
        raise ValueError('Expected the same 38 provinces in both sheets')
    return result


def metric_options(classes, transition=False):
    """Hierarchical totals use only mutually exclusive observed leaf classes."""
    a = classes[0]
    if not transition:
        options = [(CLASSES[a][0], CLASSES[a][1])]
        if a in FOREST:
            options.append(('forest', 'hutan (formasi hutan, mangrove, dan hutan rawa gambut)'))
        return options
    b = classes[1]
    options = [(f'{CLASSES[a][0]}-to-{CLASSES[b][0]}',
                f'{CLASSES[a][1]} menjadi {CLASSES[b][1]}')]
    if a in FOREST and b not in FOREST:
        options.append(('forest-to-nonforest', 'hutan menjadi nonhutan'))
    if a not in FOREST and b in FOREST:
        options.append(('nonforest-to-forest', 'nonhutan menjadi hutan'))
    if a in FOREST and b in (35, 30, 9):
        options.append((f'forest-to-{CLASSES[b][0]}', f'hutan menjadi {CLASSES[b][1]}'))
    return options


def build_records(tables, sha):
    """Aggregate provinces to disjoint island groups and national coverage.

    Every sum retains the original cell locators. Missing explicit cells cancel
    an aggregate; absent class rows never generate synthetic zero observations.
    """
    with localcontext() as context:
        context.prec = 60
        for sheet, table in tables.items():
            transitions = sheet == 'TRANSITION'
            groups = {}
            for row in table['rows']:
                province = PROVINCE_NAMES.get(row['province'], row['province'])
                for column, period in table['periods'].items():
                    value = row['values'][column]
                    for metric, label in metric_options(row['classes'], transitions):
                        for level, area in [('province', province), ('island', island_area(row['island'])), ('national', 'Indonesia')]:
                            key = (level, area, metric, column)
                            entry = groups.setdefault(key, {'value': Decimal(0), 'rows': [], 'classes': set(),
                                'label': label, 'period': period, 'missing': False})
                            entry['rows'].append(row['row'])
                            entry['classes'].add(row['classes'])
                            if value is None:
                                entry['missing'] = True
                            else:
                                entry['value'] += value
            for (level, area, metric, column), entry in sorted(groups.items()):
                if entry['missing']:
                    continue
                period = entry['period']
                start, end = (period[0], period[-1])
                annual = not transitions or end == start + 1
                mode = 'annual-transition' if transitions and annual else 'transition' if transitions else 'extent'
                indicator_id = f'mapbiomas-{mode}-{metric}'
                label = ('Luas transisi ' + entry['label'] if transitions else 'Luas tutupan ' + entry['label'])
                if transitions and annual:
                    label += ' tahunan (tahun akhir transisi)'
                elif transitions:
                    label += ' antarperiode langsung'
                label += ' menurut provinsi, pulau dan nasional'
                definition = ('Luas kelas pada peta tutupan/penggunaan lahan tahunan MapBiomas Indonesia Koleksi 4.1.'
                    if not transitions else 'Luas yang diklasifikasikan dalam kelas awal dan kelas akhir pada dua peta MapBiomas Indonesia Koleksi 4.1. Bukan selisih luas bersih kedua kelas.')
                if transitions:
                    definition += (' Transisi tahunan diberi tahun akhir pasangan peta; akumulasi transisi dapat menghitung lokasi yang berubah kembali.' if annual else
                                   ' Angka transisi langsung antar-peta awal dan akhir, bukan penjumlahan transisi tahunan.')
                if metric == 'forest':
                    definition += ' Total menjumlahkan baris kelas formasi hutan, mangrove, dan hutan rawa gambut yang tercantum pada sumber; tidak termasuk kebun kayu.'
                if metric == 'oil-palm' and not transitions:
                    definition += ' Kelas sawit dipetakan dari pola tutupan perkebunan; bukan luas izin konsesi atau sensus seluruh petani sawit.'
                identity = f'mapbiomas:landy:{VERSION}:{sha[:12]}:{level}:{area}:{mode}:{metric}:{start}-{end}'
                yield {
                    'id': str(uuid.uuid5(uuid.NAMESPACE_URL, identity)), 'indicator_id': indicator_id,
                    'indicator': label, 'area': area, 'area_key': area.casefold(), 'year': end,
                    'period_text': f'{start}–{end}' if transitions and not annual else '',
                    'temporal_basis': 'land_transition' if transitions and not annual else 'annual',
                    'aggregation_kind': 'annual_flow' if transitions and annual else 'direct_transition' if transitions else 'annual_stock',
                    'period_start': f'{start}-01-01', 'period_end': f'{end}-12-31',
                    'value': str(entry['value']), 'unit': 'ha', 'source': SOURCE, 'source_name': SOURCE,
                    'title': f'{"Transisi" if transitions else "Tutupan"} lahan — MapBiomas Koleksi {VERSION}',
                    'source_url': PAGE, 'download_url': DOWNLOAD, 'methodology_url': METHOD,
                    'definition': definition, 'method': f'LANDY {VERSION}; Landsat 30 m; 38 provinsi sumber; {mode}.',
                    'source_note': definition + ' ' + NOTE, 'population': 'total', 'source_record_id': identity,
                    'provider': 'mapbiomas', 'dataset_version': VERSION, 'schema_version': SCHEMA,
                    'geographic_level': level, 'usable': True, 'data_status': 'annual_published',
                    'source_sha256': sha, 'source_locator': {'sheet': sheet, 'column': column, 'rows': entry['rows']},
                    'class_pairs': [list(c) for c in sorted(entry['classes'])],
                    'derived': len(entry['rows']) > 1, 'synthetic': False,
                }


def aliases(areas):
    result = {'sumatra': 'Sumatera', 'pulau sumatra': 'Sumatera', 'pulau sumatera': 'Sumatera',
              'pulau jawa': 'Jawa', 'pulau kalimantan': 'Kalimantan', 'pulau sulawesi': 'Sulawesi',
              'pulau papua': 'Wilayah Papua (6 provinsi)', 'kepulauan papua': 'Wilayah Papua (6 provinsi)',
              'bali dan nusa tenggara': 'Bali & Nusa Tenggara',
              'dki jakarta': 'Jakarta Raya', 'jakarta': 'Jakarta Raya',
              'daerah istimewa yogyakarta': 'Yogyakarta', 'kepulauan bangka belitung': 'Bangka Belitung'}
    return {a: v for a, v in result.items() if v in areas}


def archive():
    path = DIRECTORY / 'raw/landcover-4.1.xlsx'
    receipt = path.with_suffix('.receipt.json')
    if path.exists() and receipt.exists():
        info = json.loads(receipt.read_text())
        if info['url'] != DOWNLOAD or hashlib.sha256(path.read_bytes()).hexdigest() != info['sha256']:
            raise ValueError('Original workbook checksum or URL changed')
        return path, info
    response = httpx.get(DOWNLOAD, follow_redirects=True, timeout=180)
    response.raise_for_status()
    if not response.content.startswith(b'PK') or len(response.content) > 100 * 1024**2:
        raise ValueError('Expected bounded XLSX workbook')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    info = {'url': DOWNLOAD, 'source_url': PAGE, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'sha256': hashlib.sha256(response.content).hexdigest(), 'bytes': len(response.content)}
    receipt.write_text(json.dumps(info, indent=2) + '\n')
    return path, info


def build():
    path, info = archive()
    snapshot = hashlib.sha256((SCHEMA + info['sha256']).encode()).hexdigest()[:12]
    directory = DIRECTORY / snapshot
    directory.mkdir(parents=True, exist_ok=True)
    tables = read_tables(path)
    catalogs, counts, ids = {}, defaultdict(int), set()
    missing = []
    for sheet, table in tables.items():
        missing.extend({'sheet': sheet, 'row': r['row'], 'column': c}
                       for r in table['rows'] for c, v in r['values'].items() if v is None)
    target = directory / 'records.jsonl'
    with target.open('w') as output:
        for row in build_records(tables, info['sha256']):
            if row['id'] in ids:
                raise ValueError('Duplicate observation identity')
            ids.add(row['id'])
            counts[row['aggregation_kind']] += 1
            c = catalogs.setdefault(row['indicator_id'], {'indicator_id': row['indicator_id'],
                'label': row['indicator'], 'definition': row['definition'], 'source': SOURCE,
                'unit': 'ha', 'areas': set(), 'years': set(), 'populations': ['total']})
            c['areas'].add(row['area']); c['years'].add(row['year'])
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
    catalog = [{**c, 'areas': sorted(c['areas']), 'years': sorted(c['years']),
                'area_aliases': aliases(c['areas'])} for c in catalogs.values()]
    (directory / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    report = {'status': 'validated', 'schema_version': SCHEMA, 'dataset_version': VERSION,
              'collection': 'cekdata_mapbiomas_41_' + snapshot, 'records': len(ids),
              'record_kinds': dict(counts), 'catalog_entries': len(catalog),
              'province_count': 38, 'district_count': 0, 'island_groups': 7, 'years': [1990, 2024],
              'source': info, 'license': 'CC-BY-SA', 'license_url': 'https://landy.mapbiomas.id/en/termsofuse',
              'missing_cells_not_assumed_zero': missing,
              'source_rows': {s: len(t['rows']) for s, t in tables.items()},
              'records_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'catalog_sha256': hashlib.sha256((directory / 'catalog.json').read_bytes()).hexdigest()}
    (directory / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'source'}, ensure_ascii=False), flush=True)
    return directory, report


def publish(directory, report):
    """Resume an isolated collection; switch the small active pointer only after verification."""
    verification = json.loads((directory / 'verification.json').read_text())
    if (verification.get('status') != 'verified' or verification.get('records_checked_against_original_cells') != report['records']
            or verification.get('source_sha256') != report['source']['sha256']
            or hashlib.sha256((directory / 'records.jsonl').read_bytes()).hexdigest() != report['records_sha256']
            or hashlib.sha256((directory / 'catalog.json').read_bytes()).hexdigest() != report['catalog_sha256']):
        raise ValueError('Original-cell verification required before publication')
    client = QdrantClient(url=QDRANT_URL, timeout=120)
    collection = report['collection']
    try:
        if not client.collection_exists(collection):
            client.create_collection(collection, vectors_config={})
        batch, done = [], 0
        def flush():
            nonlocal done
            client.upsert(collection, points=[models.PointStruct(id=r['id'], vector={}, payload=r) for r in batch], wait=True)
            done += len(batch)
            if done % 10000 == 0:
                print('Published candidate', done, flush=True)
            batch.clear()
        for line in (directory / 'records.jsonl').open():
            batch.append(json.loads(line))
            if len(batch) == 250:
                flush()
        if batch:
            flush()
        for name, schema in [('indicator_id', 'keyword'), ('area_key', 'keyword'), ('source', 'keyword'),
                             ('year', 'integer'), ('population', 'keyword'), ('usable', 'bool')]:
            client.create_payload_index(collection, name, field_schema=schema, wait=True)
        if client.count(collection, exact=True).count != report['records']:
            raise ValueError('Qdrant count mismatch')
        # Compare the full database payload to the archived normalized stream.
        expected = {}
        def digest(payload):
            return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        for line in (directory / 'records.jsonl').open():
            row = json.loads(line); expected[row['id']] = digest(row)
        offset, verified = None, 0
        while True:
            points, offset = client.scroll(collection, offset=offset, limit=500, with_payload=True, with_vectors=False)
            for point in points:
                if expected.pop(str(point.id), None) != digest(point.payload):
                    raise ValueError('Qdrant payload mismatch')
                verified += 1
            if offset is None:
                break
        if expected or verified != report['records']:
            raise ValueError('Incomplete verification')
    finally:
        client.close()
    active = {**report, 'status': 'published', 'directory': str(directory.relative_to(DIRECTORY)),
              'verified_payloads': verified, 'published_at': datetime.now(timezone.utc).isoformat()}
    pointer = DIRECTORY / 'active.json'
    if pointer.exists():
        (DIRECTORY / 'previous-active.json').write_bytes(pointer.read_bytes())
    temporary = pointer.with_suffix('.tmp')
    temporary.write_text(json.dumps(active, ensure_ascii=False, indent=2) + '\n'); temporary.replace(pointer)
    print('ACTIVE', collection, verified, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    directory, report = build()
    if args.publish:
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from verify_mapbiomas import verify
        print(json.dumps(verify(directory)), flush=True)
        publish(directory, report)
