"""Read-only adapter for audited BPS Qdrant snapshots, also used by General."""
import asyncio
import json
import os
import re
from pathlib import Path

from qdrant_client import QdrantClient, models
from flow import Evidence, SearchBatch, CekDataWorkflow
from pilot_data import PilotAI

ROOT = Path(__file__).resolve().parents[1]


def catalog_from_snapshot(entries):
    catalog = []
    for e in entries:
        category = e['derived_label']
        label = e.get('label') or e['title'] + (' — ' + category if category.casefold() not in {'tidak ada', ''} else '')
        periods = e['period_metadata']
        aliases = {}
        if 'kabupaten' in e.get('vertical_axis', '').casefold():
            # BPS administrative codes distinguish regencies (01–70) and cities
            # (71–99); commodity/category codes must never enter this mapping.
            for code, area in e['vertical_members']:
                code = str(code)
                if re.fullmatch(r'\d{4}', code) and int(code[-2:]) > 0:
                    prefix = 'Kabupaten' if int(code[-2:]) < 71 else 'Kota'
                    if not re.match(r'^(?:Kabupaten|Kab\.|Kota)\s', area, re.I):
                        aliases[f'{prefix} {area}'] = area
        catalog.append({
            **{k: v for k, v in e.items() if k not in {'vertical_members', 'periods'}},
            'label': label, 'measure_label': label,
            'member_ids': [e['indicator_id']], 'areas': [v[1] for v in e['vertical_members']],
            'area_aliases': aliases,
            'months': sorted({m for basis, m, q in periods if basis == 'month'}),
            'temporal_bases': sorted({b for b, m, q in periods}), 'period_labels': [p[1] for p in e['periods']],
            'units': [e['unit']], 'populations': e['populations'], 'definition': ''})
    return catalog


def evidence(payload, area):
    if payload.get('schema_version') != 'cekdata-statistical-observation-v2':
        raise ValueError('Snapshot BPS harus memakai format observasi standar v2.')
    # Preserve standardized periods and categories; no source-label reinterpretation.
    fields = {k: v for k, v in payload.items() if k in Evidence.model_fields}
    fields['area'] = area
    return Evidence(**fields)


class BPSLocalRetriever:
    def __init__(self, client, collection, catalog, question):
        self.client, self.collection = client, collection
        self.allowed = {e['indicator_id'] for e in catalog}

    async def search(self, query):
        return await asyncio.to_thread(self._search, query)

    def _search(self, query):
        ids = [i for i in query.indicator_ids if i in self.allowed]
        if not ids or not query.areas:
            return SearchBatch()
        fields = {'indicator_id': ids, 'area_key': [a.casefold() for a in query.areas],
                  'population': [query.population]}
        if query.years:
            fields['year'] = query.years
        if query.sources:
            fields['source'] = query.sources
        conditions = [models.FieldCondition(key=k, match=models.MatchAny(any=v)) for k, v in fields.items()]
        conditions.append(models.FieldCondition(key='usable',match=models.MatchValue(value=True)))
        points, offset = self.client.scroll(self.collection, scroll_filter=models.Filter(must=conditions),
                                             limit=2000, with_payload=True, with_vectors=False)
        rows = []
        for point in points:
            p = point.payload
            if not p.get('usable'):
                continue
            from period_contract import matches
            candidate = evidence(p, p['area'])
            if query.periods:
                if not matches(candidate, query.periods):
                    continue
            elif query.month is not None and (candidate.quarter is not None or candidate.month != query.month):
                continue
            area = next((a for a in query.areas if a.casefold() == p['area_key']), None)
            if area is None:
                continue
            rows.append(evidence(p, area))
        return SearchBatch(records=rows, truncated=offset is not None)


def snapshot_manifest(directory, year=None):
    directory = Path(directory)
    path = directory / (f'qdrant-{year}-manifest.json' if year is not None else 'qdrant-current-manifest.json')
    if year is None and not path.exists():
        path = directory / 'qdrant-2026-manifest.json'
    manifest = json.loads(path.read_text())
    if manifest.get('status') != 'verified':
        raise ValueError('Snapshot BPS belum terverifikasi.')
    return manifest


async def run(key, question, reference, directory=ROOT / 'data/bps', year=None):
    from llama_index.llms.openai import OpenAI
    directory = Path(directory)
    manifest = snapshot_manifest(directory, year)
    catalog = catalog_from_snapshot(json.loads((directory / manifest.get('catalog_file', f'qdrant-{year}-catalog.json')).read_text()))
    llm = OpenAI(model=os.environ.get('CEKDATA_MODEL', 'gpt-4.1-mini-2025-04-14'),
                 api_key=key, temperature=0, max_tokens=2400, timeout=45, max_retries=0)
    client = QdrantClient(url=os.environ.get('QDRANT_URL', 'http://127.0.0.1:6333'), timeout=60)
    try:
        retriever = BPSLocalRetriever(client, manifest['collection'], catalog, question)
        ai = PilotAI(llm, catalog)
        result = await CekDataWorkflow(ai, retriever, catalog).run(question=question, reference_date=reference)
        result['retrieval_backend'] = 'bps_local_qdrant_trial'
        result['retrieval_collection'] = manifest['collection']
        result['selection_diagnostics'] = getattr(ai, 'last_selection', {})
        return result
    finally:
        client.close()
