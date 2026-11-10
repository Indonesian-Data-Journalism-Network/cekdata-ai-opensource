import unittest
import tempfile
from pathlib import Path
from tools.bps.static import grids,make_document,classify,collect
from tools.bps.client import BPSError

class StaticTests(unittest.TestCase):
 def test_spans_keep_header_association_and_missing_cells(self):
  html='<table><tr><th rowspan="2">Provinsi</th><th colspan="2">2019</th></tr><tr><th>Maret</th><th>September</th></tr><tr><td>Aceh</td><td>1.234,56</td><td>-</td></tr></table>'
  t=grids(html)[0]
  self.assertEqual(t['grid'][0][0],t['grid'][1][0]);self.assertEqual(t['grid'][0][1],t['grid'][0][2])
  self.assertEqual(t['cells'][t['grid'][2][1]]['text'],'1.234,56')
  self.assertEqual(t['cells'][t['grid'][2][2]]['text'],'-')
 def test_update_date_and_title_not_observation_year(self):
  d=make_document({'table_id':1,'title':'Kemiskinan 2026','updt_date':'2026-11-07','table':'<table><tr><td>2019</td><td>2020*</td><td>2027</td></tr></table>'},{'retrieved_at':'now','sha256':'x'},['kemiskinan_ketimpangan'],2019,2026)
  self.assertEqual(d['years_with_label_candidates'],[2019,2020]);self.assertFalse(d['ready_for_numeric_answers']);self.assertFalse(d['source_url_verified'])
 def test_unrecognised_layout_preserved_without_guessed_period(self):
  d=make_document({'table_id':1,'title':'Angka','table':'<p>Catatan: tahun dasar 2019.</p><table><tr><td>Jan</td><td>12,5</td></tr></table>'},{'retrieved_at':'now','sha256':'x'},[],2019,2026)
  self.assertEqual(d['year_cell_candidates'],[]);self.assertIn('tahun dasar 2019',d['text'])
 def test_topic_discovery_is_multi_label(self):
  self.assertIn('pendidikan',classify('Rata-rata Lama Sekolah'))
  self.assertIn('konsumsi',classify('Rata-rata Pengeluaran per Kapita'))
  self.assertIn('kriminalitas',classify('Jumlah Kejahatan'))
 def test_collect_excludes_only_known_old_catalogue_entries(self):
  with tempfile.TemporaryDirectory() as tmp:
   class A:
    root=Path(tmp)
    calls=[]
    def list(self,path,params):
     return [{'table_id':1,'title':'Upah 2018','updt_date':'2018-12-01'}, {'table_id':2,'title':'Upah 2018','updt_date':'2026-01-01'}, {'table_id':3,'title':'Upah 2019','updt_date':'2020-01-01'}],[]
    def get(self,path):
     self.calls.append(path);ident=int(path.rsplit('/',1)[1])
     return {'data-availability':'available','data':{'table_id':ident,'title':'Upah','table':'<table><tr><td>2019</td></tr></table>'}}, {'sha256':'x','retrieved_at':'now'}
   a=A();m=collect(a,2019,2026)
   self.assertEqual(m['archived_tables'],2);self.assertEqual(len(m['excluded_before_period']),1)
   self.assertTrue(all('/id/1' not in x for x in a.calls));self.assertFalse(m['qdrant_ingested'])
 def test_bad_span_stops_not_silently_shifted(self):
  with self.assertRaises(BPSError):grids('<table><tr><td rowspan="0">X</td></tr></table>')

if __name__=='__main__':unittest.main()
