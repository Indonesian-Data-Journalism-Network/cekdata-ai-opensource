"""Local credential handoff; no credentials are saved or returned."""
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, SecretStr
from exporter import ExportError, PineconeReader, namespace_count

ROOT = Path(__file__).resolve().parent
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
lock = asyncio.Lock()
result = None
export_attempted = False
attempted_targets = set()
progress_state = {'records': 0, 'target': 10000}

def update_progress(value):
    global progress_state
    progress_state = value


class Input(BaseModel):
    api_key: SecretStr = Field(min_length=10, max_length=512)
    index: str = Field(default='', max_length=255)
    namespace: str = Field(default='', max_length=1024)


@app.middleware('http')
async def boundary(request: Request, call_next):
    host = request.headers.get('host', '')
    if host not in {'127.0.0.1:8766', 'localhost:8766'}:
        return JSONResponse({'detail': 'Gunakan alamat localhost yang tersedia.'}, status_code=403)
    if request.method == 'POST':
        if request.headers.get('origin') != 'http://' + host:
            return JSONResponse({'detail': 'Gunakan halaman localhost ini.'}, status_code=403)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 8192:
                return JSONResponse({'detail': 'Isian terlalu panjang.'}, status_code=413)
        request._body = bytes(data)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.exception_handler(RequestValidationError)
async def validation(request, exc):
    return JSONResponse({'detail': 'Periksa isian API key dan index.'}, status_code=422)


def work(data, action):
    reader = PineconeReader(data.api_key.get_secret_value().strip())
    try:
        if action == 'indexes':
            return {'indexes': [{'name': x['name'], 'dimension': x.get('dimension'),
                                 'supported': 'serverless' in x.get('spec', {}) and bool(x.get('dimension'))}
                                for x in reader.indexes()]}
        index = reader.index(data.index)
        if action == 'namespaces':
            return {'namespaces': [{'name': k, 'count': namespace_count(v)} for k, v in reader.namespaces(index).items()]}
        return reader.export(index, data.namespace, ROOT / 'exports', limit=10000,
                             progress=update_progress)
    finally:
        reader.close()


@app.post('/api/{action}')
async def api(action: str, data: Input):
    global result, export_attempted
    if action not in {'indexes', 'namespaces', 'export'}:
        raise HTTPException(404)
    if lock.locked():
        raise HTTPException(409, 'Pengambilan masih berjalan.')
    target = (data.index, data.namespace)
    if action == 'export' and target in attempted_targets:
        raise HTTPException(409, 'Index dan namespace ini sudah diambil pada sesi ini. Periksa hasilnya dahulu; index atau namespace lain tetap bisa dipilih.')
    async with lock:
        if action == 'export':
            export_attempted = True
            attempted_targets.add(target)
            result = None
            update_progress({'records': 0, 'target': 10000})
        try:
            output = await asyncio.to_thread(work, data, action)
            if action == 'export':
                result = output
            return output
        except ExportError as exc:
            if action == 'export':
                result = {'status': 'failed', 'records': 0, 'error': str(exc)}
            raise HTTPException(400, str(exc)) from None
        except Exception:
            if action == 'export':
                result = {'status': 'failed', 'records': 0, 'error': 'Koneksi atau layanan belum siap.'}
            raise HTTPException(502, 'Koneksi atau layanan belum siap. Detail rahasia tidak ditampilkan.') from None


@app.get('/api/status')
async def status():
    return {'running': lock.locked(), 'attempted': export_attempted,
            'attempted_targets': sorted(attempted_targets), 'result': result, 'progress': progress_state}


@app.get('/')
async def page():
    return FileResponse(ROOT / 'index.html')


@app.get('/app.js')
async def script():
    return FileResponse(ROOT / 'app.js', media_type='application/javascript')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8766, access_log=False)
