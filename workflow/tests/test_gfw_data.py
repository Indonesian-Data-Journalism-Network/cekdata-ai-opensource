import unittest
from copy import deepcopy
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
from gfw_data import normalize, province_directory, reconcile, sql_for, YEAR


class GFWImportTests(unittest.TestCase):
    def setUp(self):
        self.provinces = province_directory([{'gid_0':'IDN','gid_1':'IDN.1_1','name_1':'Aceh','adm_level':'1'}])
        self.rows = [{'iso':'IDN','adm1':1,YEAR:2025,'loss_ha':'123.1234567890123456789','fire_loss_ha':'0'}]

    def test_exact_values_and_record_specific_public_source_links(self):
        rows = normalize(self.rows,'adm1',False,self.provinces,{'sha256':'fixture'})
        self.assertEqual(rows[0]['value'],'123.1234567890123456789')
        self.assertEqual(rows[1]['value'],'0')
        self.assertNotEqual(rows[0]['indicator_id'],rows[1]['indicator_id'])
        for row in rows:
            self.assertEqual(row['area'],'Aceh')
            self.assertEqual(row['boundary_gid'],'IDN.1_1')
            self.assertIn('v20260424',row['source_url'])
            params = parse_qs(urlsplit(row['download_url']).query)
            self.assertEqual(set(params),{'sql'})
            self.assertIn('adm1 = 1',params['sql'][0])
            self.assertIn('year = 2025',params['sql'][0])
            self.assertIn('tidak otomatis berarti deforestasi',row['source_note'])
            self.assertFalse(row['synthetic'])

    def test_missing_negative_invalid_duplicate_and_unmapped_data_rejected(self):
        for update in [{'loss_ha':None},{'loss_ha':'NaN'},{'loss_ha':'-1'}, {'adm1':999},{YEAR:2026},{'iso':'MYS'}]:
            with self.subTest(update=update), self.assertRaises((ValueError,ArithmeticError)):
                normalize([{**self.rows[0],**update}],'adm1',False,self.provinces,{})
        with self.assertRaises(ValueError):
            normalize(self.rows*2,'adm1',False,self.provinces,{})

    def test_primary_uses_baseline_mask_and_starts_after_2001(self):
        sql=sql_for('adm1',True)
        self.assertIn('is__umd_regional_primary_forest_2001 = true',sql)
        self.assertIn('year >= 2002',sql)
        with self.assertRaises(ValueError):sql_for('iso',True,year=2001)
        rows=normalize([{'iso':'IDN',YEAR:2002,'primary_loss_ha':'4'}],'iso',True,self.provinces,{})
        self.assertEqual(rows[0]['area'],'Indonesia')
        self.assertEqual(rows[0]['indicator_id'],'gfw-primary-forest-loss')

    def test_reconciliation_detects_missing_or_mislabeled_province_values(self):
        rows=normalize(self.rows,'adm1',False,self.provinces,{})
        national=normalize(self.rows,'iso',False,self.provinces,{})
        self.assertTrue(all(Decimal(v)==0 for v in reconcile(rows+national).values()))
        wrong=deepcopy(rows);wrong[0]['value']='100'
        with self.assertRaises(ValueError):reconcile(wrong+national)

    def test_unknown_boundary_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):province_directory([{'gid_0':'IDN','gid_1':'bad','name_1':'Aceh','adm_level':'1'}])

if __name__=='__main__':unittest.main()
