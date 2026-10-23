"""Read-only, bounded export from a legacy Pinecone serverless vector index."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import httpx

LIMIT = 1000
API_VERSION = '2025-10'
MAX_FETCH_URL_BYTES = 2000


class ExportError(Exception):
    pass


class FetchUrlTooLong(ExportError):
    pass


def namespace_count(stats):
    """Accept both API spellings; missing counts are unknown, never zero."""
    value = stats.get('vector_count', stats.get('vectorCount', stats.get('record_count')))
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return None


def exact_json(value):
    """Serialize JSON numbers without rounding metadata through binary floats."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ExportError('Sumber mengandung angka yang tidak valid.')
        return str(value)
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k, ensure_ascii=False) + ':' + exact_json(v) for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(exact_json(v) for v in value) + ']'
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class PineconeReader:
    def __init__(self, key, client=None):
        self.key = key
        self.client = client or httpx.Client(timeout=40, follow_redirects=False, trust_env=False)
        self.fetch_attempts = 0
        self.fetch_414s = 0

    def request(self, method, host, path, **kwargs):
        if not re.fullmatch(r'[a-zA-Z0-9.-]+\.pinecone\.io', host):
            raise ExportError('Alamat index bukan domain Pinecone yang diizinkan.')
        if (method, path) not in {('GET', '/indexes'), ('POST', '/describe_index_stats'),
                                  ('GET', '/vectors/list'), ('GET', '/vectors/fetch')}:
            raise ExportError('Operasi di luar cakupan ekspor baca.')
        try:
            response = self.client.request(method, f'https://{host}{path}',
                headers={'Api-Key': self.key, 'X-Pinecone-Api-Version': API_VERSION}, **kwargs)
        except httpx.HTTPError:
            raise ExportError('Koneksi Pinecone gagal. Data yang sudah diterima tetap disimpan sebagai ekspor parsial.') from None
        if response.status_code != 200:
            if response.status_code == 414 and path == '/vectors/fetch':
                self.fetch_414s += 1
                raise FetchUrlTooLong('Alamat pengambilan terlalu panjang.')
            messages = {401: 'API key Pinecone tidak diterima.', 403: 'Key belum memiliki izin baca untuk operasi ini.',
                        429: 'Kuota atau batas permintaan Pinecone tercapai. Ekspor dihentikan.',
                        404: 'Index atau endpoint tidak ditemukan.'}
            raise ExportError(messages.get(response.status_code, f'Pinecone mengembalikan HTTP {response.status_code}; ekspor dihentikan.'))
        try:
            result = json.loads(response.text, parse_float=Decimal)
            if not isinstance(result, dict):
                raise ValueError()
            return result, response.content
        except (ValueError, TypeError):
            raise ExportError('Respons Pinecone tidak dapat dibaca.') from None

    def indexes(self):
        data, _ = self.request('GET', 'api.pinecone.io', '/indexes')
        return data.get('indexes', [])

    def index(self, name):
        found = next((x for x in self.indexes() if x.get('name') == name), None)
        if not found:
            raise ExportError('Pilih index yang tersedia untuk API key ini.')
        if 'serverless' not in found.get('spec', {}) or not found.get('dimension'):
            raise ExportError('Pengambil ini mendukung index vektor serverless. Index ini perlu jalur ekspor lain.')
        return found

    def namespaces(self, index):
        data, _ = self.request('POST', index['host'], '/describe_index_stats', json={})
        return data.get('namespaces', {})

    def fetch_batches(self, host, namespace, ids):
        """Pack by encoded URL bytes, then split only a rejected 414 request.

        IDs are never truncated or replaced; children are disjoint subsets of
        their parent. Other failures stop immediately, without broad retries.
        """
        base = f'https://{host}/vectors/fetch'

        def params_for(batch):
            return [('namespace', namespace)] + [('ids', value) for value in batch]

        def fetch(batch):
            self.fetch_attempts += 1
            try:
                result, content = self.request('GET', host, '/vectors/fetch', params=params_for(batch))
                yield batch, result, content
            except FetchUrlTooLong:
                if len(batch) == 1:
                    raise ExportError('Satu ID masih melebihi batas panjang URL Pinecone. Ekspor parsial disimpan; ID tidak dipotong.') from None
                middle = len(batch) // 2
                yield from fetch(batch[:middle])
                yield from fetch(batch[middle:])

        batch = []
        for record_id in ids:
            candidate = batch + [record_id]
            size = len(str(httpx.URL(base, params=params_for(candidate))).encode('ascii'))
            if batch and size > MAX_FETCH_URL_BYTES:
                yield from fetch(batch)
                batch = []
            batch.append(record_id)
        if batch:
            yield from fetch(batch)

    def export(self, index, namespace, output_root, *, limit=LIMIT, exclude_ids=(), progress=None):
        if not 1 <= limit <= 10000:
            raise ExportError('Batas pengambilan harus antara 1 dan 10.000 record.')
        excluded = set(exclude_ids)
        namespaces = self.namespaces(index)
        if namespace not in namespaces:
            raise ExportError('Namespace tidak ditemukan atau kosong.')
        # Stats can lag writes. Listing, bounded by the requested limit, is the
        # authority on which IDs exist; a zero/missing count must not skip it.
        count = namespace_count(namespaces[namespace])
        target = min(limit, count) if count else limit
        max_lists = (target + len(excluded) + 99) // 100
        folder = Path(output_root) / datetime.now(timezone.utc).strftime(f'pinecone-{limit}-%Y%m%dT%H%M%S%fZ')
        folder.mkdir(parents=True, mode=0o700)
        raw = folder / 'raw'
        raw.mkdir(mode=0o700)
        manifest = {'status': 'running', 'index': index['name'], 'namespace': namespace,
                    'dimension': index['dimension'], 'metric': index.get('metric'),
                    'embedding_config': index.get('embed'), 'api_version': API_VERSION,
                    'limit': limit, 'target': target, 'excluded_previous_ids': len(excluded), 'records': 0, 'read_units': 0,
                    'response_bytes': 0, 'sampling': 'first unseen IDs in Pinecone sorted order; not random or representative',
                    'missing_ids': [], 'source_counts': {}, 'files': {}}
        seen, tokens, counts = set(), set(), Counter()
        token = None
        number_of_lists = 0
        number_of_fetches = 0
        try:
            with (folder / 'records.jsonl').open('x', encoding='utf-8') as stream:
                while len(seen) < target and number_of_lists < max_lists:
                    params = {'namespace': namespace, 'limit': min(100, target - len(seen))}
                    if token:
                        params['pagination_token'] = token
                    listing, content = self.request('GET', index['host'], '/vectors/list', params=params)
                    number_of_lists += 1
                    ids = [v['id'] for v in listing.get('vectors', []) if v['id'] not in seen and v['id'] not in excluded][:params['limit']]
                    ids = list(dict.fromkeys(ids))
                    manifest['read_units'] += listing.get('usage', {}).get('readUnits', listing.get('usage', {}).get('read_units', 0))
                    manifest['response_bytes'] += len(content)
                    seen.update(ids)
                    for batch_ids, batch, content in self.fetch_batches(index['host'], namespace, ids):
                        number_of_fetches += 1
                        # Each smaller response has its own file; none is overwritten.
                        (raw / f'fetch-{number_of_fetches:02}.json').write_bytes(content)
                        manifest['response_bytes'] += len(content)
                        manifest['read_units'] += batch.get('usage', {}).get('readUnits', batch.get('usage', {}).get('read_units', 0))
                        vectors = batch.get('vectors', {})
                        for record_id in batch_ids:
                            record = vectors.get(record_id)
                            if record is None:
                                manifest['missing_ids'].append(record_id)
                                continue
                            if record.get('id') != record_id or len(record.get('values', [])) != index['dimension']:
                                raise ExportError('ID atau dimensi vektor tidak cocok; ekspor parsial ditahan untuk pemeriksaan.')
                            stream.write(exact_json(record) + '\n')
                            manifest['records'] += 1
                            counts[str((record.get('metadata') or {}).get('source', '(tidak tercantum)'))] += 1
                        stream.flush()
                        if progress:
                            progress({'records': manifest['records'], 'target': target, 'read_units': float(manifest['read_units'])})
                    next_token = listing.get('pagination', {}).get('next')
                    if not next_token:
                        break
                    if next_token in tokens:
                        raise ExportError('Pinecone mengulang token halaman; pengambilan dihentikan.')
                    tokens.add(next_token)
                    token = next_token
            manifest['status'] = 'complete' if manifest['records'] == target else 'partial'
        except Exception as exc:
            manifest['status'] = 'partial'
            manifest['error'] = str(exc) if isinstance(exc, ExportError) else 'Ekspor berhenti karena kegagalan lokal.'
        finally:
            manifest['source_counts'] = dict(counts)
            manifest['list_requests'] = number_of_lists
            manifest['fetch_responses'] = number_of_fetches
            manifest['fetch_attempts'] = self.fetch_attempts
            manifest['fetch_414s'] = self.fetch_414s
            manifest['read_units_note'] = 'Usage reported on successful responses; rejected requests may not report usage.'
            for path in folder.rglob('*'):
                if path.is_file():
                    manifest['files'][str(path.relative_to(folder))] = hashlib.sha256(path.read_bytes()).hexdigest()
            (folder / 'manifest.json').write_text(exact_json(manifest) + '\n')
        return {'status': manifest['status'], 'records': manifest['records'], 'target': target,
                'folder': str(folder.resolve()), 'read_units': float(manifest['read_units']),
                'error': manifest.get('error', '')}

    def close(self):
        self.key = ''
        self.client.close()
