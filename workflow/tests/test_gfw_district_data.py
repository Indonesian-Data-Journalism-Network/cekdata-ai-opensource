import unittest
from copy import deepcopy
from decimal import Decimal
from gfw_data import normalize, province_directory, sql_for, YEAR, build_catalog
from gfw_district_data import district_directory, district_aliases, reconcile_districts
from pilot_data import PilotAI, group_catalog, select_catalog


class DistrictImportTests(unittest.TestCase):
    def setUp(self):
        self.provinces=province_directory([{'gid_0':'IDN','gid_1':'IDN.1_1','name_1':'Aceh','adm_level':'1'}])
        self.boundaries=[{'gid_0':'IDN','gid_1':'IDN.1_1','name_1':'Aceh',
            'gid_2':f'IDN.1.{i}_1','name_2':name,'type_2':kind,'adm_level':'2'}
            for i,name,kind in [(1,'Contoh','Kabupaten'),(2,'Kota Contoh','Kota'),(3,'Aceh Selatan','Kabupaten'),(4,'Danau','Water Body')]]
        self.districts=district_directory(self.boundaries,self.provinces)
        self.rows=[{'iso':'IDN','adm1':1,'adm2':i,YEAR:2025,'loss_ha':str(i),'fire_loss_ha':'0'} for i in range(1,5)]
        self.children=normalize(self.rows,'adm2',False,self.provinces,{},self.districts)
        self.parents=normalize([{'iso':'IDN','adm1':1,YEAR:2025,'loss_ha':'10','fire_loss_ha':'0'}],'adm1',False,self.provinces,{})

    def test_district_source_urls_and_identity_include_both_parent_and_child(self):
        self.assertEqual(len({r['id'] for r in self.children}),8)
        r=self.children[0]
        self.assertEqual(r['area'],'Kabupaten Contoh, Aceh')
        self.assertEqual(r['province_context'],'Aceh')
        self.assertEqual(r['value'],'1')
        self.assertEqual(r['boundary_gid'],'IDN.1.1_1')
        self.assertIn('adm1 = 1',r['source_sql']);self.assertIn('adm2 = 1',r['source_sql'])
        self.assertIn('gadm__tcl__adm2_change',r['download_url'])
        with self.assertRaises(ValueError):sql_for('adm2',adm2=1)
        with self.assertRaises(ValueError):sql_for('adm1',adm1=1,adm2=1)

    def test_reconciliation_uses_all_source_geometries_and_detects_missing_district(self):
        self.assertTrue(all(Decimal(v)==0 for v in reconcile_districts(self.parents,self.children).values()))
        with self.assertRaises(ValueError):reconcile_districts(self.parents,self.children[:-2])
        with self.assertRaises(ValueError):reconcile_districts([],self.children)

    def test_boundary_validation_and_source_gid_without_version_suffix(self):
        for change in ({'name_1':'Wrong'},{'gid_1':'IDN.9_1'},{'gid_2':'invalid'},{'type_2':'unexpected'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                district_directory([{**self.boundaries[0],**change}],self.provinces)
        rows=deepcopy(self.boundaries[:1]);rows[0].update(gid_2='IDN.1.1',type_2='NA')
        self.assertEqual(district_directory(rows,self.provinces)[1,1]['type'],'NA')
        with self.assertRaises(ValueError):district_directory(self.boundaries*2,self.provinces)
        with self.assertRaises(ValueError):normalize([{**self.rows[0],'adm2':99}],'adm2',False,self.provinces,{},self.districts)

    def test_aliases_preserve_city_regency_distinction_and_reach_catalog(self):
        aliases=district_aliases(self.districts,self.provinces)
        self.assertNotIn('contoh',aliases)
        self.assertNotIn('danau',aliases)
        self.assertEqual(aliases['kabupaten contoh'],'Kabupaten Contoh, Aceh')
        self.assertEqual(aliases['kota contoh'],'Kota Contoh, Aceh')
        catalog=build_catalog(self.children+self.parents)
        for c in catalog:c['area_aliases']=aliases
        grouped=group_catalog(catalog)
        ai=PilotAI(None,grouped)
        self.assertEqual(ai.canonical_area('Aceh Selatan'),'Kabupaten Aceh Selatan, Aceh')
        self.assertEqual(ai.canonical_area('Contoh'),'Contoh')
        self.assertEqual(ai.canonical_area('Kota Contoh'),'Kota Contoh, Aceh')
        self.assertEqual(ai.stated_areas('Kehilangan tutupan pohon di Aceh Selatan 2025?'),['Kabupaten Aceh Selatan, Aceh'])
        selected=select_catalog('kehilangan tutupan pohon Aceh Selatan',grouped)
        self.assertEqual(selected[0]['areas'][0],'Kabupaten Aceh Selatan, Aceh')


if __name__=='__main__':unittest.main()
