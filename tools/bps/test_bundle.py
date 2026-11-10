import copy,hashlib,unittest
from tools.bps.bundle import national_payload,source_chunks
from tools.bps.national import national_rows
from tools.bps.ingest import normalize
from tools.bps.test_ingest import table

class BundleTests(unittest.TestCase):
 def row(self):
  d=table();d['vervar'][0]['label']='Indonesia'
  rows,_=normalize(d,'0000','12','125')
  return national_rows(rows,d,{'topics':[]},{'sha256':'fixture','retrieved_at':'2026-11-07'},'https://www.bps.go.id/')[0]
 def test_sector_identity_does_not_collapse_to_national_total(self):
  a=self.row();a['categories']=[{'axis':'vervar','id':'a','label':'Pertanian'},{'axis':'turvar','id':'0','label':'Harga Berlaku'}]
  b=copy.deepcopy(a);b['categories'][0]={'axis':'vervar','id':'b','label':'Industri'}
  pa,pb=national_payload(a),national_payload(b)
  self.assertNotEqual(pa['indicator_id'],pb['indicator_id']);self.assertIn('Pertanian',pa['indicator']);self.assertEqual(pa['area'],'Indonesia')
 def test_held_units_and_potential_cannot_enter_numeric_answers(self):
  a=self.row();a['status']='missing_unit';self.assertFalse(national_payload(a)['usable'])
  a=self.row();a['data_status']='potential';self.assertFalse(national_payload(a)['usable'])
  a=self.row();a['period_ended_at_retrieval']=False;self.assertFalse(national_payload(a)['usable'])
 def test_zero_and_country_source_metadata_survive(self):
  a=self.row();p=national_payload(a)
  self.assertTrue(p['usable']);self.assertEqual(p['value'],'0');self.assertEqual(p['original_row'],a)
  self.assertEqual(p['source_locator']['source_cell'],a['source_cell'])
  self.assertEqual(p['id'],national_payload(a)['id'])
 def test_lossless_document_chunks_with_original_html_and_unicode(self):
  d={'id':'d','title':'Judul','source_url':'https://www.bps.go.id/','source_snapshot_sha256':'sha','source_type':'bps_static_table','retrieved_at':'2026-11-07','text':'kalimat α\n'*3000,'html':'<table><td>1,23</td></table>'*2500}
  chunks=list(source_chunks(d));self.assertTrue(all(not p['usable'] for p in chunks))
  self.assertEqual(len({p['id'] for p in chunks}),len(chunks))
  for kind in ['text','html']:
   ps=[p for p in chunks if p['record_type']==kind+'_chunk'];joined=''.join(p['text' if kind=='text' else 'content'] for p in ps)
   self.assertEqual(joined,d[kind]);self.assertEqual(hashlib.sha256(joined.encode()).hexdigest(),ps[0]['body_sha256'])

if __name__=='__main__':unittest.main()
