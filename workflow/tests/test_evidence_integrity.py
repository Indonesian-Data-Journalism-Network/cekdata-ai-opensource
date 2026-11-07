import unittest
from unittest.mock import patch
from types import SimpleNamespace
from ngo_answer import requested,fallback_requested,Finding,public_evidence,DocumentAnswer,supported_findings
from ngo_source_facts import quantities,source_quantity
from ngo_numeric_claim import eligible,compare,NumberMatch
from ngo_entities import aliases,merge_rows
from ngo_combined import summary_errors


class EvidenceIntegrityTests(unittest.TestCase):
    def test_mixed_narrative_and_statistics(self):
        self.assertTrue(requested('Apa persoalan pertambangan emas di Pulau Melati? Bagaimana kehilangan tutupan pohonnya?'))
        self.assertTrue(fallback_requested('Ceritakan perubahan kehidupan warga.',SimpleNamespace(needs_reports=True,indicator_ids=['loss'],clarification='')))
        self.assertFalse(requested('Berapa kehilangan tutupan pohon akibat kebakaran pada 2024 menurut GFW?'))

    def test_count_population_claim_and_false_control(self):
        source='Sekitar 27 orang dari 620 jiwa warga Dusun Melati mengalami bronkitis.'
        f=Finding(text=source,evidence_id='D1',validated_source_text=source)
        m=NumberMatch(report_content_only=True,all_components_covered=True,finding_id='F1',claim_quantity='C1',source_quantity='Q1',same_measure=True,same_population=True,same_place=True,same_time=True)
        for count,expected in [(27,'Benar'),(270,'Salah')]:
            q=f'Benarkah laporan menyebut sekitar {count} dari 620 warga Dusun Melati mengalami bronkitis?'
            self.assertTrue(eligible(q));self.assertEqual(compare(m,q,f),expected)
        self.assertEqual(source_quantity(source,source)['basis'],'620 orang')
        self.assertEqual(len(quantities('12 kasus dan 24 kunjungan')),2)
        self.assertEqual(quantities('tahun 2025 halaman 35'),[])
        two='27 orang dari 620 orang mengalami penyakit.'
        self.assertIsNotNone(source_quantity(two,two))

    def test_health_passage_survives_many_land_passages(self):
        text=('Di Dusun Melati, sebanyak 27 warga mengalami penyakit bronkitis. Mereka bekerja sebagai petani. '
              + ' '.join(f'PLTU Mawar memakai lahan {n} hektar untuk kegiatan biomassa dan percontohan penanaman.' for n in range(10,22)))
        p={'evidence_id':'D1','sha256':'x','title':'Kajian','page_text':text}
        public=public_evidence([p],'Apa dampak PLTU Mawar terhadap kesehatan dan pekerjaan warga? Jelaskan dengan angka.')
        self.assertTrue(any('bronkitis' in x['text'] for x in public[0]['passages']))

    def test_facility_inheritance_stops_at_next_heading(self):
        text='Warga Dusun Melati melaporkan sebanyak 27 orang mengalami gangguan kesehatan akibat debu. Mereka tinggal di belakang wilayah PLTU dan melaporkan kejadian kepada pengelola.'
        pages=[{'pdf_page':1,'text':'PLTU Mawar, Provinsi Contoh\nUraian fasilitas.'},{'pdf_page':2,'text':text}]
        p={'evidence_id':'D1','sha256':'x','title':'Kajian','page_text':text,'pdf_page':2,'provider':'test','document_id':'test'}
        with patch('ngo_answer.source_pages',return_value=pages):public_evidence([p],'Dampak PLTU Mawar')
        self.assertEqual(p['facility_scope']['text'],'PLTU Mawar')
        f=Finding(text='Warga Dusun Melati di sekitar PLTU Mawar melaporkan sebanyak 27 orang mengalami gangguan kesehatan akibat debu.',evidence_id='D1',passage_id=p['passages'][0]['passage_id'])
        self.assertTrue(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))
        p['facility_scope']['text']='PLTU Kenanga'
        self.assertFalse(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))

    def test_model_qualification_cannot_disappear(self):
        text='Dalam skenario pemodelan, kerugian ekonomi diperkirakan Rp4 triliun.'
        f=Finding(text=text,evidence_id='D1',support_quote=text)
        self.assertTrue(summary_errors('Kerugian ekonomi sebesar Rp4 triliun.',[f],{'reports':[]}))
        self.assertFalse(summary_errors('Dalam skenario pemodelan, kerugian ekonomi diperkirakan Rp4 triliun.',[f],{'reports':[]}))

    def test_statement_cannot_become_model_estimate(self):
        source='Komisi menyatakan bahwa polusi pembangkit berdampak pada kesehatan.'
        f=Finding(text=source,evidence_id='D1',support_quote=source)
        self.assertTrue(summary_errors('Pernyataan komisi sebagai estimasi dampak.',[f],{'reports':[]}))
        self.assertFalse(summary_errors('Pernyataan komisi bukan estimasi pemodelan.',[f],{'reports':[]}))

    def test_multiple_measures_cannot_become_one_mislabeled_table_row(self):
        source='Sebanyak 620 ribu hari kerja hilang dan biaya kesehatan mencapai Rp12 triliun.'
        self.assertIsNone(source_quantity(source,source))
        self.assertEqual(source_quantity('Terdapat 92 pasien.','Terdapat 92 pasien.')['display'],'92 pasien')

    def test_alias_merges_sources_not_different_periods_or_units(self):
        e=[{'page_text':'PT Hutan Sejahtera (HS) mengelola konsesi.'}]
        rows=[['Konsesi PT HS 2020','100 hektar','[1]'],['Konsesi PT Hutan Sejahtera 2020','100 hektar','[2]'],['Konsesi PT HS 2024','100 hektar','[3]'],['Konsesi PT HS 2020','100 persen','[4]']]
        merged=merge_rows(rows,e)
        self.assertEqual(len(merged),3);self.assertEqual(merged[0][2],'[1][2]')
        self.assertEqual(aliases(e+[{'page_text':'PT Harta Sentosa (HS) bergerak di bidang lain.'}]),{})

    def test_numeric_recovery_keeps_counterevidence(self):
        from ngo_source_facts import report_count_excerpts
        q='Benarkah laporan menyebut 270 dari 620 warga Dusun Melati mengalami bronkitis?'
        source='Warga Dusun Melati tinggal dekat pabrik. Sekitar 27 orang dari 620 jiwa mengalami bronkitis.'
        self.assertTrue(any('27 orang' in text for text in report_count_excerpts(source,q)))

    def test_alias_parentheses_and_explicit_district_without_word_data(self):
        from ngo_entities import canonical
        from ngo_gfw_context import plan
        from datetime import date
        self.assertEqual(canonical('PT Hutan Sejahtera (PT HS)',{'pt hs':'PT Hutan Sejahtera'}),'PT Hutan Sejahtera')
        family={'indicator_id':'loss','member_ids':['gfw-tree-cover-loss'],'areas':['Kabupaten Kepulauan Mawar, Contoh'],'area_aliases':{},'years':[2021,2022]}
        query=plan('Persoalan tambang di Pulau Mawar dan bagaimana kehilangan tutupan pohon di Kabupaten Kepulauan Mawar selama 2021–2022?',[family],date(2026,11,6))
        self.assertEqual(query.areas,['Kabupaten Kepulauan Mawar, Contoh'])
        self.assertIsNone(plan('Kehilangan tutupan pohon di Pulau Mawar selama 2021–2022?',[family],date(2026,11,6)))

    def test_hamlets_and_order_are_not_interchangeable_with_completed_action(self):
        from ngo_metadata import explicit_places
        from ngo_source_facts import unbacked_outcome,event_scope_valid
        self.assertEqual(explicit_places('Dusun Mawar')[0]['kind'],'hamlet')
        text='Warga Dusun Mawar mengalami gangguan air. Di Dusun Melati lahan pertanian dibayar murah.'
        self.assertFalse(event_scope_valid('Dampak di Dusun Mawar','Lahan warga Dusun Mawar dibayar murah.','Di Dusun Melati lahan pertanian dibayar murah.',text))
        self.assertTrue(unbacked_outcome('Pengadilan telah mencabut izin.','Pengadilan memerintahkan pencabutan izin.'))
        self.assertFalse(unbacked_outcome('Pengadilan memerintahkan pencabutan izin.','Pengadilan memerintahkan pencabutan izin.'))


class ClaimConclusionTests(unittest.IsolatedAsyncioTestCase):
    async def test_free_summary_cannot_reverse_checked_verdict(self):
        import json
        from datetime import date
        from unittest.mock import AsyncMock
        from ngo_answer import AnswerSummary,EvidenceReview
        from ngo_evidence_policy import ClaimAssessment,FindingFit
        from ngo_combined import answer
        q='Benarkah seluruh warga menjadi sejahtera karena proyek tersebut?'
        source='Hasil pemodelan memperkirakan penurunan output ekonomi sebesar Rp4 triliun. Estimasi ini berlaku pada wilayah provinsi dalam skenario kajian.'
        page={'evidence_id':'D1','sha256':'a','document_id':'d','title':'Kajian','host_organization':'Peneliti','page_text':source,'pdf_page':1,'page_side':'full','source_url':'https://example.org/report','download_url':'https://example.org/report.pdf'}
        public=public_evidence([page],q)
        f=Finding(text=source,evidence_id='D1',support_quote=source,validated_source_text=source)
        fit=FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=False,geography='broader_context',activity='same',relation='context_only',outcome_basis='interpretation_only',evidence_basis='model_result',explanation='Model regional')
        reason='Belum ada pengukuran perubahan kesejahteraan warga yang sebanding.'
        class AI:
            async def astructured_predict(self,schema,prompt,**kwargs):
                if schema is DocumentAnswer:return DocumentAnswer(kind='question',answer='',findings=[f])
                if schema is ClaimAssessment:return ClaimAssessment(verdict='Tidak dapat diverifikasi',reason=reason,supporting_finding_ids=[],contradicting_finding_ids=[],supported_components=[],missing_components=['kesejahteraan'],coverage='none',causal_support='not_established',contradiction_explanation='')
                if schema is AnswerSummary:return AnswerSummary(verdict='Tidak dapat diverifikasi',answer='Seluruh warga tidak menjadi sejahtera akibat proyek ini.')
                if schema is EvidenceReview:return EvidenceReview(supported=True)
                raise AssertionError(schema)
        with patch('ngo_combined.check_fits',AsyncMock(return_value=([f],[fit]))):
            result=await answer(AI(),q,date(2026,11,6),[page],public,None,'claim')
        self.assertEqual(result['parsed']['alasan'],reason)
        self.assertEqual(result['parsed']['kesimpulan'],'')
        self.assertEqual(result['answer'].count(reason),1)
        self.assertNotIn('Seluruh warga tidak',result['answer'])

if __name__=='__main__':unittest.main()
