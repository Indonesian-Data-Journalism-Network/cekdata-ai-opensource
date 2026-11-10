"""Synthetic cross-source period/percentage regression checks."""
import unittest
from datetime import date
from decimal import Decimal
from flow import (Intent, Evidence, ObservationPeriod, Predicate, RequestState,
                  assess, render, Analysis, guard_temporal_scope)


def row(id,month=None,quarter=None,year=2026,value='1',unit='Persen'):
    return Evidence(id=id,indicator_id='x',indicator='Ukuran simulasi',area='Daerah Uji',
                    source='Simulasi',year=year,month=month,quarter=quarter,value=value,unit=unit,
                    temporal_basis='quarter' if quarter else 'month' if month else 'annual',
                    period_text=f'Triwulan {quarter} {year}' if quarter else '')


def intent(question,**kw):
    i=Intent(kind='lookup',indicator_ids=['x'],areas=['Daerah Uji'])
    for k,v in kw.items():setattr(i,k,v)
    guard_temporal_scope(i,question)
    return i


def result(question,i,records):
    s=RequestState(question=question,intent=i,reference_date=date(2026,11,7),records=records)
    s.assessment=assess(s)
    return s,render(s,Analysis())


class PeriodContractTests(unittest.TestCase):
    def test_single_quarter_overrides_spurious_month(self):
        q='Berapa ukuran Daerah Uji triwulan II 2026?';i=intent(q,month=4)
        self.assertIsNone(i.month)
        self.assertEqual(i.requested_periods[0].quarter,2)
        s,r=result(q,i,[row('q1',quarter=1,value='10'),row('q2',quarter=2,value='12')])
        self.assertEqual([e.id for e in s.assessment.primary],['q2'])
        self.assertEqual(r['gaps'],[])

    def test_two_month_claim_preserves_both_and_correct_unit(self):
        q='Benarkah ukuran turun dari Februari ke Agustus 2026?'
        i=intent(q,kind='claim',predicate=Predicate(metric='change',operator='lt',threshold='0',unit='poin persentase'))
        s,r=result(q,i,[row('feb',2,value='4.68'),row('aug',8,value='4.75')])
        self.assertEqual(r['verdict'],'Salah')
        self.assertEqual(r['calculations'][0]['value'],'0.07')
        self.assertEqual(r['calculations'][0]['unit'],'poin persentase')
        self.assertEqual(len(r['evidence']),2)

    def test_two_months_missing_start_not_self_comparison(self):
        q='Benarkah ukuran turun dari Februari ke Agustus 2026?'
        i=intent(q,kind='claim',predicate=Predicate(metric='change',operator='lt',threshold='0',unit='poin persentase'))
        s,r=result(q,i,[row('aug',8)])
        self.assertEqual(r['verdict'],'Tidak dapat diverifikasi')
        self.assertEqual(r['calculations'],[])
        self.assertIn('comparable_baseline_missing',r['gaps'])

    def test_cross_year_months_and_relative_percent(self):
        q='Berapa persen kenaikan dari November 2025 ke Februari 2026?'
        i=intent(q,kind='comparison')
        s,r=result(q,i,[row('a',11,year=2025,value='2'),row('b',2,value='3')])
        self.assertEqual(r['gaps'],[])
        self.assertEqual([c['unit'] for c in r['calculations']],['poin persentase','persen'])
        self.assertEqual(Decimal(r['calculations'][1]['value']),50)

    def test_quarter_comparison_and_month_not_interchangeable(self):
        q='Bandingkan triwulan I dan II 2026, berapa selisihnya?'
        i=intent(q,kind='comparison')
        s,r=result(q,i,[row('a',quarter=1,value='20'),row('b',quarter=2,value='25'),row('month',6,value='100')])
        self.assertEqual(r['gaps'],[])
        self.assertEqual(r['calculations'][0]['value'],'5')
        self.assertEqual(len(r['evidence']),2)

    def test_monthly_trend_requires_intermediate_months(self):
        q='Bagaimana tren Januari hingga Maret 2026?';i=intent(q,kind='trend')
        self.assertEqual([p.month for p in i.requested_periods],[1,2,3])
        s,r=result(q,i,[row('a',1,value='3'),row('b',2,value='2'),row('c',3,value='1')])
        self.assertEqual(r['gaps'],[])
        self.assertIn('turun',r['answer'])
        s,r=result(q,i,[row('a',1,value='3'),row('c',3,value='1')])
        self.assertIn('trend_incomplete',r['gaps'])

    def test_march_annual_series_and_annual_gfw_still_work(self):
        q='Tren Maret 2024–2026';i=intent(q,kind='trend')
        self.assertEqual([(p.year,p.month) for p in i.requested_periods],[(2024,3),(2025,3),(2026,3)])
        q='Bagaimana tren tahun 2024–2026?';i=intent(q,kind='trend')
        self.assertFalse(i.requested_periods)
        s,r=result(q,i,[row(str(y),year=y,value=str(y-2020),unit='ha') for y in (2024,2025,2026)])
        self.assertEqual(r['gaps'],[])
        self.assertEqual(len(r['calculations']),2)

    def test_abbreviated_quarter_trend_includes_middle(self):
        i=intent('Tren triwulan I–III 2026',kind='trend')
        self.assertEqual([p.quarter for p in i.requested_periods],[1,2,3])

    def test_relative_zero_and_provisional_note(self):
        q='Berapa persen kenaikan Januari ke Maret 2026?'
        i=intent(q,kind='comparison')
        end=row('end',3,value='3').model_copy(update={
            'data_status':'provisional','data_status_note':'Angka sementara'})
        s,r=result(q,i,[row('start',1,value='0'),end])
        self.assertIn('relative_baseline_invalid',r['gaps'])
        self.assertNotIn('relative',[c['kind'] for c in r['calculations']])
        self.assertIn('berstatus angka sementara',r['answer'])

    def test_multiple_lookup_missing_period_is_not_complete(self):
        q='Tampilkan data Februari dan Agustus 2026'
        i=intent(q)
        s,r=result(q,i,[row('aug',8)])
        self.assertIn('requested_scope_missing',r['gaps'])

    def test_invalid_frequency_and_self_pair_guard(self):
        with self.assertRaises(ValueError):ObservationPeriod(year=2026,month=6,quarter=2)
        i=Intent(kind='claim',indicator_ids=['x'],areas=['Daerah Uji'],year=2026,month=8,baseline_year=2026,
                 predicate=Predicate(metric='change',operator='eq',threshold='0',unit='poin persentase'))
        s,r=result('Klaim perubahan',i,[row('aug',8)])
        self.assertEqual(r['calculations'],[])
        self.assertEqual(r['verdict'],'Tidak dapat diverifikasi')

if __name__=='__main__':unittest.main()
