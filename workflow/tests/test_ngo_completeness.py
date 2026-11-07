"""Generic completeness regressions: no production place/company exceptions."""
import unittest
from ngo_answer import Finding, DocumentAnswer, supported_findings, render
from ngo_evidence_policy import FindingFit, sentence_support_valid
from ngo_geography_policy import document_addresses, address_supports, scope_decision, measurement_clauses


class CompletenessTests(unittest.TestCase):
    def test_explicit_address_allows_parent_in_grounding_and_final_render(self):
        for district in ('Garut','Ketapang','Sleman'):
            with self.subTest(district=district):
                quote='Warga Desa Suka Hijau melaporkan kehilangan lahan pertanian seluas 17,5 ha setelah perluasan perkebunan kayu.'
                addresses=document_addresses([{'pdf_page':2,'text':f'Desa Suka Hijau, Kecamatan Suka Rukun, Kabupaten {district} merupakan lokasi penelitian.'}])
                page=dict(evidence_id='D1',sha256='fixture',document_id='fixture',title='Laporan contoh',
                          host_organization='Organisasi Contoh',source_url='https://example.org/report',download_url='https://example.org/report.pdf',
                          pdf_page=4,printed_page='4',page_side='full',page_text=quote+' Penelitian ini menggunakan wawancara warga.',
                          source_addresses=addresses)
                finding=Finding(text=quote.replace('Desa Suka Hijau',f'Desa Suka Hijau, Kecamatan Suka Rukun, Kabupaten {district}'),evidence_id='D1',support_quote=quote)
                answer=DocumentAnswer(kind='question',answer='Temuan warga tersedia.',findings=[finding])
                self.assertEqual(len(supported_findings(answer,[page])),1)
                result=render(answer,[page],'Apa dampak perkebunan kayu?')
                self.assertIn('17,5',result['answer'])
                page['source_addresses']=[]
                self.assertEqual(supported_findings(answer,[page]),[])

    def test_unrelated_address_cannot_rescue_a_finding(self):
        addresses=document_addresses([{'pdf_page':2,'text':'Desa Suka Merah, Kabupaten Garut menjadi lokasi lain.'}])
        self.assertFalse(address_supports('Garut','Warga Desa Suka Hijau kehilangan lahan.',addresses))
        ambiguous=document_addresses([{'pdf_page':2,'text':'Desa Suka Hijau, Kecamatan Suka Rukun, Kabupaten Garut menjadi lokasi penelitian. Desa Suka Hijau, Kecamatan Suka Asri, Kabupaten Garut menjadi lokasi lain.'}])
        self.assertFalse(address_supports('Suka Rukun','Warga Desa Suka Hijau kehilangan lahan.',ambiguous))

    def test_line_wrapping_and_peer_lists_do_not_corrupt_addresses(self):
        addresses=document_addresses([{'pdf_page':2,'text':'Desa Suka Hijau, Kecamatan Suka\nRukun, Kabupaten Garut menjadi lokasi penelitian. Peserta datang dari Desa Suka Hijau, Desa Suka Merah dan Desa Suka Biru.'}])
        self.assertTrue(address_supports('Suka Rukun','Warga Desa Suka Hijau kehilangan lahan.',addresses))
        self.assertFalse(address_supports('Suka Merah','Warga Desa Suka Hijau kehilangan lahan.',addresses))
        source='Warga Desa Suka Hijau menolak penggusuran lahan.'
        self.assertEqual(scope_decision('Apa dampak di Garut?','Warga Kabupaten Garut menolak penggusuran lahan.',source,addresses=addresses)[0],'narrowed')

    def test_separately_assigned_values_do_not_become_a_shared_total(self):
        source='Kabupaten Garut kehilangan 121 ha, sedangkan Kabupaten Sleman kehilangan 83 ha pada 2025.'
        finding='Kabupaten Sleman kehilangan 83 ha pada 2025.'
        self.assertNotIn('Garut',measurement_clauses(finding,source))
        self.assertEqual(scope_decision('Berapa kehilangan di Sleman?',finding,source)[0],'same')
        wrong='Kabupaten Garut kehilangan 83 ha pada 2025.'
        self.assertEqual(scope_decision('Berapa kehilangan di Garut?',wrong,source)[0],'different')
        combined='Kabupaten Garut dan Kabupaten Sleman kehilangan total 204 ha pada 2025.'
        self.assertEqual(measurement_clauses('Garut kehilangan 204 ha.',combined),combined)
        self.assertEqual(scope_decision('Berapa kehilangan di Garut?','Kabupaten Garut kehilangan 204 ha.',combined)[0],'narrowed')

    def test_sentence_review_accepts_separate_measurements_and_grounded_parent(self):
        source='Kabupaten Garut kehilangan 121 ha, sedangkan Kabupaten Sleman kehilangan 83 ha pada 2025.'
        f=Finding(text='Kabupaten Sleman kehilangan 83 ha pada 2025.',evidence_id='D1')
        item=FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=False,geography='same',
                        activity='same',relation='context_only',outcome_basis='observed_outcome',explanation='Test',supporting_sentence_ids=['S1'])
        row={'source_sentences':[{'sentence_id':'S1','text':source}], 'page_text':source}
        self.assertTrue(sentence_support_valid(f,row,item))
        source='Desa Suka Hijau mengalami kehilangan 17,5 ha lahan pertanian setelah perluasan perkebunan kayu.'
        f.text='Desa Suka Hijau, Kabupaten Garut mengalami kehilangan 17,5 ha lahan pertanian setelah perluasan perkebunan kayu.'
        row={'source_sentences':[{'sentence_id':'S1','text':source}], 'page_text':source,
             'source_addresses':document_addresses([{'pdf_page':2,'text':'Desa Suka Hijau, Kabupaten Garut menjadi lokasi penelitian.'}])}
        self.assertTrue(sentence_support_valid(f,row,item))
