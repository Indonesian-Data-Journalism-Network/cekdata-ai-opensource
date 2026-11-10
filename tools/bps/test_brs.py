import json,tempfile,unittest
from pathlib import Path
from tools.bps.brs import record,plain_text,collect,safe_download_url
from tools.bps.client import BPSError


def fixture():
 return {'status':'OK','data-availability':'available','data':{'brs_id':123,'title':'Statistik contoh 2025','rl_date':'2026-02-01','abstract':'<p>Nilai 2025 sebesar <b>1,25</b> persen.</p><p>Naik 0,05 poin.</p>','pdf':'https://webapi.bps.go.id/download.php?f=fixture','subj':'Contoh'}}

class BRSTests(unittest.TestCase):
 def test_title_and_abstract_keep_period_values_and_no_release_year_inference(self):
  r=record(fixture(),{'sha256':'sample','retrieved_at':'2026-11-07'},'0000','https://www.bps.go.id',2026)
  self.assertIn('1,25 persen',r['text']);self.assertIn('2025',r['text'])
  self.assertEqual(r['observation_periods'],[]);self.assertEqual(r['release_year'],2026)
  self.assertFalse(r['download_file_fetched']);self.assertFalse(r['ready_for_numeric_answers'])
 def test_missing_abstract_not_invented_and_release_filter_checked(self):
  d=fixture();d['data']['abstract']=''
  self.assertEqual(record(d,{'sha256':'x','retrieved_at':'t'},'0000','https://www.bps.go.id',2026)['text_status'],'empty_abstract')
  with self.assertRaises(BPSError):record(d,{'sha256':'x','retrieved_at':'t'},'0000','https://www.bps.go.id',2025)
 def test_parser_and_download_reference(self):
  self.assertEqual(plain_text('<script>bad</script><p>1&nbsp;orang</p>'),'1 orang')
  self.assertEqual(safe_download_url('https://example.com/unknown.pdf'),'')
  self.assertEqual(safe_download_url('https://webapi.bps.go.id/key/secret'),'')
 def test_collect_never_requests_pdf_and_stages_only_text(self):
  with tempfile.TemporaryDirectory() as tmp:
   class Archive:
    root=Path(tmp)
    requests=[]
    def list(self,path,params):return [{'brs_id':123}],[]
    def get(self,path):
     self.requests.append(path)
     return fixture(),{'sha256':'source','retrieved_at':'2026-11-07'}
   a=Archive();m=collect(a,2026)
   self.assertEqual(a.requests,['view/domain/0000/model/pressrelease/lang/ind/id/123'])
   self.assertEqual(m['pdf_downloads'],0);self.assertEqual(m['with_abstract'],1)
   self.assertFalse(m['qdrant_ingested'])

if __name__=='__main__':unittest.main()
