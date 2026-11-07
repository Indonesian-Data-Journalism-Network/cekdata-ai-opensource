import json
from pathlib import Path
import unittest
from datetime import date
from geography import Geography, REFERENCE
from pilot_data import PilotAI, group_catalog, IndicatorSelection
from flow import Intent

ROOT=Path(__file__).resolve().parents[2]

def reference_catalog():
    entries=json.loads(REFERENCE.read_text())['entries']
    areas=sorted({b['area'] for e in entries for b in e['source_bindings'] if b['provider']=='gfw'})
    return [dict(indicator_id='gfw-tree-cover-loss',label='Kehilangan tutupan pohon menurut kabupaten/kota',
                 source='Global Forest Watch / UMD GLAD',areas=areas,years=[2024,2025],populations=['total'],unit='ha')]

class GeographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=reference_catalog()
        cls.geo=Geography(cls.catalog)

    def test_source_identity_and_integrity(self):
        ref=json.loads(REFERENCE.read_text());entries=ref['entries'];ids={e['id'] for e in entries}
        self.assertEqual(len(entries),len(ids))
        self.assertEqual(ref['counts']['kabupaten']+ref['counts']['kota'],498)
        self.assertEqual(ref['excluded_water_bodies'],4)
        for e in entries:
            if e.get('parent_id'):self.assertIn(e['parent_id'],ids)
            for i in e.get('member_ids',[]):self.assertIn(i,ids)
            self.assertTrue(e['source_url'].startswith('https://'))

    def test_nested_address_is_one_target(self):
        for question in ['Kota Jambi, Jambi','Kota Jambi, Provinsi Jambi',
                         'Bandingkan angka Kota Jambi, Jambi pada 2024 dan 2025',
                         'Kota Jambi di Prov. Jambi', 'Kota Jambi, Jambi, Indonesia',
                         'Jambi khususnya Kota Jambi']:
            self.assertEqual(self.geo.resolve(question).areas,['Kota Jambi, Jambi'])

    def test_explicit_parent_comparison_is_preserved(self):
        for question in ['Bandingkan Kota Jambi dengan Provinsi Jambi',
                         'Kota Jambi dan Jambi', 'Kota Jambi versus Provinsi Jambi']:
            self.assertEqual(self.geo.resolve(question).areas,['Kota Jambi, Jambi','Jambi'])

    def test_reviewed_abbreviations_and_original_source_keys(self):
        cases={'Kab. Bandung, Jabar':'Kabupaten Bandung, Jawa Barat',
               'Tanjabtim, Jambi':'Kabupaten Tanjung Jabung T, Jambi',
               'Tanjung Jabung Timur':'Kabupaten Tanjung Jabung T, Jambi',
               'Tanjabbar':'Kabupaten Tanjung Jabung B, Jambi',
               'Kota Tarakan, Kaltara':'Tarakan, Kalimantan Utara',
               'Kab. Nunukan':'Nunukan, Kalimantan Utara','NTB':'Nusa Tenggara Barat',
               'Sumatra Selatan':'Sumatera Selatan','Kab. Agam, Sumatra Barat':'Kabupaten Agam, Sumatera Barat'}
        for q,area in cases.items():
            with self.subTest(q=q):self.assertEqual(self.geo.resolve(q).areas,[area])

    def test_ambiguous_names_are_not_guessed(self):
        for q in ['Bandung','Malang','Bogor','Bandung, Jabar']:
            self.assertTrue(self.geo.resolve(q).clarification,q)
        self.assertEqual(self.geo.resolve('Kota Malang dan Kab. Malang').areas,
                         ['Kota Malang, Jawa Timur','Kabupaten Malang, Jawa Timur'])

    def test_unavailable_region_does_not_use_parent(self):
        self.assertEqual(self.geo.resolve('Papua Selatan').areas,['Papua Selatan'])
        self.assertEqual(self.geo.resolve('Pulau Papua').areas,['Pulau Papua'])
        self.assertEqual(self.geo.resolve('Pulau Bali').areas,['Pulau Bali'])
        self.assertEqual(self.geo.resolve('Bali').areas,['Bali'])
        self.assertEqual(self.geo.resolve('nasional').areas,['Indonesia'])
        self.assertEqual(self.geo.resolve('Sumatra').areas,['Sumatera'])

    def test_source_specific_island_group_and_locality(self):
        self.assertEqual(self.geo.resolve('Kepulauan Maluku').areas,['Kepulauan Maluku'])
        self.assertEqual(self.geo.resolve('Maluku').areas,['Maluku'])
        self.assertEqual(self.geo.resolve('Pulau Kabaena').areas,['Pulau Kabaena'])
        self.assertEqual(self.geo.reconcile('Desa Baliara, Kabupaten Bombana',['Baliara']).areas,['Baliara'])
        # General's unique short names retain their actual filter keys.
        g=Geography([{'areas':['Brebes']}])
        self.assertEqual(g.canonical('Kab. Brebes'),'Brebes')

    def test_all_reference_children_resolve_without_parent(self):
        for e in self.geo.entities.values():
            if e['level'] in {'kabupaten','kota'}:
                b=e['source_bindings'][0]
                expected=self.geo.destination(e['id'])
                with self.subTest(area=b['area']):
                    self.assertEqual(self.geo.resolve('Berapa luas hutan di '+b['area']+'?').areas,[expected])

    def test_prior_random_suite_scope(self):
        plan=ROOT/'tmp/gfw-district100-20261106/plan.json'
        if not plan.exists():self.skipTest('Local evaluation artifact unavailable')
        for case in json.loads(plan.read_text()):
            with self.subTest(id=case['id']):
                actual=self.geo.reconcile(case['question'],[case['area'],case['area'].split(', ')[-1]])
                self.assertEqual(actual.areas,[case['area']])

class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_extra_province_is_removed_before_retrieval(self):
        catalog=group_catalog(reference_catalog())
        class Model:
            async def astructured_predict(self,schema,prompt,**kw):
                if issubclass(schema,Intent):return Intent(kind='lookup',areas=['Kota Jambi','Jambi'],indicator_terms=['kehilangan tutupan pohon'])
                rows=json.loads(kw['catalog'])
                return IndicatorSelection(indicator_ids=[rows[0]['indicator_id']])
        ai=PilotAI(Model(),catalog)
        result=await ai.understand('Berapa kehilangan tutupan pohon GFW di Kota Jambi, Jambi pada 2025?',date(2026,11,6),[])
        self.assertEqual(result.areas,['Kota Jambi, Jambi'])
        other=await ai.understand('Bandingkan kehilangan tutupan pohon GFW Kota Jambi dengan Provinsi Jambi pada 2025?',date(2026,11,6),[])
        self.assertEqual(other.areas,['Kota Jambi, Jambi','Jambi'])
