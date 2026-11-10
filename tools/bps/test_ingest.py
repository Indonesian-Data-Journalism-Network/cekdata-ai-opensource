import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from tools.bps import connect_server
from tools.bps.client import BPSClient, BPSError
from tools.bps.ingest import Archive, Store, normalize, ingest_plan


def table():
    # Synthetic decoder fixture; deliberately not a real BPS statistic.
    return {'status': 'OK', 'data-availability': 'available',
            'labelvervar': 'Provinsi',
            'var': [{'val': 12, 'label': 'Indikator uji', 'unit': 'Persen', 'def': 'Definisi uji'}],
            'vervar': [{'val': 31, 'label': 'Wilayah uji'}],
            'turvar': [{'val': 0, 'label': 'Total'}, {'val': 1, 'label': 'Perdesaan'}],
            'tahun': [{'val': 125, 'label': '2025'}],
            'turtahun': [{'val': 3, 'label': 'Maret'}, {'val': 9, 'label': 'September'}],
            'datacontent': {'311201253': '0', '311201259': '12.34567890123456789',
                            '311211253': '-', '311211259': '1,23'}}


class DecoderTests(unittest.TestCase):
    def test_exact_numbers_dimensions_and_missing_values_remain_distinct(self):
        rows, summary = normalize(table(), '0000', '12', '125')
        self.assertEqual(summary['observed'], 2)
        self.assertEqual(summary['held'], 2)
        self.assertEqual({r['value'] for r in rows if r['status'] == 'observed'},
                         {'0', '12.34567890123456789'})
        self.assertEqual(len({r['id'] for r in rows}), 4)
        self.assertEqual({r['subperiod_label'] for r in rows}, {'Maret', 'September'})
        self.assertEqual({r['derived_label'] for r in rows}, {'Total', 'Perdesaan'})
        self.assertTrue(all(r['vertical_axis'] == 'Provinsi' for r in rows))

    def test_missing_unit_is_held_and_missing_cell_is_not_zero(self):
        d = table(); d['var'][0]['unit'] = ''; d['datacontent'].pop('311211259')
        rows, summary = normalize(d, '0000', '12', '125')
        self.assertEqual(len(rows), 3)
        self.assertEqual(summary['observed'], 0)
        self.assertEqual(rows[0]['status'], 'missing_unit')

    def test_unit_from_explicit_title_is_traced_and_placeholder_is_not_a_unit(self):
        d = table(); d['var'][0]['unit'] = 'Tidak Ada Satuan'
        rows, summary = normalize(d, '0000', '12', '125')
        self.assertEqual(summary['observed'], 0)
        d['var'][0]['label'] = 'Jumlah Penduduk (Ribu Jiwa)'
        rows, summary = normalize(d, '0000', '12', '125')
        self.assertEqual(rows[0]['unit'], 'Ribu Jiwa')
        self.assertEqual(rows[0]['unit_origin'], 'explicit_unit_in_variable_title')
        self.assertEqual(rows[0]['unit_raw'], 'Tidak Ada Satuan')

    def test_requested_year_is_prioritized_using_catalog_labels(self):
        class FixtureArchive:
            fetched = []
            def list(self, path, params):
                return [{'th': '2025', 'th_id': 125}, {'th': '2026', 'th_id': 126}], []
            def get(self, path):
                pid = path.rsplit('/', 1)[-1]; self.fetched.append(pid)
                d = table(); d['tahun'] = [{'val': int(pid), 'label': '2026' if pid == '126' else '2025'}]
                d['datacontent'] = {key.replace('125', pid): val for key, val in d['datacontent'].items()}
                return d, {'sha256': 'fixture', 'retrieved_at': '2026-11-07'}
        archive = FixtureArchive()
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.sqlite3'); self.addCleanup(store.close)
            plan = {'start_year': 2025, 'end_year': 2026, 'priority_year': 2026,
                    'tables': [{'selected': True, 'domain': '0000', 'variable_id': '12'}]}
            with patch('builtins.print'): ingest_plan(archive, store, plan)
        self.assertEqual(archive.fetched, ['126', '125'])

    def test_different_variable_year_and_unknown_cells_fail_closed(self):
        for variable, year in [('99', '125'), ('12', '124')]:
            with self.assertRaises(BPSError): normalize(table(), '0000', variable, year)
        d = table(); d['datacontent']['unmapped'] = '7'
        with self.assertRaises(BPSError): normalize(d, '0000', '12', '125')

    def test_ambiguous_concatenated_cell_ids_are_not_guessed(self):
        d = table()
        d['vervar'] = [{'val': 1, 'label': 'a'}, {'val': 112, 'label': 'b'}]
        d['turvar'] = [{'val': 123, 'label': 'c'}, {'val': 3, 'label': 'd'}]
        d['datacontent'] = {'1121231253': '42'}
        with self.assertRaisesRegex(BPSError, 'ambigu'): normalize(d, '0000', '12', '125')

    def test_non_geographic_vertical_axis_is_preserved(self):
        d = table(); d['labelvervar'] = 'Lapangan Usaha'
        rows, _ = normalize(d, '0000', '12', '125')
        self.assertEqual(rows[0]['vertical_axis'], 'Lapangan Usaha')
        self.assertNotIn('area', rows[0])

    def test_import_replaces_revised_partition_and_keeps_other_periods(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.sqlite3')
            self.addCleanup(store.close)
            rows, summary = normalize(table(), '0000', '12', '125')
            saved = {'sha256': 'fixture', 'retrieved_at': '2026-11-07'}
            store.put('0000', '12', '125', rows, summary, saved, '', False)
            store.put('0000', '12', '125', rows[:1], summary, saved, '', False)
            self.assertEqual(store.db.execute('SELECT count(*) FROM observations').fetchone()[0], 1)
            self.assertEqual(store.db.execute('SELECT value_text FROM observations').fetchone()[0], '0')
            self.assertEqual(store.db.execute('SELECT source_verified FROM imports').fetchone()[0], 0)


class ClientTests(unittest.TestCase):
    def client(self, handler):
        c = BPSClient('fixture-secret', transport=httpx.MockTransport(handler), interval=0)
        self.addCleanup(c.close)
        return c

    def test_numbers_and_raw_are_exact_and_key_is_not_in_returned_metadata(self):
        raw = b'{"status":"OK","value":12.34567890123456789}'
        c = self.client(lambda req: httpx.Response(200, content=raw))
        parsed, result = c.get('domain/type/prov')
        self.assertEqual(parsed['value'], '12.34567890123456789')
        self.assertEqual(result, raw)

    def test_error_and_redirect_do_not_leak_key(self):
        for status in [302, 401, 403, 429, 503]:
            c = self.client(lambda req: httpx.Response(status, text='fixture-secret', headers={'location': 'https://evil.org'}))
            with self.assertRaises(BPSError) as error: c.get('domain/type/prov')
            self.assertNotIn('fixture-secret', str(error.exception))
        c = self.client(lambda req: httpx.Response(200, json={'status': 'OK', 'echo': 'fixture-secret'}))
        with self.assertRaises(BPSError): c.get('domain/type/prov')

    def test_invalid_path_never_requests(self):
        c = self.client(lambda req: self.fail('unexpected request'))
        with self.assertRaises(ValueError): c.get('https://evil.org')

    def test_archive_resumes_without_network_and_detects_corruption(self):
        c = self.client(lambda req: httpx.Response(200, json={'status': 'OK', 'hello': 'world'}))
        with tempfile.TemporaryDirectory() as tmp:
            a = Archive(tmp, c)
            _, meta = a.get('domain/type/prov')
            with patch.object(c, 'get', side_effect=AssertionError('must reuse cache')):
                a.get('domain/type/prov')
            rawpath = Path(tmp) / 'raw' / (meta['sha256'] + '.json')
            rawpath.write_text('{}')
            with self.assertRaises(BPSError): a.get('domain/type/prov')

    def test_incomplete_paginated_catalog_is_not_accepted(self):
        c = self.client(lambda req: httpx.Response(200, json={'status': 'OK', 'data-availability': 'available',
            'data': [{'page': 1, 'pages': 1, 'total': 3}, [{'var_id': 1}]]}))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BPSError): Archive(tmp, c).list('list/model/var/domain/0000')

    def test_api_source_url_never_becomes_public_citation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.sqlite3'); self.addCleanup(store.close)
            for url in ['https://webapi.bps.go.id/v1/api/key/secret', 'https://bps.go.id.evil.org/table']:
                plan = {'tables': [{'selected': True, 'domain': '0000', 'variable_id': '12',
                                     'source_url': url, 'source_verified': True}]}
                with self.assertRaises(BPSError): ingest_plan(None, store, plan)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.json'
        self.enterContext(patch.object(connect_server, 'CONFIG', self.path))
        self.client = self.enterContext(TestClient(connect_server.app, base_url=connect_server.ORIGIN,
                                                    headers={'Origin': connect_server.ORIGIN}))

    def test_setup_checks_remote_access_and_saves_private_disabled_configuration(self):
        with patch.object(connect_server.BPSClient, 'get', return_value=({'data-availability': 'available', 'data': [1]}, b'')):
            result = self.client.post('/api/save', json={'api_key': 'fixture-secret'})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('fixture-secret', result.text)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(json.loads(self.path.read_text())['enabled'])

    def test_setup_rejects_cross_origin_and_invalid_input_without_echo(self):
        result = self.client.post('/api/save', json={'api_key': 'fixture-secret'}, headers={'Origin': 'https://evil.org'})
        self.assertEqual(result.status_code, 403)
        result = self.client.post('/api/save', json={'api_key': 'short'})
        self.assertEqual(result.status_code, 422)
        self.assertNotIn('short', result.text)
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
