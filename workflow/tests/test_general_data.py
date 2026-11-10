"""General routing must preserve source, scope and native series identity."""
import asyncio
import unittest
from unittest.mock import patch
from datetime import date
from flow import Evidence, SearchQuery, SearchBatch, Intent
from general_data import GeneralRetriever, GeneralAI, StoreRetriever, available


def row(iid='local', **changes):
    data = dict(id='cell', indicator_id=iid, indicator='Ukuran uji', area='Wilayah uji',
                year=2026, value='12', unit='persen', source='BPS',
                source_url='https://example.org/table')
    return Evidence(**(data | changes))


class FakeRetriever:
    def __init__(self, rows=(), truncated=False, error=None):
        self.rows, self.truncated, self.error = rows, truncated, error
        self.queries = []

    async def search(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return SearchBatch(records=self.rows, truncated=self.truncated)


class GeneralTests(unittest.TestCase):
    def test_native_area_and_publisher_are_translated_without_changing_requested_level(self):
        base = FakeRetriever([row(area='Aceh Jaya', source='Badan Pusat Statistik')])
        catalog = [dict(source='Badan Pusat Statistik', areas=['Aceh Jaya', 'Bogor', 'Kota Bogor'],
                        area_aliases={'Kabupaten Bogor':'Bogor'})]
        adapter = StoreRetriever(base, catalog)
        q = SearchQuery(text='uji', areas=['Kabupaten Aceh Jaya', 'Kabupaten Bogor', 'Kota Bogor'], sources=['BPS'])
        result = asyncio.run(adapter.search(q))
        self.assertEqual(base.queries[0].areas, ['Aceh Jaya', 'Bogor', 'Kota Bogor'])
        self.assertEqual(base.queries[0].sources, ['Badan Pusat Statistik'])
        self.assertEqual(result.records[0].area, 'Kabupaten Aceh Jaya')
        self.assertEqual(result.records[0].source, 'BPS')

    def test_routes_only_selected_ids_preserving_filters_and_source_links(self):
        local, pine = FakeRetriever([row()]), FakeRetriever([row('pine', id='cloud')])
        retriever = GeneralRetriever({'local': ({'local'}, local), 'pine': ({'pine'}, pine)})
        q = SearchQuery(text='uji', indicator_ids=['local'], areas=['Wilayah uji'],
                        years=[2026], month=3, sources=['BPS'], population='total')
        result = asyncio.run(retriever.search(q))
        self.assertEqual(local.queries, [q])
        self.assertFalse(pine.queries)
        self.assertEqual(result.records[0].source_url, 'https://example.org/table')
        self.assertEqual(q.indicator_ids, ['local'])

    def test_two_stores_are_separate_series_and_exact_duplicates_collapse(self):
        a, duplicate, b = row(), row(id='other'), row('pine', id='cloud')
        r = GeneralRetriever({'local': ({'local'}, FakeRetriever([a, duplicate])),
                              'pine': ({'pine'}, FakeRetriever([b], truncated=True))})
        result = asyncio.run(r.search(SearchQuery(text='uji', indicator_ids=['local', 'pine'])))
        self.assertEqual(len(result.records), 2)
        self.assertNotEqual(result.records[0].series, result.records[1].series)
        self.assertEqual(result.records[0].duplicate_record_ids, ['other'])
        self.assertTrue(result.truncated)

    def test_failure_is_not_reported_as_absent_data(self):
        r = GeneralRetriever({'local': ({'local'}, FakeRetriever(error=RuntimeError('offline')))})
        with self.assertRaises(RuntimeError):
            asyncio.run(r.search(SearchQuery(text='uji', indicator_ids=['local'])))

    def test_local_only_can_advertise_general(self):
        with patch('general_data.CONFIG_PATH') as path, patch('general_data.local_manifest', return_value={'status':'verified'}):
            path.exists.return_value = False
            self.assertTrue(available())

    def test_shortlist_reserves_both_stores_and_preserves_initial_contract(self):
        entries = [dict(indicator_id=f'{store}-{n}', retrieval_store=store,
                        label='Ukuran kemiskinan', areas=['Indonesia'], source='BPS',
                        units=['persen'], populations=['total'])
                   for store, size in [('bps_local_qdrant', 80), ('pinecone', 5)] for n in range(size)]
        intent = Intent(kind='lookup', areas=['Indonesia'], year=2026)
        ai = GeneralAI(None, entries, initial_intent=intent)
        choices = ai.candidates('Ukuran kemiskinan Indonesia', ['Indonesia'])
        self.assertEqual(sum(c['retrieval_store']=='bps_local_qdrant' for c in choices), 20)
        self.assertEqual(sum(c['retrieval_store']=='pinecone' for c in choices), 5)
        self.assertEqual(ai.request_intent, intent)
        self.assertEqual(intent.indicator_ids, [])

    def test_complete_local_coverage_does_not_hide_cloud_history(self):
        entries = [dict(indicator_id=store, retrieval_store=store,
                        label='Persentase kemiskinan', areas=['Indonesia'], source='BPS', years=[2026],
                        units=['persen'], populations=['total']) for store in ['bps_local_qdrant', 'pinecone']]
        ai = GeneralAI(None, entries, initial_intent=Intent(kind='lookup', areas=['Indonesia'], year=2020))
        choices = ai.candidates('Persentase kemiskinan Indonesia', ['Indonesia'])
        # Pinecone discovery is only a sample, so its missing year is not proof
        # that the full table lacks the requested period.
        self.assertEqual([c['indicator_id'] for c in choices], ['pinecone'])
        self.assertEqual(ai.resolve_sources(['Badan Pusat Statistik']), ['BPS'])
        self.assertEqual(ai.stated_sources('Menurut Badan Pusat Statistik, berapa kemiskinan?'), ['BPS'])


if __name__ == '__main__':
    unittest.main()
