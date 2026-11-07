"""Stages 4–6: synthetic, location-independent adversarial regressions."""
import unittest
from datetime import date
from flow import RequestState,Analysis,Predicate,Note,assess,render,apply_editorial
from test_flow import row,intent
from test_ngo_evidence_policy import fit,decision
from ngo_answer import Finding,DocumentAnswer,render as render_document,preserves_quantity_status
from ngo_combined import summary_errors
from ngo_evidence_status import status_errors,universal_kind
from ngo_evidence_policy import enforce_decision,claim_gap,check_fits,EvidenceFit
from answer_format import rounded


class EvidenceStatusTests(unittest.TestCase):
    def test_no_number_plan_risk_and_opinion_cannot_become_observed_events(self):
        for source,unsupported in [
            ('Perusahaan berencana membuka perkebunan di lahan warga.','Perusahaan membuka perkebunan di lahan warga.'),
            ('Perluasan perkebunan berisiko menggusur lahan pertanian warga.','Perluasan perkebunan menggusur lahan pertanian warga.'),
            ('Peneliti menilai ekspansi tambang memperburuk ketimpangan ekonomi.','Ekspansi tambang memperburuk ketimpangan ekonomi.'),
            ('Hasil pemodelan menunjukkan penurunan penghasilan petani.','Penghasilan petani menunjukkan penurunan.')]:
            with self.subTest(source=source):
                self.assertTrue(status_errors(unsupported,source))
                self.assertFalse(preserves_quantity_status(unsupported,source))
                self.assertFalse(status_errors(source,source))
                f=Finding(text=source,evidence_id='D1',support_quote=source)
                self.assertTrue(summary_errors(unsupported,[f],{}))

    def test_observation_in_same_passage_does_not_inherit_other_risk(self):
        source='Pembukaan tambang berisiko mencemari sungai. Warga melaporkan kehilangan kebun setelah penggusuran.'
        self.assertFalse(status_errors('Warga melaporkan kehilangan kebun setelah penggusuran.',source))
        self.assertTrue(status_errors('Pembukaan tambang mencemari sungai.',source))
        self.assertFalse(status_errors('Risiko pencemaran sungai belum membuktikan kejadian pencemaran.',source))


class QuantifierTests(unittest.TestCase):
    def test_reported_response_number_does_not_require_publisher_in_question(self):
        from ngo_numeric_claim import eligible
        self.assertTrue(eligible('Benarkah 100 persen rumah tangga menyatakan produksi pertanian menurun akibat tambang?'))
        self.assertFalse(eligible('Pertambangan menurunkan produksi pertanian sebesar 100 persen.'))

    def test_universal_true_needs_complete_population_not_sample(self):
        for q in ['Semua warga mendapat pekerjaan.','Tidak ada warga yang kehilangan pekerjaan.','Jumlah warga kehilangan pekerjaan nol.']:
            with self.subTest(q=q):
                self.assertTrue(universal_kind(q))
                self.assertEqual(enforce_decision(decision(),[fit()],q),'Tidak dapat diverifikasi')
                d=decision(quantifier_basis='complete_population')
                self.assertEqual(enforce_decision(d,[fit()],q),'Tidak dapat diverifikasi')
                self.assertEqual(enforce_decision(d,[fit(population_scope='sample_or_subgroup')],q),'Tidak dapat diverifikasi')
                self.assertEqual(enforce_decision(d,[fit(population_scope='complete_claimed_population')],q),'Benar')
                self.assertEqual(enforce_decision(d,[fit(geography='within_requested_area')],q),'Tidak dapat diverifikasi')

    def test_actual_counterexample_can_refute_universal_but_risk_cannot(self):
        d=decision(verdict='Salah',supporting_finding_ids=[],contradicting_finding_ids=['F1'],contradiction_explanation='Satu kejadian pada periode yang sama.',quantifier_basis='direct_counterexample')
        q='Tidak ada warga kehilangan pekerjaan.'
        self.assertEqual(enforce_decision(d,[fit(relation='direct_contradiction')],q),'Salah')
        self.assertEqual(enforce_decision(d,[fit(relation='direct_contradiction',outcome_basis='interpretation_only')],q),'Tidak dapat diverifikasi')
        self.assertEqual(enforce_decision(d,[fit(relation='context_only')],q),'Tidak dapat diverifikasi')

    def test_not_all_reverses_coverage_requirement(self):
        q='Tidak semua warga mendapat pekerjaan.'
        self.assertEqual(universal_kind(q),'not_all')
        self.assertEqual(enforce_decision(decision(quantifier_basis='direct_counterexample'),[fit()],q),'Benar')
        d=decision(verdict='Salah',supporting_finding_ids=[],contradicting_finding_ids=['F1'],contradiction_explanation='Seluruhnya mendapat pekerjaan.',quantifier_basis='direct_counterexample')
        self.assertEqual(enforce_decision(d,[fit(relation='direct_contradiction')],q),'Tidak dapat diverifikasi')
        d.quantifier_basis='complete_population'
        self.assertEqual(enforce_decision(d,[fit(relation='direct_contradiction',population_scope='complete_claimed_population')],q),'Salah')

    def test_conflicting_direct_evidence_does_not_authorize_true(self):
        d=decision(contradicting_finding_ids=['F2'])
        self.assertEqual(enforce_decision(d,[fit(),fit(finding_id='F2',relation='direct_contradiction')]),'Tidak dapat diverifikasi')
        self.assertNotIn('pekerja',claim_gap('Sebagian besar warga melaporkan pencemaran sungai.'))


class SourceStatusPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_risk_cannot_be_decisive_even_if_reviewer_calls_it_observed(self):
        import json
        source='Perluasan perkebunan berisiko menggusur lahan pertanian warga.'
        f=Finding(text=source,evidence_id='D1',support_quote=source)
        class AI:
            async def astructured_predict(self,schema,prompt,**kwargs):
                data=json.loads(kwargs['evidence'])
                return EvidenceFit(items=[fit(outcome_basis='observed_outcome',supporting_sentence_ids=[s['sentence_id'] for s in data[0]['source_sentences']])])
        def support(items):return [{'evidence_id':'D1','support_quote':source,'page_text':source} for _ in items]
        findings,fits=await check_fits(AI(),'Perluasan perkebunan sudah menggusur lahan pertanian warga.',[f],support)
        self.assertEqual(len(findings),1)
        self.assertEqual(fits[0].outcome_basis,'interpretation_only')
        self.assertEqual(fits[0].relation,'context_only')
        self.assertEqual(enforce_decision(decision(),fits),'Tidak dapat diverifikasi')


class PresentationTests(unittest.TestCase):
    def response(self,values,question,**options):
        state=RequestState(question=question,reference_date=date(2026,11,6),
            intent=intent(year=2025,temporal='explicit',**options),
            records=[row(str(y),y,v,month=None,unit='ha') for y,v in values])
        state.assessment=assess(state)
        return render(state,Analysis())

    def test_zero_baseline_keeps_absolute_change_without_fake_percent(self):
        for start,end in [('0','7'),('0','0'),('-5','7')]:
            with self.subTest(start=start,end=end):
                result=self.response([(2023,'12'),(2024,start),(2025,end)],'Berapa persentase perubahan pada 2025 dibandingkan 2024?',baseline_year=2024,relative_change=True)
                calculations=result['parsed']['findings_table']['calculations']
                self.assertEqual(len(calculations),1)
                self.assertNotEqual(calculations[0]['unit'],'persen')
                self.assertIn('nilai awal '+('nol' if start=='0' else 'negatif'),result['answer'])
                self.assertIn('selisih',result['answer'])
                self.assertEqual(len(result['parsed']['findings_table']['rows']),2)
                self.assertEqual(result['answer'].count('nilai awal '+('nol' if start=='0' else 'negatif')),1)

    def test_small_nonzero_is_not_zero_and_verdict_uses_original(self):
        self.assertNotEqual(rounded('0.00046'),'0,00')
        self.assertNotEqual(rounded('-0.00046'),'-0,00')
        self.assertEqual(rounded('-0'),'0,00')
        result=self.response([(2025,'0.00046')],'Benarkah nilainya nol pada 2025?',kind='claim',predicate=Predicate(metric='value',operator='eq',threshold='0',unit='ha'))
        self.assertEqual(result['verdict'],'Salah')
        self.assertIn('0,00046',result['answer'])
        missing=self.response([],'Benarkah nilainya nol pada 2025?',kind='claim',predicate=Predicate(metric='value',operator='eq',threshold='0',unit='ha'))
        self.assertEqual(missing['verdict'],'Tidak dapat diverifikasi')
        zero=self.response([(2025,'0')],'Benarkah nilainya nol pada 2025?',kind='claim',predicate=Predicate(metric='value',operator='eq',threshold='0',unit='ha'))
        self.assertEqual(zero['verdict'],'Benar')

    def test_rounding_collision_explains_different_original_values(self):
        result=self.response([(2025,'17.2341')],'Benarkah nilainya 17,2342 ha pada 2025?',kind='claim',predicate=Predicate(metric='value',operator='eq',threshold='17.2342',unit='ha'))
        self.assertEqual(result['verdict'],'Salah')
        self.assertIn('17,2341',result['reason']);self.assertIn('17,2342',result['reason'])
        self.assertIn('Nilai asli',result['reason'])

    def test_percent_claim_compares_percent_not_the_absolute_delta(self):
        for claimed,expected in [('50','Benar'),('5','Salah')]:
            result=self.response([(2024,'10'),(2025,'15')],f'Benarkah nilainya naik {claimed} persen?',kind='claim',baseline_year=2024,relative_change=True,
                predicate=Predicate(metric='change',operator='eq',threshold=claimed,unit='persen'))
            self.assertEqual(result['verdict'],expected)
            self.assertEqual({c['kind'] for c in result['calculations']},{'time','relative'})

    def test_editorial_cannot_remove_zero_baseline_explanation(self):
        state=RequestState(question='Nilainya naik nol persen.',reference_date=date(2026,11,6),
            intent=intent(kind='claim',year=2025,baseline_year=2024,temporal='explicit',relative_change=True,
                predicate=Predicate(metric='change',operator='eq',threshold='0',unit='persen')),
            records=[row('a',2024,'0',month=None,unit='ha'),row('b',2025,'0',month=None,unit='ha')])
        state.assessment=assess(state)
        original=state.assessment.reason
        apply_editorial(state,Analysis(verdict='Tidak dapat diverifikasi',reason=Note(text='Perubahannya nol persen.',evidence_ids=['a','b'])))
        self.assertEqual(state.assessment.reason,original)
        self.assertIn('tidak terdefinisi',original)

    def test_repeated_claim_reason_not_rendered_twice(self):
        source='Warga melaporkan kehilangan lahan pertanian setelah penggusuran oleh perusahaan perkebunan kayu. Temuan ini dicatat dalam wawancara lapangan.'
        page=dict(evidence_id='D1',sha256='fixture',document_id='fixture',host_organization='Organisasi Contoh',title='Laporan contoh',source_url='https://example.org/report',download_url='https://example.org/report.pdf',pdf_page=1,page_text=source)
        f=Finding(text=source,evidence_id='D1',support_quote=source)
        out=DocumentAnswer(kind='claim',answer='Temuan belum mencakup seluruh warga.',reason='Temuan belum mencakup seluruh warga.',verdict='Tidak dapat diverifikasi',findings=[f])
        result=render_document(out,[page],'Semua warga terdampak.')
        self.assertEqual(result['answer'].count(out.reason),1)
        self.assertEqual(result['parsed']['kesimpulan'],'')
        self.assertIn('Temuan Data Organisasi Contoh',result['answer'])
