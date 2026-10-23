import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from exporter import PineconeReader, ExportError
from server import app
import server
from exporter import namespace_count
from unittest.mock import patch

INDEX = {'name':'sample','host':'sample.svc.pinecone.io','dimension':2,'metric':'cosine','spec':{'serverless':{}}}


class ExportTests(unittest.TestCase):
    def test_count_spellings_and_unknown(self):
        for stats in ({'vector_count': 836770}, {'vectorCount': 836770}, {'record_count': '836770'}):
            self.assertEqual(namespace_count(stats), 836770)
        self.assertIsNone(namespace_count({}))
        self.assertEqual(namespace_count({'vectorCount': 0}), 0)

    def test_export_guard_is_per_destination(self):
        with patch.object(server, 'attempted_targets', {('old', '')}), patch.object(server, 'work', return_value={'records': 1, 'status': 'complete'}) as work:
            with TestClient(app, base_url='http://127.0.0.1:8766') as client:
                def submit(index):
                    return client.post('/api/export', json={'api_key': 'fake-test-key', 'index': index, 'namespace': ''}, headers={'Origin': 'http://127.0.0.1:8766'})
                self.assertEqual(submit('old').status_code, 409)
                self.assertEqual(submit('new').status_code, 200)
                self.assertEqual(submit('new').status_code, 409)
                self.assertEqual(work.call_count, 1)

    def test_missing_or_zero_stats_still_lists_records(self):
        for stats in ({}, {'vectorCount': 0}):
            def handler(request):
                if request.url.path == '/describe_index_stats':
                    return httpx.Response(200, json={'namespaces': {'new': stats}})
                if request.url.path == '/vectors/list':
                    return httpx.Response(200, json={'vectors': [{'id': 'a'}]})
                return httpx.Response(200, json={'vectors': {'a': {'id': 'a', 'values': [1, 2]}}})
            reader = PineconeReader('fake', httpx.Client(transport=httpx.MockTransport(handler)))
            with tempfile.TemporaryDirectory() as root:
                self.assertEqual(reader.export(INDEX, 'new', root, limit=1)['records'], 1)
            reader.close()

    def reader(self, missing=False, bad_dimension=False):
        self.calls = []
        def handler(request):
            path = request.url.path
            self.calls.append((request.method, path))
            if path == '/describe_index_stats':
                return httpx.Response(200,json={'namespaces':{'':{'vector_count':2000}}})
            if path == '/vectors/list':
                start = int(request.url.params.get('pagination_token','0'))
                size = int(request.url.params.get('limit'))
                return httpx.Response(200,json={'vectors':[{'id':str(x)} for x in range(start,start+size)],
                    'pagination':{'next':str(start+size)},'usage':{'readUnits':1}})
            if path == '/vectors/fetch':
                ids = request.url.params.get_list('ids')
                records = []
                for id in ids:
                    if missing and id == '0':continue
                    vector = '[0.5]' if bad_dimension else '[0.123456789012345678901234,0.5]'
                    records.append(json.dumps(id)+':{"id":'+json.dumps(id)+',"values":'+vector+',"metadata":{"value":12.330000000000000000001,"source":"BPS","source_url":"https://example.org/tabel?a=1&b=2"}}')
                return httpx.Response(200,content=('{"vectors":{'+','.join(records)+'},"usage":{"readUnits":10}}').encode())
            raise AssertionError('Unexpected request')
        return PineconeReader('fake-test-key-not-real', httpx.Client(transport=httpx.MockTransport(handler)))

    def test_limit_and_lossless_metadata(self):
        reader = self.reader()
        with tempfile.TemporaryDirectory() as root:
            result = reader.export(INDEX,'',root)
            self.assertEqual(result['records'],1000)
            self.assertEqual(result['status'],'complete')
            self.assertEqual(result['read_units'],110)
            rows = [json.loads(line,parse_float=Decimal) for line in (Path(result['folder'])/'records.jsonl').read_text().splitlines()]
            self.assertEqual(len({r['id'] for r in rows}),1000)
            self.assertEqual(rows[0]['metadata']['value'],Decimal('12.330000000000000000001'))
            self.assertEqual(rows[0]['metadata']['source_url'],'https://example.org/tabel?a=1&b=2')
            self.assertEqual(rows[0]['values'][0],Decimal('0.123456789012345678901234'))
            self.assertEqual(sum(path=='/vectors/fetch' for _,path in self.calls),10)
            self.assertTrue(all(method=='GET' or path=='/describe_index_stats' for method,path in self.calls))
        reader.close()

    def test_missing_record_is_partial_without_reading_extra(self):
        reader = self.reader(missing=True)
        with tempfile.TemporaryDirectory() as root:
            result = reader.export(INDEX,'',root)
            self.assertEqual(result['records'],999)
            self.assertEqual(result['status'],'partial')
            self.assertEqual(sum(path=='/vectors/list' for _,path in self.calls),10)
        reader.close()

    def test_wrong_dimension_retains_raw_and_stops(self):
        reader = self.reader(bad_dimension=True)
        with tempfile.TemporaryDirectory() as root:
            result=reader.export(INDEX,'',root)
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['records'],0)
            self.assertTrue((Path(result['folder'])/'raw/fetch-01.json').exists())
            self.assertEqual(sum(path=='/vectors/fetch' for _,path in self.calls),1)
        reader.close()

    def test_prevents_other_hosts_and_write_operations(self):
        reader=self.reader()
        with self.assertRaises(ExportError):reader.request('GET','evil.example','/indexes')
        with self.assertRaises(ExportError):reader.request('POST',INDEX['host'],'/vectors/upsert')
        self.assertEqual(self.calls,[])
        reader.close()

    def test_long_encoded_ids_split_and_preserve_all_1000_records(self):
        ids = [f'{i:04}-' + 'wilayah /% Aceh?' * 14 for i in range(1000)]
        successful_ids, paths, successful_batches = [], [], []
        def handler(request):
            if request.url.path == '/describe_index_stats':
                return httpx.Response(200,json={'namespaces':{'ruang /':{'vector_count':10000}}})
            if request.url.path == '/vectors/list':
                start=int(request.url.params.get('pagination_token','0'))
                return httpx.Response(200,json={'vectors':[{'id':v} for v in ids[start:start+100]],
                    'pagination':{'next':str(start+100)},'usage':{'readUnits':1}})
            self.assertEqual(request.url.path,'/vectors/fetch')
            paths.append(len(str(request.url).encode('ascii')))
            batch=request.url.params.get_list('ids')
            # Emulate a proxy with a stricter limit than our packing target.
            if len(request.url.raw_path)>1100:return httpx.Response(414)
            successful_ids.extend(batch)
            successful_batches.append(batch)
            self.assertEqual(request.url.params['namespace'],'ruang /')
            return httpx.Response(200,json={'vectors':{v:{'id':v,'values':[0.2,0.3],
                'metadata':{'source_url':'https://example.org/original'}} for v in batch},'usage':{'readUnits':1}})
        reader=PineconeReader('fake',httpx.Client(transport=httpx.MockTransport(handler)))
        with tempfile.TemporaryDirectory() as root:
            result=reader.export(INDEX,'ruang /',root)
            self.assertEqual(result['status'],'complete')
            self.assertEqual(result['records'],1000)
            self.assertEqual(successful_ids,ids)
            self.assertLessEqual(max(paths),2000)
            self.assertGreater(reader.fetch_414s,0)
            folder=Path(result['folder'])
            self.assertEqual(len(list((folder/'raw').glob('*.json'))),len(successful_batches))
            rows=[json.loads(x) for x in (folder/'records.jsonl').read_text().splitlines()]
            self.assertEqual([r['id'] for r in rows],ids)
        reader.close()

    def test_single_id_414_and_other_errors_stop(self):
        for code in [414,429,500]:
            reader=PineconeReader('fake',httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(code))))
            with self.assertRaises(ExportError):list(reader.fetch_batches(INDEX['host'],'',['long-id']))
            self.assertEqual(reader.fetch_attempts,1)
            reader.close()

    def test_local_input_errors_do_not_echo_secret(self):
        with TestClient(app,base_url='http://127.0.0.1:8766') as client:
            response=client.post('/api/indexes',json={'api_key':'short'},headers={'Origin':'http://127.0.0.1:8766'})
            self.assertEqual(response.status_code,422)
            self.assertNotIn('short',response.text)
            response=client.post('/api/indexes',json={'api_key':'fake-test-key'},headers={'Origin':'https://other.example'})
            self.assertEqual(response.status_code,403)

    def test_10000_additional_skip_previous_and_never_fetch_over_limit(self):
        fetched=[]
        def handler(request):
            if request.url.path=='/describe_index_stats':
                return httpx.Response(200,json={'namespaces':{'':{'vector_count':20000}}})
            if request.url.path=='/vectors/list':
                start=int(request.url.params.get('pagination_token','0'))
                return httpx.Response(200,json={'vectors':[{'id':str(n)} for n in range(start,start+100)],'pagination':{'next':str(start+100)}})
            ids=request.url.params.get_list('ids');fetched.extend(ids)
            return httpx.Response(200,json={'vectors':{i:{'id':i,'values':[0.2,0.3],'metadata':{'source_url':'https://example.org/source'}} for i in ids}})
        reader=PineconeReader('fake',httpx.Client(transport=httpx.MockTransport(handler)))
        with tempfile.TemporaryDirectory() as root:
            result=reader.export(INDEX,'',root,limit=10000,exclude_ids={str(n) for n in range(1000)})
            self.assertEqual(result['status'],'complete')
            self.assertEqual(result['records'],10000)
            self.assertEqual(fetched,[str(n) for n in range(1000,11000)])
            self.assertEqual(len(set(fetched)),10000)
            manifest=json.loads((Path(result['folder'])/'manifest.json').read_text())
            self.assertEqual(manifest['list_requests'],110)
            self.assertEqual(manifest['excluded_previous_ids'],1000)
        reader.close()


if __name__=='__main__':unittest.main(verbosity=2)
