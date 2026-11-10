"""One request contract and indicator selection for General's two stores.

Tables retain their native identities: proximity in search is not permission to
join observations, replace units, or sum overlapping BPS releases.
"""
import asyncio
import json
import os
from contextlib import ExitStack
from datetime import date

from llama_index.core import PromptTemplate
from flow import CekDataWorkflow, LlamaAI, SearchBatch, distinct_evidence
from pilot_data import PilotAI, MATCH_PROMPT
from bps_local import ROOT, snapshot_manifest, catalog_from_snapshot, BPSLocalRetriever
from pinecone_data import CONFIG_PATH, load_config, PineconeEvidenceRetriever
from pinecone_client import PineconeClient, PineconeUnavailable

DIRECTORY = ROOT / 'data/bps'


def publisher(name):
    return 'BPS' if name.casefold() in {'bps', 'badan pusat statistik'} else name


class StoreRetriever:
    """Translate shared geography/publisher labels to this store's native labels."""
    def __init__(self, retriever, catalog):
        from geography import Geography
        self.retriever = retriever
        self.geography = Geography(catalog)
        self.sources = {e['source'] for e in catalog}
        self.aliases = {a.casefold(): target for e in catalog for a, target in e.get('area_aliases', {}).items()}

    async def search(self, query):
        names = {self.aliases.get(a.casefold()) or self.geography.canonical(a) or a: a for a in query.areas}
        sources = [s for s in self.sources if any(publisher(s) == publisher(q) for q in query.sources)]
        # Preserve an unrecognized publisher filter; never expand it to all sources.
        translated = query.model_copy(update={'areas': list(names), 'sources': sources or query.sources})
        batch = await self.retriever.search(translated)
        return SearchBatch(records=[r.model_copy(update={'area': names.get(r.area, r.area),
                                                       'source': publisher(r.source)}) for r in batch.records],
                           truncated=batch.truncated)


def local_manifest(directory=DIRECTORY):
    # Absence is allowed. A present but invalid snapshot must not silently become
    # a claim that BPS has no data.
    if not any((directory / name).exists() for name in
               ('qdrant-current-manifest.json', 'qdrant-2026-manifest.json')):
        return None
    return snapshot_manifest(directory)


def available():
    return CONFIG_PATH.exists() or local_manifest() is not None


class GeneralAI(PilotAI):
    selection_prompt = PromptTemplate(MATCH_PROMPT.template + '''
Katalog General berasal dari penyimpanan pinecone dan bps_local_qdrant.
Keduanya dapat memuat tabel BPS yang sama; penyimpanan bukan penerbit berbeda.
Untuk satu konsep dengan lingkup yang sama, pilih satu tabel yang paling tepat
dan mencakup wilayah, kategori, satuan, serta periode yang diminta. Jika setara
dan cakupannya cukup, utamakan bps_local_qdrant. Jangan memilih dua salinan
tabel hanya karena berasal dari penyimpanan berbeda. Gunakan Pinecone untuk
konsep atau lingkup yang tidak dicakup tabel lokal. Bila memang membutuhkan
beberapa tabel, pertahankan seri masing-masing; jangan menyambung periode atau
menjumlahkan tabel berbeda tanpa identitas seri yang terbukti setara.
''')

    def resolve_sources(self, sources):
        return super().resolve_sources([publisher(s) for s in sources])

    def stated_sources(self, question):
        names = super().stated_sources(question)
        if 'badan pusat statistik' in question.casefold():
            names.append('BPS')
        return list(dict.fromkeys(names))

    def candidates(self, text, areas=()):
        # Reserve candidate space for both stores, so thousands of local
        # categories cannot crowd out the broader Pinecone catalog (or reverse).
        groups = {}
        for entry in self.catalog:
            groups.setdefault(entry['retrieval_store'], []).append(entry)
        choices = []
        quota = max(1, 40 // max(1, len(groups)))
        for entries in groups.values():
            selector = PilotAI(self.llm, entries, initial_intent=self.request_intent)
            ranked = selector.candidates(text, areas)
            if entries[0]['retrieval_store'] == 'bps_local_qdrant':
                # Local catalogs describe the complete imported snapshot. Unlike
                # Pinecone's bounded discovery sample, absence here is known.
                intent = self.request_intent
                years = set(intent.requested_years or ([intent.year] if intent.year else [])) if intent else set()
                if intent and intent.requested_periods:
                    years = {p.year for p in intent.requested_periods}
                native = [selector.area_aliases.get(a.casefold()) or selector.geography.canonical(a) or a for a in areas]
                ranked = [e for e in ranked if
                          (not years or not e.get('years') or years.intersection(e['years'])) and
                          (not native or any(a.casefold() in {v.casefold() for v in e['areas']} for a in native))]
            choices.extend(ranked[:quota])
        return choices


class GeneralRetriever:
    def __init__(self, routes):
        self.routes = routes
        self.counts = {}

    async def search(self, query):
        rows, truncated = [], False
        for store, (ids, retriever) in self.routes.items():
            selected = [iid for iid in query.indicator_ids if iid in ids]
            if not selected:
                continue
            batch = await retriever.search(query.model_copy(update={'indicator_ids': selected}))
            self.counts[store] = self.counts.get(store, 0) + len(batch.records)
            rows.extend(batch.records)
            truncated |= batch.truncated
        # Only identical evidence is deduplicated. Conflicting values and
        # different native table/series IDs remain visible to the assessor.
        return SearchBatch(records=distinct_evidence(rows), truncated=truncated)


async def run(key, question, reference):
    from openai import AsyncOpenAI
    from llama_index.llms.openai import OpenAI
    from qdrant_client import QdrantClient
    config, manifest = load_config(), local_manifest()
    llm = OpenAI(model=os.environ.get('CEKDATA_MODEL', 'gpt-4.1-mini-2025-04-14'),
                 api_key=key, temperature=0, max_tokens=2400, timeout=45, max_retries=0)
    preliminary = await LlamaAI(llm).understand(question, date.fromisoformat(reference), [])
    catalog, routes = [], {}
    with ExitStack() as resources:
        if manifest:
            entries = catalog_from_snapshot(json.loads((DIRECTORY / manifest['catalog_file']).read_text()))
            client = QdrantClient(url=os.environ.get('QDRANT_URL', 'http://127.0.0.1:6333'), timeout=15)
            resources.callback(client.close)
            store = 'bps_local_qdrant'
            catalog.extend({**e, 'source': publisher(e['source']), 'retrieval_store': store} for e in entries)
            routes[store] = ({e['indicator_id'] for e in entries},
                            StoreRetriever(BPSLocalRetriever(client, manifest['collection'], entries, question), entries))
        if config:
            client = PineconeClient(config['api_key'], config['host'], config.get('namespace', ''))
            resources.callback(client.close)
            async with AsyncOpenAI(api_key=key, timeout=30, max_retries=0) as embedding:
                search_text = '\n'.join([question, *[m.concept for m in preliminary.requested_measures],
                                          *preliminary.search_terms])
                result = await embedding.embeddings.create(model=config['embedding_model'], input=search_text)
            vector = result.data[0].embedding
            if len(vector) != config['dimension']:
                raise PineconeUnavailable('Dimensi model pencarian tidak sesuai dengan index Pinecone.')
            retriever = PineconeEvidenceRetriever(client, vector)
            entries = await asyncio.to_thread(retriever.discover, preliminary.areas, preliminary.month)
            store = 'pinecone'
            catalog.extend({**e, 'source': publisher(e['source']), 'retrieval_store': store} for e in entries)
            routes[store] = ({e['indicator_id'] for e in entries}, StoreRetriever(retriever, entries))
        if not routes:
            raise RuntimeError('Belum ada sumber General yang terhubung.')
        retriever = GeneralRetriever(routes)
        ai = GeneralAI(llm, catalog, initial_intent=preliminary)
        result = await CekDataWorkflow(ai, retriever, catalog).run(question=question, reference_date=reference)
        result['retrieval_backend'] = 'general_combined'
        result['retrieval_diagnostics'] = {'stores': list(routes), 'record_counts': retriever.counts,
                                           'local_collection': manifest['collection'] if manifest else None}
        result['selection_diagnostics'] = getattr(ai, 'last_selection', {})
        return result
