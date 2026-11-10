import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import connect_server as server

class Reader:
 def __init__(self,key):pass
 def indexes(self):return [{'name':'fixture','host':'fixture.svc.pinecone.io','dimension':3,'metric':'cosine'}]
 def namespaces(self,index):return {'':{'vector_count':123456}}
 def request(self,method,host,path,**kwargs):
  assert method=='GET' and path=='/vectors/list' and kwargs['params']['limit']==20
  return {'vectors':[{'id':'sample'}]},b''
 def fetch_batches(self,host,namespace,ids):yield ids,{'vectors':{'sample':{'metadata':{'year':2025,'value':'12.5','source_url':'https://example.org/table'}}}},b''
 def close(self):pass

class SetupTests(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
  self.path=Path(self.directory.name)/'connection.json'
  self.enterContext(patch.object(server,'CONFIG',self.path))
  self.enterContext(patch.object(server,'PineconeReader',Reader))
  self.client=self.enterContext(TestClient(server.app,base_url=server.ORIGIN,headers={'Origin':server.ORIGIN}))
  self.data={'api_key':'fixture-pinecone-secret','index':'fixture','namespace':''}
 def test_private_setup_is_bounded_and_does_not_activate_unvalidated_data(self):
  r=self.client.post('/api/save',json=self.data)
  self.assertEqual(r.status_code,200);self.assertNotIn(self.data['api_key'],r.text)
  obj=json.loads(self.path.read_text());self.assertFalse(obj['enabled']);self.assertEqual(obj['namespace'],'')
  self.assertEqual(self.path.stat().st_mode&0o777,0o600)
  self.assertEqual(self.client.post('/api/save',json=self.data).status_code,400)
 def test_origin_and_validation_do_not_echo_credentials(self):
  self.assertEqual(self.client.post('/api/save',json=self.data,headers={'origin':'https://evil.org'}).status_code,403)
  r=self.client.post('/api/save',json={'api_key':'short'})
  self.assertEqual(r.status_code,422);self.assertNotIn('short',r.text)
  self.assertEqual(self.client.post('/api/delete',json=self.data).status_code,404)
 def test_unknown_index_does_not_get_written(self):
  r=self.client.post('/api/save',json={**self.data,'index':'other'})
  self.assertEqual(r.status_code,400);self.assertFalse(self.path.exists())
if __name__=='__main__':unittest.main()
