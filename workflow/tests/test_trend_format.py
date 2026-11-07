import unittest
from datetime import date
from flow import Analysis,Note,RequestState,assess,render
from test_flow import intent,row

class TrendFormatTests(unittest.TestCase):
    def result(self,values,**kwargs):
        records=[row(str(n),2023+n,v) for n,v in enumerate(values)]
        if kwargs.pop('incompatible',False):records[-1].unit='unit'
        i=intent(kind='trend',**kwargs)
        state=RequestState(question='Bagaimana trennya?',reference_date=date(2026,10,23),intent=i,records=records)
        state.assessment=assess(state)
        # An AI narrative cannot override the validated path or lead the data.
        return render(state,Analysis(summary=Note(text='Trennya naik.',evidence_ids=[r.id for r in records])))

    def test_all_four_patterns_follow_data_not_ai_summary(self):
        for values,label in [([10,12,14],'naik'),([14,12,10],'turun'),([10,14,10],'kemudian turun'),([10,10,10],'tetap')]:
            with self.subTest(values=values):
                r=self.result(values)
                self.assertIn(label,r['parsed']['kesimpulan'])
                self.assertNotIn('Trennya',r['parsed']['temuan_data'])
                self.assertNotIn('Perubahan',r['parsed']['temuan_data'])
                self.assertLess(r['answer'].index(r['parsed']['jawaban_utama']),r['answer'].index('Temuan Data'))
                self.assertLess(r['answer'].index('Temuan Data'),r['answer'].index('Sumber:'))
                self.assertEqual(len(r['parsed']['findings_table']['rows']),3)
                self.assertIsNone(r['verdict'])

    def test_flat_intervals_do_not_hide_direction(self):
        self.assertIn('naik pada',self.result([10,10,14])['parsed']['kesimpulan'])

    def test_one_point_cannot_imply_flat_trend(self):
        r=self.result([10])
        self.assertIn('baru ada satu periode',r['parsed']['kesimpulan'])
        self.assertNotIn('trennya datar',r['answer'])

    def test_incompatible_series_remains_unclassified(self):
        r=self.result([10,12,14],incompatible=True)
        self.assertIn('kesetaraan',r['parsed']['kesimpulan'])
        self.assertNotIn('naik pada',r['parsed']['kesimpulan'])

    def test_incomplete_series_limits_conclusion_to_displayed_periods(self):
        r=self.result([10,12])
        self.assertIn('naik pada',r['parsed']['kesimpulan'])
        self.assertIn('hanya berlaku pada periode yang ditampilkan',r['parsed']['kesimpulan'])
        self.assertNotIn('periode yang diminta belum lengkap',r['answer'])

    def test_new_section_does_not_change_lookup(self):
        state=RequestState(question='Berapa?',reference_date=date(2026,10,23),intent=intent(),records=[row('x',2025,14)])
        state.assessment=assess(state)
        r=render(state,Analysis())
        self.assertEqual(r['parsed']['kesimpulan'],'')
        self.assertNotIn('Kesimpulan',r['answer'])
