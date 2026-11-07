import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock
from zipfile import ZipFile

from flow import Evidence, Intent, SearchQuery, SearchBatch, RequestState, Analysis, assess, render
from environment_data import EnvironmentRetriever, prioritize, source_context, explain_unavailable
from mapbiomas_data import build_records, numeric, xlsx_rows, island_area


def table_rows():
    return {'COVERAGE': {'periods': {'J': (2023,), 'K': (2024,)}, 'rows': [
        {'row': 2, 'island': 'Sumatera', 'province': 'Aceh', 'classes': (3,), 'values': {'J': Decimal('10.123456789123'), 'K': Decimal('8')}},
        {'row': 3, 'island': 'Sumatera', 'province': 'Aceh', 'classes': (5,), 'values': {'J': Decimal('2'), 'K': Decimal('2')}},
        {'row': 4, 'island': 'Sumatera', 'province': 'Riau', 'classes': (3,), 'values': {'J': Decimal('20'), 'K': Decimal('20')}},
    ]}, 'TRANSITION': {'periods': {'M': (2023, 2024), 'N': (1990, 2024)}, 'rows': [
        {'row': 2, 'island': 'Sumatera', 'province': 'Aceh', 'classes': (3, 35), 'values': {'M': Decimal('1.23456789'), 'N': Decimal('6')}},
        {'row': 3, 'island': 'Sumatera', 'province': 'Aceh', 'classes': (5, 35), 'values': {'M': Decimal('0'), 'N': Decimal('1')}},
    ]}}


class MapbiomasTests(unittest.TestCase):
    def records(self):
        return list(build_records(table_rows(), '0' * 64))

    def test_original_decimal_text_blank_and_explicit_zero(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.xlsx'
            with ZipFile(path, 'w') as z:
                z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" r:id="r1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
                z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="A2"><v>54.10000000000001</v></c><c r="B2"><v>0</v></c><c r="C2"/></row></sheetData></worksheet>')
            _, r = list(xlsx_rows(path, 'Data'))[0]
            self.assertEqual(r['A'], '54.10000000000001')
            self.assertEqual(numeric(r['B']), Decimal(0))
            self.assertIsNone(numeric(r.get('C')))
        for value in ['-1', 'NaN', 'Infinity']:
            with self.assertRaises(ValueError): numeric(value)

    def test_disjoint_geography_totals_and_source_cell_provenance(self):
        rows = self.records()
        forests = [r for r in rows if r['indicator_id'] == 'mapbiomas-extent-forest' and r['year'] == 2023]
        national = next(r for r in forests if r['area'] == 'Indonesia')
        self.assertEqual(Decimal(national['value']), Decimal('32.123456789123'))
        self.assertEqual(national['source_locator'], {'sheet': 'COVERAGE', 'column': 'J', 'rows': [2, 3, 4]})
        self.assertFalse(any(r['geographic_level'] == 'district' for r in rows))
        self.assertFalse(any(r['indicator_id'] == 'mapbiomas-extent-peat-swamp-forest' for r in rows))
        self.assertEqual(len(rows), len({r['id'] for r in rows}))
        self.assertNotEqual(island_area('Papua'), 'Papua')
        self.assertNotEqual(island_area('Maluku'), 'Maluku')

    def test_missing_cell_suppresses_sum_instead_of_becoming_zero(self):
        t = table_rows(); t['COVERAGE']['rows'][0]['values']['K'] = None
        rows = list(build_records(t, 'a' * 64))
        self.assertFalse(any(r['indicator_id'] == 'mapbiomas-extent-forest' and r['year'] == 2024 and r['area'] == 'Indonesia' for r in rows))
        self.assertTrue(any(r['indicator_id'] == 'mapbiomas-extent-forest' and r['year'] == 2024 and r['area'] == 'Riau' for r in rows))

    def answer(self, q, intent, rows):
        state = RequestState(question=q, reference_date=date(2026,11,6), intent=intent,
                             records=[Evidence.model_validate(r) for r in rows])
        state.assessment = assess(state)
        return render(state, Analysis())

    def test_direct_transition_is_one_period_not_a_difference_or_cumulative_sum(self):
        rows = [r for r in self.records() if r['indicator_id'] == 'mapbiomas-transition-forest-to-oil-palm' and r['area'] == 'Aceh']
        intent = Intent(kind='lookup', areas=['Aceh'], indicator_ids=['mapbiomas-transition-forest-to-oil-palm'], temporal='explicit', year=2024, baseline_year=1990, requires_series=True)
        result = self.answer('Berapa luas hutan menjadi sawit di Aceh antara 1990 dan 2024?', intent, rows)
        self.assertEqual(result['evidence'][0]['value'], '7')
        self.assertEqual(result['evidence'][0]['period_text'], '1990–2024')
        self.assertFalse(result['calculations'])
        self.assertFalse(result['gaps'])
        self.assertEqual(result['answer'].count('Sumber:'), 1)
        self.assertEqual(result['parsed']['konteks_penting'].count('Transisi membandingkan'), 1)
        self.assertIn('Koleksi 4.1', result['answer'])
        self.assertIn('.xlsx', result['answer'])
        wrong = intent.model_copy(update={'baseline_year': 2001})
        result = self.answer('Berapa luas hutan menjadi sawit di Aceh antara 2001 dan 2024?', wrong, rows)
        self.assertEqual(result['evidence'], [])

    def test_2026_is_not_replaced_by_2024(self):
        rows = [r for r in self.records() if r['indicator_id'] == 'mapbiomas-extent-forest' and r['area'] == 'Aceh']
        intent = Intent(kind='lookup', areas=['Aceh'], indicator_ids=['mapbiomas-extent-forest'], temporal='explicit', year=2026)
        result = self.answer('Berapa luas hutan Aceh 2026?', intent, rows)
        self.assertEqual(result['evidence'], [])
        self.assertEqual(result['context'][0]['year'], 2024)
        self.assertIn('belum ditemukan', result['parsed']['jawaban_utama'])

    def test_stock_mean_is_allowed_but_not_cumulative_forest_area(self):
        rows = [r for r in self.records() if r['indicator_id'] == 'mapbiomas-extent-forest' and r['area'] == 'Aceh']
        intent = Intent(kind='lookup', areas=['Aceh'], indicator_ids=['mapbiomas-extent-forest'], temporal='explicit', year=2024, baseline_year=2023, requires_series=True)
        result = self.answer('Berapa rata-rata luas hutan Aceh 2023–2024?', intent, rows)
        self.assertEqual([c['kind'] for c in result['parsed']['context_calculations']], ['annual_mean'])
        result = self.answer('Berapa total luas hutan Aceh 2023–2024?', intent, rows)
        self.assertFalse(result['parsed']['context_calculations'])

    def test_rank_keeps_extents_and_transitions_separate(self):
        cs = [{'indicator_id': i, 'member_ids': [i]} for i in [
            'mapbiomas-transition-forest-to-oil-palm', 'mapbiomas-annual-transition-forest-to-oil-palm', 'mapbiomas-extent-oil-palm', 'gfw-tree-cover-loss']]
        self.assertEqual(prioritize(cs, 'Berapa luas sawit di Aceh?')[0]['indicator_id'], 'mapbiomas-extent-oil-palm')
        self.assertEqual(prioritize(cs, 'Hutan menjadi sawit Aceh 1990–2024')[0]['indicator_id'], 'mapbiomas-transition-forest-to-oil-palm')
        self.assertFalse(any(c['indicator_id'].startswith('gfw-') for c in prioritize(cs, 'Menurut MapBiomas luas sawit')))

    def test_unavailable_scope_explains_catalog_coverage_without_creating_evidence(self):
        catalog = [{'indicator_id': 'map-stock', 'source': 'MapBiomas Indonesia',
                    'years': [2023, 2024], 'areas': ['Riau', 'Aceh']}]
        config = {'dataset_version': '4.1', 'district_count': 0, 'province_count': 38}
        for area, year, expected in [('Kabupaten Bombana, Sulawesi Tenggara', 2024, 'Rincian kabupaten/kota'),
                                     ('Aceh', 2026, 'data 2026 belum tersedia')]:
            state = RequestState(question='Pertanyaan uji', reference_date=date(2026, 11, 6),
                intent=Intent(kind='lookup', areas=[area], year=year, temporal='explicit', indicator_ids=['map-stock']))
            state.assessment = assess(state)
            result = explain_unavailable(render(state, Analysis()), state, catalog, config)
            self.assertIn(expected, result['answer'])
            self.assertFalse(result['evidence'])
            self.assertFalse(result['parsed']['download_records'])
            self.assertEqual(result['parsed']['source_items'][0]['source_role'], 'coverage_metadata')
            self.assertIn('landy.mapbiomas.id/en/statistics', result['answer'])
        state.intent.indicator_ids = []
        state.question = 'Berapa luas sawit menurut MapBiomas pada 2026?'
        result = explain_unavailable(render(state, Analysis()), state, catalog, config)
        self.assertIn('data 2026 belum tersedia', result['answer'])
        self.assertFalse(result['evidence'])


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_errors_propagate_and_truncation_is_preserved(self):
        a, b = AsyncMock(), AsyncMock()
        a.search.return_value = SearchBatch()
        b.search.return_value = SearchBatch(truncated=True)
        r = EnvironmentRetriever(a, b, ['gfw-id'], ['map-id'])
        result = await r.search(SearchQuery(text='x', indicator_ids=['map-id'], areas=['Aceh']))
        a.search.assert_not_called()
        self.assertTrue(result.truncated)
        b.search.side_effect = RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            await r.search(SearchQuery(text='x', indicator_ids=['map-id'], areas=['Aceh']))
