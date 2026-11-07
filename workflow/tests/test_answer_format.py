import unittest
from datetime import date
from flow import Analysis, RequestState, assess, render, guard_claim_kind, guard_temporal_scope
from test_flow import row, intent


class AnswerFormatTests(unittest.TestCase):
    def answer(self, records, question, parsed):
        state=RequestState(question=question,reference_date=date(2026,11,5),intent=parsed,records=records)
        state.assessment=assess(state)
        return render(state,Analysis())

    def test_fire_indicator_is_not_a_policy_causal_claim(self):
        q='Benarkah kehilangan tutupan pohon akibat kebakaran di Aceh meningkat pada 2025 dibandingkan 2024?'
        i=intent(kind='claim',causal=True,areas=['Aceh'],year=2025,baseline_year=2024,temporal='explicit')
        guard_claim_kind(i,q)
        self.assertFalse(i.causal)
        self.assertIsNotNone(i.predicate)
        i.predicate.unit='ha'
        r=self.answer([row('a',2024,'1256.69059743844397745',area='Aceh',month=None,unit='ha'),
                       row('b',2025,'2455.50793836951037398',area='Aceh',month=None,unit='ha')],q,i)
        self.assertEqual(r['verdict'],'Benar')
        self.assertEqual(r['parsed']['peringatan_editorial'],'')
        self.assertIn('Penilaian: Benar',r['answer'])
        self.assertEqual(r['parsed']['findings_table']['rows'][0][-1],'1.256,69')
        self.assertEqual(r['evidence'][0]['value'],'1256.69059743844397745')
        self.assertLess(r['answer'].index('Penilaian:'),r['answer'].index('Temuan Data'))

    def test_program_failure_requires_causal_evidence(self):
        i=intent(kind='claim',causal=False)
        guard_claim_kind(i,'Kenaikan kehilangan tutupan pohon akibat kebakaran membuktikan program pemerintah gagal.')
        self.assertTrue(i.causal)

    def test_total_complete_loss_series_only(self):
        q='Berapa total kehilangan tutupan pohon akibat kebakaran di Aceh selama 2021–2025?'
        i=intent(areas=['Aceh'],year=2025)
        guard_temporal_scope(i,q)
        self.assertTrue(i.requires_series)
        rs=[row(str(y),y,str(v),area='Aceh',month=None,unit='ha',source_record_id=f'gfw:gadm__tcl__adm1_change:v20260424:IDN:1:{y}:t30:tree-cover-loss-fire') for y,v in zip(range(2021,2026),[1,2,3,4,5])]
        r=self.answer(rs,q,i)
        self.assertIn('15,00 ha',r['parsed']['jawaban_utama'])
        self.assertEqual(len(r['parsed']['findings_table']['rows']),6)
        missing=self.answer(rs[:-1],q,i)
        self.assertFalse(missing['parsed']['context_calculations'])
        self.assertNotIn('10,00 ha',missing['parsed']['jawaban_utama'])
        for record in rs: record.source_record_id='stock'
        stock=self.answer(rs,q,i)
        self.assertFalse(stock['parsed']['context_calculations'])

    def test_context_records_are_labeled_and_missing_is_never_zero(self):
        r=self.answer([row('x',2025,12)],'Berapa di Indonesia pada 2026?',intent(year=2026,temporal='explicit'))
        t=r['parsed']['findings_table']
        self.assertEqual(len(t['rows']),1)
        self.assertIn('bukan periode/lingkup',t['rows'][0][-1])
        self.assertIn('tidak dianggap nol',r['parsed']['konteks_penting'])

    def test_different_populations_are_not_pivoted_or_lost(self):
        rs=[row('a',2025,10,area='A',month=None,population='male',population_label='Laki-laki'),row('b',2025,20,area='B',month=None,population='female',population_label='Perempuan')]
        r=self.answer(rs,'Bandingkan A dan B',intent(kind='comparison',areas=['A','B'],population='all'))
        # Rendering of the available evidence must retain its population identity.
        from answer_format import evidence_table
        state=RequestState(question='Bandingkan',reference_date=date(2026,11,5),intent=intent(),records=rs)
        state.assessment=assess(state)
        t=evidence_table(state,rs,[])
        self.assertIn('Laki-laki',str(t))
        self.assertIn('Perempuan',str(t))
        self.assertEqual(len(t['rows']),2)
