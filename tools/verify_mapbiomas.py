"""Audit every imported number against its physical original workbook cells."""
import json
import hashlib
from collections import defaultdict
from decimal import Decimal, localcontext
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from mapbiomas_data import DIRECTORY, SOURCE, VERSION, PROVINCE_NAMES, read_tables, island_area, numeric


def verify(directory):
    report = json.loads((directory / 'validation.json').read_text())
    original = DIRECTORY / 'raw/landcover-4.1.xlsx'
    if hashlib.sha256(original.read_bytes()).hexdigest() != report['source']['sha256']:
        raise ValueError('Original changed')
    target = directory / 'records.jsonl'
    if hashlib.sha256(target.read_bytes()).hexdigest() != report['records_sha256']:
        raise ValueError('Normalized records changed')
    if hashlib.sha256((directory / 'catalog.json').read_bytes()).hexdigest() != report['catalog_sha256']:
        raise ValueError('Catalog changed')
    tables = read_tables(original)
    lookups = {s: {r['row']: r for r in table['rows']} for s, table in tables.items()}
    audited, ids, counts = 0, set(), defaultdict(int)
    with localcontext() as ctx:
        ctx.prec = 60
        coverage, outgoing, incoming = {}, defaultdict(Decimal), defaultdict(Decimal)
        for r in tables['COVERAGE']['rows']:
            for c, (year,) in tables['COVERAGE']['periods'].items():
                coverage[r['province'], r['classes'][0], year] = r['values'][c]
        for r in tables['TRANSITION']['rows']:
            for c, (start, end) in tables['TRANSITION']['periods'].items():
                if r['values'][c] is None:
                    continue
                outgoing[r['province'], r['classes'][0], start, end] += r['values'][c]
                incoming[r['province'], r['classes'][1], start, end] += r['values'][c]
        diffs = []
        for sums, index in [(outgoing, 2), (incoming, 3)]:
            for key, value in sums.items():
                original_value = coverage.get((key[0], key[1], key[index]))
                if original_value is not None:
                    diffs.append(abs(value - original_value))
        if not diffs or max(diffs) > Decimal('.01'):
            raise ValueError('Source transition margins differ from cover areas')
        for line in target.open():
            row = json.loads(line)
            loc = row['source_locator']
            source = lookups[loc['sheet']]
            selected = [source[n] for n in loc['rows']]
            if len(loc['rows']) != len(set(loc['rows'])):
                raise ValueError('A cell has been counted twice')
            values = [r['values'][loc['column']] for r in selected]
            if None in values or sum(values, Decimal(0)) != Decimal(row['value']):
                raise ValueError('Imported value differs from original cells')
            if row['geographic_level'] == 'province' and {PROVINCE_NAMES.get(r['province'], r['province']) for r in selected} != {row['area']}:
                raise ValueError('Province scope mismatch')
            if row['geographic_level'] == 'island' and {island_area(r['island']) for r in selected} != {row['area']}:
                raise ValueError('Island scope mismatch')
            if row['geographic_level'] == 'national' and row['area'] != 'Indonesia':
                raise ValueError('National scope mismatch')
            if row['source'] != SOURCE or row['dataset_version'] != VERSION or row['source_sha256'] != report['source']['sha256']:
                raise ValueError('Source identity mismatch')
            periods = tables[loc['sheet']]['periods'][loc['column']]
            if row['year'] != periods[-1] or row['period_start'][:4] != str(periods[0]):
                raise ValueError('Observation period mismatch')
            if row['id'] in ids:
                raise ValueError('Duplicate ID')
            ids.add(row['id']); audited += 1
            counts[row['aggregation_kind']] += 1
        if audited != report['records']:
            raise ValueError('Record count mismatch')
    result = {'status': 'verified', 'records_checked_against_original_cells': audited,
              'source_transition_margin_checks': len(diffs), 'max_margin_difference_ha': str(max(diffs)),
              'record_kinds': dict(counts), 'source_sha256': report['source']['sha256']}
    (directory / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    directory = Path(sys.argv[1])
    print(json.dumps(verify(directory)))
