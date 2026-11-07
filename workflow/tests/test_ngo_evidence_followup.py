"""Source semantics regressions, without case-specific production rules."""
import unittest
from types import SimpleNamespace
from ngo_geography_policy import places,document_addresses,scope_decision
from ngo_evidence_status import status_tags,status_errors
from ngo_source_facts import quantities,source_quantity,restore_quantity_bounds,quantity_errors
from ngo_question_parts import requested_facets,missing_facets,source_candidates
from ngo_retrieval import select_pages,selection_body
from test_ngo_evidence_policy import fit


class GeographicAddressTests(unittest.TestCase):
    def test_village_list_does_not_create_parent_relationship(self):
        text='Listrik tersedia di Desa Saliguma, Madobag dan Matotonan.'
        locations=places(text)
        self.assertEqual({p['name'] for p in locations},{'Saliguma','Madobag','Matotonan'})
        self.assertTrue(all(not p['parents'] for p in locations))
        self.assertFalse(document_addresses([{'pdf_page':1,'text':text}]))
        self.assertEqual(scope_decision('Apa dampak di Madobag?',
            'Warga Desa Saliguma kehilangan akses listrik.',
            'Warga Desa Saliguma kehilangan akses listrik.',addresses=document_addresses(
                [{'pdf_page':1,'text':text}]))[0],'different')

    def test_reference_ancestor_cannot_become_child(self):
        text='Berada di Pantai Barat Pulau Sumatera, Kepulauan Mentawai memiliki pulau kecil.'
        for p in places(text):
            if p['name']=='Pulau Sumatera':self.assertFalse(p['parents'])

    def test_explicit_address_still_works(self):
        proof='Warga Desa Contoh Hilir kehilangan lahan.'
        addresses=document_addresses([{'pdf_page':1,'text':
            'Desa Contoh Hilir, Kecamatan Contoh Hulu, Kabupaten Garut menjadi lokasi penelitian.'}])
        self.assertEqual(scope_decision('Apa dampak di Kabupaten Garut?',proof,proof,
                                       addresses=addresses)[0],'within_requested_area')


class StatusTests(unittest.TestCase):
    def test_actual_inability_is_not_a_risk(self):
        for text in ['Pembangkit mangkrak dan tidak bisa lagi beroperasi.',
                     'Petani tidak dapat menggarap lahan sejak saluran irigasi rusak.',
                     'Lahan pertanian tersebut tidak bisa diusahakan selama setahun.',
                     'Nelayan tidak lagi bisa melaut setelah akses pantai ditutup.']:
            self.assertNotIn('risiko',status_tags(text))

    def test_hypothetical_inability_still_risk_or_plan(self):
        self.assertIn('risiko',status_tags('Ada risiko petani tidak bisa menggarap lahan.'))
        self.assertIn('rencana',status_tags('Petani akan tidak bisa menggarap lahan.'))
        self.assertTrue(status_errors('Tambang mencemari sungai.',
                                     'Tambang bisa mencemari sungai.'))
        self.assertIn('risiko',status_tags('Penyebab kerusakan tidak dapat dipastikan.'))

    def test_subjective_witness_is_not_publisher_but_remains_attributed(self):
        for text in ['Saya menilai proyek merugikan warga.',
                     'Warga menilai proyek merugikan warga.',
                     'Responden yang diwawancarai merasa proyek merugikan warga.']:
            self.assertIn('penilaian responden',status_tags(text))
            self.assertNotIn('analisis penerbit',status_tags(text))
        self.assertTrue(status_errors('Proyek merugikan warga.',
                                     'Saya menilai proyek merugikan warga.'))
        self.assertFalse(status_errors('Warga menilai proyek merugikan warga.',
                                      'Saya menilai proyek merugikan warga.'))
        self.assertIn('analisis penerbit',status_tags('Peneliti menilai proyek merugikan warga.'))
        self.assertEqual(status_tags('Warga menilai proyek merugikan warga. Peneliti menilai kebijakan gagal.'),
                         {'analisis penerbit','penilaian responden'})

    def test_reported_event_is_not_subjective_opinion(self):
        self.assertFalse(status_tags('Warga melaporkan penggusuran kebun mereka pada 2023.'))


class NearQuantityTests(unittest.TestCase):
    def test_near_is_preserved_in_text_and_table(self):
        for bound in ['hampir','nearly','almost']:
            source=bound+' 70 persen rumah tangga kehilangan lahan.'
            self.assertEqual(quantities(source)[0]['operator'],'near')
            text=restore_quantity_bounds('Sebanyak 70 persen rumah tangga kehilangan lahan.',source)
            self.assertIn('hampir 70 persen',text)
            self.assertFalse(quantity_errors(text,source))
            self.assertEqual(source_quantity(text,source)['display'],'Hampir 70 persen')
            self.assertTrue(quantity_errors('Sebanyak 70 persen rumah tangga kehilangan lahan.',source))
            self.assertTrue(quantity_errors('Sekitar 70 persen rumah tangga kehilangan lahan.',source))

    def test_exact_number_is_not_changed(self):
        text='Sebanyak 54,1 persen rumah tangga melaporkan kerusakan.'
        self.assertEqual(restore_quantity_bounds(text,text),text)
        self.assertEqual(source_quantity(text,text)['display'],'54,1 persen')
        self.assertTrue(quantity_errors('Hampir 54,1 persen rumah tangga melaporkan kerusakan.',text))


class CoverageAndRankingTests(unittest.TestCase):
    def point(self,page,score,text,**kwargs):
        return dict(sha256='doc',pdf_page=page,page_side='full',score=score,text=text,
                    scope_strength=1,**kwargs)

    def test_life_and_energy_are_separate_requests(self):
        q='Apa data tentang akses energi dan kehidupan warga?'
        self.assertEqual(requested_facets(q),{'energy','livelihood'})
        self.assertEqual(missing_facets(q,[SimpleNamespace(text='Listrik tersedia.')],
            [fit(answered_aspects=['energy'])]),{'livelihood'})
        self.assertEqual(requested_facets('Bagaimana akses energi?'),{'energy'})

    def test_body_evidence_outranks_repeated_cover(self):
        title='Penghidupan masyarakat dan pembangunan'
        cover=selection_body(title+'\n'+title+'\n4',title,[title])
        self.assertEqual(cover,'')
        points=[self.point(i,.95,title,selection_text=cover) for i in range(5)]
        source=('Survei terhadap 105 responden menemukan 70 persen rumah tangga kehilangan lahan. '
                'Sebanyak 38 persen responden melaporkan pendapatan menurun setelah proyek dimulai.')
        points.append(self.point(9,.74,'Penutup laporan',selection_text=source))
        chosen=select_pages(points,limit=2,question='Bagaimana pendapatan dan lahan warga?')
        self.assertEqual(chosen[0]['pdf_page'],9)
        self.assertEqual(len(chosen),2)
        self.assertIn('70 persen',chosen[0]['selection_text'])

    def test_unrelated_large_numbers_do_not_replace_relevant_measurements(self):
        unrelated='Perusahaan mengoperasikan 9000 hektar konsesi. Luas kawasan industri mencapai 90000 hektar.'
        source='Sebanyak 30 persen warga belum memperoleh akses listrik di desa yang menjadi lokasi survei rumah tangga.'
        chosen=select_pages([self.point(1,.80,unrelated),self.point(2,.78,source)],
                            limit=1,question='Berapa akses listrik dan elektrifikasi warga?')
        self.assertEqual(chosen[0]['pdf_page'],2)

    def test_passage_selection_uses_energy_aspect(self):
        from ngo_answer import passages_for
        filler=' '.join(f'Ekonomi industri daerah meningkat pada sektor ke {i} dengan dukungan investasi pemerintah.' for i in range(12))
        source='Rasio elektrifikasi warga tercatat 32 persen pada 2017 dan meningkat menjadi 56,41 persen pada 2019.'
        p={'page_text':filler+'\n\n'+source,'evidence_id':'D1','context_parents':[]}
        passages=passages_for(p,'Apa data tentang akses energi dan kehidupan warga di daerah ini?')
        self.assertTrue(any('56,41' in item['text'] for item in passages))
        self.assertLessEqual(len(passages),8)

    def test_validated_numeric_data_survives_final_limit(self):
        from ngo_evidence_selection import select_findings
        findings=[SimpleNamespace(text='Pembangkit sudah beroperasi.',evidence_id='D1'),
                  SimpleNamespace(text='Rasio elektrifikasi mencapai 56,41 persen pada 2019.',evidence_id='D2')]
        fits=[fit(relation='context_only',answered_aspects=['energy']) for _ in findings]
        sources={'D1':{'sha256':'a'},'D2':{'sha256':'b'}}
        selected,_=select_findings('Apa data akses energi?',findings,fits,sources,limit=1)
        self.assertIn('56,41',selected[0].text)


class ActualInabilityIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_inability_is_not_downgraded_after_model_review(self):
        import json
        from ngo_answer import Finding
        from ngo_evidence_policy import check_fits,EvidenceFit,FindingFit
        source='Pembangkit mangkrak dan tidak bisa lagi beroperasi sejak 2022.'
        class AI:
            async def astructured_predict(self,schema,prompt,**kwargs):
                data=json.loads(kwargs['evidence'])
                item=fit(outcome_basis='observed_outcome',
                    supporting_sentence_ids=[s['sentence_id'] for s in data[0]['source_sentences']])
                return EvidenceFit(items=[FindingFit(**item.model_dump())])
        f=Finding(text=source,evidence_id='D1',support_quote=source)
        def support(items):return [{'evidence_id':'D1','support_quote':source,'page_text':source} for _ in items]
        findings,fits=await check_fits(AI(),'Benarkah pembangkit mangkrak sejak 2022?',[f],support)
        self.assertEqual(len(findings),1)
        self.assertEqual(fits[0].outcome_basis,'observed_outcome')


class NumericCompletionTests(unittest.TestCase):
    def evidence(self):
        text='Rasio elektrifikasi di Kabupaten Garut sebesar 56,41 persen pada 2019.'
        return [{'sha256':'doc','evidence_id':'D1','title':'Kajian energi','page_text':text,
                 'passages':[{'text':text,'context':text}]}]

    def test_qualitative_answer_does_not_hide_available_number(self):
        findings=[SimpleNamespace(text='Pembangkit di Kabupaten Garut telah beroperasi.')]
        fits=[fit(answered_aspects=['energy'])]
        rows=source_candidates('Apa data akses energi di Kabupaten Garut?',findings,fits,self.evidence())
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['quote'],self.evidence()[0]['page_text'])

    def test_no_retry_when_number_already_answered(self):
        e=self.evidence()
        self.assertEqual(source_candidates('Apa data akses energi di Kabupaten Garut?',
            [SimpleNamespace(text=e[0]['page_text'])],[fit(answered_aspects=['energy'])],e),[])

    def test_number_from_other_region_not_promoted(self):
        self.assertEqual(source_candidates('Apa data akses energi di Kabupaten Sleman?',[],[],self.evidence()),[])

    def test_caption_copy_not_injected_as_duplicate_finding(self):
        e=self.evidence();plain=e[0]['page_text']
        e[0]['passages'].insert(0,{'text':'Kronologi pembangunan '+plain})
        rows=source_candidates('Apa data akses energi di Kabupaten Garut?',[],[],e)
        self.assertEqual([r['text'] for r in rows],[plain])

    def test_foreign_translation_and_truncated_fragment_use_normal_extraction(self):
        e=self.evidence();plain=e[0]['page_text']
        e[0]['passages'] += [{'text':'The electricity access for the residents in Kabupaten Garut was 56.41 percent.'},
                            {'text':'Rasio elektrifikasi di Kabupaten Garut meningkat dari 56,41 persen menjadi'}]
        rows=source_candidates('Apa data akses energi di Kabupaten Garut?',[],[],e)
        self.assertEqual([r['text'] for r in rows],[plain])


class NumericCompletionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_literal_completion_still_requires_fit_approval(self):
        import json
        from ngo_answer import public_evidence
        from ngo_combined import answer
        from test_ngo_combined import CombinedReportsTests
        for approved in (True,False):
            with self.subTest(approved=approved):
                e,_=CombinedReportsTests().evidence();e=e[:1]
                numeric='Rasio elektrifikasi di Kabupaten Garut sebesar 56,41 persen pada 2019.'
                qualitative='Pembangkit di Kabupaten Garut telah beroperasi untuk memasok kebutuhan listrik warga.'
                e[0].update(title='Kajian energi',page_text=qualitative+' '+numeric)
                q='Apa data akses energi di Kabupaten Garut?'
                public=public_evidence(e,q);checked=[]
                class AI:
                    async def astructured_predict(self,schema,prompt,**kw):
                        if schema.__name__=='DocumentAnswer':
                            return schema(kind='question',answer='',findings=[dict(
                                text=qualitative,evidence_id='D1',support_quote=qualitative)])
                        if schema.__name__=='EvidenceFit':
                            rows=json.loads(kw['evidence']);checked.extend(rows)
                            return schema(items=[dict(finding_id=r['finding_id'],faithful=approved or '56,41' not in r['finding']['text'],
                                same_event=True,measure_supported=False,geography='same',activity='same',
                                relation='context_only',outcome_basis='observed_outcome',answered_aspects=['energy'],
                                explanation='Match source.',supporting_sentence_ids=[s['sentence_id'] for s in r['source_sentences']]) for r in rows])
                        if schema.__name__=='AnswerSummary':return schema(answer=qualitative,context='')
                        if schema.__name__=='EvidenceReview':return schema(supported=True)
                        raise AssertionError(schema.__name__)
                result=await answer(AI(),q,'2026-11-07',e,public,None,'question')
                self.assertTrue(any('56,41' in r['finding']['text'] for r in checked))
                self.assertEqual('56,41' in result['answer'],approved)
