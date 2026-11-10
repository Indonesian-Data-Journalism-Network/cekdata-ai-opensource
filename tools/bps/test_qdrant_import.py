import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.bps.ingest import BPSError, Store, normalize
from tools.bps.qdrant_import import prepare, verify, fingerprint
from tools.bps.test_ingest import table


class QdrantImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root / 'raw').mkdir()
        self.store = Store(self.root / 'bps.sqlite3'); self.addCleanup(self.store.close)
        self.source = 'https://www.bps.go.id/id/statistics-table/fixture'
        self.add_year('125', '2025')
        self.add_year('126', '2026')

    def add_year(self, pid, year):
        data = table(); data['tahun'] = [{'val': int(pid), 'label': year}]
        data['datacontent'] = {'31120' + pid + '3': '12.34567890123456789'}
        raw = json.dumps(data).encode(); checksum = hashlib.sha256(raw).hexdigest()
        (self.root / 'raw' / (checksum + '.json')).write_bytes(raw)
        rows, summary = normalize(data, '0000', '12', pid)
        self.store.put('0000', '12', pid, rows, summary,
                       {'sha256': checksum, 'retrieved_at': '2026-11-07'}, self.source, True)

    def test_only_requested_year_and_all_provenance_survive(self):
        rows, hashes, name = prepare(self.root, 2026)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['year'], 2026)
        self.assertEqual(rows[0]['value'], '12.34567890123456789')
        self.assertEqual(rows[0]['source_url'], self.source)
        self.assertEqual(rows[0]['period_text'], 'Maret 2026')
        self.assertEqual(rows[0]['derived_label'], 'Total')
        self.assertEqual(rows[0]['month'], 3)
        self.assertIsNone(rows[0]['quarter'])
        self.assertEqual(rows[0]['unit'], 'persen')
        self.assertEqual(rows[0]['unit_source'], 'Persen')
        self.assertEqual(rows[0]['period_start'], '2026-03-01')
        self.assertEqual(rows[0]['area'], 'Wilayah uji')
        original = json.loads(self.store.db.execute(
            "SELECT record FROM observations WHERE period_id='126'").fetchone()[0])
        self.assertEqual(rows[0]['original_row'], original)
        self.assertEqual(name, prepare(self.root, 2026)[2])
        self.assertTrue(name.startswith('cekdata_bps_2026_'))
        self.assertEqual(hashes[rows[0]['id']], fingerprint(rows[0]))

    def test_source_mismatch_or_unverified_link_prevents_preparation(self):
        self.store.db.execute("UPDATE imports SET source_verified=0 WHERE period_id='126'")
        self.store.db.commit()
        with self.assertRaises(BPSError): prepare(self.root, 2026)
        self.store.db.execute('UPDATE imports SET source_verified=1'); self.store.db.commit()
        row = json.loads(self.store.db.execute("SELECT record FROM observations WHERE period_id='126'").fetchone()[0])
        row['value'] = '99'
        self.store.db.execute("UPDATE observations SET record=? WHERE period_id='126'", (json.dumps(row),)); self.store.db.commit()
        with self.assertRaises(BPSError): prepare(self.root, 2026)

    def test_readback_checks_full_payload_not_just_counts(self):
        rows, hashes, name = prepare(self.root, 2026)
        class Reader:
            def scroll(self, *args, **kwargs):
                return [SimpleNamespace(id=rows[0]['id'], payload=dict(rows[0]))], None
        self.assertEqual(verify(Reader(), name, hashes, complete=True), 1)
        rows[0]['source_url'] = 'https://example.org/wrong-source'
        with self.assertRaises(BPSError): verify(Reader(), name, hashes, complete=True)

    def test_multi_year_snapshot_keeps_distinct_periods_and_source_ids(self):
        rows, hashes, name = prepare(self.root, 2025, 2026)
        self.assertEqual({r['year'] for r in rows}, {2025,2026})
        self.assertEqual(len(hashes),2)
        self.assertEqual(len({r['source_record_id'] for r in rows}),2)
        self.assertTrue(name.startswith('cekdata_bps_2025_2026_'))
        with self.assertRaises(BPSError):prepare(self.root,2026,2025)


if __name__ == '__main__':
    unittest.main()
