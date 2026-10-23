import unittest
from datetime import date
from flow import Analysis,RequestState,Predicate,assess,render,guard_claim_kind,guard_temporal_scope,absence_count_claim,quantity,distinct_evidence
from test_flow import row,intent

class GeneralFixTests(unittest.TestCase):
    def result(self,rs,i=None,q='Bagaimana?'):
        state=RequestState(question=q,reference_date=date(2026,10,23),intent=i or intent(),records=rs)
        state.assessment=assess(state)
        return render(state,Analysis())

    def test_duplicate_is_one_observation_and_preserves_ids(self):
        rs=[row('a',2025,10),row('b',2025,10)]
        r=self.result(rs)
        self.assertEqual(len(r['evidence']),1)
        self.assertEqual(r['evidence'][0]['duplicate_record_ids'],['b'])
        self.assertEqual(r['evidence'][0]['duplicate_source_record_ids'],['b'])

    def test_different_values_and_sources_are_not_deduplicated(self):
        rs=[row('a',2025,10),row('b',2025,11),row('c',2025,10,source='Other')]
        self.assertEqual(len(distinct_evidence(rs)),3)
        self.assertIn('source_conflict',self.result(rs)['gaps'])

    def test_duplicate_does_not_block_comparison(self):
        rs=[row('a',2025,10,area='A'),row('b',2025,10,area='A'),row('c',2025,15,area='B')]
        r=self.result(rs,intent(kind='comparison',areas=['A','B']),q='Bandingkan A dan B')
        self.assertIn('B lebih banyak daripada A',r['parsed']['kesimpulan'])
        self.assertNotIn('Selisih',r['answer'])

    def test_count_unit_prefix_does_not_block_change(self):
        rs=[row('a',2024,3,unit='desa/kelurahan'),row('b',2025,1,unit='jumlah desa/kelurahan')]
        r=self.result(rs,intent(kind='trend',baseline_year=2024,year=2025,temporal='explicit'))
        self.assertNotIn('incompatible_definitions',r['gaps'])
        self.assertIn('trennya turun',r['parsed']['kesimpulan'])
        self.assertEqual(r['calculations'][0]['value'],'-2')

    def test_scale_unit_is_not_count_prefix_alias(self):
        r=self.result([row('a',2024,3,unit='orang'),row('b',2025,1,unit='ribu orang')],intent(kind='trend'))
        self.assertIn('incompatible_definitions',r['gaps'])

    def test_stability_claim_guard_preserves_unit_and_endpoints(self):
        i=intent(kind='trend');q='Jumlah unit tidak berubah antara 2024 dan 2025.'
        guard_claim_kind(i,q);guard_temporal_scope(i,q)
        self.assertEqual(i.kind,'claim');self.assertEqual(i.predicate.threshold,'0')
        self.assertEqual((i.baseline_year,i.year),(2024,2025))
        i.predicate.unit='orang'
        self.assertEqual(self.result([row('a',2024,3),row('b',2025,3)],i,q)['verdict'],'Benar')
        self.assertEqual(self.result([row('a',2024,3),row('b',2025,4)],i,q)['verdict'],'Salah')

    def test_absence_claim_is_presence_count_zero(self):
        q='Tidak ada sekolah yang memiliki perpustakaan.';i=intent(kind='lookup')
        guard_claim_kind(i,q)
        self.assertTrue(absence_count_claim(q));self.assertEqual(i.kind,'claim')
        self.assertEqual((i.predicate.metric,i.predicate.operator,i.predicate.threshold),('value','eq','0'))
        self.assertFalse(absence_count_claim('Berapa sekolah yang tidak memiliki perpustakaan?'))

    def test_percent_request_is_relative_not_percentage_level(self):
        i=intent(kind='lookup');guard_temporal_scope(i,'Berapa persen kenaikan dari 2022 ke 2025?')
        self.assertTrue(i.relative_change);self.assertFalse(i.endpoint_difference)
        self.assertEqual((i.baseline_year,i.year),(2022,2025))
        j=intent();guard_temporal_scope(j,'Berapa persen penduduk miskin pada 2025?')
        self.assertFalse(j.relative_change)

    def test_percent_uses_baseline_and_conclusion(self):
        i=intent(kind='comparison',relative_change=True,year=2025,baseline_year=2024,temporal='explicit')
        r=self.result([row('a',2024,80),row('b',2025,100)],i,'Berapa persen kenaikannya?')
        self.assertIn('25,00 persen',r['parsed']['kesimpulan'])
        self.assertIn('÷ 80',r['parsed']['kesimpulan'])
        self.assertNotIn('25,00',r['parsed']['temuan_data'])
        self.assertLess(r['answer'].index('Temuan data'),r['answer'].index('Kesimpulan'))

    def test_zero_baseline_never_invents_percent(self):
        i=intent(kind='comparison',relative_change=True,year=2025,baseline_year=2024,temporal='explicit')
        r=self.result([row('a',2024,0),row('b',2025,10)],i)
        self.assertIn('relative_baseline_invalid',r['gaps'])
        self.assertFalse([c for c in r['calculations'] if c['kind']=='relative'])

    def test_money_summary_has_one_scale(self):
        self.assertIn('33,06 miliar rupiah',quantity('33057360','ribu Rupiah'))
        self.assertNotIn('juta ribu',quantity('33057360','ribu Rupiah'))
        self.assertEqual(quantity('50','ribu Rupiah'),'50 ribu Rupiah')

    def test_explanation_default_range_is_not_attributed_to_user(self):
        r=self.result([row('a',2024,10),row('b',2025,12)],intent(kind='explanation',requires_series=True))
        self.assertNotIn('periode yang diminta belum lengkap',r['answer'])
        self.assertIn('rentang bawaan',r['answer'])

    def test_period_comparison_always_has_data_then_relationship(self):
        i=intent(kind='comparison',year=2025,baseline_year=2024,temporal='explicit')
        r=self.result([row('a',2024,3),row('b',2025,1)],i,'Bagaimana perubahan dari2024ke2025?')
        self.assertIn('trennya turun',r['parsed']['kesimpulan'])
        self.assertNotIn('selisih',r['parsed']['kesimpulan'].lower())
        self.assertNotIn('Perubahan',r['parsed']['temuan_data'])
