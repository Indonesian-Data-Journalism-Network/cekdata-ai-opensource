"""Read-only General retrieval from the configured Pinecone index.

Semantic search discovers tables; subsequent searches bind their metadata identity.
PDF cells are not statistical tables: their incomplete headers need a separate adapter.
No record is written back, and no corpus-wide completeness is inferred from top-k.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from flow import Evidence, MONTHS, SearchBatch, LlamaAI
from pinecone_client import PineconeClient, PineconeUnavailable
from unit_reading import read_unit

CONFIG_PATH = Path(__file__).resolve().parents[1] / '.local/pinecone-connection.json'
IDENTITY_FIELDS = ('source', 'dataset_id', 'series_label', 'unit', 'subgroup_label',
                   'subgroup_value', 'secondary_series', 'breakdown_label', 'breakdown_value')
ELIGIBLE = {'$and': [
    {'unit': {'$exists': True}}, {'source_url': {'$exists': True}},
    {'$or': [{'record_type': {'$eq': 'statistics_table_cell'}},
             {'record_type': {'$exists': False}}]},
]}
# A separate discovery window preserves the existing metadata-backed candidates.
FALLBACK_ELIGIBLE = {'$and': [
    {'$or': [{'unit': {'$exists': False}}, {'unit': {'$eq': ''}}]},
    *ELIGIBLE['$and'][1:],
]}


def load_config(path=CONFIG_PATH):
    if not path.exists():
        return None
    try:
        c = json.loads(path.read_text())
        if not c.get('enabled'):
            raise ValueError()
        if not c.get('embedding_model') or not isinstance(c.get('dimension'), int):
            raise ValueError()
        if not c.get('api_key') or not c.get('host'):
            raise ValueError()
        return c
    except (ValueError, TypeError, KeyError):
        raise PineconeUnavailable('Koneksi General belum selesai divalidasi.') from None


def public_url(value):
    if not isinstance(value, str):
        return ''
    try:
        u = urlsplit(value)
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            return ''
        if u.hostname in {'localhost', '127.0.0.1'} or not re.search(r'[a-z]', u.hostname, re.I):
            return ''
        if re.search(r'(?:api[_-]?key|access_token|authorization)=', u.query, re.I):
            return ''
        return value
    except ValueError:
        return ''


def identity(m):
    return {k: str(m.get(k) or '') for k in IDENTITY_FIELDS}


def map_record(record):
    """Return explicit, attributable numeric evidence, or a machine-readable reason."""
    m = record.get('metadata') or {}
    if m.get('doc_type') != 'atomic' or m.get('record_type') not in (None, 'statistics_table_cell'):
        return None, 'unsupported_schema'
    if m.get('synthetic') or re.search(r'(?i)(?:^|[\W_])(contoh|simulasi|dummy|fixture|example)(?:$|[\W_])',
                                     str(m.get('source_file', ''))):
        return None, 'example_data'
    url = public_url(m.get('source_url')) or public_url(m.get('source_page_url'))
    if not url:
        return None, 'missing_public_source'
    if m.get('value_status') not in (None, 'observed'):
        return None, 'not_observed'
    # Only explicit unit labels on this record may fill an absent unit.
    required = ('area_name', 'source', 'title', 'dataset_id', 'series_label')
    if any(not str(m.get(k) or '').strip() for k in required):
        return None, 'missing_metadata'
    unit, unit_reading, reason = read_unit(m)
    if reason:
        return None, reason
    try:
        y = Decimal(str(m.get('year', '')))
        if y != y.to_integral_value():
            raise ValueError()
        value = str(m.get('value', ''))
        if isinstance(m.get('value'), bool) or not Decimal(value).is_finite():
            raise ValueError()
        period = str(m.get('period') or '').strip()
        month = next((n for n in range(1, 13) if MONTHS[n].casefold() == period.casefold()), None)
        if not month and period.casefold() not in {'', 'tahunan', 'tahun', 'annual', str(int(y))}:
            return None, 'unsupported_period'
        area = str(m['area_name']).strip()
        if not re.search('[A-Za-z]', area):
            return None, 'invalid_area'
        level = str(m.get('area_level') or '').casefold()
        # Keep city/regency identity explicit. Do not trust province_context when
        # the original extractor has copied a district name into that field.
        if level in {'kabupaten', 'kota'} and not re.match(r'^(kabupaten|kota)\b', area, re.I):
            area = level.capitalize() + ' ' + area
        scope = str(m.get('breakdown_value') or '').strip()
        population = 'total' if scope.casefold() in {'', 'total', 'perkotaan + perdesaan'} else scope
        ident = identity(m)
        if unit_reading:
            ident['unit'] = unit
        iid = 'pinecone-' + hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:24]
        label = str(m['title'])
        series = str(m['series_label'])
        if series.casefold() != label.casefold():
            label += ' — ' + series
        for k in ('subgroup_value', 'secondary_series'):
            extra = str(m.get(k) or '').strip()
            if extra and extra.casefold() not in {'tidak ada', 'total'} and extra.casefold() not in label.casefold():
                label += ' — ' + extra
        if population != 'total' and population.casefold() not in label.casefold():
            label += ' — ' + population
        row = Evidence(id='pinecone:' + str(record['id']), indicator_id=iid, indicator=label,
            area=area, year=int(y), month=month, value=value, unit=unit,
            source=str(m['source']), title=str(m['title']), source_url=url,
            download_url=public_url(m.get('download_url')), population=population,
            population_label=scope, source_record_id=str(record['id']), provider='pinecone',
            geographic_level=level, definition=str(m.get('definition') or ''),
            method=str(m.get('method') or ''), source_locator={'dataset_id': str(m['dataset_id']),
                **({'unit_reading': unit_reading} if unit_reading else {})})
        return row, ''
    except (ValueError, TypeError, KeyError, InvalidOperation):
        return None, 'invalid_numeric_metadata'


def area_variants(areas):
    variants = []
    for area in areas:
        # Retrieval may be broad; final row matching preserves the requested level.
        variants.extend([area, area.upper(), area.title()])
        bare = re.sub(r'^(?:provinsi|kabupaten|kota|kab\.)\s+', '', area, flags=re.I)
        variants.extend([bare, bare.upper(), bare.title()])
    return list(dict.fromkeys(variants))


class PineconeEvidenceRetriever:
    def __init__(self, client, vector, *, limit=500):
        self.client, self.vector, self.limit = client, vector, limit
        self.catalog = []
        self.bindings = {}
        self.unit_bindings = {}
        self.rejected = Counter()
        self.discovery_truncated = False

    def discover(self, areas, month=None):
        # Scope discovery independently per requested area, avoiding one region
        # crowding another out of a shared top-k window.
        groups = [[a] for a in areas[:6]] or [[]]
        entries = {}
        for group in groups:
            clauses = [ELIGIBLE]
            if group:
                clauses.append({'area_name': {'$in': area_variants(group)}})
            if month:
                clauses.append({'period': {'$eq': MONTHS[month]}})
            matches = []
            for eligibility in (ELIGIBLE, FALLBACK_ELIGIBLE):
                batch = self.client.query(self.vector, top_k=200,
                    filters={'$and': [eligibility, *clauses[1:]]}).get('matches', [])
                self.discovery_truncated |= len(batch) >= 200
                matches.extend(batch)
            matches = list({m['id']: m for m in matches}.values())
            for match in matches:
                row, reason = map_record(match)
                if row is None:
                    self.rejected[reason] += 1
                    continue
                if month and row.month != month:
                    continue
                m = match['metadata']
                self.bindings[row.indicator_id] = identity(m)
                self.unit_bindings.setdefault(row.indicator_id, set()).add(str(m.get('unit') or ''))
                c = entries.setdefault(row.indicator_id, {'indicator_id': row.indicator_id,
                    'label': row.indicator, 'source': row.source, 'unit': row.unit,
                    'measure_label': ' — '.join(str(m.get(k) or '') for k in
                        ('series_label', 'subgroup_value', 'secondary_series')),
                    'units': [row.unit], 'member_ids': [row.indicator_id],
                    'definition': row.definition, 'areas': set(), 'years': set(),
                    'months': set(), 'geographic_levels': set(),
                    'populations': [row.population]})
                c['areas'].add(row.area)
                c['years'].add(row.year)
                if row.month:
                    c['months'].add(row.month)
                if row.geographic_level:
                    c['geographic_levels'].add(row.geographic_level)
        self.catalog = [{k: sorted(v) if isinstance(v, set) else v for k, v in c.items()} for c in entries.values()]
        return self.catalog

    async def search(self, query):
        return await asyncio.to_thread(self._search, query)

    def _search(self, query):
        if not query.indicator_ids or not query.areas:
            return SearchBatch()
        rows, truncated = {}, False
        for iid in query.indicator_ids:
            binding = self.bindings.get(iid)
            if not binding:
                continue
            units = self.unit_bindings.get(iid, {binding.get('unit', '')})
            unit_filters = [{'unit': {'$eq': u}} for u in sorted(units) if u]
            if '' in units:
                unit_filters.extend([{'unit': {'$exists': False}}, {'unit': {'$eq': ''}}])
            clauses = [*ELIGIBLE['$and'][1:], {'$or': unit_filters},
                       {'area_name': {'$in': area_variants(query.areas)}}]
            clauses.extend({k: {'$eq': v}} for k, v in binding.items() if v and k != 'unit')
            if query.years:
                clauses.append({'year': {'$in': query.years}})
            if query.sources:
                clauses.append({'source': {'$in': query.sources}})
            if query.month:
                clauses.append({'period': {'$eq': MONTHS[query.month]}})
            matches = self.client.query(self.vector, top_k=self.limit, filters={'$and': clauses}).get('matches', [])
            truncated |= len(matches) >= self.limit
            for match in matches:
                row, reason = map_record(match)
                if row is None:
                    self.rejected[reason] += 1
                    continue
                # Recheck after retrieval, including optional fields absent in
                # the metadata filter. Nearby but different series never qualify.
                if row.indicator_id != iid or row.population != query.population:
                    continue
                area = next((a for a in query.areas if a.casefold() == row.area.casefold()), None)
                if not area or (query.years and row.year not in query.years) or (query.month and row.month != query.month):
                    continue
                if query.sources and row.source not in query.sources:
                    continue
                rows[row.id] = row.model_copy(update={'area': area})
        return SearchBatch(records=list(rows.values()), truncated=truncated)


async def run(key, question, reference, config):
    from openai import AsyncOpenAI
    from llama_index.llms.openai import OpenAI
    import os
    from flow import CekDataWorkflow
    from pilot_data import PilotAI
    llm = OpenAI(model=os.environ.get('CEKDATA_MODEL', 'gpt-4.1-mini-2025-04-14'),
        api_key=key, temperature=0, max_tokens=2400, timeout=45, max_retries=0)
    preliminary = await LlamaAI(llm).understand(question, date.fromisoformat(reference), [])
    client = PineconeClient(config['api_key'], config['host'], config.get('namespace', ''))
    try:
        async with AsyncOpenAI(api_key=key, timeout=30, max_retries=0) as embedding:
            search_text = '\n'.join([question, *[m.concept for m in preliminary.requested_measures],
                                      *preliminary.search_terms])
            result = await embedding.embeddings.create(model=config['embedding_model'], input=search_text)
        vector = result.data[0].embedding
        if len(vector) != config['dimension']:
            raise PineconeUnavailable('Dimensi model pencarian tidak sesuai dengan index Pinecone.')
        retriever = PineconeEvidenceRetriever(client, vector)
        catalog = await asyncio.to_thread(retriever.discover, preliminary.areas, preliminary.month)
        result = await CekDataWorkflow(PilotAI(llm, catalog, initial_intent=preliminary), retriever, catalog).run(
            question=question, reference_date=reference)
        # Operational diagnostics contain no keys or raw prompts. Not sent by the web adapter.
        result['retrieval_backend'] = 'pinecone'
        result['retrieval_diagnostics'] = {'catalog_tables': len(catalog),
            'rejected': dict(retriever.rejected), 'discovery_limited': retriever.discovery_truncated}
        return result
    finally:
        client.close()
