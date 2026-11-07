"""Regression coverage for stage one: preserve the requested measurement/activity."""
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from flow import Intent
from pilot_data import PilotAI, IndicatorSelection
from environment_data import preserve_loss_selection, forest_measure_clarification
from ngo_source_facts import activity_conflict, activity_context, activity_supported


def catalog():
    return [dict(indicator_id=name, member_ids=[name], label=label,
                 source='Global Forest Watch / UMD GLAD', areas=['Aceh'],
                 years=[2024, 2025], populations=['total'], units=['ha'])
            for name, label in [
                ('gfw-tree-cover-loss', 'Kehilangan tutupan pohon tahunan'),
                ('gfw-primary-forest-loss', 'Kehilangan tutupan pohon dalam hutan primer'),
                ('gfw-tree-cover-loss-fire', 'Kehilangan tutupan pohon akibat kebakaran')]]


class IndicatorTopicScopeTests(unittest.TestCase):
    def test_original_question_overrides_wrong_subset_selection(self):
        rows = catalog()
        for q, expected in [
            ('Kehilangan tutupan pohon di Sulawesi Tenggara naik pada 2025 dibanding 2024. Benarkah?', rows[0]),
            ('Berapa hutan yang hilang di Sulawesi Tengah tahun lalu?', rows[0]),
            ('Berapa kehilangan tutupan pohon dalam hutan primer di Kota Bandung tahun 2023?', rows[1]),
            ('Berapa hutan primer yang hilang di Bali pada 2025?', rows[1]),
            ('Bagaimana tren kehilangan tutupan pohon akibat kebakaran di Jambi?', rows[2]),
        ]:
            with self.subTest(q=q):
                self.assertEqual(preserve_loss_selection([rows[0], rows[1]], rows, q), [expected])

    def test_missing_primary_family_does_not_turn_into_total(self):
        rows = catalog()[:1]
        self.assertEqual(preserve_loss_selection(rows, rows,
            'Berapa kehilangan hutan primer di Medan?'), [])

    def test_unrelated_statistics_and_named_provider_remain_untouched(self):
        selected = [{'indicator_id': 'mapbiomas-extent-forest', 'source': 'MapBiomas Indonesia'}]
        for q in ['Berapa luas hutan di Aceh?', 'Berapa kehilangan hutan menurut MapBiomas?']:
            self.assertEqual(preserve_loss_selection(selected, catalog(), q), selected)
        self.assertEqual(preserve_loss_selection([], catalog(), 'Berapa kehilangan tutupan pohon?', ['Other']), [])
        for q in ['Berapa emisi dari kehilangan tutupan pohon di Aceh?',
                  'Berapa kehilangan tutupan pohon dalam konsesi sawit?',
                  'Berapa kehilangan hutan primer akibat kebakaran?']:
            self.assertEqual(preserve_loss_selection(selected, catalog(), q), selected)

    def test_broad_concept_requires_measure_clarification_not_arbitrary_subset(self):
        for q in ['Katanya kerusakan hutan di Riau sudah menurun. Betul?',
                  'Deforestasi di Kalimantan Timur tahun lalu turun. Benarkah?']:
            self.assertTrue(forest_measure_clarification(q, catalog()))
        for q in ['Berapa kehilangan tutupan pohon di Riau?',
                  'Apa penyebab deforestasi di Riau?',
                  'Berapa luas hutan menjadi sawit di Aceh?']:
            self.assertFalse(forest_measure_clarification(q, catalog()))

    def test_explicit_total_and_primary_can_be_compared(self):
        rows = catalog()
        result = preserve_loss_selection([], rows,
            'Bandingkan kehilangan tutupan pohon total dengan kehilangan hutan primer di Aceh.')
        self.assertEqual(result, rows[:2])

    def test_different_activity_is_not_rescued_by_report_title_or_neighbor(self):
        q = 'Apa dampak perkebunan sawit terhadap masyarakat adat?'
        proof = 'Pembangunan perkebunan tebu mengancam lahan adat.'
        self.assertTrue(activity_conflict(q, proof, 'Laporan ini juga membahas sawit.'))
        self.assertIn('pangan/energi', activity_context(q, proof, '', 'Sawit dan pangan'))
        q = 'Apa dampak perkebunan kayu terhadap warga?'
        self.assertTrue(activity_conflict(q, 'Perkebunan sawit memicu konflik lahan.'))
        self.assertTrue(activity_conflict(q, 'Pembangunan PLTU batu bara mencemari udara.'))

    def test_supported_cross_activity_link_and_generic_questions_are_retained(self):
        self.assertFalse(activity_conflict('Apa dampak perkebunan kayu?',
            'Perkebunan kayu memasok biomassa untuk menggantikan batu bara.'))
        self.assertFalse(activity_conflict('Bandingkan sawit dan perkebunan tebu.',
            'Perkebunan tebu menyebabkan konflik lahan.'))
        self.assertFalse(activity_conflict('Apa masalah lingkungan di Papua?',
            'Perkebunan tebu menyebabkan konflik lahan.'))
        self.assertFalse(activity_conflict('Apa dampak pertambangan nikel?',
            'Warga kehilangan sumber air.', 'Dampak pertambangan nikel terhadap warga.'))

    def test_generic_project_cannot_become_specific_commodity(self):
        q = 'Apa dampak perkebunan sawit terhadap warga?'
        self.assertFalse(activity_supported(q, 'Perkebunan sawit mengancam 24 kampung.',
            'Kebijakan ini mengancam 24 kampung.', 'Kawasan Swasembada Pangan, Energi, dan Air Nasional.'))
        self.assertFalse(activity_supported(q, 'Perkebunan sawit mengancam warga.',
            'Perusahaan mengancam warga.', 'Kebijakan pembangunan industri.'))
        self.assertFalse(activity_supported(q, 'Perempuan kehilangan ruang hidup.',
            'Perempuan kehilangan ruang hidup.', 'Pertemuan korban PSN.', 'Audit PSN'))
        self.assertTrue(activity_supported(q, 'Warga kehilangan lahan.',
            'Warga kehilangan lahan.', 'Perluasan kebun sawit.'))
        self.assertFalse(activity_supported(q, 'Warga kehilangan lahan.',
            'Warga kehilangan lahan.', 'Perluasan kebun sawit.', fit_activity='general_context'))


class SelectionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_relevance_model_cannot_approve_explicitly_different_activity(self):
        from ngo_answer import Finding
        from ngo_evidence_policy import check_fits, EvidenceFit, FindingFit
        f = Finding(text='Perkebunan tebu mengancam lahan adat.', evidence_id='D1')
        row = dict(finding_id='F1', page_text=f.text, support_context='',
                   source_sentences=[{'sentence_id':'S1','text':f.text}])
        llm = AsyncMock()
        llm.astructured_predict.return_value = EvidenceFit(items=[FindingFit(
            finding_id='F1', faithful=True, same_event=True, measure_supported=True,
            geography='same', activity='same', relation='context_only',
            outcome_basis='not_outcome', explanation='Matches', supporting_sentence_ids=['S1'])])
        with patch('ngo_evidence_policy.evidence_rows', return_value=[row]), \
             patch('ngo_evidence_policy.sentence_support_valid', return_value=True), \
             patch('ngo_source_facts.event_scope_valid', return_value=True):
            accepted, fits = await check_fits(llm, 'Apa dampak perkebunan sawit?', [f], {})
        self.assertEqual(accepted, [])
        self.assertEqual(fits, [])

    async def test_wrong_model_selection_is_corrected_before_retrieval(self):
        rows = catalog()
        llm = AsyncMock()
        llm.astructured_predict.return_value = IndicatorSelection(indicator_ids=[rows[1]['indicator_id']])
        ai = PilotAI(llm, rows)
        intent = Intent(kind='lookup', areas=['Aceh'], temporal='explicit', year=2025,
                        indicator_terms=['kehilangan hutan primer'], reformulated='Hutan primer Aceh')
        with patch('flow.LlamaAI.understand', new=AsyncMock(return_value=intent)):
            result = await ai.understand('Berapa kehilangan tutupan pohon di Aceh pada 2025?', date(2026,11,6), rows)
        self.assertEqual(result.indicator_ids, [rows[0]['indicator_id']])


if __name__ == '__main__':
    unittest.main()
