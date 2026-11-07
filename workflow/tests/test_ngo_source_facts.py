import unittest
from unittest.mock import patch
from ngo_answer import Finding,passages_for
from ngo_source_facts import quantities,source_quantity,quantity_errors,prose_blocks,event_scope_valid
from ngo_numeric_claim import NumberMatch,compare
from ngo_editions import verified_content_groups


class SourceFactsTests(unittest.TestCase):
    def test_percent_bounds_denominator_and_range_survive(self):
        source='Dari 52 orang narasumber, lebih dari 82% menyatakan perekonomian menurun.'
        f='Dari 52 narasumber, lebih dari 82 persen melaporkan penurunan perekonomian.'
        q=source_quantity(f,source)
        self.assertEqual(q['display'],'Lebih dari 82 persen')
        self.assertEqual(q['basis'],'52 narasumber')
        self.assertTrue(quantity_errors('Sebanyak 82 persen melaporkan penurunan.',source))
        self.assertFalse(quantity_errors(f,source))
        for literal in ('kurang dari 17%','setidaknya 23 persen','sekitar 12,5 ha','10–20 ha'):
            q=source_quantity('Luas/nilai '+literal,literal)
            self.assertIsNotNone(q,literal)
            self.assertNotEqual(q['operator'],'eq')

    def test_robust_windows_do_not_merge_neighboring_projects(self):
        page=('Kajian mencakup Kabupaten Solok dan Kabupaten Solok Selatan. '
              'Proyek panas bumi di Gunung Talang, Kabupaten Solok, melahirkan konflik horizontal. '
              'Konflik ini merusak tatanan adat dan sosial masyarakat setempat. '
              'Sementara itu, proyek Muaro Labuh di Kabupaten Solok Selatan menyebabkan debit air berkurang. '
              'Petani mengalami gagal panen dan mengeluhkan intimidasi perusahaan.')
        windows=passages_for({'page_text':page,'evidence_id':'D1'},'Proyek di Kabupaten Solok Selatan')
        self.assertFalse(any('konflik horizontal' in w['text'] and 'debit air' in w['text'] for w in windows))
        self.assertFalse(event_scope_valid('Apa risiko proyek di Kabupaten Solok Selatan?',
            'Proyek ini menimbulkan konflik horizontal.',
            'Konflik ini merusak tatanan adat dan sosial masyarakat setempat.',page))
        self.assertFalse(event_scope_valid('Apa risiko proyek di Kabupaten Solok Selatan?',
            'Proyek di Kabupaten Solok Selatan menimbulkan konflik horizontal.',
            'Konflik ini merusak tatanan adat dan sosial masyarakat setempat.',page))
        self.assertTrue(event_scope_valid('Apa risiko proyek di Kabupaten Solok Selatan?',
            'Petani mengalami gagal panen.',
            'Petani mengalami gagal panen dan mengeluhkan intimidasi perusahaan.',page))

    def test_number_checks_use_same_measure_and_exact_source_anchor(self):
        f=Finding(text='Sebanyak 37,2 persen rumah tangga melaporkan produksi menurun.',evidence_id='D1',
                  validated_source_text='Ada sekitar 37,2% dari rumah tangga menyatakan produksi menurun.')
        m=NumberMatch(report_content_only=True,all_components_covered=True,finding_id='F1',
          claim_quantity='100 persen',source_quantity='sekitar 37,2%',same_measure=True,
          same_population=True,same_place=True,same_time=True)
        self.assertEqual(compare(m,'Laporan menyatakan 100 persen rumah tangga.',f),'Salah')
        m.claim_quantity='37,2 persen'
        self.assertEqual(compare(m,'Laporan menyatakan 37,2 persen rumah tangga.',f),'Benar')
        m.same_population=False
        self.assertIsNone(compare(m,'Laporan menyatakan 37,2 persen rumah tangga.',f))
        m.same_population=True;m.source_quantity='37,9%'
        self.assertIsNone(compare(m,'Laporan menyatakan 37,2 persen rumah tangga.',f))
        m.source_quantity='37,2%';m.report_content_only=False
        self.assertIsNone(compare(m,'Laporan menyatakan 37,2 persen rumah tangga.',f))

    def test_report_number_match_cannot_substitute_another_indicator_or_population(self):
        f=Finding(text='Dari 52 narasumber, lebih dari 82 persen menyatakan perekonomian rumah tangga menurun.',
                  evidence_id='D1',validated_source_text='Dari 52 narasumber, lebih dari 82% menyatakan perekonomian rumah tangga menurun.')
        m=NumberMatch(report_content_only=True,all_components_covered=True,finding_id='F1',
          claim_quantity='C1',source_quantity='Q2',same_measure=True,
          same_population=True,same_place=True,same_time=True)
        self.assertIsNone(compare(m,'Laporan mencatat 45,8 persen rumah tangga mengalami penurunan produksi pertanian.',f))
        self.assertIsNone(compare(m,'Laporan mencatat 45,8 persen rumah tangga mengalami penurunan pendapatan.',f))
        f=Finding(text='Sebanyak 37,2 persen rumah tangga mengalami produksi menurun.',evidence_id='D1',
                  validated_source_text='Sebanyak 37,2% mengalami produksi menurun, sedangkan 42,1% melaporkan konflik.')
        m.source_quantity='Q2'
        self.assertIsNone(compare(m,'Laporan mencatat 37,2 persen rumah tangga mengalami penurunan produksi.',f))
        m.source_quantity='Q1'
        self.assertEqual(compare(m,'Laporan mencatat 37,2 persen rumah tangga mengalami penurunan produksi.',f),'Benar')

    def test_summary_answers_the_requested_sample_instead_of_another_survey(self):
        from ngo_combined import fallback_summary,summary_errors
        question='Apa perubahan pendapatan dalam wawancara 52 narasumber?'
        findings=[Finding(text='Sebanyak 38,2 persen rumah tangga melaporkan pendapatan menurun.',evidence_id='D1'),
                  Finding(text='Lebih dari 82 persen dari 52 narasumber melaporkan penurunan perekonomian rumah tangga.',evidence_id='D2')]
        summary=fallback_summary(findings,{'D1':{'host_organization':'Contoh'},'D2':{'host_organization':'Contoh'}},question)
        self.assertIn('52 narasumber',summary)
        self.assertIn('82 persen',summary)
        self.assertTrue(summary_errors('Laporan Contoh mencatat 38,2 persen rumah tangga.',findings,{},question))

    def test_forest_stock_area_is_not_actual_converted_area(self):
        from ngo_source_facts import quantity_relation_supported
        source='Analisis menunjukkan 265.208 hektar dari area tersebut merupakan hutan alam. Alih fungsi menjadi kebun tebu berpotensi melepas emisi.'
        self.assertFalse(quantity_relation_supported('Sebanyak 265.208 hektar hutan alam dialihfungsikan menjadi kebun tebu.',source))
        self.assertTrue(quantity_relation_supported('Sebanyak 265.208 hektar dari area tersebut merupakan hutan alam.',source))
        self.assertTrue(quantity_relation_supported('Sebanyak 265.208 hektar hutan alam akan dialihfungsikan menjadi kebun tebu.',source))
        self.assertTrue(quantity_relation_supported('Seluas 1.340 hektar hutan dibuka.', 'Perusahaan telah membuka 1.340 hektar hutan.'))

    def test_synthesis_cannot_attach_one_villages_protest_date_to_another(self):
        from ngo_combined import summary_errors
        f=Finding(text='Masyarakat melakukan penolakan di Desa Sekucing Kualan pada Juli dan September 2024.',evidence_id='D1')
        self.assertTrue(summary_errors('Masyarakat Desa Kualan Hilir melakukan protes pada Juli dan September 2024.',[f],{},'Bagaimana konflik masyarakat?'))
        self.assertFalse(summary_errors('Masyarakat Desa Sekucing Kualan melakukan protes pada Juli dan September 2024.',[f],
                         {'text':f.text},'Bagaimana konflik masyarakat?'))

    def test_nearby_province_list_cannot_relocate_a_local_observation(self):
        from ngo_source_facts import local_geography_supported
        proof=('Operasi pertambangan terlihat di Sulawesi Tengah, Sulawesi Tenggara, dan Maluku Utara. '
               'Studi WALHI menemukan limbah panas di Sulawesi Tengah wilayah laut Desa Fatufia Kecamatan Bahodopi.')
        from ngo_metadata import Gazetteer
        # Supply the boundary names explicitly, as production imports normally do.
        gaz=Gazetteer([{'name': name, 'kind': 'province', 'id': 'test:'+str(i),
                       'parent_id': 'IDN', 'parent_name': 'Indonesia', 'aliases': [name],
                       'reference': 'test fixture'}
                      for i,name in enumerate(['Sulawesi Tengah','Sulawesi Tenggara','Maluku Utara'])])
        with patch('ngo_source_facts.boundary_gazetteer',return_value=gaz):
            self.assertFalse(local_geography_supported('Studi di Desa Fatufia Kecamatan Bahodopi, Sulawesi Tengah, menunjukkan dampak pertambangan di Sulawesi Tenggara.',proof))
            self.assertTrue(local_geography_supported('Studi di Desa Fatufia Kecamatan Bahodopi, Sulawesi Tengah, menemukan limbah panas.',proof))

    def test_household_survey_respondents_are_not_assumed_to_be_a_different_population(self):
        from ngo_source_facts import population_supported,table_label
        source='Dari 618 responden, sebanyak 38,2% rumah tangga melaporkan pendapatan menurun.'
        self.assertTrue(population_supported('Sebanyak 38,2 persen rumah tangga melaporkan pendapatan menurun.',source))
        self.assertTrue(table_label('Rumah tangga yang melaporkan penurunan',{'basis':'618 responden'}).startswith('Rumah tangga'))
        self.assertFalse(population_supported('Lebih dari 82 persen rumah tangga melaporkan ekonomi menurun.',
                          'Dari 52 narasumber, lebih dari 82% melaporkan ekonomi menurun.'))

    def test_commodity_of_another_paragraph_is_not_assigned_to_this_event(self):
        from ngo_source_facts import activity_context
        q='Apakah perkebunan sawit meningkatkan kesejahteraan?'
        self.assertIn('PSN',activity_context(q,'Perempuan sulit memperoleh sagu.',
                      'Pertemuan perempuan korban PSN Merauke.','Audit PSN'))
        self.assertIn('pangan/energi',activity_context(q,'Lahan adat dibuka.',
                      'Pembangunan perkebunan tebu di Merauke.'))
        self.assertEqual(activity_context(q,'Kebun kelapa sawit membuka lahan.',
                      'Pembahasan perkebunan sawit.'),'')

    def test_missing_bounds_restored_without_changing_values(self):
        from ngo_source_facts import restore_quantity_bounds,table_label,unbacked_outcome
        source='Dari 52 narasumber, lebih dari 82% mengalami perekonomian menurun.'
        self.assertEqual(restore_quantity_bounds('Sebanyak 82 persen mengalami penurunan.',source),
                         'lebih dari 82 persen mengalami penurunan.')
        self.assertEqual(restore_quantity_bounds('Sebanyak 91 persen mengalami penurunan.',source),
                         'Sebanyak 91 persen mengalami penurunan.')
        label=table_label('Persentase rumah tangga yang melaporkan penurunan perekonomian',{'basis':'52 narasumber'})
        self.assertTrue(label.startswith('Narasumber yang'))
        self.assertTrue(unbacked_outcome('Ekspansi menyebabkan konflik, bukan peningkatan kesejahteraan warga.',
                                        'Ekspansi identik dengan konflik dan perampasan tanah.'))

    def test_source_threshold_does_not_disprove_a_compatible_number(self):
        f=Finding(text='Lebih dari 70 persen.',evidence_id='D1',validated_source_text='Lebih dari 70 persen.')
        m=NumberMatch(report_content_only=True,all_components_covered=True,finding_id='F1',
          claim_quantity='90 persen',source_quantity='Lebih dari 70 persen',same_measure=True,
          same_population=True,same_place=True,same_time=True)
        self.assertEqual(compare(m,'Laporan mencatat 90 persen.',f),'Tidak dapat diverifikasi')

    def test_editions_need_colophon_and_content_not_translated_titles(self):
        docs=[{'id':'a','provider':'org','download_url':'https://example.org/berbeda.pdf'},
              {'id':'b','provider':'org','download_url':'https://example.org/unrelated-title.pdf'},
              {'id':'c','provider':'other','download_url':'https://example.org/c.pdf'}]
        body=' 17,3% 22,8% 36,4% 41,9% 53,2% 68,7% 79,5% 82,6% 97,1%'
        texts={'a':'Penulis:\nBudi Contoh\nSari Contoh\nPenyunting:\nEditor Contoh\nEdisi kedua: 20 Oktober 2024'+body,
               'b':'Authors:\nBudi Contoh\nSari Contoh\nEditors:\nEditor Contoh\nSecond edition: 20 October 2024'+body,
               'c':'Authors:\nBudi Contoh\nSari Contoh\nEditors:\nEditor Contoh\nSecond edition: 20 October 2024'+body}
        load=lambda d:[{'text':texts[d['id']]}]
        groups=verified_content_groups(docs,load)
        self.assertEqual([[m['document_id'] for m in g['members']] for g in groups],[['a','b']])
        texts['b']=texts['b'].replace(body,' 11,7% 25,6%')
        self.assertFalse(verified_content_groups(docs,load))

if __name__=='__main__':unittest.main()

class NumericAnswerFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_conflicting_model_relations_cannot_undo_a_checked_report_number(self):
        import json
        from ngo_answer import DocumentAnswer,public_evidence
        from ngo_combined import answer
        from ngo_evidence_policy import EvidenceFit,FindingFit,ClaimAssessment
        original=('Survei menelaah perubahan produksi di Pulau Contoh. '
                  'Ada sekitar 37,2% dari rumah tangga di Pulau Contoh menyatakan produksi pertanian dan perikanan menurun. '
                  'Temuan menggambarkan jawaban responden dan tidak mengukur semua penduduk.')
        for amount,expected in [('37,2','Benar'),('100','Salah'),('21','Salah')]:
            evidence=[{'evidence_id':'D1','sha256':'a','document_id':'test','host_organization':'Organisasi Contoh',
              'title':'Survei produksi Pulau Contoh','pdf_page':7,'page_side':'full','page_text':original,
              'source_url':'https://example.org/report','download_url':'https://example.org/report.pdf'}]
            question=f'Benarkah laporan Organisasi Contoh menyatakan {amount} persen rumah tangga di Pulau Contoh mengalami penurunan produksi pertanian dan perikanan?'
            public=public_evidence(evidence,question)
            class AI:
                async def astructured_predict(self,schema,prompt,**kwargs):
                    if schema.__name__=='DocumentAnswer':
                        window=next(w for w in public[0]['passages'] if '37,2%' in w['text'])
                        return DocumentAnswer(kind='question',answer='',findings=[Finding(evidence_id='D1',
                          passage_id=window['passage_id'],text='Sebanyak 37,2 persen rumah tangga di Pulau Contoh menyatakan produksi pertanian dan perikanan menurun.',
                          measure='Rumah tangga yang melaporkan produksi menurun')])
                    if schema.__name__=='EvidenceFit':
                        rows=json.loads(kwargs['evidence'])
                        return EvidenceFit(items=[FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=True,
                          geography='same',activity='same',relation='direct_support',outcome_basis='reported_change',
                          explanation='Source relevant.',supporting_sentence_ids=[s['sentence_id'] for s in rows[0]['source_sentences']])])
                    if schema.__name__=='ClaimAssessment':
                        return ClaimAssessment(verdict='Salah',reason='Model disagrees.',supporting_finding_ids=[],
                          contradicting_finding_ids=['F1'],supported_components=[],missing_components=['Causal study'],
                          coverage='partial',causal_support='not_established',contradiction_explanation='Different number.')
                    if schema.__name__=='NumberMatch':
                        return NumberMatch(report_content_only=True,all_components_covered=True,finding_id='F1',
                          claim_quantity='C1',source_quantity='Q1',same_measure=True,same_population=True,same_place=True,same_time=True)
                    raise AssertionError('A completed numeric comparison must not be regenerated: '+schema.__name__)
            result=await answer(AI(),question,'2026-11-06',evidence,public,None,'claim')
            self.assertEqual(result['parsed']['penilaian'],expected)
            self.assertEqual(result['parsed']['findings_table']['rows'][0][1],'Sekitar 37,2 persen')
            self.assertEqual(result['parsed']['peringatan_editorial'],'')
            self.assertEqual(len(result['parsed']['source_items']),1)
