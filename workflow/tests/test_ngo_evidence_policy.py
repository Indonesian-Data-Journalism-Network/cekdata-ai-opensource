import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ngo_evidence_policy import (FindingFit, EvidenceFit, ClaimAssessment, accept_fit,
    enforce_decision, search_absence, claim_gap, check_fits, outcome_matches, remove_search_commentary)
from ngo_answer import Finding, requested


def fit(**changes):
    return FindingFit(**dict(dict(finding_id='F1',faithful=True,same_event=True,measure_supported=True,outcome_basis='measured_change',geography='same',
        activity='same',relation='direct_support',explanation='Source matches.',supporting_sentence_ids=['S1']),**changes))


def decision(**changes):
    return ClaimAssessment(**dict(dict(verdict='Benar',reason='Direct evidence.',
        supporting_finding_ids=['F1'],contradicting_finding_ids=[],
        supported_components=['Income change'],missing_components=[],coverage='complete',
        causal_support='established',contradiction_explanation=''),**changes))


class EvidencePolicyTests(unittest.IsolatedAsyncioTestCase):
    def test_other_geography_or_activity_cannot_be_used_even_when_quote_is_faithful(self):
        self.assertFalse(accept_fit(fit(geography='different')))
        self.assertFalse(accept_fit(fit(activity='different')))
        self.assertFalse(accept_fit(fit(same_event=False)))
        self.assertFalse(accept_fit(fit(geography='unknown')))
        self.assertTrue(accept_fit(fit(geography='within_requested_area',relation='context_only')))

    def test_environmental_context_does_not_prove_income_claim_false(self):
        d=decision(verdict='Salah',supporting_finding_ids=[],contradicting_finding_ids=['F1'],contradiction_explanation='Pollution occurred.')
        self.assertEqual(enforce_decision(d,[fit(relation='context_only')]),'Tidak dapat diverifikasi')
        self.assertEqual(enforce_decision(d,[fit(relation='direct_contradiction',outcome_basis='interpretation_only')]),'Tidak dapat diverifikasi')

    def test_static_job_share_and_income_level_do_not_prove_an_income_trend(self):
        q='Pertambangan meningkatkan kesejahteraan karena pendapatan warga terus meningkat.'
        self.assertFalse(outcome_matches(q,Finding(text='Sebanyak 13,5 persen warga bekerja di pertambangan.',evidence_id='D1')))
        self.assertFalse(outcome_matches(q,Finding(text='Rata-rata pendapatan berada di atas upah minimum.',evidence_id='D1')))
        self.assertTrue(outcome_matches(q,Finding(text='Sebagian rumah tangga melaporkan pendapatan menurun.',evidence_id='D1')))
        self.assertFalse(outcome_matches('Sawit menyebabkan kemiskinan turun.',Finding(text='Luas sawit bertambah.',evidence_id='D1')))

    def test_bibliography_channel_keeps_body_text_with_footnotes(self):
        from ngo_retrieval import bibliography
        refs='[1] Study https://example.org/one\n[2] Other https://example.org/two\n[3] More study'
        self.assertTrue(bibliography('REPORT\n'+refs))
        self.assertFalse(bibliography('Hasil wawancara menunjukkan perubahan pendapatan warga. '*25+'\n'+refs))

    def test_claimed_amount_does_not_filter_out_the_actual_report_value(self):
        from ngo_retrieval import neutral_search_text
        self.assertEqual(neutral_search_text('Sebanyak 100 persen warga melaporkan dampak pada 2025.'),
                         neutral_search_text('Sebanyak 45,8 persen warga melaporkan dampak pada 2025.'))
        self.assertIn('2025',neutral_search_text('Sebanyak 100 persen warga pada 2025.'))

    def test_direct_counterevidence_can_still_produce_false(self):
        d=decision(verdict='Salah',supporting_finding_ids=[],contradicting_finding_ids=['F1'],contradiction_explanation='Comparable income series fell rather than rising every year.')
        self.assertEqual(enforce_decision(d,[fit(relation='direct_contradiction')]),'Salah')
        self.assertEqual(enforce_decision(d,[fit(relation='direct_contradiction',geography='broader_context')]),'Tidak dapat diverifikasi')

    def test_missing_evidence_or_unknown_ids_cannot_authorize_a_confident_label(self):
        self.assertEqual(enforce_decision(decision(),[]),'Tidak dapat diverifikasi')
        self.assertEqual(enforce_decision(decision(supporting_finding_ids=['unknown']),[fit()]),'Tidak dapat diverifikasi')
        self.assertEqual(enforce_decision(decision(missing_components=['Comparison group']),[fit()]),'Tidak dapat diverifikasi')
        self.assertEqual(enforce_decision(decision(causal_support='not_established'),[fit()]),'Tidak dapat diverifikasi')

    def test_true_and_partly_true_remain_available_with_matching_evidence(self):
        self.assertEqual(enforce_decision(decision(),[fit()]),'Benar')
        d=decision(verdict='Sebagian benar',coverage='partial',missing_components=['Distribution'])
        self.assertEqual(enforce_decision(d,[fit()]),'Sebagian benar')
        self.assertEqual(enforce_decision(d,[fit(relation='context_only')]),'Tidak dapat diverifikasi')

    def test_retrieval_absence_is_not_reported_as_a_source_finding(self):
        for text in ('Tidak ditemukan data atau laporan yang mendukung klaim.',
                     'Laporan tidak menyebutkan data atau survei tentang penurunan kemiskinan.',
                     'Kegiatan menimbulkan kerusakan, tanpa informasi terkait dampak positif terhadap kemiskinan.',
                     'Wilayah berubah, tanpa bukti perbaikan ekonomi masyarakat lokal.',
                     'Belum ada bukti dalam pencarian ini.'):
            self.assertTrue(search_absence(text),text)
        self.assertFalse(search_absence('Peneliti tidak menemukan pencemaran air dalam sampel.'))
        self.assertFalse(search_absence('Sebanyak 40 persen rumah tangga tidak mengalami kenaikan pendapatan.'))
        self.assertEqual(remove_search_commentary('Warga melaporkan konflik lahan, tanpa bukti perbaikan ekonomi masyarakat lokal.'),'Warga melaporkan konflik lahan.')
        self.assertEqual(remove_search_commentary('Warga tidak mendapat informasi tentang konsultasi lahan.'),'Warga tidak mendapat informasi tentang konsultasi lahan.')

    def test_welfare_claims_keep_report_route_instead_of_only_land_cover(self):
        for question in ('Penurunan kemiskinan di Wilayah Contoh terutama disebabkan industri sawit.',
                         'Pekerja perkebunan mendapat penghasilan lebih tinggi daripada petani.',
                         'Sebagian besar pekerja industri adalah warga setempat.'):
            self.assertTrue(requested(question),question)
        self.assertFalse(requested('Berapa luas sawit di Riau pada 2024?'))
        self.assertIn('kemiskinan',claim_gap('Sawit menyebabkan kemiskinan turun.'))
        self.assertIn('pekerjaan yang tercipta',claim_gap('Pekerjaan tambang lebih banyak daripada pekerjaan yang hilang.'))

    async def test_missing_or_duplicate_fit_ids_are_not_accepted(self):
        findings=[Finding(text='Temuan perubahan penghasilan masyarakat.',evidence_id='D1'),
                  Finding(text='Temuan tambahan dari studi lokal.',evidence_id='D2')]
        def support(items):return [{'evidence_id':f.evidence_id,'support_quote':f.text} for f in items]
        class AI:
            async def astructured_predict(self,*args,**kwargs):
                return EvidenceFit(items=[fit(),fit()])
        accepted,fits=await check_fits(AI(),'Klaim penghasilan.',findings,support)
        self.assertEqual(accepted,[])
        self.assertEqual(fits,[])

    async def test_filtered_fit_ids_stay_anchored_to_original_findings(self):
        findings=[Finding(text='Temuan dari tempat lain.',evidence_id='D1'),
                  Finding(text='Temuan perubahan penghasilan lokal.',evidence_id='D2')]
        def support(items):return [{'evidence_id':f.evidence_id,'support_quote':f.text} for f in items]
        class AI:
            async def astructured_predict(self,*args,**kwargs):
                return EvidenceFit(items=[fit(geography='different'),fit(finding_id='F2')])
        accepted,fits=await check_fits(AI(),'Klaim penghasilan.',findings,support)
        self.assertEqual([f.evidence_id for f in accepted],['D2'])
        self.assertEqual([f.finding_id for f in fits],['F2'])


if __name__=='__main__':unittest.main()
