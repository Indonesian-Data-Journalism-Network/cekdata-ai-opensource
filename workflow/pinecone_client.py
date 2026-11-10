"""Read-only Pinecone REST client with bounded requests and redacted failures."""
from __future__ import annotations
import json
import math
import re
from decimal import Decimal
from urllib.parse import quote
import httpx

API_VERSION='2025-10'
class PineconeUnavailable(RuntimeError):pass

def valid_host(host):
    return isinstance(host,str) and bool(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.pinecone\.io',host))

class PineconeClient:
    def __init__(self,key,host,namespace='',*,client=None):
        if not valid_host(host):raise ValueError('Host Pinecone tidak valid.')
        if not key or len(namespace)>1024:raise ValueError('Konfigurasi Pinecone belum lengkap.')
        self._key=key;self.host=host;self.namespace=namespace
        self.client=client or httpx.Client(timeout=30,follow_redirects=False,trust_env=False)
    def close(self):self.client.close()
    def _request(self,method,path,*,control=False,**kwargs):
        allowed={( 'GET','/indexes'),('POST','/query'),('POST','/describe_index_stats'),('GET','/vectors/fetch'),('GET','/vectors/list')}
        describe=method=='GET' and re.fullmatch(r'/indexes/[a-z0-9-]{1,45}',path)
        if (method,path) not in allowed and not describe:raise ValueError('Operasi Pinecone di luar izin baca.')
        if control != (path.startswith('/indexes')):raise ValueError('Endpoint Pinecone tidak sesuai.')
        try:
            r=self.client.request(method,'https://'+('api.pinecone.io' if control else self.host)+path,
                headers={'Api-Key':self._key,'X-Pinecone-Api-Version':API_VERSION},**kwargs)
        except httpx.HTTPError:raise PineconeUnavailable('Koneksi Pinecone belum berhasil. Coba kembali.') from None
        if r.status_code!=200:
            messages={401:'Kunci Pinecone belum diterima.',403:'Izin baca Pinecone belum tersedia.',429:'Kuota atau batas permintaan Pinecone tercapai.'}
            raise PineconeUnavailable(messages.get(r.status_code,'Layanan Pinecone belum berhasil merespons.'))
        try:
            obj=json.loads(r.text,parse_float=Decimal)
            if not isinstance(obj,dict):raise ValueError()
            return obj
        except (ValueError,TypeError):raise PineconeUnavailable('Respons Pinecone tidak dapat dibaca.') from None
    def describe(self,name):return self._request('GET','/indexes/'+quote(name,safe=''),control=True)
    def stats(self):return self._request('POST','/describe_index_stats',json={})
    def query(self,vector,*,top_k=100,filters=None):
        if not 1<=top_k<=1000:raise ValueError('Batas pencarian tidak valid.')
        if not vector or any(not isinstance(v,(float,int)) or not math.isfinite(v) for v in vector):raise ValueError('Vektor pencarian tidak valid.')
        body={'namespace':self.namespace,'vector':vector,'topK':top_k,'includeMetadata':True,'includeValues':False}
        if filters:body['filter']=filters
        return self._request('POST','/query',json=body)
