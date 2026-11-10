import json,unittest
from decimal import Decimal
import httpx
from pinecone_client import PineconeClient,PineconeUnavailable
class ClientTests(unittest.TestCase):
 def client(self,handler):return PineconeClient('fixture-secret','fixture.svc.pinecone.io','statistics',client=httpx.Client(transport=httpx.MockTransport(handler)))
 def test_query_preserves_numeric_metadata_and_namespace(self):
  def handle(r):
   body=json.loads(r.content);self.assertEqual(body['namespace'],'statistics');self.assertFalse(body['includeValues']);self.assertTrue(body['includeMetadata']);self.assertEqual(body['filter'],{'year':2025})
   return httpx.Response(200,text='{"matches":[{"id":"x","metadata":{"value":60124.53381805515000468}}]}')
  c=self.client(handle)
  self.assertEqual(c.query([.1,.2],filters={'year':2025})['matches'][0]['metadata']['value'],Decimal('60124.53381805515000468'))
 def test_credentials_never_follow_redirect_or_escape_errors(self):
  for status in [301,401,403,429,500]:
   c=self.client(lambda r:httpx.Response(status,text='fixture-secret upstream details',headers={'location':'https://evil.org'}))
   with self.assertRaises(PineconeUnavailable) as e:c.query([1])
   self.assertNotIn('fixture-secret',str(e.exception));self.assertNotIn('upstream',str(e.exception))
 def test_write_operations_and_invalid_hosts_rejected(self):
  for host in ['evil.org','test.pinecone.io.evil.org','user@api.pinecone.io','api.pinecone.io/path']:
   with self.assertRaises(ValueError):PineconeClient('key',host)
  c=self.client(lambda r:self.fail('must not request'))
  for path in ['/vectors/upsert','/vectors/delete']:
   with self.assertRaises(ValueError):c._request('POST',path)
  for vector in [[float('nan')],[],['1']]:
   with self.assertRaises(ValueError):c.query(vector)
  with self.assertRaises(ValueError):c.query([1],top_k=1001)
if __name__=='__main__':unittest.main()
