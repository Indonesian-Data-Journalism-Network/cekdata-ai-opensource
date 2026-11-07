"""One-use loopback-only setup page. Never expose this port through a tunnel."""
from pathlib import Path
import json, os, secrets, sys
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, SecretStr, Field
import uvicorn
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from public_server import Config
ORIGIN='http://127.0.0.1:8781'
PATH=ROOT/'.local/public-server.json'
NONCE=secrets.token_urlsafe(32)
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
@app.exception_handler(RequestValidationError)
async def invalid(request,exc):
    return JSONResponse({'detail':'Periksa isian kunci.'},status_code=422)
class Input(BaseModel):
    key: SecretStr=Field(min_length=20,max_length=512)
    nonce: str
@app.middleware('http')
async def local(request,call_next):
    if request.headers.get('host')!='127.0.0.1:8781' or (request.method=='POST' and request.headers.get('origin')!=ORIGIN):
        return JSONResponse({'detail':'Tidak diizinkan'},status_code=403)
    if request.method=='POST':
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>4096:return JSONResponse({},status_code=413)
        request._body=bytes(body)
    r=await call_next(request);r.headers['Cache-Control']='no-store';r.headers['X-Frame-Options']='DENY';return r
@app.get('/')
async def page():
    if PATH.exists():return HTMLResponse('<h2>Konfigurasi tersimpan. Halaman ini dapat ditutup.</h2>')
    return HTMLResponse('''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pengaturan server Cek Data AI</title><style>body{font:16px system-ui;background:#faf8f6;color:#292621;max-width:560px;margin:80px auto;padding:24px}input,button{box-sizing:border-box;width:100%;padding:14px;margin:12px 0;font:inherit}button{background:#e73588;color:white;border:0;border-radius:8px}p{line-height:1.6}</style><h1>Hubungkan mesin Cek Data AI</h1><p>Masukkan API key OpenAI yang dipakai mesin ini. Kunci disimpan hanya di komputer ini; pengunjung website tidak perlu mengisinya.</p><p>Website: <b>cekdata-ai-pilot.netlify.app</b></p><form id="setup"><label for="key">API key OpenAI</label><input id="key" type="password" minlength="20" maxlength="512" required autocomplete="off"><button>Simpan di komputer ini</button></form><p id="status" role="status"></p><script>document.querySelector('form').onsubmit=async(e)=>{e.preventDefault();const button=document.querySelector('button');button.disabled=true;try{const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:document.querySelector('input').value,nonce:''' + json.dumps(NONCE) + '''})});if(!r.ok)throw Error();document.querySelector('input').value='';document.querySelector('form').hidden=true;document.querySelector('#status').textContent='Tersimpan. Kembali ke Codex dan beri tahu bahwa sudah selesai.';}catch{document.querySelector('#status').textContent='Belum berhasil disimpan. Periksa isian lalu coba lagi.';button.disabled=false;}};</script></html>''')
@app.post('/save')
async def save(data:Input):
    if PATH.exists() or not secrets.compare_digest(data.nonce,NONCE):return JSONResponse({},status_code=409)
    obj={'database':str(ROOT/'.local/public/accounts.sqlite3'),'origin':'https://cekdata-ai-pilot.netlify.app','gateway_secret':secrets.token_urlsafe(48),'model_key':data.key.get_secret_value().strip()}
    Config(database=Path(obj['database']),origin=obj['origin'],gateway_secret=obj['gateway_secret'],model_key=obj['model_key'])
    PATH.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(PATH,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(obj,f,indent=2)
    return {'ok':True}
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=8781,access_log=False,log_level='critical')
