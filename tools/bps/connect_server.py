"""Private loopback credential setup, independent of the live application."""
import asyncio
import json
import os
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, SecretStr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.bps.client import BPSClient, BPSError

CONFIG = ROOT / '.local/bps-connection.json'
ORIGIN = 'http://127.0.0.1:8783'
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
lock = asyncio.Lock()


class Input(BaseModel):
    api_key: SecretStr = Field(min_length=10, max_length=512)


@app.middleware('http')
async def boundary(request: Request, call_next):
    if request.headers.get('host') != '127.0.0.1:8783':
        return JSONResponse({}, status_code=403)
    if request.method == 'POST':
        if request.headers.get('origin') != ORIGIN:
            return JSONResponse({}, status_code=403)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return JSONResponse({}, status_code=413)
        request._body = bytes(body)
    result = await call_next(request)
    result.headers['Cache-Control'] = 'no-store'
    result.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return result


@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    return JSONResponse({'detail': 'Periksa isian API key BPS.'}, status_code=422)


def save(key):
    if CONFIG.exists():
        raise BPSError('Koneksi sudah tersimpan; tidak ditimpa otomatis.')
    client = BPSClient(key)
    try:
        data, _ = client.get('domain/type/prov')
        if data.get('data-availability') != 'available' or not data.get('data'):
            raise BPSError('Kunci belum berhasil membaca katalog BPS.')
    finally:
        client.close()
    CONFIG.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump({'api_key': key, 'enabled': False}, f)
    return {'saved': True}


@app.post('/api/save')
async def connect(data: Input):
    if lock.locked():
        raise HTTPException(409, 'Koneksi sedang diperiksa.')
    async with lock:
        try:
            return await asyncio.to_thread(save, data.api_key.get_secret_value().strip())
        except BPSError as exc:
            raise HTTPException(400, str(exc)) from None
        except Exception:
            raise HTTPException(502, 'Koneksi belum tersimpan. Silakan coba kembali.') from None


@app.get('/')
async def page():
    return FileResponse(Path(__file__).with_name('connect.html'))


@app.get('/connect.js')
async def script():
    return FileResponse(Path(__file__).with_name('connect.js'), media_type='application/javascript')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8783, access_log=False, log_level='critical')
