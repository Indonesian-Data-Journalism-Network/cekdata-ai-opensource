import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ngo_answer import (DocumentAnswer, Finding, EvidenceReview, AnswerSummary,
                        public_evidence, number_tokens)
from ngo_combined import answer, scope_notes, preserves_scope, summary_errors
from ngo_evidence_policy import EvidenceFit, FindingFit


class CombinedReportsTests(unittest.IsolatedAsyncioTestCase):
    async def test_extraction_keeps_second_question_and_claim_qualifiers(self):
        evidence,public=self.evidence();base=self.ai();seen=[]
        class CaptureAI:
            async def astructured_predict(inner,schema,prompt,**kwargs):
                if schema.__name__=='DocumentAnswer':seen.append(json.loads(kwargs['question']))
                return await base.astructured_predict(schema,prompt,**kwargs)
        question='Apakah semua rumah tangga kehilangan pekerjaan? Berapa persen yang pendapatannya turun?'
        await answer(CaptureAI(),question,'2026-11-07',evidence,public,None,'question')
        self.assertTrue(seen)
        self.assertTrue(all(q==question for q in seen))

    def test_health_fallback_keeps_relevant_quantified_evidence(self):
        from ngo_combined import fallback_summary
        findings=[Finding(text='Warga melaporkan debu dari pembangkit.',evidence_id='D1'),
                  Finding(text='Dalam pemodelan, polusi diperkirakan berkaitan dengan 23 kematian per tahun.',evidence_id='D1')]
        result=fallback_summary(findings,{'D1':{'host_organization':'Contoh'}},'Apa dampaknya terhadap kesehatan?')
        self.assertIn('23 kematian',result);self.assertIn('pemodelan',result)

    async def test_rejected_draft_gets_one_source_grounded_retry(self):
        evidence,public=self.evidence();base=self.ai();calls={'fit':0,'extract':0}
        class RetryAI:
            async def astructured_predict(inner,schema,prompt,**kwargs):
                result=await base.astructured_predict(schema,prompt,**kwargs)
                if schema.__name__=='EvidenceFit':
                    calls['fit']+=1
                    if calls['fit']==1:
                        for item in result.items:item.faithful=False
                if schema.__name__=='DocumentAnswer':calls['extract']+=1
                return result
        result=await answer(RetryAI(),'Apa dampak pertambangan di Pulau Kabaena?','2026-11-06',evidence,public,None,'question')
        # Two extraction reviews plus at most one bounded original-sentence
        # completion review; no unbounded generation/retry loop.
        self.assertGreaterEqual(calls['fit'],2);self.assertLessEqual(calls['fit'],3)
        self.assertEqual(calls['extract'],4)
        self.assertIn('54,1',result['answer'])

    def test_summary_report_references_must_name_the_organization(self):
        for text in ('Laporan ini mencatat dampak.', 'Menurut laporan, terjadi perubahan.', 'Laporan menyebut perubahan.'):
            self.assertTrue(summary_errors(text,[],{}))
        self.assertFalse(summary_errors('Laporan Auriga mencatat dampak, sedangkan laporan WALHI menyebut perubahan.',[],{}))

    def test_summary_cannot_turn_petition_or_organization_data_into_survey_answers(self):
        findings=[Finding(text='Petisi menyebut petani mengalami gagal panen.', evidence_id='D1')]
        self.assertTrue(summary_errors('Responden melaporkan gagal panen.',findings,{}))
        self.assertFalse(summary_errors('Petisi menyebut petani mengalami gagal panen.',findings,{}))
        findings=[Finding(text='Sebanyak 54,1% rumah tangga melaporkan kerusakan lingkungan.', evidence_id='D1')]
        self.assertFalse(summary_errors('Responden melaporkan kerusakan lingkungan.',findings,{}))

    def test_summary_place_spelling_must_be_grounded(self):
        evidence={'text':'Petani di Jorong Bunga Melati mengalami perubahan.'}
        self.assertFalse(summary_errors('Petani di Jorong Bunga Melati mengalami perubahan.',[],evidence))
        self.assertTrue(summary_errors('Petani di Jorong Bunga Melitha mengalami perubahan.',[],evidence))

    def test_gfw_geography_cannot_be_attached_to_a_national_report_observation(self):
        evidence={'reports':[{'host_organization':'WALHI','title':'Laporan nasional',
                    'support_quote':'Tanah ulayat dirampas untuk perkebunan sawit di Indonesia.',
                    'support_context':'Analisis nasional tentang tanah ulayat.'}],
                  'gfw':{'summary':'GFW mencatat kehilangan tutupan pohon di Kalimantan Barat.'}}
        self.assertTrue(summary_errors('Laporan WALHI mencatat perampasan tanah di Kalimantan Barat.',[],evidence))
        self.assertFalse(summary_errors('Laporan WALHI membahas konflik tanah ulayat di Indonesia. GFW memberi konteks Kalimantan Barat.',[],evidence))

    def test_unknown_gfw_cause_is_not_evidence_of_other_causes(self):
        self.assertTrue(summary_errors('Kehilangan ini tidak secara eksklusif disebabkan oleh perkebunan kayu.',[],{'gfw':{'context':'Data tidak membuktikan penyebabnya.'}}))
        self.assertFalse(summary_errors('Data GFW belum dapat memastikan penyebab kehilangan tersebut.',[],{'gfw':{}}))

    def evidence(self):
        base = {'pdf_page': 46, 'printed_page': '46', 'page_side': 'full', 'score': .9,
                'document_id': 'local', 'sha256': 'a', 'evidence_id': 'D1',
                'host_organization': 'Satya Bumi', 'title': 'Studi Pulau Kabaena',
                'source_url': 'https://satyabumi.org/report',
                'download_url': 'https://satyabumi.org/report.pdf',
                'page_text': 'Masyarakat di Pulau Kabaena, Kabupaten Bombana diwawancarai. Pertambangan nikel berdampak pada lingkungan. Sebanyak 54,1% rumah tangga melaporkan kerusakan lingkungan. Penelitian menjelaskan pengalaman para responden.'}
        other = {**base, 'evidence_id': 'D2', 'sha256': 'b', 'document_id': 'regional',
                 'host_organization': 'WALHI', 'title': 'Tinjauan lingkungan', 'pdf_page': 86,
                 'source_url': 'https://walhi.or.id/report', 'download_url': 'https://walhi.or.id/report.pdf',
                 'page_text': 'Di Sulawesi, perempuan di kawasan industri nikel menghadapi pencemaran air serta beban merawat keluarga yang sakit. Laporan ini membahas dampak regional dan tidak mengukur luas kerusakan pada kabupaten tertentu.'}
        evidence = [base, other]
        public = public_evidence(evidence, 'Dampak tambang di Bombana')
        return evidence, public

    def gfw(self):
        return {'summary': 'GFW mencatat kehilangan tutupan pohon di Bombana sebesar 15 ha selama 2021–2025.',
                'table': {'headers': ['Tahun', 'ha'], 'rows': [['2025', '15']], 'calculations': []},
                'context': 'Data ini tidak membuktikan penyebab kehilangan.',
                'parsed': {'source_items': [{'display': 'GFW', 'url': 'https://www.globalforestwatch.org/'}], 'download_records': []}}

    def ai(self, unsupported_number=False):
        class AI:
            async def astructured_predict(inner, schema, prompt, **kwargs):
                if schema.__name__ == 'EvidenceFit':
                    return EvidenceFit(items=[FindingFit(finding_id=row['finding_id'],faithful=True,same_event=True,measure_supported=True,
                        geography='same',activity='same',outcome_basis='not_outcome',relation='context_only',explanation='Source and place agree.',
                        supporting_sentence_ids=[s['sentence_id'] for s in row['source_sentences']])
                        for row in json.loads(kwargs['evidence'])])
                if schema.__name__ == 'EvidenceReview':
                    return EvidenceReview(supported=True)
                if schema.__name__ == 'AnswerSummary':
                    return AnswerSummary(answer='Survei Kabaena melaporkan dampak lingkungan, sementara laporan regional membahas beban perempuan. Data GFW mengukur luas kehilangan tutupan pohon.', context='Cakupan dan ukuran ketiga sumber berbeda.')
                pages = json.loads(kwargs['evidence'])
                page = pages[0]
                window = next((w for w in page['passages'] if '54,1%' in w['text']), page['passages'][0])
                if page['evidence_id'] == 'D1':
                    value = '99,9' if unsupported_number else '54,1'
                    text = f'Sebanyak {value}% rumah tangga di Pulau Kabaena melaporkan kerusakan lingkungan.'
                    measure = 'Rumah tangga di Pulau Kabaena yang melaporkan kerusakan lingkungan'
                else:
                    text = 'Laporan menyebut perempuan di kawasan industri nikel Sulawesi menghadapi pencemaran air dan beban perawatan keluarga.'
                    measure = ''
                return DocumentAnswer(kind='question', answer='', findings=[Finding(
                    text=text, measure=measure, evidence_id=page['evidence_id'], passage_id=window['passage_id'])])
        return AI()

    async def test_report_sources_numeric_table_and_gfw_are_combined(self):
        evidence, public = self.evidence()
        result = await answer(self.ai(), 'Dampak nikel di Bombana?', '2026-11-05', evidence, public, self.gfw(), 'question')
        parsed = result['parsed']
        self.assertEqual({s['source'] for s in parsed['source_items']}, {'Satya Bumi', 'WALHI'})
        self.assertIn('54,1', parsed['findings_table']['rows'][0][1])
        self.assertEqual(parsed['findings_table']['headers'],['Temuan','Nilai'])
        self.assertIn('[1]',parsed['findings_table']['caption'])
        self.assertNotIn('Rujukan:',result['answer'])
        self.assertIn('[1]',parsed['temuan_data'])
        self.assertIn('[2]',parsed['temuan_data'])
        self.assertNotIn('berikut temuan', parsed['jawaban_utama'].lower())
        self.assertIn('GFW', result['answer'])
        self.assertIn('https://satyabumi.org/report.pdf', result['answer'])
        self.assertIn('https://walhi.or.id/report.pdf', result['answer'])

    async def test_grouped_findings_and_conclusion_order_without_forcing_gfw(self):
        evidence, public = self.evidence()
        result = await answer(self.ai(), 'Dampak nikel di Bombana?', '2026-11-05', evidence, public, None, 'question')
        groups = result['parsed']['finding_groups']
        self.assertEqual([g['source'] for g in groups], ['Satya Bumi', 'WALHI'])
        self.assertTrue(groups[0]['findings'][0].startswith('Sebanyak 54,1 persen'))
        self.assertNotIn('Menurut laporan,', result['answer'])
        self.assertLess(result['answer'].index('Temuan Data WALHI'), result['answer'].index('Kesimpulan'))
        self.assertNotIn('Peringatan Editorial',result['answer'])
        self.assertNotIn('Cakupan dan ukuran ketiga sumber berbeda.',result['answer'])
        self.assertIsNone(result['parsed']['gfw_context'])

    async def test_three_source_order_gfw_before_conclusion_and_footers_once(self):
        evidence, public = self.evidence()
        result = await answer(self.ai(), 'Dampak nikel di Bombana?', '2026-11-05', evidence, public, self.gfw(), 'question')
        text=result['answer']
        for first,last in [('Temuan Data Satya Bumi','Temuan Data WALHI'),('Temuan Data WALHI','Temuan Data Global Forest Watch'),('Temuan Data Global Forest Watch','Kesimpulan'),('Kesimpulan','[1] Sumber:')]:
            self.assertLess(text.index(first),text.index(last))
        self.assertEqual(text.count('https://satyabumi.org/report.pdf'),1)
        self.assertEqual(text.count('https://walhi.or.id/report.pdf'),1)
        self.assertEqual(len(result['parsed']['finding_citations']),2)

    async def test_invalid_summary_gets_one_repair_and_never_publishes_new_numbers(self):
        base=self.ai()
        class AI:
            attempts=0
            async def astructured_predict(inner,schema,prompt,**kwargs):
                if schema.__name__=='AnswerSummary':
                    inner.attempts+=1
                    if inner.attempts==1:return AnswerSummary(answer='Kehilangan mencapai 999999 hektar.')
                return await base.astructured_predict(schema,prompt,**kwargs)
        ai=AI()
        evidence,public=self.evidence()
        result=await answer(ai,'Dampak nikel di Bombana?','2026-11-05',evidence,public,self.gfw(),'question')
        self.assertEqual(ai.attempts,2)
        self.assertNotIn('999999',result['answer'])
        self.assertIn('Data GFW mengukur',result['parsed']['kesimpulan'])

    async def test_summary_failure_keeps_each_report_and_gfw_in_final_conclusion(self):
        base=self.ai()
        class AI:
            async def astructured_predict(inner,schema,prompt,**kwargs):
                if schema.__name__=='AnswerSummary':raise RuntimeError('test failure')
                return await base.astructured_predict(schema,prompt,**kwargs)
        evidence,public=self.evidence()
        result=await answer(AI(),'Dampak nikel di Bombana?','2026-11-05',evidence,public,self.gfw(),'question')
        conclusion=result['parsed']['kesimpulan']
        self.assertIn('54,1',conclusion)
        self.assertIn('perempuan',conclusion)
        self.assertIn('15 ha',conclusion)
        self.assertIn('tidak membuktikan penyebab',conclusion)

    async def test_fabricated_number_excludes_that_report_without_dropping_other_sources(self):
        evidence, public = self.evidence()
        result = await answer(self.ai(unsupported_number=True), 'Dampak nikel di Bombana?', '2026-11-05', evidence, public, self.gfw(), 'question')
        self.assertNotIn('99.9', number_tokens(result['answer']))
        self.assertEqual([s['source'] for s in result['parsed']['source_items']], ['WALHI'])
        self.assertIsNotNone(result['parsed']['gfw_context'])

    def test_explicit_multi_district_scope_must_not_be_flattened(self):
        evidence, _ = self.evidence()
        evidence[0]['scope_evidence'] = [{'pdf_page': 14, 'text': 'Pulau ini secara administrasi berada di Kabupaten Bombana dan Kabupaten Buton Tengah, Provinsi Sulawesi Tenggara.'}]
        notes = scope_notes(evidence)
        self.assertIn('Buton Tengah', notes[0]['text'])
        self.assertFalse(preserves_scope('Survei Pulau Kabaena, Kabupaten Bombana, menunjukkan dampak.', notes))
        self.assertTrue(preserves_scope('Survei Kabaena berbeda cakupannya dari seri GFW di Bombana dan Buton Tengah.', notes))

    async def test_claim_without_report_evidence_explains_the_causal_gap(self):
        class AI:
            async def astructured_predict(inner, schema, prompt, **kwargs):
                return DocumentAnswer(kind='question', answer='', findings=[], insufficient=True)
        evidence, public = self.evidence()
        result = await answer(AI(), 'Benarkah seluruh kehilangan tutupan pohon disebabkan nikel?',
                              '2026-11-05', evidence, public, self.gfw(), 'claim')
        self.assertEqual(result['parsed']['penilaian'], 'Tidak dapat diverifikasi')
        self.assertIn('tidak membuktikan penyebab', result['parsed']['alasan'])
        self.assertNotIn('Perjelas judul', result['answer'])

    async def test_unjustified_false_decision_and_summary_cannot_override_context_only_evidence(self):
        from ngo_evidence_policy import ClaimAssessment
        base=self.ai()
        class AI:
            async def astructured_predict(inner,schema,prompt,**kwargs):
                if schema.__name__=='ClaimAssessment':
                    return ClaimAssessment(verdict='Salah',reason='Pencemaran membuktikan pendapatan turun.',
                        supporting_finding_ids=[],contradicting_finding_ids=['F1'],supported_components=[],
                        missing_components=['Perubahan pendapatan'],coverage='none',causal_support='not_established',
                        contradiction_explanation='Pencemaran terjadi.')
                if schema.__name__=='AnswerSummary':
                    return AnswerSummary(answer='Pendapatan warga terbukti turun.',verdict='Salah',reason='Pencemaran terjadi.')
                return await base.astructured_predict(schema,prompt,**kwargs)
        evidence,public=self.evidence()
        result=await answer(AI(),'Pendapatan warga meningkat karena pertambangan nikel.',
                            '2026-11-06',evidence,public,None,'claim')
        self.assertEqual(result['parsed']['penilaian'],'Tidak dapat diverifikasi')
        self.assertNotIn('Pendapatan warga terbukti turun',result['answer'])
        self.assertIn('belum cukup untuk menyimpulkan',result['parsed']['alasan'])
        self.assertEqual(len(result['parsed']['source_items']),2)

    async def test_reason_can_compare_a_wrong_claimed_number_with_the_source_number(self):
        from ngo_evidence_policy import ClaimAssessment
        base=self.ai()
        reason='Klaim menyebut 100 persen, sedangkan laporan Satya Bumi mencatat 54,1 persen.'
        class AI:
            async def astructured_predict(inner,schema,prompt,**kwargs):
                if schema.__name__=='EvidenceFit':
                    return EvidenceFit(items=[FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=True,geography='same',
                        activity='same',relation='direct_contradiction',outcome_basis='observed_outcome',explanation='Angka asli berbeda dengan angka klaim.',
                        supporting_sentence_ids=[s['sentence_id'] for s in json.loads(kwargs['evidence'])[0]['source_sentences']])])
                if schema.__name__=='ClaimAssessment':
                    return ClaimAssessment(verdict='Salah',reason=reason,supporting_finding_ids=[],
                        contradicting_finding_ids=['F1'],supported_components=[],missing_components=[],
                        coverage='complete',causal_support='not_required',contradiction_explanation=reason,
                        quantifier_basis='direct_counterexample')
                if schema.__name__=='AnswerSummary':
                    return AnswerSummary(answer=reason,verdict='Salah',reason=reason)
                return await base.astructured_predict(schema,prompt,**kwargs)
        evidence,public=self.evidence()
        result=await answer(AI(),'Benarkah laporan Satya Bumi menyebut 100 persen rumah tangga melaporkan kerusakan lingkungan?',
                            '2026-11-06',evidence[:1],public[:1],None,'claim')
        self.assertEqual(result['parsed']['penilaian'],'Salah')
        self.assertIn('100 persen',result['parsed']['alasan'])
        self.assertNotIn('100',result['parsed']['temuan_data'])


if __name__ == '__main__':
    unittest.main()
