import unittest
from datetime import date
from flow import Intent, RequestState, Analysis, Note, assess, render, guard_temporal_scope, guard_claim_kind
from test_flow import row, intent

class AnnualChangeTests(unittest.TestCase):
    def answer(self, question, values=(100,120,130), kind='comparison', **updates):
        i=intent(kind=kind, year=2025, baseline_year=2024, temporal='explicit', **updates)
        guard_claim_kind(i,question)
        guard_temporal_scope(i,question)
        records=[row(str(y),y,v,month=None) for y,v in zip([2023,2024,2025],values) if v is not None]
        s=RequestState(question=question,reference_date=date(2026,11,6),intent=i,records=records)
        s.assessment=assess(s)
        return render(s,Analysis())

    def test_levels_and_changes_are_different(self):
        q='Bandingkan kenaikan pada 2024 dan 2025. Berapa selisihnya?'
        r=self.answer(q)
        self.assertEqual(r['intent']['requested_years'],[2023,2024,2025])
        cs=r['parsed']['findings_table']['calculations']
        self.assertEqual([c['value'] for c in cs],['20,00','10,00','-10,00'])
        self.assertIn('lebih rendah',r['parsed']['jawaban_utama'])
        r=self.answer('Bandingkan angka pada 2024 dan 2025. Berapa selisihnya?')
        self.assertEqual(r['intent']['change_comparison'],'none')
        self.assertEqual({x['year'] for x in r['evidence']},{2024,2025})

    def test_endpoint_change_is_not_change_comparison(self):
        for q in ['Berapa selisih kenaikan dari 2024 ke 2025?',
                  'Berapa persentase kenaikan pada 2025 dibandingkan 2024?',
                  'Benarkah kehilangan meningkat pada 2025 dibandingkan 2024?']:
            r=self.answer(q)
            self.assertEqual(r['intent']['change_comparison'],'none',q)

    def test_percent_changes_use_separate_denominators(self):
        r=self.answer('Bandingkan persentase kenaikan pada 2024 dan 2025.',values=(100,200,300))
        cs=r['parsed']['findings_table']['calculations']
        self.assertEqual([c['value'] for c in cs],['100,00','50,00','-50,00'])
        self.assertEqual(cs[-1]['unit'],'poin persentase')

    def test_claim_does_not_compare_raw_annual_levels(self):
        q='Benarkah kenaikan pada 2025 lebih besar dibandingkan 2024?'
        self.assertEqual(self.answer(q,kind='claim')['verdict'],'Salah')
        q='Benarkah kenaikan pada 2024 lebih besar dibandingkan 2025?'
        self.assertEqual(self.answer(q,kind='claim')['verdict'],'Benar')
        q='Benarkah kenaikan pada 2025 tidak lebih besar dibandingkan 2024?'
        self.assertEqual(self.answer(q,kind='claim')['verdict'],'Benar')

    def test_missing_predecessor_cannot_be_substituted(self):
        r=self.answer('Benarkah kenaikan 2025 lebih besar dibandingkan 2024?',values=(None,120,130),kind='claim')
        self.assertEqual(r['verdict'],'Tidak dapat diverifikasi')
        self.assertIn('2023 belum ditemukan',r['answer'])
        self.assertEqual(r['parsed']['findings_table']['calculations'],[])

    def test_zero_baseline_relative_does_not_divide(self):
        r=self.answer('Benarkah persentase kenaikan 2025 lebih tinggi dibandingkan 2024?',values=(0,120,130),kind='claim')
        self.assertEqual(r['verdict'],'Tidak dapat diverifikasi')
        self.assertIn('relative_baseline_invalid',r['gaps'])

    def test_decline_magnitude_and_increase_sign_are_distinct(self):
        q='Benarkah penurunan pada 2025 lebih besar dibandingkan 2024?'
        self.assertEqual(self.answer(q,values=(100,90,70),kind='claim')['verdict'],'Benar')
        q='Benarkah kenaikan pada 2025 lebih besar dibandingkan 2024?'
        self.assertEqual(self.answer(q,values=(100,80,70),kind='claim')['verdict'],'Salah')

    def test_nonadjacent_change_years_require_both_predecessors(self):
        i=intent(kind='comparison')
        guard_temporal_scope(i,'Bandingkan perubahan tahunan pada 2022 dan 2025.')
        self.assertEqual(i.requested_years,[2021,2022,2024,2025])
        records=[row(str(y),y,v,month=None) for y,v in [(2021,10),(2022,13),(2024,20),(2025,25)]]
        s=RequestState(question='Bandingkan perubahan tahunan pada 2022 dan 2025.',reference_date=date(2026,11,6),intent=i,records=records)
        s.assessment=assess(s)
        r=render(s,Analysis())
        self.assertFalse(r['gaps'])
        self.assertEqual([c['value'] for c in r['parsed']['findings_table']['calculations']],['3,00','5,00','2,00'])

    def test_editorial_cannot_override_deterministic_verdict(self):
        from flow import apply_editorial
        i=intent(kind='claim');guard_temporal_scope(i,'Benarkah kenaikan 2025 lebih besar dibandingkan 2024?')
        s=RequestState(question='Benarkah kenaikan 2025 lebih besar dibandingkan 2024?',reference_date=date(2026,11,6),intent=i,records=[row(str(y),y,v,month=None) for y,v in [(2023,100),(2024,120),(2025,130)]])
        s.assessment=assess(s)
        apply_editorial(s,Analysis(verdict='Benar',reason=Note(text='Semua mendukung klaim.',evidence_ids=['2023','2024','2025'])))
        self.assertEqual(s.assessment.verdict,'Salah')
