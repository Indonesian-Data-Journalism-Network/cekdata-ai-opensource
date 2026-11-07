import unittest
from types import SimpleNamespace
from environment_data import gfw_boundary_context, explain_unavailable


class BoundaryContextTests(unittest.TestCase):
    def test_caveat_requires_affected_area_and_source_metadata(self):
        row = SimpleNamespace(source_record_id='gfw:test', area='Papua',
                              method='34 provinsi sumber', source_note='')
        self.assertIn('sebelum pemekaran', gfw_boundary_context([row]))
        row.area = 'Aceh'
        self.assertEqual(gfw_boundary_context([row]), '')
        row.area = 'Papua'; row.method = 'batas terbaru'
        self.assertEqual(gfw_boundary_context([row]), '')

    def test_missing_new_province_uses_catalog_not_other_region_numbers(self):
        state = SimpleNamespace(question='Menurut GFW, data Papua Tengah 2025?',
            assessment=SimpleNamespace(primary=[]), intent=SimpleNamespace(indicator_ids=[]))
        catalog = [{'indicator_id':'loss','member_ids':['gfw-tree-cover-loss'], 'areas':['Papua','Papua Barat']}]
        result = {'parsed':{'konteks_penting':'Data belum ditemukan.'}}
        output = explain_unavailable(result, state, catalog)
        self.assertIn('Papua Tengah belum tersedia secara terpisah',output['parsed']['konteks_penting'])
        self.assertIn('tidak digunakan sebagai pengganti',output['answer'])
        catalog[0]['areas'].append('Papua Tengah')
        self.assertEqual(explain_unavailable({'parsed':{}},state,catalog),{'parsed':{}})

if __name__ == '__main__': unittest.main()
