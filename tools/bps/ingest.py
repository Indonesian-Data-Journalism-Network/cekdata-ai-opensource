"""Stage BPS dynamic tables in SQLite, preserving raw responses and every dimension.

No embedding, Qdrant write, or production provider switch occurs here.
Run from the repository: python -m tools.bps.ingest --help
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from tools.bps.client import BPSClient, BPSError

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / 'data/bps'
TOPICS = {
    'kemiskinan': r'kemiskinan|penduduk miskin',
    'ketenagakerjaan': r'pengangguran|angkatan kerja|penduduk.*bekerja|upah.*buruh',
    'pdrb': r'\bpdrb\b|produk domestik regional bruto',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def explicit_unit(variable):
    raw = str(variable.get('unit') or '').strip()
    if raw.casefold() not in {'', 'tidak ada satuan', '-', 'none'}:
        return raw, 'unit_field'
    # Some BPS tables put the unit only in the actual title. Preserve that origin;
    # never infer a scale from values, a neighboring table, or a topic keyword.
    candidates = [s.strip() for s in re.findall(r'\(([^()]*)\)', str(variable.get('label', '')))
                  if re.fullmatch(r'(?i)(?:(?:ribu|juta|miliar|milyar)\s+)?(?:jiwa|orang|rupiah|persen|%)(?:\s*/\s*kapita\s*/\s*bulan)?', s.strip())]
    if len(set(c.casefold() for c in candidates)) == 1:
        return candidates[0], 'explicit_unit_in_variable_title'
    return '', 'missing_or_ambiguous_unit'


class Archive:
    """Successful responses are reused; --refresh explicitly checks for revisions."""
    def __init__(self, directory, client, *, refresh=False, max_requests=250):
        self.root = Path(directory)
        self.client, self.refresh = client, refresh
        self.requests, self.max_requests = 0, max_requests
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, path, params=None):
        request = {'path': path, 'params': params or {}}
        name = digest(json.dumps(request, sort_keys=True).encode())
        manifest = self.root / 'requests' / (name + '.json')
        if manifest.exists() and not self.refresh:
            saved = json.loads(manifest.read_text())
            raw = (self.root / 'raw' / (saved['sha256'] + '.json')).read_bytes()
            if digest(raw) != saved['sha256']:
                raise BPSError('Arsip BPS berubah atau rusak; pengambilan dihentikan.')
            return json.loads(raw, parse_float=str), saved
        if self.requests >= self.max_requests:
            raise BPSError('Batas permintaan sesi tercapai. Jalankan kembali untuk melanjutkan dari cache.')
        self.requests += 1
        data, raw = self.client.get(path, params)
        checksum = digest(raw)
        rawpath = self.root / 'raw' / (checksum + '.json')
        rawpath.parent.mkdir(exist_ok=True)
        rawpath.write_bytes(raw)
        saved = {**request, 'sha256': checksum, 'retrieved_at': now()}
        write_json(manifest, saved)
        return data, saved

    def list(self, path, params=None):
        result, provenance = [], []
        for page in range(1, 1001):
            data, saved = self.get(path, {**(params or {}), 'page': page})
            provenance.append(saved)
            if data.get('data-availability') == 'not available':
                if page != 1:
                    raise BPSError('Katalog BPS tidak lengkap pada halaman lanjutan.')
                return [], provenance
            try:
                info, rows = data['data']
                if int(info['page']) != page or not isinstance(rows, list) or int(info['pages']) < page:
                    raise ValueError()
                result.extend(rows)
                if page == int(info['pages']):
                    if 'total' in info and len(result) != int(info['total']):
                        raise ValueError()
                    return result, provenance
            except (KeyError, ValueError, TypeError):
                raise BPSError('Halaman katalog BPS belum lengkap atau strukturnya berubah.') from None
        raise BPSError('Batas halaman katalog tercapai.')


def normalize(data, domain, variable_id, period_id, *, max_combinations=500000):
    """Decode all five dimensions, rejecting ambiguous concatenated source keys.

    Vertical values are deliberately NOT assumed to be geographic areas. Their
    original axis label is preserved for later reviewed geographic mapping.
    """
    axes = ('vervar', 'var', 'turvar', 'tahun', 'turtahun')
    contents = data.get('datacontent')
    if data.get('data-availability') != 'available':
        if data.get('data-availability') == 'not available':
            return [], {'source_cells': 0, 'observed': 0, 'held': 0, 'availability': 'not available'}
        raise BPSError('Status ketersediaan tabel BPS tidak dikenal.')
    if not isinstance(contents, dict):
        raise BPSError('Tabel BPS tidak memiliki datacontent yang valid.')
    dimensions = []
    combinations = 1
    for axis in axes:
        values = data.get(axis)
        if not isinstance(values, list) or not values:
            raise BPSError('Dimensi tabel BPS tidak lengkap.')
        ids = set()
        for item in values:
            if not isinstance(item, dict) or 'label' not in item or not re.fullmatch(r'\d+', str(item.get('val', ''))):
                raise BPSError('Label atau ID dimensi BPS tidak valid.')
            if str(item['val']) in ids:
                raise BPSError('ID dimensi BPS berulang.')
            ids.add(str(item['val']))
        dimensions.append(values)
        combinations *= len(values)
    if combinations > max_combinations:
        raise BPSError('Tabel terlalu besar untuk satu tahap; perlu mempersempit periode/dimensi.')
    if {str(x['val']) for x in data['var']} != {str(variable_id)} or {str(x['val']) for x in data['tahun']} != {str(period_id)}:
        raise BPSError('Variabel/periode respons berbeda dari permintaan.')
    decoded = {}
    for items in itertools.product(*dimensions):
        code = ''.join(str(x['val']) for x in items)
        if code not in contents:
            continue  # Missing cells are never manufactured as zeros.
        if code in decoded:
            raise BPSError('Kode sel BPS ambigu; tidak ditebak menjadi satu kombinasi dimensi.')
        decoded[code] = items
    if set(contents) != set(decoded):
        raise BPSError('Sebagian kode sel tidak dapat dipetakan; tabel belum diimpor.')
    rows = []
    for code, items in decoded.items():
        region, variable, derived, year, subperiod = items
        raw_value = contents[code]
        status, value = 'observed', None
        if raw_value is None or str(raw_value).strip() in {'', '-', '...', 'NA', 'N/A'}:
            status = 'missing'
        elif isinstance(raw_value, bool) or not re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', str(raw_value).strip()):
            status = 'unparsed_value'
        else:
            try:
                number = Decimal(str(raw_value).strip())
                if not number.is_finite():
                    raise InvalidOperation()
                value = str(raw_value).strip()
            except InvalidOperation:
                status = 'unparsed_value'
        unit, unit_origin = explicit_unit(variable)
        if status == 'observed' and not unit:
            status = 'missing_unit'
        rows.append({
            'id': digest(json.dumps([domain, *[str(x['val']) for x in items]]).encode()),
            'domain': domain, 'variable_id': str(variable_id), 'period_id': str(period_id),
            'source_cell': code, 'variable': variable['label'], 'unit': unit,
            'unit_raw': variable.get('unit'), 'unit_origin': unit_origin,
            'vertical_axis': data.get('labelvervar', ''), 'vertical_id': str(region['val']),
            'vertical_label': region['label'], 'derived_id': str(derived['val']),
            'derived_label': derived['label'], 'year_label': year['label'],
            'subperiod_id': str(subperiod['val']), 'subperiod_label': subperiod['label'],
            'value': value, 'raw_value': raw_value, 'status': status,
            'definition': variable.get('def', ''), 'notes': variable.get('note', ''),
            'metadata': data.get('metadata'),
        })
    return rows, {'source_cells': len(contents), 'observed': sum(r['status'] == 'observed' for r in rows),
                  'held': sum(r['status'] != 'observed' for r in rows), 'availability': 'available'}


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS imports (
            domain TEXT, variable_id TEXT, period_id TEXT, sha256 TEXT,
            retrieved_at TEXT, source_url TEXT, source_verified INTEGER,
            summary TEXT, PRIMARY KEY(domain, variable_id, period_id));
        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY, domain TEXT, variable_id TEXT, period_id TEXT,
            vertical_id TEXT, derived_id TEXT, subperiod_id TEXT,
            value_text TEXT, status TEXT, record TEXT);
        CREATE INDEX IF NOT EXISTS observation_scope ON observations
            (domain, variable_id, vertical_id, period_id, derived_id, subperiod_id);
        ''')

    def put(self, domain, variable_id, period_id, rows, summary, saved, source_url, verified):
        with self.db:
            self.db.execute('DELETE FROM observations WHERE domain=? AND variable_id=? AND period_id=?',
                            (domain, str(variable_id), str(period_id)))
            self.db.executemany('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)', [
                (r['id'], domain, str(variable_id), str(period_id), r['vertical_id'],
                 r['derived_id'], r['subperiod_id'], r['value'], r['status'],
                 json.dumps(r, ensure_ascii=False)) for r in rows])
            self.db.execute('INSERT OR REPLACE INTO imports VALUES (?,?,?,?,?,?,?,?)',
                            (domain, str(variable_id), str(period_id), saved['sha256'],
                             saved['retrieved_at'], source_url, int(verified), json.dumps(summary)))

    def close(self):
        self.db.close()


def discover(archive, domains, start, end, subjects=None):
    domain_rows, _ = archive.list('domain/type/all')
    registry = {str(d['domain_id']): d for d in domain_rows}
    # Central tables can contain all provinces: domain is publisher, NOT row geography.
    plan = {'created_at': now(), 'start_year': start, 'end_year': end, 'priority_year': end,
            'status': 'candidates_require_review', 'tables': []}
    for domain in domains:
        if not re.fullmatch(r'\d{4}', domain) or domain not in registry:
            raise BPSError('Domain tidak ditemukan dalam katalog resmi BPS.')
        variables = []
        for subject in subjects or [None]:
            subset, _ = archive.list('list/model/var/domain/' + domain,
                                    {'subject': subject} if subject is not None else {})
            variables.extend(subset)
        variables = list({str(v['var_id']): v for v in variables}.values())
        for v in variables:
            title = str(v.get('title', ''))
            topics = [t for t, pattern in TOPICS.items() if re.search(pattern, title, re.I)]
            if not topics:
                continue
            plan['tables'].append({'domain': domain, 'domain_name': registry[domain]['domain_name'],
                'variable_id': str(v['var_id']), 'title': title, 'unit': v.get('unit', ''),
                'definition': v.get('def', ''), 'notes': v.get('notes', ''), 'topics': topics,
                'selected': False, 'source_url': '', 'source_verified': False,
                'catalog_metadata': v})
        print(json.dumps({'domain': domain, 'catalog_variables': len(variables),
                          'candidate_tables': sum(t['domain'] == domain for t in plan['tables'])}))
    return plan


def ingest_plan(archive, store, plan):
    from urllib.parse import urlsplit
    if not any(t.get('selected') is True for t in plan['tables']):
        raise BPSError('Belum ada tabel yang dipilih dalam rencana pengambilan.')
    results = []
    for table in plan['tables']:
        if table.get('selected') is not True:
            continue
        domain, variable = str(table['domain']), str(table['variable_id'])
        if not re.fullmatch(r'\d{4}', domain) or not variable.isdigit():
            raise BPSError('ID tabel pada rencana tidak valid.')
        url = str(table.get('source_url') or '')
        if url:
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or not (parsed.hostname == 'bps.go.id' or (parsed.hostname or '').endswith('.bps.go.id'))
                    or parsed.username or parsed.password or parsed.hostname == 'webapi.bps.go.id' or '/key/' in url):
                raise BPSError('Sumber harus berupa halaman publik BPS tanpa API key.')
        if table.get('source_verified') and not url:
            raise BPSError('Sumber belum memiliki tautan publik.')
        periods, _ = archive.list('list/model/th/domain/' + domain, {'var': variable})
        valid_periods = [p for p in periods if re.fullmatch(r'\d{4}', str(p.get('th', '')))]
        # Use the source's period labels, not publication dates or arithmetic on IDs.
        priority = int(plan.get('priority_year', plan['end_year']))
        valid_periods.sort(key=lambda p: (int(p['th']) == priority, int(p['th'])), reverse=True)
        available_years = sorted({int(p['th']) for p in valid_periods})
        if priority not in available_years:
            result = {'domain': domain, 'variable_id': variable, 'year': str(priority),
                      'availability': 'not listed in API period catalog',
                      'available_years': available_years, 'source_cells': 0,
                      'observed': 0, 'held': 0}
            results.append(result)
            print(json.dumps(result))
        for period in valid_periods:
            label = str(period.get('th', ''))
            if not re.fullmatch(r'\d{4}', label):
                continue
            if not plan['start_year'] <= int(label) <= plan['end_year']:
                continue
            pid = str(period['th_id'])
            data, saved = archive.get(f'list/model/data/domain/{domain}/var/{variable}/th/{pid}')
            rows, summary = normalize(data, domain, variable, pid)
            if any(str(r['year_label']) != label for r in rows):
                raise BPSError('Label tahun respons berbeda dari katalog periode BPS.')
            summary['subperiods'] = sorted({str(r['subperiod_label']) for r in rows})
            summary['year_label'] = label
            store.put(domain, variable, pid, rows, summary, saved, url, bool(table.get('source_verified')))
            result = {'domain': domain, 'variable_id': variable, 'year': label, **summary,
                      'source_verified': bool(table.get('source_verified'))}
            results.append(result)
            print(json.dumps(result))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['discover', 'import'])
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--domains', nargs='+', default=['0000'])
    parser.add_argument('--subjects', type=int, nargs='+', help='ID subjek dari katalog resmi untuk mempersempit pengambilan')
    parser.add_argument('--start-year', type=int, default=2021)
    parser.add_argument('--end-year', type=int, default=datetime.now().year)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--max-requests', type=int, default=250)
    args = parser.parse_args()
    config = ROOT / '.local/bps-connection.json'
    key = os.environ.get('BPS_API_KEY', '')
    if not key and config.exists():
        key = json.loads(config.read_text()).get('api_key', '')
    if not key:
        parser.exit(2, 'Sambungkan API key melalui formulir lokal http://127.0.0.1:8783/.\n')
    if args.action == 'import' and not args.plan:
        parser.error('import memerlukan --plan dari katalog yang telah ditinjau.')
    client = BPSClient(key)
    archive = Archive(args.directory, client, refresh=args.refresh, max_requests=args.max_requests)
    try:
        if args.action == 'discover':
            plan = discover(archive, args.domains, args.start_year, args.end_year, args.subjects)
            path = args.plan or args.directory / 'candidate-plan.json'
            if path.exists():
                raise BPSError('Rencana sudah ada; pilih --plan baru agar tinjauan lama tidak tertimpa.')
            write_json(path, plan)
            print('Katalog calon tabel disimpan:', path)
        else:
            store = Store(args.directory / 'bps.sqlite3')
            try:
                results = ingest_plan(archive, store, json.loads(args.plan.read_text()))
                write_json(args.directory / 'last-import.json', {'completed_at': now(), 'results': results})
            finally:
                store.close()
    except BPSError as exc:
        parser.exit(2, str(exc) + '\n')
    finally:
        client.close()


if __name__ == '__main__':
    main()
