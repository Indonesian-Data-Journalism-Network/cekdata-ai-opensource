import copy,unittest
from tools.bps.client import BPSError
from tools.bps.ingest import normalize
from tools.bps.national import national_rows,country_scope
from tools.bps.test_ingest import table

class NationalTests(unittest.TestCase):
 def fixture(self):
  d=table();d['vervar'] += [{'val':999,'label':'INDONESIA'}]
  d['datacontent'].update({k.replace('31','999',1):v for k,v in list(d['datacontent'].items())})
  rows,_=normalize(d,'0000','12','125');return d,rows
 def test_country_is_filtered_not_provinces_summed(self):
  d,rows=self.fixture();selected=national_rows(rows,d,{'topics':['test']},{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertEqual(len(selected),4);self.assertTrue(all(r['vertical_id']=='999' for r in selected))
  self.assertEqual(selected[1]['value'],'12.34567890123456789');self.assertEqual(selected[2]['status'],'missing');self.assertIsNone(selected[2]['value'])
  self.assertEqual(selected[0]['categories'][0]['axis'],'turvar')
 def test_total_does_not_mean_indonesia(self):
  d=table();d['vervar'][0]['label']='Jumlah'
  with self.assertRaises(BPSError):country_scope(d,{})
 def test_country_on_derived_axis_preserves_sector_as_category(self):
  d=table();d['labelvervar']='Sektor';d['turvar'][0]['label']='Indonesia'
  rows,_=normalize(d,'0000','12','125');selected=national_rows(rows,d,{'topics':['test']},{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertEqual(len(selected),2);self.assertEqual(selected[0]['categories'][0]['label'],'Wilayah uji')
 def test_whole_table_needs_evidence_and_exact_axes(self):
  d=table();d['labelvervar']='Komoditas'
  review={'mode':'whole_table','reviewed':True,'vertical_axis':'Komoditas','vertical_members':[{'id':'31','label':'Wilayah uji'}],'evidence':'Reviewed official national table with commodity axis'}
  self.assertEqual(country_scope(d,{'national_scope_review':review})[0],'whole_table')
  d['vervar'][0]['label']='Changed'
  with self.assertRaises(BPSError):country_scope(d,{'national_scope_review':review})
 def test_reviewed_member_is_bound_to_source_label_and_axis(self):
  d=table();d['vervar'][0]['label']='RATA-RATA'
  review={'mode':'member','reviewed':True,'axis':'vervar','vertical_axis':'Provinsi','members':[{'id':'31','label':'RATA-RATA'}],'evidence':'Source-specific review'}
  self.assertEqual(country_scope(d,{'national_scope_review':review})[1],{'31'})
  d['vervar'][0]['label']='Other'
  with self.assertRaises(BPSError):country_scope(d,{'national_scope_review':review})
 def test_missing_unit_remains_held(self):
  d,_=self.fixture();d['var'][0]['unit']='Tidak Ada Satuan';rows,_=normalize(d,'0000','12','125')
  selected=national_rows(rows,d,{'topics':[]},{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertEqual(selected[0]['status'],'missing_unit');self.assertEqual(selected[0]['value'],'0');self.assertFalse(selected[0]['usable_for_answers'])
 def test_provisional_status_follows_observation_year_note(self):
  d,_=self.fixture();d['var'][0]['note']='<p>2024: Angka sementara<br />2025: Angka sangat sementara<br />2026: Angka sangat sangat sementara</p>'
  rows,_=normalize(d,'0000','12','125')
  for r in rows:r['year_label']='2025'
  selected=national_rows(rows,d,{'topics':[]},{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertEqual(selected[0]['data_status'],'provisional');self.assertEqual(selected[0]['data_status_note'],'Angka sangat sementara')
  for r in rows:r['year_label']='2023'
  selected=national_rows(rows,d,{'topics':[]},{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertEqual(selected[0]['data_status'],'published_status_unspecified')
  d['var'][0]['note']='September 2026 adalah angka sementara; data Januari-Agustus 2026 adalah angka tetap.'
  rows,_=normalize(d,'0000','12','125')
  for r in rows:r['year_label']='2026'
  selected=national_rows(rows,d,{'topics':[]},{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertEqual(next(r for r in selected if r['subperiod_label']=='September')['data_status'],'provisional')
  self.assertEqual(next(r for r in selected if r['subperiod_label']=='Maret')['data_status'],'published_status_unspecified')
 def test_category_units_are_kept_distinct(self):
  d,_=self.fixture();d['var'][0]['unit']='Tidak Ada Satuan'
  d['datacontent']={k:'1.5' for k in d['datacontent']}
  d['turvar'][0]['label']='Luas Panen (ha)';d['turvar'][1]['label']='Produktivitas (ku/ha)'
  rows,_=normalize(d,'0000','12','125')
  selected=national_rows(rows,d,{'topics':[]},{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  observed=[r for r in selected if r['status']=='observed']
  self.assertEqual({r['unit'] for r in observed},{'Hektar','Kuintal/Hektar'})
  self.assertTrue(all(r['unit_origin']=='explicit_source_category_suffix' for r in observed))
 def test_potential_month_review_does_not_leak_to_earlier_year(self):
  d,_=self.fixture();d['var'][0]['note']='Produksi September-November adalah angka potensi'
  rows,_=normalize(d,'0000','12','125')
  t={'topics':[],'period_status_review':{'reviewed':True,'evidence':'Reviewed current year only','rules':[{'year':2026,'first_month':9,'last_month':11,'status':'potential','source_note':d['var'][0]['note']}]}}
  earlier=national_rows(rows,d,t,{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertTrue(all(r['data_status']!='potential' for r in earlier))
  for r in rows:r['year_label']='2026'
  current=national_rows(rows,d,t,{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')
  self.assertEqual(next(r for r in current if r['subperiod_label']=='September')['data_status'],'potential')
  self.assertNotEqual(next(r for r in current if r['subperiod_label']=='Maret')['data_status'],'potential')
  for r in rows:r['notes']='Changed source note'
  with self.assertRaises(BPSError):national_rows(rows,d,t,{'sha256':'x','retrieved_at':'now'},'https://www.bps.go.id/')

if __name__=='__main__':unittest.main()
