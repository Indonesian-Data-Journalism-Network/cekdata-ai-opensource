import unittest
from unittest.mock import patch
from gfw_sources import public_evidence, DATASET_PAGE


class PublicSourceTests(unittest.TestCase):
    def setUp(self):
        self.api='https://data-api.globalforestwatch.org/dataset/gadm__tcl__adm2_change/v20260424'
        self.row={'source_record_id':'gfw:gadm__tcl__adm2_change:v20260424:IDN:1.5:2025:t30:tree-cover-loss',
            'source_url':self.api,'download_url':self.api+'/download/json?sql=original',
            'value':'3781.42822450286826391','source_note':'Original definition.'}

    def test_verified_public_page_preserves_exact_numeric_api_provenance(self):
        url='https://www.globalforestwatch.org/dashboards/country/IDN/1/5/'
        with patch('gfw_sources.public_sources',return_value={'adm2:1.5':{'url':url}}):
            row=public_evidence(self.row)
        self.assertEqual(row['source_url'],url)
        self.assertEqual(row['api_source_url'],self.api)
        self.assertEqual(row['download_url'],self.row['download_url'])
        self.assertEqual(row['value'],self.row['value'])
        self.assertEqual(self.row['source_url'],self.api)
        self.assertIn('versi arsip',row['source_note'])

    def test_unverified_region_uses_official_dataset_not_invented_dashboard(self):
        with patch('gfw_sources.public_sources',return_value={}):
            row=public_evidence(self.row)
        self.assertEqual(row['source_url'],DATASET_PAGE)
        self.assertIn('Halaman wilayah belum terverifikasi',row['source_note'])

    def test_unrelated_source_and_invalid_identity_untouched(self):
        for row in ({**self.row,'source_record_id':'other'}, {**self.row,'source_url':'https://example.org/data'},
                    {**self.row,'source_record_id':self.row['source_record_id'].replace('1.5','None')}):
            self.assertIs(public_evidence(row),row)
