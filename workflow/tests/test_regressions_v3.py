import unittest,json
from datetime import date
from flow import Intent,Predicate,RequestState,Analysis,Note,assess,render,guard_claim_kind,guard_temporal_scope
from pilot_data import PilotAI,group_catalog
from test_flow import row,intent

class IntentRegressionTests(unittest.TestCase):
    def test_assertions_are_not_lookups(self):
        for question,metric,value in [('Puskesmas di Colomadu pada 2022 ada 3.','value','3'),('Jumlah lulusan SMP di Pamotan naik 21 orang dari 2017 ke 2018.','change','21')]:
            i=intent(kind='lookup',causal=True);guard_claim_kind(i,question)
            self.assertEqual(i.kind,'claim');self.assertEqual(i.predicate.metric,metric);self.assertEqual(i.predicate.threshold,value)

    def test_explanation_cannot_be_forced_to_claim_by_direction(self):
        i=intent(kind='claim',causal=True)
        guard_claim_kind(i,'Kenapa jumlah anggota TNI di Bulakamba menurun?')
        self.assertEqual(i.kind,'explanation');self.assertFalse(i.causal);self.assertIsNone(i.predicate)
        self.assertTrue(i.requires_series)

    def test_two_year_difference_is_not_an_annual_trend(self):
        i=intent(kind='trend',requires_series=True)
        guard_temporal_scope(i,'Berapa selisih jumlah RT antara 2015 dan 2017?')
        self.assertTrue(i.endpoint_difference);self.assertFalse(i.requires_series)
        self.assertEqual((i.kind,i.baseline_year,i.year),('comparison',2015,2017))

    def test_noncausal_claim_cannot_inherit_causal_flag(self):
        i=intent(kind='claim',causal=True)
        guard_claim_kind(i,'Lulusan SD di Lasem terus meningkat.')
        self.assertFalse(i.causal)
        self.assertTrue(i.continuous)
        self.assertIsNotNone(i.predicate)

    def test_question_containing_comparison_is_not_claim(self):
        i=intent(kind='comparison')
        guard_claim_kind(i,'Pada 2022 lebih banyak puskesmas atau puskesmas pembantu?')
        self.assertEqual(i.kind,'comparison')

class CatalogRegressionTests(unittest.TestCase):
    def catalog(self):
        return [dict(indicator_id=str(y),label=f'Banyaknya Anggota TNI Menurut Kecamatan di Kabupaten Brebes {y} — {label}',source='BPS',unit='orang',definition='',populations=['total'],areas=['Bulakamba'],years=[y]) for y,label in [(2018,'Anggota TNI'),(2019,'Jumlah Anggota TNI')]]

    def test_count_prefix_alias_joins_series_without_rewriting_ids(self):
        grouped=group_catalog(self.catalog())
        self.assertEqual(len(grouped),1);self.assertEqual(grouped[0]['member_ids'],['2018','2019'])
        other=self.catalog()+[{**self.catalog()[0],'indicator_id':'different','label':self.catalog()[0]['label'].replace('Anggota TNI','Anggota Polisi')}]
        self.assertEqual(len(group_catalog(other)),2)

    def test_publication_is_resolved_to_known_publisher(self):
        c=group_catalog(self.catalog());c.append({**c[0],'label':'Angka Kelahiran Long Form SP2020 — 15-19','areas':['SLEMAN']})
        ai=PilotAI(None,c)
        self.assertEqual(ai.resolve_sources(['Long Form SP2020']),['BPS'])
        self.assertEqual(ai.resolve_sources(['Unknown agency']),['Unknown agency'])

    def test_named_area_without_preposition_is_recognized(self):
        c=group_catalog(self.catalog());c[0]['areas']=['Lasem','Jumlah','SD','Jawa Tengah']
        ai=PilotAI(None,c)
        self.assertEqual(ai.stated_areas('Lulusan SD Lasem lebih dari 700.'),['Lasem'])

class AnswerRegressionTests(unittest.TestCase):
    def result(self,i,rs,question):
        state=RequestState(question=question,reference_date=date(2026,10,23),intent=i,records=rs)
        state.assessment=assess(state)
        return render(state,Analysis())

    def test_requested_endpoint_difference_follows_data(self):
        i=intent(kind='comparison',year=2017,baseline_year=2015,temporal='explicit',endpoint_difference=True)
        result=self.result(i,[row('a',2015,439),row('b',2016,446),row('c',2017,447)],'Berapa selisih 2015 dan 2017?')
        self.assertEqual([c['value'] for c in result['calculations']],['8'])
        self.assertIn('adalah 8 orang',result['parsed']['kesimpulan'])
        self.assertIsNone(result['verdict'])

    def test_region_comparison_follows_data_without_unrequested_difference(self):
        i=intent(kind='comparison',areas=['Lasem','Pamotan'],year=2025,temporal='explicit')
        result=self.result(i,[row('a',2025,703,area='Lasem'),row('b',2025,640,area='Pamotan')],'Mana lebih banyak?')
        self.assertIn('Lasem lebih banyak daripada Pamotan',result['parsed']['kesimpulan'])
        self.assertNotIn('Selisih',result['answer'])
        self.assertNotIn('lebih banyak',result['parsed']['temuan_data'])
        self.assertLess(result['answer'].index(result['parsed']['jawaban_utama']),result['answer'].index('Temuan Data'))

    def test_explanation_does_not_get_program_template_or_verdict(self):
        i=intent(kind='explanation',requires_series=True)
        result=self.result(i,[row('a',2023,18),row('b',2024,9),row('c',2025,13)],'Kenapa menurun?')
        self.assertIsNone(result['verdict'])
        warning=result['parsed']['peringatan_editorial']
        self.assertIn('sebab-akibat',warning);self.assertNotIn('penerima program',warning)

    def test_current_year_context_uses_requested_measure_only(self):
        i=intent(kind='claim',temporal='this_year',year=2026)
        result=self.result(i,[row('a',2024,5),row('b',2025,6),row('other',2025,99,indicator_id='other',indicator='Other')],'Tahun ini bertambah.')
        self.assertEqual([r['id'] for r in result['context']],['b'])

class FinalGuardTests(unittest.TestCase):
    def test_unrequested_qualified_table_does_not_dilute_direct_match(self):
        from pilot_data import prefer_direct_scope
        direct={'label':'Banyaknya Lulusan Murid SD, SLTP, dan SLTA (SMA/SMK) Menurut Kecamatan di Kabupaten Rembang — SD','source':'BPS'}
        qualified={'label':'Banyaknya Lulusan Murid Setingkat SD, SLTP, dan SLTA Non Diknas Menurut Kecamatan di Kabupaten Rembang — SD','source':'BPS'}
        self.assertEqual(prefer_direct_scope([direct,qualified],'Lulusan SD Lasem lebih dari 700'),[direct])
        self.assertEqual(prefer_direct_scope([direct,qualified],'Bandingkan lulusan SD dan SD Non Diknas'),[direct,qualified])
        self.assertEqual(prefer_direct_scope([qualified],'Lulusan SD Lasem'),[qualified])

    def test_prose_cannot_cite_hidden_context(self):
        from flow import editorial_text
        i=intent(kind='trend')
        state=RequestState(question='Bagaimana trennya?',reference_date=date(2026,10,23),intent=i,
            records=[row('hidden',2022,90),row('a',2023,100),row('b',2024,110),row('c',2025,120)])
        state.assessment=assess(state)
        self.assertEqual(editorial_text(Note(text='Nilai 90 pada 2022.',evidence_ids=['hidden']),state),'')
        self.assertTrue(editorial_text(Note(text='Nilai 120 pada 2025.',evidence_ids=['c']),state))
