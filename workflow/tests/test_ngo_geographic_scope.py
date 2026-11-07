import unittest
from unittest.mock import AsyncMock, patch
from ngo_geography_policy import scope_decision


class GeographicScopeTests(unittest.TestCase):
    def decision(self, question, proof, finding=None, page=''):
        return scope_decision(question, finding or proof, proof, page or proof)[0]

    def test_sibling_province_english_header(self):
        proof='The company reported compensation for residents.'
        page='Overview: Timber plantation concession in Central\nKalimantan, covering 20,355 hectares. '+proof
        self.assertEqual(self.decision('Apa dampak perkebunan kayu di Kalbar?',proof,page=page),'different')
        page=page.replace(proof,'The watershed supports forests in Kalimantan. Buyers purchase timber from PT Contoh Prima. '+proof)
        self.assertEqual(self.decision('Apa dampak perkebunan kayu di Kalbar?',proof,page=page),'different')

    def test_original_address_can_link_village_from_another_page(self):
        from ngo_geography_policy import document_addresses
        addresses=document_addresses([{'pdf_page':12,'text':'Desa Contoh Hilir di Kecamatan Contoh Hulu, Kabupaten Ketapang menjadi lokasi kegiatan.'}])
        proof='Di Desa Contoh Hilir, warga menolak penggusuran.'
        self.assertEqual(scope_decision('Apa dampak di Kabupaten Ketapang?',proof,proof,addresses=addresses)[0],'within_requested_area')
        unrelated=document_addresses([{'pdf_page':12,'text':'Desa Contoh Hilir menolak proyek. Laporan juga membahas Kabupaten Ketapang.'}])
        self.assertEqual(scope_decision('Apa dampak di Kabupaten Ketapang?',proof,proof,addresses=unrelated)[0],'different')
        conflicting=addresses+document_addresses([{'pdf_page':13,'text':'Desa Contoh Hilir, Kabupaten Garut menjadi lokasi lain.'}])
        self.assertEqual(scope_decision('Apa dampak di Kabupaten Ketapang?',proof,proof,addresses=conflicting)[0],'unknown')

    def test_other_island_is_not_broader_context(self):
        self.assertEqual(self.decision('Apa dampaknya di Pulau Obi?',
            'Di Teluk Weda, warga kehilangan sumber air.'),'different')

    def test_neighboring_local_event_cannot_inherit_query(self):
        proof='Di Rempang, warga menolak relokasi.'
        self.assertEqual(self.decision('Apa konflik di Pundenrejo?',proof,
                                      'Warga Pundenrejo menolak relokasi.'),'different')

    def test_localities_are_not_silently_assigned_to_another_district(self):
        for question,proof in [
            ('Apa dampak di Halmahera Timur?', 'Di Kecamatan Weda Tengah, warga kehilangan akses air.'),
            ('Apa dampak di Kabupaten Morowali?', 'Di Pomalaa, nelayan kehilangan pendapatan.'),
            ('Apa dampak di Bombana?', 'Di Talaga Raya, Kabupaten Buton Tengah, 245 keluarga terdampak.'),
        ]:
            with self.subTest(question=question):
                self.assertEqual(self.decision(question,proof),'different')

    def test_regional_observation_is_not_local_evidence(self):
        proof='Di Maluku Utara dan Sulawesi Tengah, warga menghadapi pencemaran air.'
        self.assertEqual(self.decision('Apa dampak di Kabupaten Halmahera Tengah?',proof),'broader_context')
        self.assertEqual(self.decision('Apa dampak di Kabupaten Halmahera Tengah?',proof,
            'Di Kabupaten Halmahera Tengah, warga menghadapi pencemaran air.'),'narrowed')

    def test_verbal_quantity_retains_all_areas(self):
        proof='Ribuan hektare hutan rusak di Raja Ampat dan Sulawesi Tenggara.'
        self.assertEqual(self.decision('Apa dampak di Raja Ampat?',proof,
            'Ribuan hektare hutan rusak di Raja Ampat.'),'narrowed')
        self.assertEqual(self.decision('Apa dampak di Raja Ampat?',proof),'broader_context')

    def test_national_report_cannot_become_local(self):
        proof='Di Indonesia, tambang meninggalkan lubang tanpa reklamasi.'
        self.assertEqual(self.decision('Apa dampak di Raja Ampat?',proof),'broader_context')
        self.assertEqual(self.decision('Apa dampak di Raja Ampat?',proof,
            'Di Raja Ampat, tambang meninggalkan lubang tanpa reklamasi.'),'narrowed')

    def test_caption_does_not_locate_generic_event(self):
        proof='Foto: Pulau Gam, Raja Ampat. Perkebunan biomassa menggusur lahan warga.'
        self.assertEqual(self.decision('Apa dampak di Raja Ampat?',proof,
            'Perkebunan biomassa menggusur lahan warga di Raja Ampat.'),'unknown')

    def test_explicit_address_proves_local_relationship(self):
        proof='Warga Pulau Kabaena kehilangan lahan.'
        page='Penelitian di Pulau Kabaena, Kabupaten Bombana. '+proof
        self.assertEqual(self.decision('Apa dampak di Bombana?',proof,page=page),'within_requested_area')
        self.assertEqual(self.decision('Apa dampak di Bombana?',proof),'different')

    def test_reference_relationship_and_new_locations(self):
        for question,proof,expected in [
            ('Apa dampak di Jawa Barat?','Di Kabupaten Garut, warga kehilangan akses air.','within_requested_area'),
            ('Apa dampak di Kabupaten Garut?','Di Jawa Barat, warga kehilangan akses air.','broader_context'),
            ('Apa dampak di Kabupaten Garut?','Di Kabupaten Sleman, warga kehilangan akses air.','different'),
            ('Apa dampak di Kabupaten Bombana?','Di Sulawesi, perempuan menanggung beban perawatan.','broader_context'),
            ('Apa dampak di Aceh dan Riau?','Di Riau, warga kehilangan lahan.','same'),
            ('Apa dampak pertambangan?','Warga kehilangan lahan.','unscoped'),
        ]:
            with self.subTest(question=question,proof=proof):
                self.assertEqual(self.decision(question,proof),expected)

    def test_summary_must_preserve_validated_regional_scope(self):
        from ngo_answer import Finding
        from ngo_combined import summary_errors
        from ngo_geography_policy import places
        f=Finding(text='Di Maluku Utara, perempuan kehilangan akses pangan lokal.', evidence_id='D1')
        f._geographic_scope={'relation':'broader_context','places':places(f.text)}
        self.assertTrue(summary_errors('Perempuan kehilangan akses pangan lokal di Halmahera Tengah.',[f],{}))
        self.assertFalse(summary_errors('Di Maluku Utara, perempuan kehilangan akses pangan lokal.',[f],{}))


class GeographicIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_cannot_override_conflicting_source_scope(self):
        from ngo_answer import Finding
        from ngo_evidence_policy import check_fits, EvidenceFit, FindingFit
        f=Finding(text='Perkebunan kayu menyebabkan konflik lahan di Kalimantan Tengah.',evidence_id='D1')
        row=dict(finding_id='F1',page_text=f.text,source_sentences=[{'sentence_id':'S1','text':f.text}])
        llm=AsyncMock()
        llm.astructured_predict.return_value=EvidenceFit(items=[FindingFit(finding_id='F1',faithful=True,
            same_event=True,measure_supported=True,geography='broader_context',activity='same',
            relation='context_only',outcome_basis='not_outcome',explanation='Model incorrectly approves another province.',
            supporting_sentence_ids=['S1'])])
        with patch('ngo_evidence_policy.evidence_rows',return_value=[row]),patch('ngo_evidence_policy.sentence_support_valid',return_value=True):
            findings,_=await check_fits(llm,'Apa dampak perkebunan kayu di Kalimantan Barat?',[f],{})
        self.assertEqual(findings,[])
