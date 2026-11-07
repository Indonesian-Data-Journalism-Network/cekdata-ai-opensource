import unittest
from types import SimpleNamespace
from ngo_geography_policy import places,scope_decision
from ngo_retrieval import select_pages,geographic_points
from ngo_question_parts import missing_facets,requested_facets

class RetrievalRecoveryTests(unittest.TestCase):
    def test_unique_archipelago_alias_and_wrong_location_control(self):
        short=places('di Mentawai')[0]['id']
        self.assertEqual(short,places('di Kabupaten Kepulauan Mentawai')[0]['id'])
        proof='Di Kabupaten Kepulauan Mentawai, warga mengalami gangguan listrik.'
        self.assertEqual(scope_decision('Apa masalah di Mentawai?',proof,proof)[0],'same')
        self.assertEqual(scope_decision('Apa masalah di Kabupaten Garut?',proof,proof)[0],'different')

    def test_name_does_not_absorb_capitalized_next_sentence(self):
        self.assertEqual([p['id'] for p in places('di Mentawai Pada awal tahun 2019')],
                         [p['id'] for p in places('di Mentawai')])

    def test_nested_locality_not_another_district(self):
        names={p['name'] for p in places('Jorong Kampung Baru Pekonina')}
        self.assertIn('Kampung Baru Pekonina',names)
        self.assertNotIn('Kabupaten Baru',names)
        self.assertFalse(places('PT Peconina Baru membuka lahan baru.'))

    def test_acronym_not_a_place(self):
        self.assertEqual(places('Banks involved in ETM should consult residents.'),[])
        self.assertTrue(places('di Desa Contoh Hilir'))

    def test_unknown_locality_still_not_assigned_to_district(self):
        proof='Di Desa Contoh Hilir, warga kehilangan lahan.'
        self.assertEqual(scope_decision('Apa dampak di Kabupaten Garut?',proof,proof)[0],'different')

    def test_scroll_follows_offset(self):
        class Client:
            def __init__(self):self.offsets=[]
            def scroll(self,*args,**kwargs):
                self.offsets.append(kwargs['offset'])
                return ([1,2], 'next') if kwargs['offset'] is None else ([3],None)
        c=Client();self.assertEqual(list(geographic_points(c,'index',None)),[1,2,3])
        self.assertEqual(c.offsets,[None,'next'])

    def test_scroll_budget_bounded(self):
        class Client:
            def scroll(self,*args,**kwargs):
                n=kwargs['limit'];offset=kwargs['offset'] or 0
                return list(range(offset,offset+n)),offset+n
        self.assertEqual(len(list(geographic_points(Client(),'index',None,max_points=500))),500)

    def test_stalled_scroll_is_service_failure(self):
        class Client:
            def scroll(self,*args,**kwargs):return [],'offset'
        with self.assertRaises(RuntimeError):list(geographic_points(Client(),'index',None))

    def point(self,doc,page,score,text,provider='same'):
        return dict(sha256=doc,document_id=doc,pdf_page=page,page_side='full',score=score,text=text,provider=provider,scope_strength=2)

    def test_document_diversity_not_limited_to_first_three(self):
        points=[self.point(str(d),p,.95-d*.015-p*.002,'Dampak lingkungan') for d in range(6) for p in range(5)]
        chosen=select_pages(points,question='Apa dampak lingkungan?')
        self.assertEqual(len({p['sha256'] for p in chosen}),6)
        self.assertLessEqual(len(chosen),20)

    def test_lower_ranked_health_page_survives_repeated_background(self):
        points=[self.point('doc',p,.95-p*.01,'Tambang dan lingkungan') for p in range(8)]
        points.append(self.point('doc',14,.80,'Warga mengalami penyakit dan kehilangan sumber air.'))
        chosen=select_pages(points,limit=3,question='Apa dampaknya terhadap kesehatan dan sumber air?')
        self.assertIn(14,[p['pdf_page'] for p in chosen])

    def test_partial_finding_triggers_only_missing_aspects(self):
        f=SimpleNamespace(text='Petani kehilangan mata pencaharian.')
        self.assertEqual(missing_facets('Apa dampaknya pada sumber air dan mata pencaharian?',[f]),{'water'})
        self.assertNotIn('environment',requested_facets('Apa dampak terhadap pendapatan? Tambahkan angka kehilangan tutupan pohon di Kabupaten Garut pada 2024.'))

class ProjectLinkTests(unittest.TestCase):
    def test_source_link_supports_project_but_not_another_project_or_region(self):
        from ngo_geography_policy import project_links
        text='PLTP Contoh Indah berdampak pada petani. Warga terutama di Jorong Bunga Melati kehilangan air untuk pertanian.'
        links=project_links([{'pdf_page':4,'text':text}])
        proof='Di Jorong Bunga Melati, petani kehilangan air untuk pertanian.'
        self.assertEqual(scope_decision('Apa dampak proyek panas bumi di Contoh Indah?',proof,proof,event_links=links)[0],'within_requested_area')
        self.assertEqual(scope_decision('Apa dampak proyek panas bumi di Tempat Lain?',proof,proof,event_links=links)[0],'different')
        self.assertEqual(scope_decision('Berapa luas lahan di Kabupaten Garut?',proof,proof,event_links=links)[0],'different')
        self.assertEqual(scope_decision('Apa dampak proyek panas bumi di Contoh Indah?',proof,proof)[0],'different')

    def test_two_facilities_do_not_create_link(self):
        from ngo_geography_policy import project_links
        text='PLTP Contoh Indah dan PLTP Tempat Lain dibahas. Petani di Jorong Bunga Melati kehilangan air.'
        self.assertFalse(project_links([{'pdf_page':4,'text':text}]))

class ExtractionRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_fourth_document_is_actually_read(self):
        from workflow.tests.test_ngo_combined import CombinedReportsTests
        from ngo_answer import public_evidence
        from ngo_combined import answer
        fixture=CombinedReportsTests();e,_=fixture.evidence();base=fixture.ai();seen=set()
        e.extend([{**e[1],'sha256':f'extra-{i}','document_id':f'extra-{i}','evidence_id':f'D{i}'} for i in [3,4]])
        public=public_evidence(e,'Apa dampaknya di Pulau Kabaena?')
        class Spy:
            async def astructured_predict(self,schema,prompt,**kw):
                if schema.__name__=='DocumentAnswer':
                    import json
                    seen.add(json.loads(kw['evidence'])[0]['evidence_id'])
                return await base.astructured_predict(schema,prompt,**kw)
        await answer(Spy(),'Apa dampaknya di Pulau Kabaena?','2026-11-07',e,public,None,'question')
        self.assertEqual(seen,{'D1','D2','D3','D4'})

    async def test_partial_answer_fetches_missing_aspect(self):
        from workflow.tests.test_ngo_combined import CombinedReportsTests
        from ngo_answer import public_evidence
        from ngo_combined import answer
        fixture=CombinedReportsTests();e,_=fixture.evidence();calls=[]
        async def recover(missing,current):
            calls.append(missing)
            extra=[e[1]]
            return extra,public_evidence(extra,'Apa dampak terhadap lingkungan dan air di Pulau Kabaena?')
        first=[e[0]]
        await answer(fixture.ai(),'Apa dampak terhadap lingkungan dan air di Pulau Kabaena?',
            '2026-11-07',first,public_evidence(first,'Apa dampak terhadap lingkungan dan air di Pulau Kabaena?'),None,'question',recover=recover)
        self.assertEqual(len(calls),1);self.assertIn('water',calls[0])

    async def test_service_failure_not_reported_as_no_data(self):
        from workflow.tests.test_ngo_combined import CombinedReportsTests
        from ngo_combined import answer
        e,p=CombinedReportsTests().evidence()
        class Broken:
            async def astructured_predict(self,*args,**kw):raise TimeoutError()
        with self.assertRaisesRegex(RuntimeError,'extraction_unavailable'):
            await answer(Broken(),'Apa dampaknya?','2026-11-07',e,p,None,'question')

class CanonicalEvidenceTests(unittest.TestCase):
    def test_short_and_full_name_are_same_evidence_not_a_new_location(self):
        from ngo_answer import Finding,DocumentAnswer,supported_findings
        proof='Pada awal tahun 2019, rasio elektrifikasi di Mentawai sebesar 56,41%. '
        page={'evidence_id':'D1','page_text':proof+'Angka ini menggambarkan akses listrik pada periode yang disebutkan dalam laporan.',
              'title':'Akses energi','host_organization':'Penerbit','pdf_page':4}
        for location,expected in [('Kabupaten Kepulauan Mentawai',1),('Kabupaten Garut',0)]:
            finding=Finding(text=f'Pada awal 2019, rasio elektrifikasi di {location} sebesar 56,41%.',
                            evidence_id='D1',support_quote=proof)
            result=supported_findings(DocumentAnswer(kind='question',answer='',findings=[finding]),[page])
            self.assertEqual(len(result),expected)
