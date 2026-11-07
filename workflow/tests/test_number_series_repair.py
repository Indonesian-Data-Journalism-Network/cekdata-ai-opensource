import json
import unittest
from datetime import date
from pydantic import ValidationError
from flow import (Predicate, Intent, Analysis, RequestState, assess, render, predict_structured,
                  ModelOutputError, INTENT_PROMPT, CekDataWorkflow)
from test_flow import row, intent, ScriptedAI

class NumericOutputTests(unittest.TestCase):
    def test_nonclaims_do_not_require_a_numeric_predicate(self):
        for kind in ['lookup','comparison','trend','explanation']:
            for threshold in ['', 'tidak berlaku', '1.234,5',None]:
                i=Intent.model_validate(dict(kind=kind,predicate=dict(metric='change',operator='eq',threshold=threshold,unit='ha')))
                self.assertIsNone(i.predicate)

    def test_invalid_claim_numbers_are_validation_errors_not_zero(self):
        for value in ['', 'tidak berlaku','NaN','Infinity','1.234,5','1,234','1_000',' ']:
            with self.subTest(value=value),self.assertRaises(ValidationError):
                Predicate(metric='value',operator='eq',threshold=value,unit='ha')
        self.assertEqual(Predicate(metric='value',operator='eq',threshold='-12.50',unit='ha').threshold,'-12.50')

class RetryTests(unittest.IsolatedAsyncioTestCase):
    def model(self,always_invalid=False,service_failure=False):
        class Model:
            def __init__(self):self.calls=0
            async def astructured_predict(self,schema,prompt,**kwargs):
                self.calls+=1
                if service_failure:raise ConnectionError('sensitive provider error')
                data=Intent(kind='claim').model_dump()
                data['predicate']=dict(metric='value',operator='eq',threshold='invalid' if always_invalid or self.calls==1 else '45.8',unit='persen')
                return schema.model_validate(data)
        return Model()
    async def test_retry_keeps_original_question_and_corrects_output(self):
        model=self.model()
        result=await predict_structured(model,Intent,INTENT_PROMPT,question='claim',reference='2026-11-06',catalog='[]')
        self.assertEqual(model.calls,2);self.assertEqual(result.predicate.threshold,'45.8')
    async def test_invalid_output_retry_is_bounded(self):
        model=self.model(always_invalid=True)
        with self.assertRaises(ModelOutputError):
            await predict_structured(model,Intent,INTENT_PROMPT,question='claim',reference='2026-11-06',catalog='[]')
        self.assertEqual(model.calls,2)
    async def test_service_error_is_not_retried_as_model_format(self):
        model=self.model(service_failure=True)
        with self.assertRaises(ConnectionError):
            await predict_structured(model,Intent,INTENT_PROMPT,question='claim',reference='2026-11-06',catalog='[]')
        self.assertEqual(model.calls,1)
    async def test_workflow_format_failure_is_not_reported_as_missing_data_or_bad_key(self):
        from flow import LlamaAI
        class NoRetrieval:
            async def search(self,q):raise AssertionError('Must not search after invalid intent')
        workflow=CekDataWorkflow(LlamaAI(self.model(always_invalid=True)),NoRetrieval(),[])
        result=await workflow.run(question='Benarkah jumlahnya 45,8 persen?',reference_date='2026-11-06')
        self.assertEqual(result['parsed']['error_code'],'model_output_invalid')
        self.assertNotIn('API key',result['answer']);self.assertNotIn('Belum cukup data',result['answer'])

class PartialSeriesTests(unittest.TestCase):
    def result(self,years,**updates):
        i=intent(kind='trend',year=2025,baseline_year=2021,trend_years=5,temporal='explicit',requires_series=True)
        i=i.model_copy(update=updates)
        rs=[row(str(y),y,str(y-2000),month=None) for y in years]
        state=RequestState(question='Bagaimana tren selama 2021–2025?',reference_date=date(2026,11,6),intent=i,records=rs)
        state.assessment=assess(state)
        return render(state,Analysis())
    def test_missing_end_year_keeps_all_requested_observations(self):
        r=self.result([2020,2021,2022,2023,2024])
        self.assertEqual([e['year'] for e in r['evidence']],[2021,2022,2023,2024])
        self.assertIn('trend_incomplete',r['gaps']);self.assertNotIn('no_direct_evidence',r['gaps'])
        self.assertEqual(len(r['calculations']),3)
        self.assertIn('data tahun 2025 belum ditemukan',r['answer'])
        self.assertIn('Tahun tanpa data tidak dianggap nol',r['answer'])
        self.assertFalse(any(c['target_id']=='2025' for c in r['calculations']))
    def test_missing_first_middle_and_last_years_remain_visible(self):
        for years in [[2022,2023,2024,2025],[2021,2022,2024,2025],[2022,2024]]:
            r=self.result(years)
            self.assertEqual([e['year'] for e in r['evidence']],years)
            self.assertIn('trend_incomplete',r['gaps'])
    def test_missing_requested_endpoint_never_creates_endpoint_calculation(self):
        r=self.result([2021,2022,2023,2024],endpoint_difference=True,relative_change=True)
        self.assertFalse(any(c['kind'] in ['endpoint','relative'] for c in r['calculations']))
        self.assertIn('trend_incomplete',r['gaps'])
    def test_claim_is_not_verified_from_partial_series(self):
        r=self.result([2021,2022,2023,2024],kind='claim',continuous=True,
            predicate=Predicate(metric='change',operator='gt',threshold='0',unit='orang'))
        self.assertEqual(r['verdict'],'Tidak dapat diverifikasi')
    def test_single_year_lookup_still_does_not_substitute_older_year(self):
        r=self.result([2021,2022,2023,2024],kind='lookup',requires_series=False,baseline_year=None)
        self.assertEqual(r['evidence'],[]);self.assertIn('no_direct_evidence',r['gaps'])
    def test_explicit_year_list_does_not_expand_to_unrequested_years(self):
        r=self.result([2021,2022,2023,2024],requested_years=[2021,2023,2025])
        self.assertEqual([e['year'] for e in r['evidence']],[2021,2023]);self.assertIn('trend_incomplete',r['gaps'])
    def test_missing_series_still_has_no_direct_evidence(self):
        r=self.result([2019,2020]);self.assertEqual(r['evidence'],[])
        self.assertIn('no_direct_evidence',r['gaps'])
