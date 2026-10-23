import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qdrant_client import QdrantClient
import pilot_data


class PortableImportTests(unittest.TestCase):
    def test_demo_import_is_isolated_marked_synthetic_and_refuses_overwrite(self):
        spec=importlib.util.spec_from_file_location('demo_seed', Path(__file__).resolve().parents[2]/'scripts/seed_demo.py')
        demo=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        client=QdrantClient(':memory:')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            folder=demo.make_demo(root/'export')
            with patch('qdrant_client.QdrantClient', return_value=client), patch.object(client, 'close'), patch.object(pilot_data, 'COLLECTION', 'isolated_demo'), patch.object(pilot_data, 'CATALOG_PATH', root/'catalog.json'), patch.object(pilot_data, 'REPORT_PATH', root/'report.json'):
                pilot_data.import_exports([folder])
                report=json.loads((root/'report.json').read_text())
                self.assertEqual(report['records'],6)
                self.assertEqual(report['searchable_records'],6)
                self.assertEqual(report['vector_dimension'],2)
                points,_=client.scroll('isolated_demo',limit=10)
                self.assertTrue(all(p.payload['synthetic'] for p in points))
                self.assertTrue(all('SIMULASI' in p.payload['source'] for p in points))
                with self.assertRaisesRegex(ValueError,'sudah berisi data'):
                    pilot_data.import_exports([folder])
                self.assertEqual(client.count('isolated_demo').count,6)
        client.close()
