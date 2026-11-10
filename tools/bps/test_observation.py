import unittest
from tools.bps.observation import period_fields, unit_fields, standardize, province_reference, area_label
from tools.bps.client import BPSError


class StandardObservationTests(unittest.TestCase):
    def test_source_markup_and_equivalent_abbreviations(self):
        self.assertEqual(area_label('<b>KEP. RIAU</b>'), 'Kepulauan RIAU')
        self.assertEqual(area_label('D I YOGYAKARTA'), 'DI YOGYAKARTA')
        rows=[dict(vertical_axis='Provinsi/Kabupaten/Kota',vertical_id='2100',vertical_label='<b>KEP. RIAU</b>'),
              dict(vertical_axis='Provinsi',vertical_id='21',vertical_label='Kepulauan Riau')]
        self.assertEqual(province_reference(rows)['21'], 'Kepulauan Riau')

    def test_quarter_is_interval_not_single_month(self):
        p = period_fields(2026, 'Triwulan II')
        self.assertEqual((p['month'],p['quarter'],p['period_start'],p['period_end']),
                         (None,2,'2026-04-01','2026-06-30'))
        self.assertEqual(p['temporal_basis'], 'quarter')

    def test_source_semester_label_with_explicit_month_is_not_six_month_total(self):
        p = period_fields(2026, 'Semester 1 (Maret)')
        self.assertEqual((p['month'],p['period_start'],p['period_end']), (3,'2026-03-01','2026-03-31'))
        self.assertEqual(p['period_label_raw'], 'Semester 1 (Maret)')
        self.assertEqual(p['aggregation_kind'], '')

    def test_leap_month_annual_and_unresolved_period(self):
        self.assertEqual(period_fields(2024,'Februari')['period_end'], '2024-02-29')
        self.assertEqual(period_fields(2026,'Tahunan')['period_end'], '2026-12-31')
        self.assertEqual(period_fields(2026,'Tahunan')['period_text'], '')
        with self.assertRaises(BPSError): period_fields(2026,'Semester 1')
        with self.assertRaises(BPSError): period_fields(2026,'Januari–Maret')

    def test_case_and_scale_normalization(self):
        self.assertEqual(unit_fields('Persen')['unit'],unit_fields('%')['unit'])
        self.assertEqual(unit_fields('Ribu Jiwa')['unit_scale'],'1000')
        self.assertEqual(unit_fields('Orang')['unit_scale'],'1')
        self.assertEqual(unit_fields('Milyar Rupiah')['unit'], 'miliar rupiah')
        with self.assertRaises(BPSError): unit_fields('Tidak Ada Satuan')

    def test_source_category_geography_and_provisional_year_preserved(self):
        p=dict(id='uuid',source_record_id='rawid',vertical_label='Kota Contoh',vertical_id='1171',
               vertical_axis='Kabupaten/Kota',derived_label='Perdesaan',derived_id='433',
               title='Indikator',source='Badan Pusat Statistik',year=2026,
               notes='<p>Tahun 2025: Angka sementara<br>Tahun 2026: Angka sangat sangat sementara</p>',
               source_snapshot_sha256='sha',domain='0000',variable_id='var',period_id='126',
               subperiod_id='31',source_cell='cell',subperiod_label='Triwulan I',unit='Persen',value='1.234567890123456789')
        r=standardize(p,{'11':'Aceh'})
        self.assertEqual(r['value'],p['value'])
        self.assertEqual((r['geographic_level'],r['boundary_type'],r['province_context']),('adm2','Kota','Aceh'))
        self.assertEqual(r['population'],'rural')
        self.assertEqual(r['category_id'],'433')
        self.assertEqual(r['data_status'],'provisional')
        self.assertEqual(r['data_status_note'],'Angka sangat sangat sementara')
        p['notes']='Tahun 2025: Angka sementara'
        self.assertEqual(standardize(p,{'11':'Aceh'})['data_status'],'published_status_unspecified')
        with self.assertRaises(BPSError): standardize(p,{})
        p.update(vertical_axis='Provinsi/Kabupaten/Kota',vertical_id='1100',vertical_label='<b>ACEH</b>')
        r=standardize(p,{'11':'ACEH'})
        self.assertEqual((r['geographic_level'],r['area']),('adm1','ACEH'))
        self.assertEqual(r['original_row']['vertical_label'],'<b>ACEH</b>')

if __name__=='__main__': unittest.main()
