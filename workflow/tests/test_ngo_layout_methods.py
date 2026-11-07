import unittest
from collections import Counter
from unittest.mock import AsyncMock
from ngo_pdf_layout import read_columns
from ngo_method_context import method_evidence
from ngo_answer import Finding
from ngo_evidence_policy import FindingFit,EvidenceFit,check_fits,MethodBasis,MethodBasisReview


class Page:
    bbox=(0,0,600,800)
    def __init__(self,lines):self.words=[];self.lines=lines
    def put(self,text,x,y):
        for word in text.split():
            width=len(word)*4
            self.words.append(dict(text=word,x0=x,x1=x+width,top=y,bottom=y+10,height=10));x+=width+3
    def extract_words(self,**kwargs):return self.words


class LayoutTests(unittest.TestCase):
    def test_projection_excerpt_does_not_inherit_prior_footnoted_incident(self):
        from ngo_source_facts import qualified_numeric_excerpts
        text=('Insiden sebelumnya berdampak pada warga lainnya.16\n'
              'Di wilayah lain, proyek di NTT diproyeksikan mengurangi pendapatan hingga Rp30 miliar.')
        excerpts=list(qualified_numeric_excerpts(text,'Apakah kerugian Rp30 miliar sudah terjadi?'))
        self.assertEqual(len(excerpts),1);self.assertTrue(excerpts[0].startswith('Di wilayah lain'))
        self.assertNotIn('Insiden',excerpts[0])

    def test_money_table_retains_magnitude_and_cannot_match_different_scale(self):
        from ngo_source_facts import source_quantity
        for value in ['Rp30 juta','Rp430 miliar','Rp1,1 triliun']:
            self.assertEqual(source_quantity(value,value)['display'],value)
        self.assertIsNone(source_quantity('Rp430 juta','Rp430 miliar'))

    def test_method_pages_are_internal_and_survive_render_validation(self):
        from ngo_answer import DocumentAnswer,render
        text='Pendapatan pekerja di NTT dalam model ini berkurang Rp30 juta pada tahun pembangunan.'
        f=Finding(text=text,evidence_id='D1',support_quote=text,measure='Pendapatan pekerja',measure_validated=True)
        f.method_pages=[4]
        self.assertNotIn('method_pages',Finding.model_json_schema()['properties'])
        p={'evidence_id':'D1','document_id':'test','sha256':'x','title':'Kajian ekonomi','host_organization':'NGO',
           'pdf_page':10,'printed_page':'9','page_side':'full','source_url':'https://example.org/report',
           'download_url':'https://example.org/report.pdf','page_text':text+' Penelitian ini membahas skenario ekonomi dan bukan pengamatan kejadian aktual.'}
        r=render(DocumentAnswer(kind='question',answer=text,findings=[f]),[p],'Apa hasil model?')
        self.assertIn(4,r['parsed']['source_items'][0]['pdf_pages'])

    def test_facility_identity_includes_technology_and_name(self):
        from ngo_source_facts import facility_names_grounded,different_named_facility
        proof='PLTSa Putri\nCahaya membuang residu di sungai.'
        self.assertFalse(facility_names_grounded('Debu PLTSa Timur merugikan warga.',proof))
        self.assertTrue(facility_names_grounded('Residu PLTSa Putri Cahaya dibuang di sungai.',proof))
        self.assertTrue(different_named_facility('Apa dampak PLTU Timur terhadap udara?',proof))
        self.assertFalse(different_named_facility('Apa dampak PLTSa Putri Cahaya?',proof))

    def test_report_relative_months_do_not_become_current_months(self):
        from ngo_source_facts import report_relative_period
        self.assertEqual(report_relative_period('Hutan dibuka dalam lima bulan terakhir.'),
                         'Hutan dibuka dalam periode lima bulan yang dibahas laporan.')
        self.assertEqual(report_relative_period('Hutan dibuka selama 2021–2025.'),
                         'Hutan dibuka selama 2021–2025.')

    def test_sample_count_table_cannot_be_labeled_concentration(self):
        from ngo_source_facts import table_label
        finding='Seluruh 23 sampel ikan mengandung logam berat.'
        self.assertEqual(table_label('Kadar logam berat',{'unit':'samples'},finding),finding)
        self.assertEqual(table_label('Kadar logam berat',{'unit':'samples'}),'Jumlah sampel')

    def test_two_prose_columns_keep_reading_order_and_all_words(self):
        p=Page([])
        for i in range(12):
            p.put(f'Warga sekitar melaporkan debu lokal {i}',40,100+i*15)
            p.put(f'Perkebunan energi berada wilayah lain {i}',320,100+i*15)
        r=read_columns(p);self.assertIsNotNone(r)
        self.assertLess(r['text'].index('debu lokal 11'),r['text'].index('Perkebunan energi'))
        self.assertEqual(Counter(r['text'].split()),Counter(w['text'] for w in p.words))

    def test_numeric_table_is_not_read_as_two_prose_columns(self):
        p=Page([])
        for i in range(12):
            p.put(f'Tahun {2000+i} 123 456',40,100+i*15)
            p.put('789 123 456 789',320,100+i*15)
        self.assertIsNone(read_columns(p))

    def test_one_column_preserves_ordinary_line_order(self):
        p=Page([])
        for i in range(12):p.put('Warga melaporkan perubahan kondisi lingkungan di wilayah penelitian pada tahun berjalan',40,100+i*15)
        self.assertIsNone(read_columns(p))

    def test_method_context_is_anchored_and_does_not_claim_universal_applicability(self):
        text='Metode penelitian menggunakan model IRIO untuk mengestimasi dampak ekonomi proyek.'
        parent={'parent_id':'p','pdf_page':4,'page_side':'full','start':100,'text':text,'metadata':{'content_kind':'prose_or_unclassified'}}
        methods=method_evidence({'parents':[parent]},9)
        self.assertEqual(methods[0]['text'],text);self.assertEqual(methods[0]['start'],100)
        self.assertIn('must_be_matched',methods[0]['applicability'])
        introductory=method_evidence({'parents':[parent]},3)
        self.assertTrue(introductory[0]['method_introduction'])
        self.assertIn('must_be_matched',introductory[0]['applicability'])
        distant=method_evidence({'parents':[parent]},30)
        self.assertTrue(distant[0]['method_introduction'])
        self.assertIn('must_be_matched',distant[0]['applicability'])


class MethodReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_projection_does_not_need_invented_method_page(self):
        text='Pendapatan petani di NTT diproyeksikan berkurang Rp30 juta.'
        f=Finding(text=text,evidence_id='D1')
        fit=FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=True,geography='broader_context',
            activity='same',relation='context_only',outcome_basis='interpretation_only',explanation='Explicit projection',
            supporting_sentence_ids=['S1'],evidence_basis='model_result')
        llm=AsyncMock();llm.astructured_predict.return_value=EvidenceFit(items=[fit])
        found,fits=await check_fits(llm,'Apakah pendapatan telah turun?', [f],lambda fs:[{'support_quote':text,'page_text':text}])
        self.assertEqual(len(found),1);self.assertIn('diproyeksikan',found[0].text)
        self.assertNotIn('skenario pemodelan',found[0].text);self.assertFalse(found[0].method_pages)

    async def test_separate_method_review_catches_indicative_result_sentence(self):
        f=Finding(text='Pendapatan pekerja berkurang Rp30 juta.',evidence_id='D1')
        fit=FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=False,geography='same',
            activity='same',relation='direct_support',outcome_basis='observed_outcome',explanation='Result',
            supporting_sentence_ids=['S1'],evidence_basis='reported')
        methods=[{'method_id':'M1','pdf_page':4,'text':'Penelitian menggunakan model IRIO untuk mengestimasi pendapatan.'}]
        method=MethodBasis(finding_id='F1',basis='model_result',method_context_ids=['M1'],scope_supported=True,explanation='IRIO output')
        llm=AsyncMock();llm.astructured_predict.side_effect=[EvidenceFit(items=[fit]),MethodBasisReview(items=[method])]
        found,fits=await check_fits(llm,'Proyek menurunkan pendapatan.',[f],lambda fs:[{'support_quote':f.text,'page_text':f.text,'method_evidence':methods}])
        self.assertIn('pemodelan',found[0].text);self.assertEqual(fits[0].relation,'context_only')
        self.assertEqual(found[0].method_pages,[4])

    async def test_model_result_keeps_qualification_method_page_and_causal_limit(self):
        f=Finding(text='Pendapatan pekerja berkurang Rp30 juta pada tahun pembangunan.',evidence_id='D1')
        quote=f.text
        methods=[{'method_id':'M1','pdf_page':4,'text':'Metode menggunakan model IRIO untuk mengestimasi dampak pendapatan.'}]
        support=lambda fs:[{'support_quote':quote,'support_context':quote,'page_text':quote,'method_evidence':methods} for _ in fs]
        fit=FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=False,
            geography='same',activity='same',relation='direct_support',outcome_basis='observed_outcome',
            supporting_sentence_ids=['S1'],explanation='Model result.',evidence_basis='model_result',method_context_ids=['M1'])
        llm=AsyncMock();llm.astructured_predict.return_value=EvidenceFit(items=[fit])
        found,fits=await check_fits(llm,'Proyek ini telah menyebabkan pendapatan pekerja menurun.',[f],support)
        self.assertEqual(len(found),1);self.assertIn('pemodelan',found[0].text)
        self.assertEqual(found[0].method_pages,[4]);self.assertEqual(fits[0].relation,'context_only')
        self.assertEqual(fits[0].outcome_basis,'interpretation_only')

    async def test_unknown_method_reference_cannot_qualify_a_result(self):
        f=Finding(text='Pendapatan menurun Rp30 juta.',evidence_id='D1')
        fit=FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=False,geography='same',
            activity='same',relation='context_only',outcome_basis='interpretation_only',explanation='Model',
            supporting_sentence_ids=['S1'],evidence_basis='model_result',method_context_ids=['M99'])
        llm=AsyncMock();llm.astructured_predict.return_value=EvidenceFit(items=[fit])
        found,_=await check_fits(llm,'Bagaimana pendapatan?', [f],lambda fs:[{'support_quote':f.text,'page_text':f.text}])
        self.assertFalse(found)
