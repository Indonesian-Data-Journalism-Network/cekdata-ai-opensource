"""Offline behavior tests: real LlamaIndex Workflows and in-memory Qdrant.

AI responses are scripted. These tests do NOT measure a live model's accuracy.
Every statistical value and source name in this file is a synthetic fixture.
"""
import copy
import unittest
import uuid

from qdrant_client import QdrantClient, models
from flow import (Analysis, Alternatives, CekDataWorkflow, Evidence, Intent,
                  Note, Predicate, SearchQuery)
from storage import QdrantEvidenceRetriever, make_catalog

EXAMPLES = {}


def row(id, year, value, **kwargs):
    data = dict(id=id, indicator_id='employment', indicator='Jumlah penduduk bekerja',
                area='Indonesia', year=year, month=8, value=str(value), unit='orang',
                source='Lembaga Statistik Simulasi', definition='penduduk bekerja usia kerja',
                method='survei-simulasi-v1', population='total',
                source_record_id=id, synthetic=True)
    data.update(kwargs)
    return Evidence(**data)


def intent(**kwargs):
    data = dict(kind='lookup', indicator_ids=['employment'], areas=['Indonesia'])
    data.update(kwargs)
    return Intent(**data)


def growth(**kwargs):
    data = dict(metric='change', operator='eq', threshold='19000000', unit='orang')
    data.update(kwargs)
    return Predicate(**data)


class ScriptedAI:
    def __init__(self, parsed, alternatives=None, analysis=None):
        self.parsed = parsed
        self.proposals = alternatives or Alternatives()
        self.analysis = analysis or Analysis()
        self.alternative_calls = 0
        self.analysis_calls = 0
        self.original_questions = []

    async def understand(self, question, reference, catalog):
        self.original_questions.append(question)
        return self.parsed.model_copy(deep=True)

    async def alternatives(self, state, catalog):
        self.original_questions.append(state.question)
        self.alternative_calls += 1
        return self.proposals.model_copy(deep=True)

    async def analyse(self, state):
        self.original_questions.append(state.question)
        self.analysis_calls += 1
        return self.analysis.model_copy(deep=True)


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = QdrantClient(':memory:')
        self.client.create_collection('test_evidence', vectors_config={})
        self.records = []

    def tearDown(self):
        self.client.close()

    async def run_case(self, parsed, records, question='Pertanyaan simulasi', reference='2026-10-22',
                       alternatives=None, analysis=None, limit=200, catalog_extra=()):
        self.records = records
        if records:
            self.client.upsert('test_evidence', points=[models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, r.id)), vector={}, payload=r.model_dump()) for r in records])
        self.ai = ScriptedAI(parsed, alternatives, analysis)
        catalog = make_catalog([*records, *catalog_extra])
        workflow = CekDataWorkflow(self.ai,
            QdrantEvidenceRetriever(self.client, 'test_evidence', limit=limit), catalog)
        result = await workflow.run(question=question, reference_date=reference)
        EXAMPLES[self._testMethodName] = result
        return result

    async def test_question_latest_without_verdict(self):
        result = await self.run_case(intent(), [row('old',2024,100),row('new',2025,110)])
        self.assertIsNone(result['verdict'])
        self.assertEqual(result['evidence'][0]['id'], 'new')
        self.assertNotIn('Penilaian:', result['answer'])

    async def test_negated_claim_preserves_meaning(self):
        q = 'Jumlah penduduk bekerja tidak meningkat sebanyak 19 juta.'
        result = await self.run_case(intent(kind='claim',predicate=growth(negated=True)),
            [row('before',2024,144640000),row('after',2025,146540000)], question=q)
        self.assertEqual(result['verdict'], 'Benar')
        self.assertEqual(result['calculations'][0]['value'], '1900000')
        self.assertIn('mendukung', result['reason'])
        self.assertTrue(all(text == q for text in self.ai.original_questions))

    async def test_positive_claim_refuted(self):
        result = await self.run_case(intent(kind='claim',predicate=growth()),
            [row('before',2024,144640000),row('after',2025,146540000)])
        self.assertEqual(result['verdict'], 'Salah')
        self.assertIn('bertentangan', result['reason'])

    async def test_this_year_only_old_data_context(self):
        result = await self.run_case(intent(kind='claim',temporal='this_year',
            predicate=growth(operator='gt',threshold='0')),
            [row('old',2025,110),row('older',2024,100)])
        self.assertEqual(result['verdict'], 'Tidak dapat diverifikasi')
        self.assertEqual(result['evidence'], [])
        self.assertEqual({r['year'] for r in result['context']}, {2025})
        self.assertEqual(self.ai.alternative_calls, 1)
        self.assertIn('tahun 2026 belum ditemukan',result['reason'])
        self.assertIn('Agustus 2025 sebesar 110 orang',result['reason'])
        # A prior-year record exists; do not claim that the baseline itself is absent.
        self.assertNotIn('pembanding 2025',result['reason'])
        self.assertNotIn('Sebagian indikator',result['parsed']['konteks_penting'])
        self.assertNotIn('Bukti langsung belum ditemukan;',result['parsed']['konteks_penting'])

    async def test_this_year_available_comparable_data(self):
        result = await self.run_case(intent(kind='claim',temporal='this_year',
            predicate=growth(operator='gt',threshold='0')),
            [row('old',2025,100),row('new',2026,110)])
        self.assertEqual(result['verdict'], 'Benar')

    async def test_statement_date_overrides_current_year(self):
        result = await self.run_case(intent(kind='claim',temporal='this_year',
            predicate=growth(operator='gt',threshold='0')),
            [row('old',2024,100),row('new',2025,110)], reference='2025-09-01')
        self.assertEqual(result['intent']['year'], 2025)
        self.assertEqual(result['verdict'], 'Benar')

    async def test_explanation_has_no_verdict(self):
        result = await self.run_case(intent(kind='explanation'),
            [row('old',2024,100),row('new',2025,110)],question='Mengapa jumlah penduduk bekerja meningkat?')
        self.assertIsNone(result['verdict'])
        self.assertIn('belum menjelaskan sebab-akibat', result['answer'])

    async def test_causal_claim_not_proven_by_aggregate(self):
        result = await self.run_case(intent(kind='claim',causal=True,
            predicate=growth(operator='gt',threshold='0')),
            [row('old',2024,100),row('new',2025,110)], question='Program pemerintah berhasil meningkatkan jumlah penduduk bekerja.')
        self.assertEqual(result['verdict'], 'Tidak dapat diverifikasi')
        self.assertIn('penyebab', result['reason'])

    async def test_second_source_domain(self):
        forest = row('forest',2025,'235.2',indicator_id='forest',indicator='Luas tutupan hutan',
            source='Observatorium Lingkungan Simulasi',unit='hektar',definition='tutupan kanopi',method='satelit-v1')
        result = await self.run_case(intent(indicator_ids=['forest']),
                                    [row('work',2025,110),forest])
        self.assertEqual(result['evidence'][0]['source'], 'Observatorium Lingkungan Simulasi')
        self.assertNotIn('work', [r['id'] for r in result['evidence']])

    async def test_conflicting_sources_keep_both(self):
        result = await self.run_case(intent(kind='claim',predicate=growth(metric='value',threshold='100')),
            [row('a',2025,100),row('b',2025,105,source='Sumber Simulasi Lain')])
        self.assertIn('source_conflict',result['gaps'])
        self.assertEqual(len(result['evidence']),2)
        self.assertEqual(result['verdict'],'Tidak dapat diverifikasi')

    async def test_method_difference_not_merged(self):
        result = await self.run_case(intent(),[row('a',2025,100),
            row('b',2025,105,source='Sumber Simulasi Lain',method='administrasi')])
        self.assertIn('incompatible_definitions',result['gaps'])
        self.assertEqual(len(result['evidence']),2)

    async def test_missing_baseline_does_not_invent_change(self):
        result = await self.run_case(intent(kind='claim',predicate=growth()),[row('only',2025,110)])
        self.assertEqual(result['calculations'],[])
        self.assertEqual(result['verdict'],'Tidak dapat diverifikasi')
        self.assertEqual(self.ai.alternative_calls,1)
        self.assertIn('Agustus 2025 menunjukkan 110 orang',result['reason'])
        self.assertIn('pembanding Agustus 2024',result['reason'])

    async def test_wrong_value_reason_names_claim_and_evidence(self):
        result = await self.run_case(intent(kind='claim',predicate=growth(metric='value',threshold='15',unit='persen')),
                                    [row('only',2025,'12.33',unit='persen')])
        self.assertEqual(result['reason'], 'Klaim menyebut nilai sebesar 15 persen, sedangkan data menunjukkan 12,33 persen. Data bertentangan dengan klaim tersebut.')
        self.assertNotIn('proposisi',result['reason'])
        self.assertNotIn('negasinya',result['reason'])

    async def test_missing_period_reason_never_uses_wrong_indicator_as_proof(self):
        forest = row('forest',2025,'999',indicator_id='forest',indicator='Luas hutan',unit='hektar')
        result = await self.run_case(intent(kind='claim',temporal='this_year',predicate=growth()),[forest],
            alternatives=Alternatives(queries=[SearchQuery(text='konteks hutan',indicator_ids=['forest'],
                rationale='Konteks saja')]))
        self.assertNotIn('999',result['reason'])
        self.assertIn('2026',result['reason'])

    async def test_months_must_be_comparable(self):
        result = await self.run_case(intent(kind='claim',predicate=growth()),
            [row('march',2024,100,month=3),row('august',2025,110)])
        self.assertIn('comparable_baseline_missing',result['gaps'])
        self.assertEqual(result['calculations'],[])

    async def test_missing_year_in_trend(self):
        result = await self.run_case(intent(kind='trend',trend_years=3),
            [row('first',2022,80),row('second',2024,100),row('third',2025,110)])
        self.assertIn('trend_incomplete',result['gaps'])
        self.assertIsNone(result['verdict'])

    async def test_analysis_can_trigger_one_retry(self):
        result = await self.run_case(intent(),[row('only',2025,100)],
                                    analysis=Analysis(needs_more_evidence=True))
        self.assertEqual(self.ai.alternative_calls,1)
        self.assertEqual(self.ai.analysis_calls,2)
        self.assertLessEqual(len([t for t in result['trace'] if t['stage']=='retrieve']),4)

    async def test_unsupported_citations_and_numbers_removed(self):
        result = await self.run_case(intent(kind='explanation'),[row('only',2025,100)],analysis=Analysis(notes=[
            Note(text='Nilai sebesar 999.',evidence_ids=['only']),
            Note(text='Klaim benar.',evidence_ids=['only']),
            Note(text='Periksa metode.',evidence_ids=['invented'])]))
        self.assertEqual(result['notes'],[])
        self.assertNotIn('999',result['answer'])

    async def test_valid_editorial_note_keeps_citation(self):
        result = await self.run_case(intent(kind='explanation'),[row('only',2025,100)],analysis=Analysis(notes=[
            Note(text='Apakah definisi penduduk bekerja berubah?',evidence_ids=['only'])]))
        self.assertEqual(len(result['notes']),1)

    async def test_simple_lookup_omits_speculative_editorial_notes(self):
        result = await self.run_case(intent(),[row('internal-uuid',2025,100,
            population_label='Perkotaan + Perdesaan')],analysis=Analysis(notes=[
            Note(text='Metode tidak dijelaskan sehingga angka perlu diragukan.',evidence_ids=['internal-uuid']),
            Note(text='Rincian perkotaan dan perdesaan belum tersedia.',evidence_ids=['internal-uuid'])]))
        self.assertEqual(result['notes'],[])
        self.assertNotIn('internal-uuid',result['answer'])
        self.assertNotIn('diragukan',result['answer'])
        self.assertIn('(Perkotaan + Perdesaan)',result['answer'])
        self.assertEqual(result['evidence'][0]['id'],'internal-uuid')

    async def test_lookup_still_displays_real_source_conflict(self):
        result = await self.run_case(intent(),[row('a',2025,100),
            row('b',2025,105,source='Sumber Simulasi Lain')])
        self.assertIn('Ada nilai berbeda',result['answer'])
        self.assertIn('100,00',result['answer'])
        self.assertIn('105,00',result['answer'])
        self.assertIsNone(result['verdict'])

    async def test_simple_lookup_hides_unrequested_historical_context(self):
        result = await self.run_case(intent(),[row('old',2024,90),row('new',2025,100)])
        self.assertIn('100,00',result['answer'])
        self.assertNotIn('90 orang',result['answer'])

    async def test_question_uses_existing_parsed_contract_and_source_footer(self):
        result = await self.run_case(intent(),[row('private-id',2025,100,
            title='Tabel Ketenagakerjaan Simulasi',source_url='https://example.org/table',
            download_url='https://example.org/data.csv')])
        parsed = result['parsed']
        self.assertEqual(parsed['penilaian'],'')
        self.assertEqual(parsed['alasan'],'')
        self.assertEqual(parsed['claim'],'')
        self.assertEqual(parsed['peringatan_editorial'],'')
        self.assertEqual(parsed['sumber'],'Tabel Ketenagakerjaan Simulasi — Lembaga Statistik Simulasi')
        self.assertEqual(parsed['link_sumber'],'https://example.org/table')
        self.assertEqual(parsed['unduh_data'],'https://example.org/data.csv')
        self.assertEqual(parsed['raw_answer'],result['answer'])
        self.assertIn('Temuan Data\n',result['answer'])
        self.assertNotIn('private-id',result['answer'])
        self.assertTrue(result['answer'].endswith('Unduh data: https://example.org/data.csv'))

    async def test_claim_sections_precede_source_footer(self):
        result = await self.run_case(intent(kind='claim',temporal='this_year',causal=True,
            predicate=growth(operator='gt',threshold='0')),
            [row('before',2025,100,title='Tabel Simulasi'),row('after',2026,110,title='Tabel Simulasi')],
            question='Klaim simulasi tentang keberhasilan program')
        text = result['answer']
        positions = [text.index(label) for label in ['Klaim\n','Penilaian:','Temuan Data\n','Konteks\n','Peringatan editorial\n','Sumber:']]
        self.assertEqual(positions,sorted(positions))
        self.assertEqual(result['parsed']['penilaian'],result['verdict'])
        self.assertEqual(result['parsed']['alasan'],result['reason'])
        self.assertEqual(result['parsed']['sumber'],'Tabel Simulasi — Lembaga Statistik Simulasi')

    async def test_legacy_download_not_mislabeled_as_source_page(self):
        legacy = {'dataset_id':'employment','series_label':'Penduduk bekerja',
                  'area_name':'Indonesia','year':2025,'period':'Agustus','value':100,
                  'unit':'orang','source':'Lembaga Simulasi','title':'Judul tabel sumber',
                  'breakdown_value':'Perkotaan + Perdesaan','download_url':'https://example.org/file.csv'}
        self.client.upsert('test_evidence',points=[models.PointStruct(id=1,vector={},payload=legacy)])
        retriever = QdrantEvidenceRetriever(self.client,'test_evidence',legacy=True)
        batch = await retriever.search(SearchQuery(text='contoh',indicator_ids=['employment'],areas=['Indonesia']))
        self.assertEqual(batch.records[0].source_url,'')
        self.assertEqual(batch.records[0].download_url,'https://example.org/file.csv')
        self.assertEqual(batch.records[0].title,'Judul tabel sumber')

    async def test_unit_mismatch_cannot_verify(self):
        result = await self.run_case(intent(kind='claim',predicate=growth(metric='value',threshold='100',unit='persen')),
                                    [row('only',2025,100)])
        self.assertEqual(result['verdict'],'Tidak dapat diverifikasi')

    async def test_proxy_is_context_only(self):
        forest = row('forest',2025,100,indicator_id='forest',indicator='Luas hutan',unit='hektar')
        result = await self.run_case(intent(indicator_ids=['biodiversity']),[forest],
            alternatives=Alternatives(queries=[SearchQuery(text='hutan',indicator_ids=['forest'],
                areas=['Indonesia'],rationale='Hutan sebagai konteks, bukan ukuran biodiversitas.')]))
        self.assertEqual(result['evidence'],[])
        self.assertEqual(result['context'][0]['id'],'forest')
        self.assertIsNone(result['verdict'])

    async def test_explicit_source_constraint_survives_alternatives(self):
        result = await self.run_case(intent(sources=['Sumber Pilihan']),[row('other',2025,100)],
            alternatives=Alternatives(queries=[SearchQuery(text='pekerjaan',indicator_ids=['employment'],
                areas=['Provinsi Lain'],rationale='Cari padanan')]))
        self.assertEqual(result['evidence'],[])
        self.assertEqual(result['context'],[])
        queries = [t['query'] for t in result['trace'] if t['stage']=='retrieve']
        self.assertTrue(all(q['sources']==['Sumber Pilihan'] for q in queries))

    async def test_truncated_search_not_claimed_complete(self):
        result = await self.run_case(intent(kind='claim',predicate=growth(metric='value',threshold='100')),
                                    [row('a',2025,100),row('b',2024,99)],limit=1)
        self.assertIn('retrieval_truncated',result['gaps'])
        self.assertEqual(result['verdict'],'Tidak dapat diverifikasi')

    async def test_unrelated_future_record_does_not_downgrade(self):
        result = await self.run_case(intent(kind='claim',predicate=growth(metric='value',threshold='100')),
            [row('a',2025,100),row('unrelated',2026,90,indicator_id='forest')])
        self.assertEqual(result['verdict'],'Benar')

    async def test_future_observation_excluded(self):
        result = await self.run_case(intent(),[row('a',2025,100),row('future',2027,900)])
        self.assertEqual([r['id'] for r in result['evidence']],['a'])
        self.assertNotIn('900',result['answer'])

    async def test_decimal_and_percentage_point_calculation(self):
        result = await self.run_case(intent(kind='claim',predicate=growth(operator='eq',threshold='-0.10',unit='poin persentase')),
            [row('a',2024,'12.43',unit='persen'),row('b',2025,'12.33',unit='persen')])
        self.assertEqual(result['calculations'][0]['value'],'-0.10')
        self.assertEqual(result['verdict'],'Benar')

    async def test_no_source_link_fabricated(self):
        result = await self.run_case(intent(),[row('only',2025,100)])
        self.assertEqual(result['sources'][0]['url'],'')
        self.assertNotIn('https://',result['answer'])

    async def test_storage_error_is_not_missing_data(self):
        class BrokenRetriever:
            async def search(self, query):
                raise ConnectionError('test failure')
        workflow = CekDataWorkflow(ScriptedAI(intent()),BrokenRetriever(),[])
        with self.assertRaises(Exception):
            await workflow.run(question='Pertanyaan simulasi',reference_date='2026-10-22')

    async def test_all_results_are_explicitly_simulations(self):
        result = await self.run_case(intent(),[row('only',2025,100)])
        self.assertTrue(result['answer'].startswith('SIMULASI'))


if __name__ == '__main__':
    unittest.main()
