"""Copy audited BPS observations to an isolated, content-addressed Qdrant collection.

Structured payload retrieval, as used for GFW. No invented vectors, embedding
calls, changes to production aliases, or replacement of other collections.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
import uuid

from qdrant_client import QdrantClient, models

from tools.bps.ingest import DEFAULT_DIR, BPSError, normalize, now, write_json

from tools.bps.observation import SCHEMA, standardize, province_reference


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def public_source(url):
    u = urlsplit(url)
    return (u.scheme == 'https' and (u.hostname == 'bps.go.id' or (u.hostname or '').endswith('.bps.go.id'))
            and not u.username and not u.password and u.hostname != 'webapi.bps.go.id'
            and '/key/' not in url and 'api_key' not in url.casefold())


def prepare(directory, year, end_year=None):
    """Reconcile source snapshots and SQLite before any Qdrant mutation."""
    directory = Path(directory)
    end_year = year if end_year is None else end_year
    if end_year < year:
        raise BPSError('Rentang tahun tidak valid.')
    db = sqlite3.connect(f'file:{directory / "bps.sqlite3"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    payloads = []
    try:
        db.execute('BEGIN')  # Consistent snapshot if the acquisition process is active.
        for imported in db.execute('SELECT * FROM imports ORDER BY domain, variable_id, period_id'):
            records = [json.loads(r['record']) for r in db.execute(
                'SELECT record FROM observations WHERE domain=? AND variable_id=? AND period_id=?',
                (imported['domain'], imported['variable_id'], imported['period_id']))]
            if not any(year <= int(r['year_label']) <= end_year for r in records):
                continue
            source_years = {int(r['year_label']) for r in records}
            if len(source_years) != 1:
                raise BPSError('Tahun tercampur di partisi sumber; impor ditahan.')
            source_year = next(iter(source_years))
            if not imported['source_verified'] or not public_source(imported['source_url']):
                raise BPSError('Tautan publik BPS belum diverifikasi; impor ditahan.')
            raw = (directory / 'raw' / (imported['sha256'] + '.json')).read_bytes()
            if hashlib.sha256(raw).hexdigest() != imported['sha256']:
                raise BPSError('Checksum sumber berubah; impor ditahan.')
            expected, _ = normalize(json.loads(raw, parse_float=str), imported['domain'],
                                    imported['variable_id'], imported['period_id'])
            if {r['id']: r for r in expected} != {r['id']: r for r in records}:
                raise BPSError('Isi SQLite berbeda dari respons BPS; impor ditahan.')
            for row in records:
                if row['status'] != 'observed':
                    raise BPSError('Ada sel yang belum terverifikasi; impor tahun ini ditahan.')
                indicator_id = 'bps-' + fingerprint([row['domain'], row['variable_id'],
                    row['derived_id'], row['unit']])[:24]
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'cekdata:bps:observation:' + row['id']))
                payloads.append({**row, 'id': point_id, 'source_record_id': row['id'],
                    'provider': 'bps_api', 'schema_version': SCHEMA, 'source': 'Badan Pusat Statistik',
                    'indicator_id': indicator_id, 'title': row['variable'], 'year': source_year,
                    'source_url': imported['source_url'], 'source_snapshot_sha256': imported['sha256'],
                    'retrieved_at': imported['retrieved_at'],
                    'vertical_key': row['vertical_label'].casefold(),
                    'period_text': row['subperiod_label']})
    finally:
        db.close()
    if not payloads:
        raise BPSError('Tidak ada data terverifikasi untuk tahun yang diminta.')
    provinces = province_reference(payloads)
    payloads = [standardize(p, provinces) for p in payloads]
    payloads.sort(key=lambda p: p['id'])
    if len({p['id'] for p in payloads}) != len(payloads):
        raise BPSError('ID sumber berulang; impor ditahan.')
    checksums = {p['id']: fingerprint(p) for p in payloads}
    snapshot = fingerprint(checksums)
    scope = str(year) if year == end_year else f'{year}_{end_year}'
    return payloads, checksums, f'cekdata_bps_{scope}_{snapshot[:14]}'


def verify(client, collection, expected, *, complete):
    seen = set()
    offset = None
    while True:
        points, offset = client.scroll(collection, limit=256, offset=offset,
                                       with_payload=True, with_vectors=False)
        for point in points:
            point_id = str(point.id)
            if point_id in seen or point_id not in expected or fingerprint(point.payload) != expected[point_id]:
                raise BPSError('Isi koleksi Qdrant tidak sesuai snapshot; proses dihentikan.')
            seen.add(point_id)
        if offset is None:
            break
    if complete and seen != set(expected):
        raise BPSError('Jumlah/ID Qdrant belum lengkap; koleksi belum dinyatakan selesai.')
    return len(seen)


def build_catalog(payloads):
    grouped = defaultdict(list)
    for p in payloads:
        grouped[p['indicator_id']].append(p)
    entries = []
    for iid, rows in sorted(grouped.items()):
        first = rows[0]
        entries.append({'indicator_id': iid, 'variable_id': first['variable_id'],
            'domain': first['domain'], 'title': first['title'], 'unit': first['unit'],
            'derived_id': first['derived_id'], 'derived_label': first['derived_label'],
            'vertical_axis': first['vertical_axis'],
            'vertical_members': sorted({(r['vertical_id'], r['area']) for r in rows}),
            'periods': sorted({(r['subperiod_id'], r['subperiod_label']) for r in rows}),
            'period_metadata': sorted({(r['temporal_basis'], r['month'] or 0, r['quarter'] or 0) for r in rows}),
            'populations': sorted({r['population'] for r in rows}),
            'years': sorted({r['year'] for r in rows}), 'source': first['source'],
            'source_url': first['source_url'], 'records': len(rows)})
    return entries


def run(directory, year, url, end_year=None, activate_trial=False):
    payloads, checksums, collection = prepare(directory, year, end_year)
    scope = str(year) if end_year is None or year == end_year else f'{year}-{end_year}'
    path = Path(directory) / f'qdrant-{scope}-manifest.json'
    manifest = {'schema': SCHEMA, 'collection': collection, 'year': year,
                'years': sorted({p['year'] for p in payloads}),
                'records': len(payloads), 'snapshot_sha256': fingerprint(checksums),
                'retrieval': 'structured payload filters; no vector embeddings',
                'chat_provider_activated': False, 'status': 'importing', 'started_at': now()}
    client = QdrantClient(url=url, timeout=90)
    try:
        if client.collection_exists(collection):
            if client.get_collection(collection).config.params.vectors != {}:
                raise BPSError('Konfigurasi koleksi berbeda; tidak ditimpa.')
            verify(client, collection, checksums, complete=False)
        else:
            client.create_collection(collection, vectors_config={}, on_disk_payload=True)
        pending_path = path.with_name(path.stem + '.pending.json')
        write_json(pending_path, manifest)
        for i in range(0, len(payloads), 256):
            batch = payloads[i:i + 256]
            client.upsert(collection, points=[models.PointStruct(id=p['id'], vector={}, payload=p)
                                              for p in batch], wait=True)
            if i % 4096 == 0:
                print(json.dumps({'imported': min(i + 256, len(payloads)), 'total': len(payloads)}), flush=True)
        for field, schema in [('year', 'integer'), ('indicator_id', 'keyword'), ('variable_id', 'keyword'),
                              ('vertical_id', 'keyword'), ('vertical_key', 'keyword'), ('derived_id', 'keyword'),
                              ('subperiod_id', 'keyword'), ('status', 'keyword'),
                              ('area_key','keyword'), ('area_code','keyword'), ('geographic_level','keyword'),
                              ('month','integer'), ('quarter','integer'), ('temporal_basis','keyword'),
                              ('source','keyword'), ('population','keyword'), ('usable','bool')]:
            client.create_payload_index(collection, field_name=field, field_schema=schema, wait=True)
        verified = verify(client, collection, checksums, complete=True)
        if client.count(collection, exact=True).count != len(payloads):
            raise BPSError('Jumlah Qdrant tidak cocok dengan sumber.')
        catalog = build_catalog(payloads)
        catalog_path = Path(directory) / (collection + '-catalog.json')
        write_json(catalog_path, catalog)
        manifest.update(status='verified', completed_at=now(), verified_payloads=verified,
                        source_tables=len({p['variable_id'] for p in payloads}), catalog_entries=len(catalog),
                        catalog_file=catalog_path.name)
        # Publish the verified snapshot pointer last. A failed import leaves the previous one usable.
        if path.exists():
            old = json.loads(path.read_text())
            if old.get('collection') != collection:
                write_json(path.with_name(old['collection'] + '-manifest.json'), old)
        write_json(path, manifest)
        write_json(Path(directory) / f'qdrant-{scope}-catalog.json', catalog)
        if activate_trial:
            write_json(Path(directory) / 'qdrant-current-manifest.json', manifest)
        pending_path.unlink(missing_ok=True)
        print(json.dumps(manifest, ensure_ascii=False), flush=True)
        return manifest
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--end-year', type=int, help='Sertakan semua tahun hingga tahun ini')
    parser.add_argument('--activate-trial', action='store_true', help='Gunakan snapshot untuk adapter uji lokal')
    parser.add_argument('--qdrant-url', default=os.environ.get('QDRANT_URL', 'http://127.0.0.1:6333'))
    args = parser.parse_args()
    try:
        run(args.directory, args.year, args.qdrant_url, args.end_year, args.activate_trial)
    except BPSError as exc:
        parser.exit(2, str(exc) + '\n')
