"""Public adapter: private gateway, account DB, bounded volatile question queue.

Run one worker process only. The existing localhost adapter remains unchanged.
Only profile fields, password hashes, hashed sessions and usage counters persist.
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

COOKIE = 'cekdata_public_session'
SESSION_TTL = 7 * 86400
RESULT_TTL = 300
JOB_TTL = 900
MAX_BODY = 16384

@dataclass(frozen=True)
class Config:
    database: Path
    origin: str
    gateway_secret: str = field(repr=False)
    model_key: str = field(repr=False)
    queue_size: int = 8
    daily_limit: int = 20
    timeout: float = 180
    secure_cookie: bool = True

    def __post_init__(self):
        u = urlsplit(self.origin)
        local = u.hostname in {'127.0.0.1', 'localhost'}
        if not u.netloc or u.path or u.query or u.fragment or u.username:
            raise ValueError('PUBLIC_ORIGIN must be an origin without a path')
        if u.scheme != 'https' and not (u.scheme == 'http' and local and not self.secure_cookie):
            raise ValueError('HTTPS required')
        if not self.secure_cookie and not local:
            raise ValueError('Insecure cookies are only allowed for local tests')
        if len(self.gateway_secret) < 32 or not self.model_key.strip():
            raise ValueError('Server credentials not configured')
        if not 1 <= self.queue_size <= 32 or not 1 <= self.daily_limit <= 1000:
            raise ValueError('Invalid queue or quota')

class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=254)
    password: SecretStr = Field(min_length=12, max_length=128)
    @field_validator('email')
    @classmethod
    def email_address(cls, value):
        value = value.strip().casefold()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Invalid email')
        return value

class Signup(Login):
    name: str = Field(min_length=2, max_length=100)
    organization: str = Field(min_length=2, max_length=160)
    beat: str = Field(min_length=2, max_length=200)
    consent: bool
    @field_validator('name', 'organization', 'beat')
    @classmethod
    def clean(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2: raise ValueError('Required field')
        return value
    @field_validator('consent')
    @classmethod
    def consent_required(cls, value):
        if not value: raise ValueError('Consent required')
        return value

class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=3, max_length=1600)
    sources: list[str] = Field(default_factory=lambda: ['environment'], min_length=1, max_length=1)
    @field_validator('question')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if len(value) < 3: raise ValueError('Question too short')
        return value


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64*1024*1024).hex()


def digest(value): return hashlib.sha256(value.encode()).hexdigest()

class Accounts:
    def __init__(self, path):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = path
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                organization TEXT NOT NULL, beat TEXT NOT NULL, salt TEXT NOT NULL,
                password_hash TEXT NOT NULL, created_at INTEGER NOT NULL,
                last_login INTEGER, consent_version TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS usage (
                user_id TEXT NOT NULL, day TEXT NOT NULL, count INTEGER NOT NULL,
                PRIMARY KEY(user_id,day));
            ''')
        os.chmod(path, 0o600)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path, timeout=5); db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def get_user(self, email):
        with self.connect() as db:
            row=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        return dict(row) if row else None
    def register(self, data, salt, hashed):
        user_id=secrets.token_urlsafe(18)
        try:
            with self.connect() as db:
                db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (user_id,data.email,data.name,data.organization,data.beat,salt,hashed,int(time.time()),None,'2026-11-07'))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'Pendaftaran belum berhasil. Coba masuk jika sudah memiliki akun.')
        return user_id
    def session(self, user_id):
        token=secrets.token_urlsafe(32); now=int(time.time())
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires_at<=?',(now,))
            db.execute('INSERT INTO sessions VALUES (?,?,?)',(digest(token),user_id,now+SESSION_TTL))
            db.execute('UPDATE users SET last_login=? WHERE id=?',(now,user_id))
        return token
    def user(self, token):
        if not token or len(token)>128:return None
        with self.connect() as db:
            row=db.execute('''SELECT u.id,u.name,u.email,u.organization,u.beat FROM sessions s
                JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?''',
                (digest(token),int(time.time()))).fetchone()
        return dict(row) if row else None
    def logout(self, token):
        with self.connect() as db:db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(token),))
    def use(self, uid, day, limit):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT count FROM usage WHERE user_id=? AND day=?',(uid,day)).fetchone()
            if row and row['count']>=limit:raise HTTPException(429,'Batas pertanyaan harian tercapai. Coba kembali besok.')
            db.execute('INSERT INTO usage VALUES (?,?,1) ON CONFLICT(user_id,day) DO UPDATE SET count=count+1',(uid,day))
            db.execute("DELETE FROM usage WHERE day < date('now','-90 days')")

class Limiter:
    def __init__(self):self.buckets={}
    def take(self, key, limit, window):
        now=time.monotonic()
        if len(self.buckets)>10000:
            self.buckets={k:v for k,v in self.buckets.items() if v[0]>now}
            if len(self.buckets)>10000:raise HTTPException(429,'Layanan sedang sibuk.')
        expiry,count=self.buckets.get(key,(now+window,0))
        if expiry<=now:expiry,count=now+window,0
        if count>=limit:raise HTTPException(429,'Terlalu banyak percobaan. Tunggu sebelum mencoba lagi.')
        self.buckets[key]=(expiry,count+1)

class Jobs:
    def __init__(self, config, runner):
        self.config=config; self.runner=runner; self.queue=asyncio.Queue(maxsize=config.queue_size)
        self.items={}; self.running=None
    def prune(self):
        now=time.monotonic()
        for jid,item in list(self.items.items()):
            if item['expires']<=now:
                self.remove(jid)
    def remove(self, jid):
        item=self.items.pop(jid,None)
        if item:
            item.pop('question',None); item.pop('result',None)
            if item.get('task'):item['task'].cancel()
    def clear_user(self, uid):
        for jid,item in list(self.items.items()):
            if item['uid']==uid:self.remove(jid)
    def check_capacity(self, uid):
        self.prune()
        if any(x['uid']==uid and x['status'] in ('queued','running') for x in self.items.values()):
            raise HTTPException(409,'Pertanyaan sebelumnya masih diproses.')
        if self.queue.full() or len(self.items)>=200:
            raise HTTPException(429,'Antrean penuh. Silakan coba lagi sebentar.')
    def submit(self, uid, data):
        jid=secrets.token_urlsafe(24)
        self.items[jid]={'uid':uid,'question':data.question,'source':data.sources[0],
            'status':'queued','expires':time.monotonic()+JOB_TTL}
        self.queue.put_nowait(jid)
        return jid
    def get(self, jid, uid):
        self.prune(); item=self.items.get(jid)
        if not item or item['uid']!=uid:raise HTTPException(404,'Proses tidak ditemukan atau sudah kedaluwarsa. Kirim ulang pertanyaan.')
        result={'job_id':jid,'status':item['status']}
        if item['status']=='queued':
            pending=[k for k,v in self.items.items() if v['status']=='queued']
            result['position']=pending.index(jid)+1
        if 'result' in item:result['result']=item['result']
        if 'error' in item:result['error']=item['error']
        return result
    async def work(self):
        while True:
            jid=await self.queue.get()
            try:
                self.prune(); item=self.items.get(jid)
                if not item:continue
                item['status']='running'
                reference=datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat()
                task=asyncio.create_task(self.runner(self.config.model_key,item.pop('question'),reference,item['source']))
                item['task']=task
                try:
                    result=await asyncio.wait_for(task,timeout=self.config.timeout)
                    if jid in self.items:
                        item['result']={k:result.get(k,{} if k=='parsed' else '') for k in ('answer','parsed','kind','reference_date')}
                        item['status']='completed'
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():raise
                    # Cancellation on logout or expiry must not stop the queue worker.
                except Exception:
                    if jid in self.items:
                        item['status']='failed'; item['error']='Proses belum berhasil karena gangguan layanan. Ini bukan bukti bahwa data tidak tersedia.'
                finally:
                    item.pop('task',None); item['expires']=time.monotonic()+RESULT_TTL
            finally:self.queue.task_done()
    async def clean(self):
        while True:
            await asyncio.sleep(30); self.prune()

async def default_runner(key, question, reference, source):
    from server import run_environment_workflow, run_workflow
    return await (run_environment_workflow if source=='environment' else run_workflow)(key,question,reference)


def create_app(config: Config, runner=default_runner, sources=None):
    accounts=Accounts(config.database); limiter=Limiter(); jobs=Jobs(config,runner); auth_lock=asyncio.Lock()
    if sources is None:
        from server import gfw_report, REPORT_PATH
        def sources():
            result=[]
            if REPORT_PATH.exists():result.append('bps')
            if gfw_report():result.append('environment')
            return result
    @asynccontextmanager
    async def lifespan(app):
        tasks=[asyncio.create_task(jobs.work()),asyncio.create_task(jobs.clean())]
        yield
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        for jid in list(jobs.items):jobs.remove(jid)
    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.accounts=accounts;app.state.jobs=jobs
    @app.middleware('http')
    async def boundary(request,call_next):
        if not hmac.compare_digest(request.headers.get('x-cekdata-gateway',''),config.gateway_secret):
            return JSONResponse({'detail':'Akses tidak tersedia.'},status_code=403)
        if request.method not in ('GET','HEAD'):
            if request.headers.get('origin')!=config.origin:
                return JSONResponse({'detail':'Asal permintaan tidak diizinkan.'},status_code=403)
            if not request.headers.get('content-type','').startswith('application/json'):
                return JSONResponse({'detail':'Gunakan JSON.'},status_code=415)
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>MAX_BODY:return JSONResponse({'detail':'Isian terlalu panjang.'},status_code=413)
            request._body=bytes(body)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc):
        return JSONResponse({'detail':'Periksa isian: email valid, kata sandi 12–128 karakter, dan seluruh kolom wajib.'},status_code=422)
    def user(request):
        result=accounts.user(request.cookies.get(COOKIE,''))
        if not result:raise HTTPException(401,'Sesi berakhir. Silakan masuk kembali.')
        return result
    def set_session(response,uid):
        response.set_cookie(COOKIE,accounts.session(uid),max_age=SESSION_TTL,httponly=True,
                            secure=config.secure_cookie,samesite='lax',path='/api')
    def auth_rate(request,email):
        ip=request.headers.get('x-cekdata-client','unknown')
        limiter.take('auth-ip:'+digest(ip),15,600)
        limiter.take('auth-email:'+digest(email),8,600)
        if auth_lock.locked():raise HTTPException(429,'Layanan masuk sedang sibuk. Coba sebentar lagi.')
    @app.get('/api/health')
    async def health():return {'status':'ok','mode':'public'}
    @app.get('/api/auth/me')
    async def me(request:Request):return {'user':user(request)}
    @app.post('/api/auth/signup',status_code=201)
    async def signup(data:Signup,request:Request,response:Response):
        auth_rate(request,data.email)
        async with auth_lock:
            salt=secrets.token_hex(16)
            hashed=await asyncio.to_thread(password_hash,data.password.get_secret_value(),salt)
            uid=accounts.register(data,salt,hashed)
        set_session(response,uid)
        return {'user':{'id':uid,'name':data.name,'email':data.email,'organization':data.organization,'beat':data.beat}}
    @app.post('/api/auth/login')
    async def login(data:Login,request:Request,response:Response):
        auth_rate(request,data.email)
        async with auth_lock:
            row=accounts.get_user(data.email)
            hashed=await asyncio.to_thread(password_hash,data.password.get_secret_value(),row['salt'] if row else '00'*16)
            if not row or not hmac.compare_digest(hashed,row['password_hash']):
                raise HTTPException(401,'Email atau kata sandi tidak cocok.')
        set_session(response,row['id'])
        return {'user':{k:row[k] for k in ('id','name','email','organization','beat')}}
    @app.post('/api/auth/logout')
    async def logout(request:Request,response:Response):
        current=accounts.user(request.cookies.get(COOKIE,''))
        accounts.logout(request.cookies.get(COOKIE,''))
        if current:jobs.clear_user(current['id'])
        response.delete_cookie(COOKIE,path='/api',secure=config.secure_cookie,httponly=True,samesite='lax')
        return {'ok':True}
    @app.get('/api/search/sources')
    async def search_sources(request:Request):
        user(request); available=sources()
        return {'sources':available,'default_source':'environment' if 'environment' in available else 'bps','mode':'public'}
    @app.post('/api/jobs',status_code=202)
    async def submit(data:Question,request:Request):
        uid=user(request)['id']
        if data.sources[0] not in sources():raise HTTPException(409,'Sumber data belum tersedia.')
        limiter.take('jobs:'+uid,3,60);jobs.check_capacity(uid)
        accounts.use(uid,datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat(),config.daily_limit)
        jid=jobs.submit(uid,data)
        return jobs.get(jid,uid)
    @app.get('/api/jobs/{jid}')
    async def get_job(jid:str,request:Request):
        return jobs.get(jid,user(request)['id'])
    return app


def from_file():
    path=Path(os.environ.get('CEKDATA_PUBLIC_CONFIG',str(Path(__file__).resolve().parents[1]/'.local/public-server.json')))
    if path.stat().st_mode & 0o077:raise RuntimeError('Configuration must be readable only by its owner (chmod 600)')
    obj=json.loads(path.read_text())
    return create_app(Config(database=Path(obj['database']),origin=obj['origin'],
        gateway_secret=obj['gateway_secret'],model_key=obj['model_key']))

if __name__=='__main__':
    import uvicorn
    uvicorn.run(from_file(),host='127.0.0.1',port=8780,access_log=False,workers=1)
