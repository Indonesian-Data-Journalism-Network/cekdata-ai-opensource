"""Offline HTTP integration with real workflow/Qdrant; no live OpenAI calls."""
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient, models
from server import create_app
from flow import CekDataWorkflow, Intent, Predicate
from storage import QdrantEvidenceRetriever, make_catalog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'workflow/tests'))
from test_flow import ScriptedAI, row

BASE = 'http://127.0.0.1:8765'
HEADERS = {'Origin': BASE}
FAKE_KEY = 'sk-test-fixture-not-a-real-key'


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.db = QdrantClient(':memory:')
        self.db.create_collection('test', vectors_config={})
        self.record = row('fixture', 2025, '12.33', indicator_id='poverty',
                          indicator='Persentase penduduk miskin', area='Aceh', month=3, unit='persen',
                          title='Tabel simulasi kemiskinan', source='Sumber simulasi',
                          source_url='https://example.org/source', download_url='https://example.org/data.csv')
        self.db.upsert('test', points=[models.PointStruct(id=1, vector={}, payload=self.record.model_dump())])
        self.seen = []
        self.parsed = Intent(kind='lookup', indicator_ids=['poverty'], areas=['Aceh'])
        self.provider_error = False

        async def runner(key, question, reference):
            self.seen.append((key, question, reference))
            if self.provider_error:
                raise RuntimeError('Provider detail containing ' + key)
            workflow = CekDataWorkflow(ScriptedAI(self.parsed),
                QdrantEvidenceRetriever(self.db, 'test'), make_catalog([self.record]))
            return await workflow.run(question=question, reference_date=reference)

        self.client = TestClient(create_app(runner), base_url=BASE, headers=HEADERS)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.db.close()

    def connect(self):
        return self.client.post('/api/local/session', json={'api_key': FAKE_KEY})

    def test_session_cookie_clear_and_redaction(self):
        self.assertFalse(self.client.get('/api/local/session').json()['configured'])
        response = self.connect()
        self.assertEqual(response.status_code, 200)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        self.assertNotIn(FAKE_KEY, response.text)
        self.assertTrue(self.client.get('/api/local/session').json()['configured'])
        self.client.delete('/api/local/session')
        self.assertFalse(self.client.get('/api/local/session').json()['configured'])

    def test_auth_origin_and_host_required(self):
        self.assertEqual(self.client.post('/api/ask', json={'question': 'Kemiskinan Aceh?'}).status_code, 401)
        for path in ['/api/local/session', '/api/ask']:
            response = self.client.post(path, json={'api_key': FAKE_KEY}, headers={'Origin': 'https://other.example'})
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get('/api/local/session', headers={'Host': 'other.example'}).status_code, 403)
        self.assertEqual(self.seen, [])

    def test_validation_never_echoes_key(self):
        key = FAKE_KEY * 30
        response = self.client.post('/api/local/session', json={'api_key': key})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(FAKE_KEY, response.text)

    def test_question_has_no_verdict_and_sources_at_bottom(self):
        self.connect()
        response = self.client.post('/api/ask', json={'question': 'Berapa kemiskinan Aceh?', 'sources': ['bps']})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertIn('12,33', result['parsed']['temuan_data'])
        self.assertEqual(result['parsed']['penilaian'], '')
        self.assertEqual(result['parsed']['alasan'], '')
        self.assertIn('Tabel simulasi kemiskinan', result['parsed']['sumber'])
        self.assertIn('https://example.org/source', result['parsed']['link_sumber'])
        self.assertIn('https://example.org/data.csv', result['parsed']['unduh_data'])
        self.assertLess(result['answer'].index('Temuan data'), result['answer'].index('Sumber:'))
        self.assertNotIn('fixture', result['answer'])
        self.assertNotIn(FAKE_KEY, response.text)
        self.assertEqual(self.seen[0][0], FAKE_KEY)

    def test_false_numeric_claim(self):
        self.connect()
        self.parsed = self.parsed.model_copy(update={'kind': 'claim', 'temporal': 'explicit', 'year': 2025, 'month': 3,
            'predicate': Predicate(metric='value', operator='eq', threshold='15', unit='persen')})
        result = self.client.post('/api/ask', json={'question': 'Benarkah kemiskinan Aceh Maret 2025 sebesar 15 persen?'}).json()
        self.assertEqual(result['parsed']['penilaian'], 'Salah')
        self.assertIn('15', result['parsed']['alasan'])
        self.assertIn('12,33', result['parsed']['alasan'])

    def test_current_year_missing_keeps_context(self):
        self.connect()
        self.parsed = self.parsed.model_copy(update={'kind': 'claim', 'temporal': 'this_year',
            'predicate': Predicate(metric='change', operator='lt', threshold='0', unit='persen')})
        result = self.client.post('/api/ask', json={'question': 'Benarkah kemiskinan Aceh turun tahun ini?'}).json()
        self.assertEqual(result['parsed']['penilaian'], 'Tidak dapat diverifikasi')
        self.assertIn('2025', result['parsed']['konteks_penting'])
        self.assertIn(result['reference_date'][:4], result['parsed']['alasan'])

    def test_failure_is_not_missing_data_and_does_not_echo_key(self):
        self.connect()
        self.provider_error = True
        response = self.client.post('/api/ask', json={'question': 'Kemiskinan Aceh?'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(FAKE_KEY, response.text)
        self.assertIn('Gangguan layanan bukan bukti', response.text)
        self.assertNotIn('penilaian', response.json())

    def test_unsupported_sources_and_ambiguous_context_fail_before_model(self):
        self.connect()
        for data, code in [({'question': 'Iklim?', 'sources': ['environment']}, 409),
                           ({'question': 'Kalau 2024?', 'previous_question': 'Aceh?'}, 422)]:
            self.assertEqual(self.client.post('/api/ask', json=data).status_code, code)
        self.assertEqual(self.seen, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
