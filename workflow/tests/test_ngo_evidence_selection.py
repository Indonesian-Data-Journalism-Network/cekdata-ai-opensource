import unittest
from types import SimpleNamespace
from ngo_retrieval import rank,select_pages
from ngo_question_parts import missing_facets,aspect_queries
from ngo_evidence_selection import select_findings
from ngo_evidence_policy import FindingFit


def fit(**kwargs):
    return FindingFit(**dict(dict(finding_id='F1',faithful=True,same_event=True,
        measure_supported=False,geography='same',activity='same',relation='context_only',
        outcome_basis='observed_outcome',explanation='Source-supported finding'),**kwargs))


class EvidenceSelectionTests(unittest.TestCase):
    def test_repeated_title_cannot_outrank_answering_passage(self):
        question='Apa dampak terhadap pendapatan dan pekerjaan warga?'
        header={'title':question,'text':'Daftar nama perusahaan dan profil pengurus.'}
        finding={'title':'Kajian lapangan','text':'Pendapatan warga menurun dan pekerjaan hilang.'}
        self.assertGreater(rank(.5,finding,question,[],[]),rank(.5,header,question,[],[]))

    def test_recovery_excludes_used_pages_before_filling_budget(self):
        points=[dict(sha256='doc',pdf_page=n,page_side='full',score=1-n*.01,
            scope_strength=2 if n==1 else 0,text='Pendapatan warga') for n in range(1,10)]
        used={('doc',n,'full') for n in range(1,6)}
        chosen=select_pages(points,limit=3,question='Apa dampak pada pendapatan?',exclude_pages=used)
        self.assertEqual(len(chosen),3)
        self.assertTrue(all(p['pdf_page']>5 for p in chosen))

    def test_keyword_only_does_not_close_coverage_gap(self):
        findings=[SimpleNamespace(text='Rekomendasi: pendapatan warga perlu ditingkatkan.')]
        self.assertEqual(missing_facets('Bagaimana pendapatan warga?',findings,[fit()]),{'livelihood'})
        fits=[fit(answered_aspects=['livelihood'])]
        self.assertEqual(missing_facets('Bagaimana pendapatan warga?',findings,fits),set())
        fits[0].geography='broader_context'
        self.assertEqual(missing_facets('Bagaimana pendapatan warga?',findings,fits),{'livelihood'})

    def test_queries_preserve_subject_and_search_both_directions(self):
        queries=aspect_queries('Benarkah pendapatan warga di Kabupaten Garut meningkat?')
        self.assertTrue(any('naik turun' in q and 'Kabupaten Garut' in q for q in queries))

    def test_core_finding_beyond_ten_survives_display_cap(self):
        findings=[SimpleNamespace(evidence_id=f'D{i}',text=f'Latar {i}') for i in range(12)]
        fits=[fit() for _ in findings]
        fits[-1].answered_aspects=['livelihood']
        sources={f.evidence_id:{'sha256':f.evidence_id} for f in findings}
        selected,checked=select_findings('Bagaimana pendapatan warga?',findings,fits,sources)
        self.assertEqual(len(selected),10)
        self.assertEqual(selected[0].evidence_id,'D11')
        self.assertEqual([x.finding_id for x in checked],[f'F{i}' for i in range(1,11)])

    def test_counterevidence_is_not_penalized_for_disagreeing(self):
        findings=[SimpleNamespace(evidence_id='D1',text='Pendapatan meningkat.'),
                  SimpleNamespace(evidence_id='D2',text='Pendapatan menurun.')]
        fits=[fit(relation='direct_support'),fit(relation='direct_contradiction')]
        sources={f.evidence_id:{'sha256':f.evidence_id} for f in findings}
        selected,_=select_findings('Benarkah pendapatan meningkat?',findings,fits,sources)
        self.assertEqual(len(selected),2)

    def test_unchecked_fit_alignment_cannot_silently_drop_findings(self):
        with self.assertRaises(ValueError):select_findings('Apa dampaknya?',[object()],[],{})

    def test_verdict_pool_excludes_risks_and_regional_context(self):
        from ngo_evidence_policy import verdict_evidence,claim_packet
        fits=[fit(finding_id='F1',relation='direct_contradiction'),
              fit(finding_id='F2',relation='direct_contradiction',outcome_basis='interpretation_only'),
              fit(finding_id='F3',relation='direct_contradiction',geography='broader_context'),
              fit(finding_id='F4',relation='direct_support',outcome_basis='reported_change')]
        self.assertEqual(verdict_evidence(fits),{'supporting_finding_ids':['F4'],'contradicting_finding_ids':['F1']})
        combined={'verdict_evidence':verdict_evidence(fits),'reports':[{'finding_id':f.finding_id} for f in fits]}
        self.assertEqual([r['finding_id'] for r in claim_packet(combined)['reports']],['F1','F4'])
        self.assertEqual(len(combined['reports']),4)  # Displayed context remains available.

    def test_regional_production_is_not_household_welfare_evidence(self):
        from ngo_evidence_policy import outcome_matches
        q='Benarkah industri hanya membawa keuntungan bagi seluruh warga?'
        for text in ('Kontribusi industri pada PDRB mencapai 70 persen.',
                     'Kapasitas produksi besar memungkinkan ekspor baja ke pasar global.'):
            f=SimpleNamespace(text=text,measure='')
            self.assertFalse(outcome_matches(q,f))
            self.assertTrue(outcome_matches('Apa data ekonomi daerah?',f))
        self.assertTrue(outcome_matches(q,SimpleNamespace(text='Pendapatan petani menurun.',measure='')))

    def test_positive_cases_do_not_cancel_a_real_counterexample_to_all(self):
        from ngo_evidence_policy import ClaimAssessment,enforce_decision
        support=fit(finding_id='F1',relation='direct_support',population_scope='sample_or_subgroup')
        counter=fit(finding_id='F2',relation='direct_contradiction',population_scope='sample_or_subgroup')
        decision=ClaimAssessment(verdict='Salah',reason='Ada contoh tandingan.',
            supporting_finding_ids=['F1'],contradicting_finding_ids=['F2'],
            supported_components=['Sebagian warga memperoleh manfaat.'],missing_components=[],
            coverage='partial',causal_support='not_required',contradiction_explanation='Warga lain mengalami kerugian.',
            quantifier_basis='limited_sample')
        self.assertEqual(enforce_decision(decision,[support,counter],'Semua warga memperoleh manfaat tanpa kerugian.'),'Salah')
        self.assertEqual(enforce_decision(decision,[support,counter],'Kesejahteraan warga meningkat.'),'Tidak dapat diverifikasi')
        support.population_scope='complete_claimed_population'
        self.assertEqual(enforce_decision(decision,[support,counter],'Semua warga memperoleh manfaat tanpa kerugian.'),'Tidak dapat diverifikasi')
        support.population_scope='sample_or_subgroup'
        counter.outcome_basis='interpretation_only'
        self.assertEqual(enforce_decision(decision,[support,counter],'Semua warga memperoleh manfaat tanpa kerugian.'),'Tidak dapat diverifikasi')
        counter.outcome_basis='observed_outcome';counter.population_scope='unknown'
        self.assertEqual(enforce_decision(decision,[support,counter],'Semua warga memperoleh manfaat tanpa kerugian.'),'Tidak dapat diverifikasi')


class ReviewBeforeLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_bad_review_revision_does_not_erase_other_valid_findings(self):
        from unittest.mock import patch
        from workflow.tests.test_ngo_combined import CombinedReportsTests
        from ngo_answer import supported_findings,DocumentAnswer
        from ngo_combined import answer
        fixture=CombinedReportsTests();e,p=fixture.evidence()
        async def reviewed(llm,q,items,support_for):
            # Simulate a bad geographic/numeric edit introduced during review.
            items[-1].text+=' Total 99999 orang.'
            return items,[fit() for _ in items]
        with patch('ngo_combined.check_fits',side_effect=reviewed):
            result=await answer(fixture.ai(),'Apa dampak nikel di Pulau Kabaena?',
                                '2026-11-07',e,p,None,'question')
        self.assertIn('54,1',result['answer'])
        self.assertNotIn('99999',result['answer'])
        self.assertEqual(len(result['parsed']['source_items']),1)

    async def test_bad_explanation_is_repaired_without_losing_valid_verdict(self):
        import json
        from workflow.tests.test_ngo_combined import CombinedReportsTests
        from ngo_evidence_policy import ClaimAssessment
        from ngo_combined import answer
        fixture=CombinedReportsTests();e,p=fixture.evidence();base=fixture.ai();calls=[]
        class AI:
            async def astructured_predict(self,schema,prompt,**kw):
                if schema.__name__=='ClaimAssessment':
                    calls.append(kw)
                    return ClaimAssessment(verdict='Salah',reason=(
                        'Sebanyak 99,9 persen rumah tangga melaporkan kerusakan.' if len(calls)==1 else
                        'Survei Satya Bumi mencatat 54,1 persen rumah tangga di Pulau Kabaena melaporkan kerusakan lingkungan.'),
                        supporting_finding_ids=[],contradicting_finding_ids=['F1'],supported_components=[],
                        missing_components=[],coverage='complete',causal_support='not_required',
                        contradiction_explanation='Ada rumah tangga yang melaporkan kerusakan.',quantifier_basis='direct_counterexample')
                result=await base.astructured_predict(schema,prompt,**kw)
                if schema.__name__=='EvidenceFit':
                    for item in result.items:
                        item.relation='direct_contradiction';item.outcome_basis='reported_change'
                return result
        result=await answer(AI(),'Benarkah tidak ada rumah tangga di Pulau Kabaena yang melaporkan kerusakan lingkungan?',
                            '2026-11-07',e[:1],p[:1],None,'claim')
        self.assertEqual(len(calls),2)
        self.assertIn('feedback',calls[1])
        self.assertEqual(result['parsed']['penilaian'],'Salah')
        self.assertNotIn('99,9',result['answer'])

    async def test_recovery_reads_only_new_pages_from_existing_document(self):
        import json
        from unittest.mock import patch
        from ngo_answer import Finding,DocumentAnswer
        from ngo_combined import answer
        calls=[]
        old=dict(sha256='doc',document_id='doc',evidence_id='D1',title='Laporan',host_organization='Penerbit')
        fresh={**old,'evidence_id':'R1'}
        class AI:
            async def astructured_predict(self,schema,prompt,**kw):
                if schema.__name__=='DocumentAnswer':
                    ids=[p['evidence_id'] for p in json.loads(kw['evidence'])];calls.append(ids)
                    return DocumentAnswer(kind='question',answer='',findings=[
                        Finding(evidence_id=ids[0],text='Temuan '+ids[0])])
                raise RuntimeError('No summary needed')
        async def review(llm,q,items,support_for):return items,[fit() for _ in items]
        async def recover(missing,current):return [fresh],[fresh]
        with patch('ngo_answer.supported_findings',side_effect=lambda out,actual:out.findings), \
             patch('ngo_combined.preserves_scope',return_value=True), \
             patch('ngo_combined.check_fits',side_effect=review), \
             patch('ngo_answer.render',side_effect=lambda out,*args:{'findings':out.findings}):
            await answer(AI(),'Bagaimana pendapatan warga?','2026-11-07',[old],[old],None,'question',recover=recover)
        self.assertEqual(calls,[['D1'],['R1']])

    async def test_eleven_candidates_all_reviewed_before_display_cap(self):
        import json
        from unittest.mock import patch
        from ngo_answer import Finding,DocumentAnswer
        from ngo_combined import answer
        reviewed=[]
        evidence=[dict(sha256=f'doc{i}',document_id=f'doc{i}',evidence_id=f'D{i}',
                       title='Laporan',host_organization='Penerbit') for i in range(3)]
        public=[{'evidence_id':p['evidence_id']} for p in evidence]
        class AI:
            async def astructured_predict(self,schema,prompt,**kw):
                if schema.__name__=='DocumentAnswer':
                    eid=json.loads(kw['evidence'])[0]['evidence_id']
                    return DocumentAnswer(kind='question',answer='',findings=[
                        Finding(evidence_id=eid,text=f'Temuan {eid} nomor {n}') for n in range(5)])
                raise RuntimeError('Summary intentionally unavailable in isolated test')
        async def review(llm,q,items,support_for):
            reviewed.extend(f.text for f in items)
            return items,[fit() for _ in items]
        def render(out,*args):return {'findings':out.findings}
        with patch('ngo_answer.supported_findings',side_effect=lambda out,actual:out.findings), \
             patch('ngo_combined.preserves_scope',return_value=True), \
             patch('ngo_combined.check_fits',side_effect=review), \
             patch('ngo_answer.render',side_effect=render):
            result=await answer(AI(),'Jelaskan temuan.','2026-11-07',evidence,public,None,'question')
        self.assertEqual(len(reviewed),15)
        self.assertEqual(len(result['findings']),10)
