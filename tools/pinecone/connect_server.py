"""Loopback-only Pinecone connection setup; read-only remote inspection."""
import asyncio
import json
import os
from pathlib import Path
import secrets
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, SecretStr
from exporter import PineconeReader, ExportError, exact_json, namespace_count

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'.local/pinecone-connection.json'
ORIGIN='http://127.0.0.1:8782'
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
lock=asyncio.Lock()
class Input(BaseModel):
    api_key: SecretStr=Field(min_length=10,max_length=512)
    index: str=Field(default='',max_length=255)
    namespace: str=Field(default='',max_length=1024)
@app.middleware('http')
async def boundary(request,call_next):
    if request.headers.get('host')!='127.0.0.1:8782':return JSONResponse({},status_code=403)
    if request.method=='POST':
        if request.headers.get('origin')!=ORIGIN:return JSONResponse({},status_code=403)
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>8192:return JSONResponse({},status_code=413)
        request._body=bytes(body)
    r=await call_next(request)
    r.headers['Cache-Control']='no-store'
    r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return r
@app.exception_handler(RequestValidationError)
async def invalid(request,exc):return JSONResponse({'detail':'Periksa isian koneksi.'},status_code=422)

def work(data,action):
    reader=PineconeReader(data.api_key.get_secret_value().strip())
    try:
        indexes=reader.indexes()
        if action=='indexes':return {'indexes':[{'name':x['name'],'dimension':x.get('dimension'),'embed':x.get('embed')} for x in indexes]}
        index=next((x for x in indexes if x.get('name')==data.index),None)
        if not index:raise ExportError('Pilih index yang tersedia.')
        namespaces=reader.namespaces(index)
        if action=='namespaces':return {'namespaces':[{'name':k,'count':namespace_count(v)} for k,v in namespaces.items()]}
        if data.namespace not in namespaces:raise ExportError('Namespace tidak ditemukan.')
        if CONFIG.exists():raise ExportError('Koneksi sudah disimpan. Tidak ditimpa otomatis.')
        # Bounded sample: inspect at most 20 IDs, preserving exact metadata values.
        listed,_=reader.request('GET',index['host'],'/vectors/list',params={'namespace':data.namespace,'limit':20})
        ids=[x['id'] for x in listed.get('vectors',[])][:20]
        records=[]
        for _,result,_ in reader.fetch_batches(index['host'],data.namespace,ids):
            for key,row in result.get('vectors',{}).items():records.append({'id':key,'metadata':row.get('metadata',{})})
        obj={'api_key':data.api_key.get_secret_value().strip(),'index':index['name'],'host':index['host'],
             'namespace':data.namespace,'dimension':index.get('dimension'),'metric':index.get('metric'),
             'embed':index.get('embed'),'api_version':'2025-10','enabled':False}
        CONFIG.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(CONFIG,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:json.dump(obj,f,indent=2)
        sample=CONFIG.with_name('pinecone-inspection.json')
        fd=os.open(sample,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:f.write(exact_json({'index':index,'namespace':data.namespace,'count':namespace_count(namespaces[data.namespace]),'records':records}))
        return {'saved':True,'count':namespace_count(namespaces[data.namespace]),'sample_count':len(records)}
    finally:reader.close()
@app.post('/api/{action}')
async def action(action:str,data:Input):
    if action not in {'indexes','namespaces','save'}:raise HTTPException(404)
    if lock.locked():raise HTTPException(409,'Masih memeriksa koneksi.')
    async with lock:
        try:return await asyncio.to_thread(work,data,action)
        except ExportError as exc:raise HTTPException(400,str(exc)) from None
        except Exception:raise HTTPException(502,'Koneksi belum berhasil. Detail rahasia tidak ditampilkan.') from None
@app.get('/')
async def page():return FileResponse(Path(__file__).with_name('connect.html'))
@app.get('/connect.js')
async def script():return FileResponse(Path(__file__).with_name('connect.js'),media_type='application/javascript')
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8782,access_log=False,log_level='critical')
