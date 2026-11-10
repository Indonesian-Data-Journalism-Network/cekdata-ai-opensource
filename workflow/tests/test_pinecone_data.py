import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from datetime import date

from flow import SearchQuery
from pinecone_client import PineconeUnavailable
from pinecone_data import map_record, PineconeEvidenceRetriever, load_config, public_url


def record(**overrides):
    m = dict(doc_type='atomic', record_type='statistics_table_cell', source='BPS',
        title='Penduduk miskin menurut kabupaten/kota', dataset_id='table-poverty',
        series_label='Persentase penduduk miskin', area_name='Wilayah A', area_level='kabupaten',
        year=2025, period='Tahunan', value='24.500001', unit='Persen', value_status='observed',
        source_url='https://www.bps.go.id/id/statistics-table/2/example',
        download_url='database_download/local.csv')
    m.update(overrides)
    return {'id': 'observation', 'metadata': m}


class MappingTests(unittest.TestCase):
    def test_percentage_alias_keeps_verdict_and_percentage_points_distinct(self):
        from flow import canonical_unit, assess, RequestState, Intent, Predicate
        row, _ = map_record(record(value='24.5'))
        for threshold, verdict in [('24.5', 'Benar'), ('100', 'Salah')]:
            intent = Intent(kind='claim', indicator_ids=[row.indicator_id], areas=[row.area],
                temporal='explicit', year=2025,
                predicate=Predicate(metric='value', operator='eq', threshold=threshold, unit='percent'))
            state = RequestState(question='Klaim angka', reference_date=date(2026, 11, 7),
                intent=intent, records=[row])
            self.assertEqual(assess(state).verdict, verdict)
        self.assertNotEqual(canonical_unit('percent'), canonical_unit('percentage points'))
        self.assertNotEqual(canonical_unit('orang'), canonical_unit('ribu orang'))

    def test_exact_numbers_sources_period_and_geography(self):
        row, reason = map_record(record(period='Maret'))
        self.assertEqual(reason, '')
        self.assertEqual(row.value, '24.500001')
        self.assertEqual(row.month, 3)
        self.assertEqual(row.area, 'Kabupaten Wilayah A')
        self.assertEqual(row.download_url, '')
        self.assertEqual(row.source_record_id, 'observation')

    def test_incomplete_pdf_example_missing_data_not_promoted(self):
        for overrides in [dict(record_type='publication_table_cell'), dict(source_file='000_contoh_tabel.txt'),
                          dict(synthetic=True), dict(value=None), dict(value='NaN'), dict(value=True),
                          dict(value_status='missing'), dict(unit=''), dict(source_url='local.csv'),
                          dict(year='2025.5'), dict(period='Triwulan I')]:
            with self.subTest(overrides=overrides):
                self.assertIsNone(map_record(record(**overrides))[0])

    def test_categories_and_city_regency_not_combined(self):
        total, _ = map_record(record())
        urban, _ = map_record(record(breakdown_value='Perkotaan'))
        rural, _ = map_record(record(breakdown_value='Perdesaan'))
        city, _ = map_record(record(area_level='kota'))
        self.assertEqual(len({total.indicator_id, urban.indicator_id, rural.indicator_id}), 3)
        self.assertEqual(urban.population, 'Perkotaan')
        self.assertNotEqual(total.area, city.area)
        secondary, _ = map_record(record(secondary_series='Perempuan'))
        self.assertNotEqual(total.indicator_id, secondary.indicator_id)
        self.assertIn('Perempuan', secondary.indicator)

    def test_public_source_does_not_expose_credentials_or_local_paths(self):
        for url in ['file:///private.csv', 'http://127.0.0.1/x', 'https://user:password@example.org',
                    'https://example.org?api_key=secret', 'https://localhost/x', 'javascript:alert(1)']:
            self.assertEqual(public_url(url), '')

    def test_config_not_silently_downgraded_to_pilot(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'config.json'
            self.assertIsNone(load_config(p))
            p.write_text(json.dumps({'enabled': False}))
            with self.assertRaises(PineconeUnavailable):
                load_config(p)


class RetrievalTests(unittest.TestCase):
    def test_explicit_month_does_not_discover_annual_proxy_table(self):
        class Client:
            def query(self, vector, **kwargs):
                self.filters = kwargs['filters']
                return {'matches': [record(), record(period='Maret', dataset_id='monthly-table')]}
        client = Client()
        retriever = PineconeEvidenceRetriever(client, [.1])
        catalog = retriever.discover(['Kabupaten Wilayah A'], month=3)
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]['months'], [3])
        self.assertIn('Maret', json.dumps(client.filters))
        self.assertEqual(retriever.bindings[catalog[0]['indicator_id']]['dataset_id'], 'monthly-table')

    def setup_retriever(self):
        class Client:
            calls = []
            matches = [record()]
            def query(self, vector, **kwargs):
                self.calls.append(kwargs)
                return {'matches': self.matches}
        client = Client()
        retriever = PineconeEvidenceRetriever(client, [.1], limit=10)
        catalog = retriever.discover(['Kabupaten Wilayah A'])
        self.assertEqual(len(catalog), 1)
        query = SearchQuery(text='data', indicator_ids=[catalog[0]['indicator_id']],
            areas=['Kabupaten Wilayah A'], years=[2025], population='total')
        return client, retriever, query

    def test_filter_and_postfilter_both_bind_scope(self):
        client, retriever, query = self.setup_retriever()
        wrong = [record(area_name='Wilayah B'), record(year=2024), record(breakdown_value='Perkotaan'),
                 record(secondary_series='Perempuan'), record(area_level='kota'), record(dataset_id='other')]
        client.matches = [record(), *wrong]
        result = asyncio.run(retriever.search(query))
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].value, '24.500001')
        body = json.dumps(client.calls[-1]['filters'])
        self.assertIn('table-poverty', body)
        self.assertIn('2025', body)
        self.assertIn('area_name', body)

    def test_full_window_marks_incomplete_and_failures_propagate(self):
        client, retriever, query = self.setup_retriever()
        client.matches = [record()]*10
        self.assertTrue(asyncio.run(retriever.search(query)).truncated)
        def fail(*a, **kw):
            raise PineconeUnavailable('Layanan belum merespons.')
        client.query = fail
        with self.assertRaises(PineconeUnavailable):
            asyncio.run(retriever.search(query))

    def test_empty_concept_never_scans_index(self):
        client, retriever, query = self.setup_retriever()
        before = len(client.calls)
        query.indicator_ids = []
        self.assertEqual(asyncio.run(retriever.search(query)).records, [])
        self.assertEqual(len(client.calls), before)


if __name__ == '__main__':
    unittest.main()
