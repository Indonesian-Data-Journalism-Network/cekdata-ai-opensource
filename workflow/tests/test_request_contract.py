import json
import unittest
from datetime import date
from unittest.mock import patch
from llama_index.core import PromptTemplate
from flow import Intent, RequestedMeasure
from pilot_data import PilotAI, IndicatorSelection
from request_contract import compatible_candidates, ContractLLM


def candidate(i, label, unit):
    return dict(indicator_id=i, label=label, source='Statistik', unit=unit,
        units=[unit], populations=['total'], areas=['Wilayah A'], years=[2025])


class ContractTests(unittest.IsolatedAsyncioTestCase):
    def test_named_index_can_keep_source_percent_without_changing_metadata(self):
        from copy import deepcopy
        choices=[candidate('depth','Indeks Kedalaman Kemiskinan (P1) Menurut Provinsi','Persen'),
                 candidate('severity','Indeks Keparahan Kemiskinan (P2)','Persen'),
                 candidate('poverty','Persentase penduduk miskin','Persen'),
                 candidate('other','Indeks Kualitas Lingkungan','Persen')]
        before=deepcopy(choices)
        intent=Intent(kind='lookup',requested_measures=[RequestedMeasure(
            concept='indeks kedalaman kemiskinan',dimension='index')])
        self.assertEqual([c['indicator_id'] for c in compatible_candidates(choices,intent)],['depth'])
        intent.requested_measures[0].concept='indeks keparahan kemiskinan'
        self.assertEqual([c['indicator_id'] for c in compatible_candidates(choices,intent)],['severity'])
        self.assertEqual(choices,before)

    def test_index_representation_needs_full_measurement_name_and_compatible_scale(self):
        intent=Intent(kind='lookup',requested_measures=[RequestedMeasure(
            concept='Indeks Kualitas Lingkungan',dimension='index')])
        correct=candidate('index','Indeks Kualitas Lingkungan (IKL)','Persen')
        wrong_column=candidate('column','Indeks Kualitas Lingkungan — Luas lahan','Persen')
        explicit_column=candidate('explicit','Indeks Kualitas Lingkungan','Persen')
        explicit_column['measure_label']='Penduduk yang tinggal di kawasan industri'
        choices=[correct,wrong_column,explicit_column,
                 candidate('currency','Indeks Kualitas Lingkungan','Rp'),
                 candidate('topic','Kualitas Lingkungan','Persen')]
        self.assertEqual(compatible_candidates(choices,intent),[correct])
        intent.requested_measures[0].concept='indeks'
        self.assertEqual(compatible_candidates(choices,intent),[])

    def test_index_representation_still_honours_exclusions(self):
        intent=Intent(kind='lookup',requested_measures=[RequestedMeasure(
            concept='Indeks Kualitas Lingkungan',dimension='index',excluded_measures=['proyeksi'])])
        choices=[candidate('a','Indeks Kualitas Lingkungan aktual','Persen'),
                 candidate('b','Indeks Kualitas Lingkungan proyeksi','Persen')]
        self.assertEqual(compatible_candidates(choices,intent),choices[:1])

    def test_broad_exclusion_cannot_erase_requested_qualified_measure(self):
        intent=Intent(kind='lookup',requested_measures=[RequestedMeasure(
            concept='Jumlah penduduk miskin',dimension='count',excluded_measures=['jumlah penduduk','persentase penduduk miskin'])])
        choices=[candidate('count','Jumlah penduduk miskin','ribu orang'),
                 candidate('percent','Persentase penduduk miskin','persen')]
        self.assertEqual([c['indicator_id'] for c in compatible_candidates(choices,intent)],['count'])

    def test_measurement_column_and_dimension_override_broad_title(self):
        intent=Intent(kind='trend',requested_measures=[RequestedMeasure(
            concept='Persentase penduduk miskin',dimension='percentage',
            excluded_measures=['garis kemiskinan','indeks kedalaman kemiskinan'])])
        candidates=[candidate('p0','Jumlah dan Persentase Penduduk Miskin — Persentase penduduk miskin','persen'),
            candidate('line','Jumlah dan Persentase Penduduk Miskin — Garis kemiskinan','Rp'),
            candidate('p1','Kemiskinan — Indeks kedalaman kemiskinan','persen'),
            candidate('count','Kemiskinan — Jumlah penduduk miskin','ribu orang')]
        self.assertEqual([c['indicator_id'] for c in compatible_candidates(candidates,intent)],['p0'])
        intent.requested_measures=[RequestedMeasure(concept='Garis kemiskinan',dimension='currency')]
        self.assertEqual([c['indicator_id'] for c in compatible_candidates(candidates,intent)],['line'])

    def test_other_topics_and_multiple_measures_keep_their_dimensions(self):
        choices=[candidate('a','Luas sawit','ha'),candidate('b','Penduduk bekerja','orang'),
                 candidate('c','Pengeluaran','ribu rupiah')]
        intent=Intent(kind='comparison',requested_measures=[RequestedMeasure(concept='Luas sawit',dimension='area'),
            RequestedMeasure(concept='Penduduk bekerja',dimension='count')])
        self.assertEqual([c['indicator_id'] for c in compatible_candidates(choices,intent)],['a','b'])

    def test_one_statistical_answer_does_not_hide_other_requested_measure(self):
        from ngo_answer import fallback_requested
        intent=Intent(kind='lookup',indicator_ids=['forest'],needs_reports=False,
            requested_measures=[RequestedMeasure(concept='Persentase rumah tangga',dimension='percentage'),
                                RequestedMeasure(concept='Kehilangan tutupan pohon',dimension='area')])
        catalog=[candidate('forest','Kehilangan tutupan pohon','ha')]
        self.assertTrue(fallback_requested('Persentase rumah tangga dan kehilangan tutupan pohon?',intent,catalog))
        intent.requested_measures=intent.requested_measures[1:]
        self.assertFalse(fallback_requested('Kehilangan tutupan pohon?',intent,catalog))

    async def test_initial_understanding_is_reused_and_selector_cannot_reintroduce_wrong_measure(self):
        intent=Intent(kind='trend',areas=['Wilayah A'],indicator_terms=['kemiskinan'],
            requested_measures=[RequestedMeasure(concept='Persentase penduduk miskin',dimension='percentage')])
        class Model:
            calls=[]
            async def astructured_predict(self,schema,prompt,**kwargs):
                self.calls.append(schema.__name__)
                if schema.__name__=='Intent':
                    raise AssertionError('The initial request was reinterpreted')
                choices=json.loads(kwargs['catalog'])
                assert all(c['units']==['persen'] for c in choices)
                return IndicatorSelection(indicator_ids=['wrong','right'])
        model=Model()
        ai=PilotAI(model,[candidate('right','Kemiskinan — Persentase penduduk miskin','persen'),
            candidate('wrong','Kemiskinan — Garis kemiskinan','Rp')],initial_intent=intent)
        result=await ai.understand('Tren kemiskinan di Wilayah A?',date(2026,11,7),[])
        self.assertEqual(result.indicator_ids,['right'])
        self.assertEqual(model.calls,['IndicatorSelection'])
        self.assertEqual(intent.indicator_ids,[])  # request remains immutable

    async def test_contract_reaches_each_ngo_stage_without_cutting_question(self):
        question='Berapa persen mengalami kehilangan pekerjaan? Berapa persen pendapatannya turun?'
        intent=Intent(kind='lookup',question_parts=question.split('?')[:2],
            requested_measures=[RequestedMeasure(concept='Persentase responden',dimension='percentage')])
        class Model:
            seen=[]
            async def astructured_predict(self,schema,prompt,**kwargs):
                self.seen.append(prompt.format(**kwargs))
                return kwargs['question']
        model=Model();wrapped=ContractLLM(model,intent)
        for stage in ('search','extract','review','summary'):
            result=await wrapped.astructured_predict(object,PromptTemplate(stage+' {question}'),question=question)
            self.assertEqual(result,question)
        self.assertEqual(len(model.seen),4)
        for text in model.seen:
            self.assertIn('pendapatannya turun',text)
            self.assertIn('percentage',text)

    async def test_ngo_search_planner_cannot_change_claim_kind(self):
        import ngo_answer
        from ngo_answer import SearchPlan
        class Model:
            async def astructured_predict(self,schema,prompt,**kwargs):
                return SearchPlan(kind='question',queries=[])
        with patch('ngo_answer.search',return_value=[]):
            result=await ngo_answer.answer_question(Model(),'Seluruh warga bertambah sejahtera.',date(2026,11,7),
                request_intent=Intent(kind='claim',needs_reports=True))
        self.assertEqual(result['parsed']['penilaian'],'Tidak dapat diverifikasi')

    async def test_report_years_do_not_replace_explicit_statistical_period(self):
        from ngo_gfw_context import retrieve
        from unittest.mock import AsyncMock
        from flow import SearchBatch
        catalog=[dict(indicator_id='f',member_ids=['gfw-tree-cover-loss'],areas=['Aceh'],years=list(range(2021,2026)))]
        retriever=type('Retriever',(),{'search':AsyncMock(return_value=SearchBatch())})()
        await retrieve('Apa temuan laporan di Aceh 2018? Bagaimana kehilangan tutupan pohon di Aceh 2021–2025?',
            catalog,date(2026,11,7),retriever,request_intent=Intent(kind='trend',question_parts=[
                'Temuan laporan di Aceh 2018','Kehilangan tutupan pohon di Aceh 2021–2025']))
        self.assertEqual(retriever.search.call_args.args[0].years,list(range(2021,2026)))


if __name__=='__main__': unittest.main()
