"""Loopback-only adapter for the existing LlamaIndex pilot and GitHub UI."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import secrets
import sys
import time
import traceback
import importlib
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'workflow'))
from flow import CekDataWorkflow, LlamaAI
from storage import QdrantEvidenceRetriever
from pilot_data import COLLECTION, CATALOG_PATH, REPORT_PATH, PilotAI, group_catalog
from settings import QDRANT_URL
from gfw_data import DIRECTORY as GFW_DIRECTORY, COLLECTION as GFW_COLLECTION
from gfw_district_data import DIRECTORY as GFW_DISTRICT_DIRECTORY, COLLECTION as GFW_DISTRICT_COLLECTION

COOKIE = 'cekdata_local_session'
SESSION_SECONDS = 8 * 60 * 60
ORIGINS = {'http://127.0.0.1:8765', 'http://localhost:8765'}
HOSTS = {'127.0.0.1:8765', 'localhost:8765'}


class SessionInput(BaseModel):
    api_key: SecretStr = Field(min_length=20, max_length=512)


class AskInput(BaseModel):
    question: str = Field(min_length=3, max_length=1600)
    sources: list[str] = Field(default_factory=lambda: ['bps'], max_length=4)
    previous_question: str = Field(default='', max_length=1600)


async def run_workflow(key: str, question: str, reference: str):
    # Environment reloads flow's Pydantic types. Refresh General's adapters
    # before using them so evidence from either store has the same type identity.
    reload_statistical_engine()
    import bps_local, pinecone_data
    for module in (bps_local, pinecone_data):
        importlib.reload(module)
    import general_data
    importlib.reload(general_data)
    if general_data.available():
        return await general_data.run(key, question, reference)
    return await run_dataset_workflow(key, question, reference, CATALOG_PATH, COLLECTION)


async def run_environment_workflow(key: str, question: str, reference: str):
    directory,collection = gfw_location()
    return await run_dataset_workflow(key, question, reference, directory / 'catalog.json', collection)


def gfw_location():
    path = GFW_DISTRICT_DIRECTORY / 'import-report.json'
    if path.exists() and json.loads(path.read_text()).get('publication_status') == 'published':
        return GFW_DISTRICT_DIRECTORY, GFW_DISTRICT_COLLECTION
    return GFW_DIRECTORY, GFW_COLLECTION


def gfw_report():
    directory,_ = gfw_location()
    path = directory / 'import-report.json'
    report = json.loads(path.read_text()) if path.exists() else {}
    return report if report.get('publication_status') == 'published' else {}


def reload_statistical_engine():
    # Reload only the stateless engine between requests, keeping session secrets
    # in RAM in this server. The request lock prevents concurrent reloads.
    import flow, storage, pilot_data
    for module in (flow, storage, pilot_data):
        importlib.reload(module)
    return flow, storage, pilot_data


async def run_dataset_workflow(key, question, reference, catalog_path, collection):
    from llama_index.llms.openai import OpenAI
    from qdrant_client import QdrantClient

    flow, storage, pilot_data = reload_statistical_engine()
    catalog = pilot_data.group_catalog(json.loads(catalog_path.read_text()))
    llm = OpenAI(model=os.environ.get('CEKDATA_MODEL', 'gpt-4.1-mini-2025-04-14'),
                 api_key=key, temperature=0, max_tokens=2400, timeout=45, max_retries=0)
    client = QdrantClient(url=QDRANT_URL, timeout=10)
    try:
        workflow = flow.CekDataWorkflow(pilot_data.PilotAI(llm, catalog),
            storage.QdrantEvidenceRetriever(client, collection, usable_only=True, catalog=catalog, limit=2000), catalog)
        return await workflow.run(question=question, reference_date=reference)
    finally:
        client.close()


def create_app(runner=run_workflow, environment_runner=run_environment_workflow):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    # Credentials never enter files, responses, browser storage, or application logs.
    sessions: dict[str, tuple[str, float]] = {}
    active = asyncio.Lock()

    def session(request):
        now = time.monotonic()
        for token in list(sessions):
            if sessions[token][1] <= now:
                del sessions[token]
        return sessions.get(request.cookies.get(COOKIE, ''))

    @app.middleware('http')
    async def local_boundary(request: Request, call_next):
        if request.headers.get('host', '') not in HOSTS:
            return JSONResponse({'detail': 'Alamat layanan lokal tidak valid.'}, status_code=403)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin', '')
            if origin not in ORIGINS or origin != 'http://' + request.headers['host']:
                return JSONResponse({'detail': 'Permintaan harus berasal dari halaman lokal ini.'}, status_code=403)
            if not request.headers.get('content-type', '').startswith('application/json') and request.method != 'DELETE':
                return JSONResponse({'detail': 'Gunakan permintaan JSON.'}, status_code=415)
            # Bound the entire body, including requests without Content-Length.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16384:
                    return JSONResponse({'detail': 'Permintaan terlalu panjang.'}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # FastAPI's default error payload includes submitted input: redact it.
        return JSONResponse({'detail': 'Isian tidak valid. Periksa API key atau panjang pertanyaan.'}, status_code=422)

    @app.get('/api/local/session')
    async def session_status(request: Request):
        report = json.loads(REPORT_PATH.read_text()) if REPORT_PATH.exists() else {}
        environment = gfw_report()
        return {'configured': session(request) is not None, 'mode': 'local',
                'sample_records': report.get('records', 0) + environment.get('records', 0),
                'searchable_records': report.get('searchable_records', 0) + environment.get('searchable_records', 0),
                'gfw_records': environment.get('records', 0), 'gfw_provinces': environment.get('province_count', 0)}

    @app.post('/api/local/session')
    async def set_session(data: SessionInput, request: Request, response: Response):
        key = data.api_key.get_secret_value().strip()
        if len(key) < 20 or any(char.isspace() for char in key):
            raise HTTPException(422, 'API key tidak valid. Tempel key lengkap tanpa spasi.')
        session(request)  # Prune expired sessions.
        sessions.pop(request.cookies.get(COOKIE, ''), None)
        if len(sessions) >= 16:
            raise HTTPException(429, 'Terlalu banyak sesi lokal. Hapus sesi yang tidak dipakai.')
        token = secrets.token_urlsafe(32)
        sessions[token] = (key, time.monotonic() + SESSION_SECONDS)
        response.set_cookie(COOKIE, token, httponly=True, samesite='strict', path='/api')
        return {'configured': True}

    @app.delete('/api/local/session')
    async def end_session(request: Request, response: Response):
        sessions.pop(request.cookies.get(COOKIE, ''), None)
        response.delete_cookie(COOKIE, path='/api')
        return {'configured': False}

    @app.get('/api/search/sources')
    async def sources():
        available = bool(gfw_report())
        return {'sources': ['bps', 'environment'] if available else ['bps'],
                'default_source': 'environment' if available else 'bps',
                'preview_sources': [], 'mode': 'local'}

    @app.post('/api/ask')
    async def ask(data: AskInput, request: Request):
        credentials = session(request)
        if not credentials:
            raise HTTPException(401, 'Masukkan API key melalui Pengaturan API key.')
        if data.sources != ['bps'] and not (data.sources == ['environment'] and gfw_report()):
            raise HTTPException(409, 'Sumber yang dipilih belum terhubung ke database lokal.')
        question = data.question.strip()
        if len(question) < 3:
            raise HTTPException(422, 'Tulis pertanyaan atau klaim yang ingin diperiksa.')
        if data.previous_question:
            raise HTTPException(422, 'Pada prototipe ini, tuliskan kembali indikator, wilayah, dan periode dalam pertanyaan.')
        if active.locked():
            raise HTTPException(429, 'Satu pencarian masih berjalan. Tunggu sampai selesai.')
        reference = datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat()
        async with active:
            try:
                selected_runner = environment_runner if data.sources == ['environment'] else runner
                result = await asyncio.wait_for(selected_runner(credentials[0], question, reference), timeout=155)
            except Exception as exc:
                # Only exception class and code locations; never exception text,
                # local variables, request body, headers or provider payloads.
                chain = []
                current = exc
                while current is not None and len(chain) < 4:
                    chain.append({'type':type(current).__name__, 'frames':[
                        f'{Path(f.filename).name}:{f.lineno}:{f.name}'
                        for f in traceback.extract_tb(current.__traceback__)[-8:]]})
                    current = current.__cause__
                logging.getLogger('cekdata.local').error('Workflow diagnostic: %s', chain)
                # Provider errors may contain request content or key fragments.
                raise HTTPException(502, 'Proses belum berhasil. Periksa API key, saldo/akses model, koneksi internet, dan Qdrant. Gangguan layanan bukan bukti bahwa data tidak tersedia.') from None
        # A legitimate clarification may stop before a parsed statistical answer exists.
        return {name: result.get(name, {} if name == 'parsed' else reference if name == 'reference_date' else '')
                for name in ('answer', 'parsed', 'kind', 'reference_date')}

    @app.get('/api/{path:path}')
    async def unknown_api(path: str):
        raise HTTPException(404, 'Fitur ini belum tersedia pada prototipe lokal.')

    app.mount('/', StaticFiles(directory=ROOT / 'frontend/dist', html=True, check_dir=False), name='frontend')
    return app


app = create_app()

if __name__ == '__main__':
    import uvicorn
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    print('Cek Data AI lokal: http://127.0.0.1:8765', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=8765, access_log=False)
