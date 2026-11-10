"""Audit staged BPS values against archived responses and export a requested year."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3

from tools.bps.ingest import DEFAULT_DIR, now, write_json


def audit(directory, year):
    directory = Path(directory)
    db = sqlite3.connect(f'file:{directory / "bps.sqlite3"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    report = {'checked_at': now(), 'priority_year': year, 'counts_by_year': {},
              'tables': [], 'checked_cells': 0, 'errors': [],
              'scope': 'Source-to-local value integrity, not end-to-end answer accuracy'}
    csv_path = directory / f'bps-{year}.csv'
    tmp_path = csv_path.with_suffix('.csv.tmp')
    fields = ['variable_id', 'indicator', 'vertical_axis', 'vertical_id', 'area_or_category',
              'year', 'period', 'category', 'value', 'unit', 'unit_origin', 'source_notes', 'source_url', 'retrieved_at']
    try:
        with tmp_path.open('w', encoding='utf-8-sig', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
            for imported in db.execute('SELECT * FROM imports ORDER BY variable_id, period_id'):
                raw = (directory / 'raw' / (imported['sha256'] + '.json')).read_bytes()
                if hashlib.sha256(raw).hexdigest() != imported['sha256']:
                    report['errors'].append({'variable_id': imported['variable_id'], 'error': 'raw_checksum'})
                    continue
                source = json.loads(raw, parse_float=str)
                records = [json.loads(r['record']) for r in db.execute(
                    'SELECT record FROM observations WHERE domain=? AND variable_id=? AND period_id=?',
                    (imported['domain'], imported['variable_id'], imported['period_id']))]
                source_cells = source.get('datacontent', {})
                if len(records) != len(source_cells) or {r['source_cell'] for r in records} != set(source_cells):
                    report['errors'].append({'variable_id': imported['variable_id'], 'error': 'source_cell_coverage'})
                for record in records:
                    report['checked_cells'] += 1
                    y = str(record['year_label'])
                    report['counts_by_year'][y] = report['counts_by_year'].get(y, 0) + 1
                    if record['raw_value'] != source_cells.get(record['source_cell']):
                        report['errors'].append({'id': record['id'], 'error': 'raw_value'})
                    if record['status'] == 'observed':
                        if Decimal(record['value']) != Decimal(str(source_cells[record['source_cell']])):
                            report['errors'].append({'id': record['id'], 'error': 'numeric_value'})
                        if not record['unit'] or record['unit'].casefold() == 'tidak ada satuan':
                            report['errors'].append({'id': record['id'], 'error': 'unit_missing'})
                    if y == str(year) and record['status'] == 'observed':
                        writer.writerow({'variable_id': record['variable_id'], 'indicator': record['variable'],
                            'vertical_axis': record['vertical_axis'], 'vertical_id': record['vertical_id'],
                            'area_or_category': record['vertical_label'], 'year': y,
                            'period': record['subperiod_label'], 'category': record['derived_label'],
                            'value': record['value'], 'unit': record['unit'], 'unit_origin': record['unit_origin'],
                            'source_notes': record['notes'],
                            'source_url': imported['source_url'], 'retrieved_at': imported['retrieved_at']})
                if records:
                    report['tables'].append({'domain': imported['domain'], 'variable_id': imported['variable_id'],
                        'title': records[0]['variable'], 'year': records[0]['year_label'],
                        'source_cells': len(records), 'observed': sum(r['status'] == 'observed' for r in records),
                        'held': sum(r['status'] != 'observed' for r in records),
                        'vertical_axis': records[0]['vertical_axis'],
                        'vertical_members': len({r['vertical_id'] for r in records}),
                        'subperiods': sorted({r['subperiod_label'] for r in records}),
                        'categories': len({r['derived_id'] for r in records}),
                        'source_notes': records[0]['notes'],
                        'source_url': imported['source_url'], 'source_verified': bool(imported['source_verified'])})
        if report['errors']:
            tmp_path.unlink(missing_ok=True)
        else:
            tmp_path.replace(csv_path)
            report['csv'] = csv_path.name
        write_json(directory / 'audit.json', report)
        return report
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--year', type=int, required=True)
    args = parser.parse_args()
    result = audit(args.directory, args.year)
    print(json.dumps({k: result[k] for k in ('checked_cells', 'counts_by_year', 'errors')}, ensure_ascii=False))
    raise SystemExit(1 if result['errors'] else 0)
