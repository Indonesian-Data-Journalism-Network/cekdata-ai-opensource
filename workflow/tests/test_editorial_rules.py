"""Regression cases for agreed editorial rules, using synthetic observations."""
import json
import unittest
from datetime import date
from flow import (Analysis, Note, Intent, Predicate, RequestState, assess, render,
                  INTENT_PROMPT, ANALYSIS_PROMPT)
from pilot_data import group_catalog, PilotAI, IndicatorSelection
from test_flow import row, intent


def evaluate(parsed, records, analysis=None):
    state=RequestState(question='Klaim simulasi',reference_date=date(2026,10,23),intent=parsed,records=records)
    state.assessment=assess(state)
    return render(state,analysis or Analysis())


class EditorialRulesTests(unittest.TestCase):
    def test_claim_kind_guard_does_not_turn_trend_questions_into_claims(self):
        from flow import guard_claim_kind
        for question in ['Pernikahan lebih dari 500.', 'Pengguna listrik tidak sampai 700.',
                         'Pernikahan terus meningkat.', 'Program pemerintah berhasil.']:
            parsed = intent()
            guard_claim_kind(parsed, question)
            self.assertEqual(parsed.kind, 'claim')
        parsed = intent(kind='trend')
        guard_claim_kind(parsed, 'Bagaimana tren jumlah pernikahan yang meningkat?')
        self.assertEqual(parsed.kind, 'trend')

    def test_blank_method_does_not_discard_comparable_series(self):
        rs=[row(str(y),y,v,definition='',method='') for y,v in [(2015,423),(2016,171),(2017,214)]]
        result=evaluate(intent(kind='trend',year=2017,baseline_year=2015,temporal='explicit'),rs)
        self.assertEqual([r['year'] for r in result['evidence']],[2015,2016,2017])
        self.assertEqual([c['value'] for c in result['calculations']],['-252','43'])
        self.assertFalse(result['gaps'])
        self.assertEqual(result['parsed']['claim'],'')
        self.assertIsNone(result['verdict'])

    def test_continuous_claim_checks_every_transition(self):
        rs=[row(str(y),y,v) for y,v in [(2023,100),(2024,80),(2025,110)]]
        parsed=intent(kind='claim',continuous=True,requires_series=True,
            predicate=Predicate(metric='change',operator='gt',threshold='0',unit='orang'))
        result=evaluate(parsed,rs)
        self.assertEqual(result['verdict'],'Salah')
        self.assertEqual(len(result['calculations']),2)

    def test_single_point_still_shows_observation_and_source(self):
        result=evaluate(intent(kind='trend'),[row('one',2025,796,title='Sumber simulasi')])
        self.assertIn('796',result['parsed']['temuan_data'])
        self.assertIn('Sumber simulasi',result['parsed']['sumber'])
        self.assertIn('comparable_baseline_missing',result['gaps'])

    def test_unit_difference_keeps_all_years_without_arithmetic(self):
        rs=[row(str(y),y,v,unit=u) for y,v,u in [(2023,191,'unit'),(2024,102,'jumlah kamar'),(2025,191,'unit')]]
        result=evaluate(intent(kind='trend'),rs)
        self.assertEqual(len(result['evidence']),3)
        self.assertEqual(result['calculations'],[])
        self.assertIn('incompatible_definitions',result['gaps'])

    def test_known_changed_method_blocks_calculation(self):
        result=evaluate(intent(kind='trend',trend_years=2),[row('a',2024,100),row('b',2025,120,method='different')])
        self.assertIn('incompatible_definitions',result['gaps'])
        self.assertFalse(result['calculations'])

    def test_editorial_slots_use_exact_evidence_and_lock_verdict(self):
        parsed=intent(kind='claim',predicate=Predicate(metric='value',operator='gt',threshold='500',unit='orang'))
        rs=[row('one',2025,533)]
        result=evaluate(parsed,rs,Analysis(verdict='Benar',reason=Note(
            text='Angka {value:one} pada {period:one} melampaui ambang {claim_value}.',evidence_ids=['one'])))
        self.assertEqual(result['reason'],'Angka 533 orang pada Agustus 2025 melampaui ambang 500 orang.')
        wrong=evaluate(parsed,rs,Analysis(verdict='Salah',reason=Note(text='Angka lebih rendah.',evidence_ids=['one'])))
        self.assertEqual(wrong['verdict'],'Benar')
        self.assertNotIn('Angka lebih rendah',wrong['reason'])

    def test_fabricated_number_and_unknown_slot_rejected(self):
        for text in ['Angka 999 orang.', 'Angka {value:invented}.']:
            result=evaluate(intent(kind='claim',predicate=Predicate(metric='value',operator='gt',threshold='500',unit='orang')),
                [row('one',2025,533)], Analysis(verdict='Benar',reason=Note(text=text,evidence_ids=['one'])))
            self.assertNotIn('999',result['reason'])
            self.assertNotIn('invented',result['reason'])

    def test_editorial_can_use_literal_numbers_from_cited_records(self):
        parsed=intent(kind='claim',predicate=Predicate(metric='value',operator='gt',threshold='500',unit='orang'))
        result=evaluate(parsed,[row('one',2025,533,source_record_id='original')],Analysis(verdict='Benar',
            reason=Note(text='Jumlah 533 orang pada 2025 melampaui angka 500 dalam klaim.',evidence_ids=['original'])))
        self.assertEqual(result['reason'],'Jumlah 533 orang pada 2025 melampaui angka 500 dalam klaim.')

    def test_causal_cannot_be_promoted_by_ai(self):
        result=evaluate(intent(kind='claim',causal=True),[row('a',2024,100),row('b',2025,120)],
            Analysis(verdict='Benar',reason=Note(text='Program terbukti efektif.',evidence_ids=['a','b'])))
        self.assertEqual(result['verdict'],'Tidak dapat diverifikasi')
        self.assertNotIn('terbukti efektif',result['reason'])
        self.assertGreaterEqual(result['parsed']['peringatan_editorial'].count('?'),2)

    def test_complex_claim_editorial_decision_preserved(self):
        result=evaluate(intent(kind='claim'),[row('one',2025,533)], Analysis(verdict='Sebagian benar',
            reason=Note(text='Angka mendukung bagian pernyataan, tetapi kesimpulannya melampaui cakupan bukti.',evidence_ids=['one'])))
        self.assertEqual(result['verdict'],'Sebagian benar')

    def test_causal_note_without_questions_gets_followup(self):
        result=evaluate(intent(kind='claim',causal=True),[row('a',2024,100),row('b',2025,120)],
            Analysis(notes=[Note(text='Perubahan angka belum membuktikan pengaruh program.',evidence_ids=['a','b'])]))
        warning=result['parsed']['peringatan_editorial']
        self.assertIn('Perubahan angka belum',warning)
        self.assertGreaterEqual(warning.count('?'),2)
        self.assertLessEqual(warning.count('?'),4)

    def test_prompt_placeholders_render(self):
        self.assertIn('{claim_value}',ANALYSIS_PROMPT.format(state='{}'))
        self.assertIn('2026',INTENT_PROMPT.format(reference='2026-10-23',catalog='[]',question='contoh'))


class CatalogRulesTests(unittest.IsolatedAsyncioTestCase):
    def catalog(self):
        return [dict(indicator_id=f'{category}-{year}',label=f'Jumlah Nikah dan Rujuk Tahun {year} — {category}',
            source='Simulasi',unit='jumlah',definition='',areas=['Banyudono'],years=[year],populations=['total'])
            for category in ['Nikah','Rujuk'] for year in [2015,2016,2017]]

    def test_grouping_preserves_categories_and_all_annual_ids(self):
        grouped=group_catalog(self.catalog())
        self.assertEqual(len(grouped),2)
        for c in grouped:
            self.assertEqual(c['years'],[2015,2016,2017])
            self.assertEqual(len(c['member_ids']),3)
            self.assertEqual(len({x.split('-')[0] for x in c['member_ids']}),1)

    async def test_understanding_happens_before_catalog_selection(self):
        catalog=group_catalog(self.catalog());calls=[]
        selected=next(c for c in catalog if c['label'].endswith('Nikah'))
        class LLM:
            async def astructured_predict(self,cls,prompt,**kwargs):
                calls.append(kwargs)
                if issubclass(cls, Intent):
                    return Intent(kind='trend',areas=['Banyudono'],indicator_terms=['nikah'],reformulated='Jumlah nikah Banyudono')
                return IndicatorSelection(indicator_ids=[selected['indicator_id']])
        ai=PilotAI(LLM(),catalog)
        result=await ai.understand('Bagaimana perkembangan pernikahan Banyudono?',date(2026,10,23),catalog)
        self.assertEqual(json.loads(calls[0]['catalog']),[])
        self.assertIn('2016',calls[1]['catalog'])
        self.assertEqual(result.indicator_ids,[selected['indicator_id']])
