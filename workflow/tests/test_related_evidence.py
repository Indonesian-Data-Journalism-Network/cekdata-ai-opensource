import sys
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flow import Evidence, SearchBatch
from related_evidence import attach, plans

REF = date(2026, 11, 8)
CAT = [{'indicator_id': 'fire', 'member_ids': ['gfw-tree-cover-loss-fire'],
        'areas': ['Indonesia', 'Aceh', 'Bali', 'Jambi', 'Riau'], 'years': [2023, 2024, 2025]}]
INTENT = SimpleNamespace(indicator_ids=['fire'], population='total')

def row(area='Jambi', year=2025, **kwargs):
    return Evidence(**dict(id=f'{area}-{year}', indicator_id='fire', indicator='Kehilangan tutupan pohon akibat kebakaran',
        area=area, year=year, value='12.5', unit='ha', source='GFW', source_url='https://example.org/source', **kwargs))

def result():
    return {'verdict': 'Tidak dapat diverifikasi', 'evidence': [], 'gaps': ['missing_period'],
            'parsed': {'answer_format': 2, 'claim': 'Karhutla 2026 turun',
            'penilaian': 'Tidak dapat diverifikasi', 'alasan': 'Periode belum tersedia.'}}

class RelatedTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_preserves_verdict_intent_and_primary_evidence(self):
        original = result(); intent = deepcopy(INTENT)
        retriever = SimpleNamespace(search=AsyncMock(return_value=SearchBatch(records=[row()])))
        out = await attach(original, 'Karhutla Jambi 2026 menurun', intent, CAT, REF, retriever)
        self.assertEqual(out['verdict'], 'Tidak dapat diverifikasi')
        self.assertEqual(out['evidence'], [])
        self.assertEqual(intent.__dict__, INTENT.__dict__)
        group = out['parsed']['related_evidence'][0]
        self.assertEqual(group['table']['rows'][0][1], '2025')
        self.assertIn('berbeda dari seluruh luas karhutla', group['context'])
        self.assertIn('Seri tidak lengkap', group['context'])
        self.assertEqual(group['table']['calculations'], [])
        self.assertIn('Temuan Data Terkait', out['answer'])
        self.assertIn('https://example.org/source', out['answer'])

    async def test_national_fallback_is_deterministic_not_chosen_by_value(self):
        search = AsyncMock(side_effect=[SearchBatch(records=[]), SearchBatch(records=[row('Aceh')])])
        out = await attach(result(), 'Karhutla Indonesia 2026 turun', INTENT, CAT, REF, SimpleNamespace(search=search))
        self.assertEqual(search.call_args_list[1].args[0].areas, ['Aceh', 'Bali', 'Jambi'])
        group = out['parsed']['related_evidence'][0]
        self.assertEqual(group['reason'], 'provincial_examples')
        self.assertIn('bukan total', group['context'])

    async def test_service_failure_not_data_absence(self):
        out = await attach(result(), 'Karhutla Jambi', INTENT, CAT, REF,
                           SimpleNamespace(search=AsyncMock(side_effect=ConnectionError())))
        self.assertEqual(out['parsed']['related_evidence_status'], 'service_unavailable')
        self.assertEqual(out['verdict'], 'Tidak dapat diverifikasi')
        self.assertIn('gangguan layanan', out['answer'])

    async def test_successful_answer_does_not_search_or_change(self):
        original = result(); original.update(evidence=[row().model_dump()], gaps=[])
        before = deepcopy(original); search = AsyncMock()
        self.assertEqual(await attach(original, 'Karhutla Jambi', INTENT, CAT, REF,
                                     SimpleNamespace(search=search)), before)
        search.assert_not_called()

    async def test_wrong_scope_month_and_truncation_are_not_presented(self):
        for batch in [SearchBatch(records=[row('Riau')]), SearchBatch(records=[row(month=1)]),
                      SearchBatch(records=[row()], truncated=True)]:
            out = await attach(result(), 'Karhutla Jambi', INTENT, CAT, REF,
                               SimpleNamespace(search=AsyncMock(return_value=batch)))
            self.assertNotIn('related_evidence', out['parsed'])

    def test_no_parent_substitution_or_unrelated_indicator(self):
        self.assertEqual(plans('Karhutla di Kecamatan Jambi', INTENT, CAT, REF), [])
        self.assertEqual(plans('Banjir di Papua Selatan', INTENT, CAT, REF), [])
        self.assertEqual(plans('Harga beras di Jambi', SimpleNamespace(indicator_ids=[], population='total'), CAT, REF), [])

if __name__ == '__main__': unittest.main()

class ComparisonContextTests(unittest.TestCase):
    def test_ongoing_events_cannot_refute_a_decline(self):
        from ngo_evidence_policy import statistical_comparison_supported as supported
        self.assertFalse(supported('Kasus kebakaran menurun dibanding daerah lain.',
            'Kerusakan gambut mencapai 3,3 juta hektar. Kebakaran terus terjadi setiap tahun.'))
        self.assertFalse(supported('Luas kebakaran pada 2025 turun dibanding 2024.',
            'Luas kebakaran turun dari 200 hektar pada 2022 menjadi 100 hektar pada 2023.'))
        self.assertTrue(supported('Luas kebakaran pada 2025 turun dibanding 2024.',
            'Luas kebakaran turun dari 200 hektar pada 2024 menjadi 100 hektar pada 2025.'))
        self.assertTrue(supported('Pendapatan warga menurun.', 'Warga melaporkan penghasilan berkurang.'))

    def test_descriptive_level_is_not_a_place_name(self):
        queries = plans('Karhutla di tiga provinsi terdampak: Aceh, Bali, Jambi.', INTENT, CAT, REF)
        self.assertEqual(queries[0][0].areas, ['Aceh', 'Bali', 'Jambi'])

    def test_provinces_available_even_without_national_catalog_row(self):
        catalog = [{**CAT[0], 'areas': ['Aceh', 'Bali', 'Jambi']}]
        queries = plans('Karhutla Indonesia', INTENT, catalog, REF)
        self.assertTrue(queries[0][2])
        self.assertEqual(queries[0][0].areas, ['Aceh', 'Bali', 'Jambi'])

class CompoundPlaceTests(unittest.TestCase):
    def test_unindexed_compound_is_not_known_short_name(self):
        from geography import embedded_place_alias
        aliases = {'alpha': {'regency'}, 'beta': {'province'}}
        self.assertTrue(embedded_place_alias('Hutan di Alpha Delta, Beta.', 'alpha', aliases))
        self.assertFalse(embedded_place_alias('Hutan di Alpha dan Beta.', 'alpha', aliases))
        self.assertFalse(embedded_place_alias('Hutan di Alpha Delta.', 'alpha', {**aliases, 'alpha delta': {'district'}}))
