"""Bounded read-only Qdrant payload retrieval for the local workflow pilot."""
from __future__ import annotations

import asyncio
from qdrant_client import QdrantClient, models
from flow import Evidence, MONTHS, SearchBatch, SearchQuery


class QdrantEvidenceRetriever:
    def __init__(self, client: QdrantClient, collection: str, *, legacy=False, limit=200, usable_only=False, catalog=()):
        self.client, self.collection, self.legacy, self.limit = client, collection, legacy, limit
        self.usable_only = usable_only
        self.families = {c['indicator_id']: c for c in catalog}
        self.member_families = {m: c for c in catalog for m in c.get('member_ids', [])}

    async def search(self, query: SearchQuery) -> SearchBatch:
        return await asyncio.to_thread(self._search, query)

    def _search(self, query):
        # An unbound concept must not trigger a whole-collection scan.
        if not query.indicator_ids or not query.areas:
            return SearchBatch()
        fields = {
            'dataset_id' if self.legacy else 'indicator_id': [m for i in query.indicator_ids
                for m in self.families.get(i, {}).get('member_ids', [i])],
            'area_name' if self.legacy else 'area': query.areas,
        }
        if self.usable_only:
            fields.pop('area')
            fields['area_key'] = [area.casefold() for area in query.areas]
        if query.sources:
            fields['source'] = query.sources
        if query.years:
            fields['year'] = query.years
        must = [models.FieldCondition(key=k, match=models.MatchAny(any=v)) for k, v in fields.items()]
        if self.usable_only:
            must.append(models.FieldCondition(key='usable', match=models.MatchValue(value=True)))
        if query.month:
            must.append(models.FieldCondition(key='period' if self.legacy else 'month',
                match=models.MatchValue(value=MONTHS[query.month] if self.legacy else query.month)))
        if self.legacy:
            population = 'Perkotaan + Perdesaan' if query.population == 'total' else query.population
            must.append(models.FieldCondition(key='breakdown_value', match=models.MatchValue(value=population)))
        else:
            must.append(models.FieldCondition(key='population', match=models.MatchValue(value=query.population)))
        points, next_offset = self.client.scroll(collection_name=self.collection,
            scroll_filter=models.Filter(must=must), limit=self.limit,
            with_payload=True, with_vectors=False)
        rows = []
        for point in points:
            p = point.payload or {}
            if self.legacy:
                metadata = p.get('metadata') or {}
                month = MONTHS.index(p['period']) if p.get('period') in MONTHS[1:] else None
                row = Evidence(id=str(point.id), indicator_id=p['dataset_id'], indicator=p['series_label'],
                    area=p['area_name'], year=p['year'], month=month, value=str(p['value']), unit=p['unit'],
                    source=p['source'], title=p.get('title', ''),
                    source_name=p.get('source_name') or metadata.get('source_name') or '',
                    province_context=p.get('province_context') or metadata.get('province_context') or '',
                    source_url=p.get('source_url') or metadata.get('source_url') or '',
                    download_url=p.get('download_url') or next(iter(reversed(p.get('download_urls') or [])), ''),
                    definition=p.get('definition', ''), method=p.get('method', ''),
                    population='total' if p.get('breakdown_value') == 'Perkotaan + Perdesaan' else p.get('breakdown_value', ''),
                    population_label=p.get('breakdown_value', ''),
                    source_record_id=p.get('pinecone_id') or str(point.id))
            else:
                if p.get('provider') == 'gfw':
                    from gfw_sources import public_evidence
                    p = public_evidence(p)
                row = Evidence.model_validate(p)
                family = self.member_families.get(row.indicator_id)
                if family:
                    row = row.model_copy(update={'indicator_id':family['indicator_id'], 'indicator':family['label']})
                if self.usable_only:
                    # Normalize capitalization only, preserving requested geographic scope.
                    area = next((a for a in query.areas if a.casefold() == row.area.casefold()), row.area)
                    row = row.model_copy(update={'area': area})
            rows.append(row)
        return SearchBatch(records=rows, truncated=next_offset is not None)


def make_catalog(records: list[Evidence]) -> list[dict]:
    catalog = {}
    for r in records:
        key = (r.indicator_id, r.source, r.definition, r.unit)
        catalog[key] = {'indicator_id': r.indicator_id, 'label': r.indicator,
                        'source': r.source, 'definition': r.definition, 'unit': r.unit}
    return list(catalog.values())
