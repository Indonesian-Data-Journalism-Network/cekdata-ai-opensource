import unittest
from datetime import date
from flow import Analysis, RequestState, assess, render, guard_temporal_scope
from test_flow import row, intent


class ContextTests(unittest.TestCase):
    def test_mean_difference_retains_all_years_instead_of_only_endpoints(self):
        i=intent(kind='comparison',endpoint_difference=True)
        guard_temporal_scope(i,'Bandingkan rata-rata tahunan Aceh dan Riau selama 2021–2025. Berapa selisihnya?')
        self.assertTrue(i.requires_series)
        self.assertFalse(i.endpoint_difference)
        self.assertEqual((i.baseline_year,i.year),(2021,2025))

    def result(self, records, question, parsed):
        state=RequestState(question=question,reference_date=date(2026,11,5),intent=parsed,records=records)
        state.assessment=assess(state)
        return render(state,Analysis())

    def averages(self, missing=False):
        records=[row(f'{area}-{y}',y,v,area=area,month=None,unit='ha',source_note='Technical source note.')
                 for area,values in [('Aceh',[10,20,30,40,50]),('Riau',[30,40,50,60,70])]
                 for y,v in zip(range(2021,2026),values)]
        if missing:records.pop(1)
        return self.result(records,'Bandingkan rata-rata tahunan Aceh dan Riau selama 2021–2025. Berapa selisihnya?',
            intent(kind='comparison',requires_series=True,areas=['Aceh','Riau'],temporal='explicit',baseline_year=2021,year=2025))

    def test_means_explain_total_denominator_and_difference_without_losing_data(self):
        r=self.averages();p=r['parsed']
        self.assertEqual(len(r['evidence']),10)
        self.assertEqual(p['temuan_data'].count('pada '),10)
        self.assertIn('5 tahun dibagi 5',p['konteks_penting'])
        self.assertIn(['Total','150,00','250,00'],p['findings_table']['rows'])
        self.assertIn(['Rata-rata tahunan','30,00','50,00'],p['findings_table']['rows'])
        self.assertEqual(p['findings_table']['calculations'][0]['value'],'20,00')
        self.assertIn('Riau lebih tinggi daripada Aceh',p['kesimpulan'])
        self.assertNotIn('fluktuatif',p['kesimpulan'])
        self.assertNotIn('Technical source note',p['konteks_penting'])
        self.assertEqual(p['source_notes'],['Technical source note.'])
        self.assertIn('\n\nKonteks\n',r['answer'])
        self.assertNotIn('Konteks penting',r['answer'])
        self.assertEqual(next(c for c in p['context_calculations'] if c['kind']=='annual_mean')['count'],5)

    def test_missing_year_never_reduces_denominator_or_fills_zero(self):
        r=self.averages(missing=True)
        self.assertEqual(r['parsed']['context_calculations'],[])
        self.assertIn('belum dapat disimpulkan',r['parsed']['kesimpulan'])
        self.assertNotIn('÷ 4',r['parsed']['konteks_penting'])

    def test_relative_change_explains_denominator(self):
        r=self.result([row('a',2024,80),row('b',2025,100)],'Berapa persen kenaikannya?',
            intent(kind='comparison',relative_change=True,baseline_year=2024,year=2025,temporal='explicit'))
        self.assertIn('nilai awal sebagai pembagi',r['parsed']['konteks_penting'])
        self.assertTrue(any(c['value']=='25,00' for c in r['parsed']['findings_table']['calculations']))

    def test_lookup_has_no_fabricated_analysis_or_source_boilerplate(self):
        r=self.result([row('a',2025,12,source_note='Technical source note.')],'Berapa di Indonesia?',intent())
        self.assertEqual(r['parsed']['konteks_penting'],'')
        self.assertEqual(r['parsed']['source_notes'],['Technical source note.'])

    def test_trend_explains_actual_decline_and_rebound(self):
        r=self.result([row('a',2023,20),row('b',2024,10),row('c',2025,25)],'Bagaimana tren 2023–2025?',
            intent(kind='trend',baseline_year=2023,year=2025,temporal='explicit'))
        self.assertIn('turun pada Agustus 2023–Agustus 2024, kemudian naik pada Agustus 2024–Agustus 2025',r['parsed']['kesimpulan'])
        self.assertEqual(len(r['evidence']),3)
