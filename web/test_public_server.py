"""Public boundary tests: isolated fake AI, no provider calls or production accounts."""
import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from public_server import Config, create_app, Jobs, Question, COOKIE

ORIGIN='https://fixture.netlify.app'
SECRET='fixture-gateway-secret-not-real-123456'
PROFILE=dict(email='reader@example.org',password='fixture-password-123',name='Test Reader',organization='Fixture media',beat='Lingkungan',consent=True)

class PublicTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.cfg=Config(Path(self.directory.name)/'accounts.sqlite3',ORIGIN,SECRET,'fixture-model-key')
        async def runner(key,question,reference,source):
            if question=='provider fails':raise RuntimeError(key)
            return dict(answer='Jawaban '+question,parsed={'kind':'lookup'},kind='lookup',reference_date=reference,secret=key)
        self.app=create_app(self.cfg,runner,lambda:['environment'])
        self.client=self.enterContext(TestClient(self.app,base_url=ORIGIN,headers={'x-cekdata-gateway':SECRET,'origin':ORIGIN}))
    def signup(self,**changes):
        r=self.client.post('/api/auth/signup',json={**PROFILE,**changes});self.assertEqual(r.status_code,201,r.text);return r
    def job(self,question='Luas hutan Aceh?'):
        r=self.client.post('/api/jobs',json={'question':question,'sources':['environment']});self.assertEqual(r.status_code,202,r.text)
        for _ in range(100):
            p=self.client.get('/api/jobs/'+r.json()['job_id'])
            if p.json()['status'] not in ['running','queued']:return p
            time.sleep(.01)
        self.fail('worker did not complete')
    def test_boundary_auth_and_validation_redaction(self):
        self.assertEqual(self.client.get('/api/health',headers={'x-cekdata-gateway':'wrong'}).status_code,403)
        self.assertEqual(self.client.post('/api/auth/signup',json=PROFILE,headers={'origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.assertEqual(self.client.post('/api/auth/signup',content='x'*17000,headers={'content-type':'application/json'}).status_code,413)
        r=self.client.post('/api/auth/signup',json={**PROFILE,'consent':False,'api_key':'sensitive-value'})
        self.assertEqual(r.status_code,422);self.assertNotIn('sensitive-value',r.text)
    def test_signup_login_logout_and_private_storage(self):
        r=self.signup();cookie=r.headers['set-cookie']
        for flag in ['HttpOnly','Secure','SameSite=lax','Path=/api']:self.assertIn(flag,cookie)
        self.assertEqual(self.client.get('/api/auth/me').json()['user']['name'],PROFILE['name'])
        self.job('private-question-marker')
        raw=self.cfg.database.read_bytes()
        for text in [PROFILE['password'],'private-question-marker','fixture-model-key',self.client.cookies[COOKIE]]:self.assertNotIn(text.encode(),raw)
        self.assertEqual(self.cfg.database.stat().st_mode & 0o777,0o600)
        self.client.post('/api/auth/logout',json={})
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.assertEqual(len(self.app.state.jobs.items),0)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':PROFILE['email'],'password':'wrong-password-123'}).status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json={k:PROFILE[k] for k in ['email','password']}).status_code,200)
    def test_job_ownership_and_provider_failure(self):
        self.signup();r=self.job();jid=r.json()['job_id']
        self.assertNotIn('secret',r.json()['result']);self.assertNotIn('fixture-model-key',r.text)
        first=self.client.cookies[COOKIE]
        self.signup(email='other@example.org')
        self.assertEqual(self.client.get('/api/jobs/'+jid).status_code,404)
        r=self.job('provider fails');self.assertEqual(r.json()['status'],'failed');self.assertNotIn('fixture-model-key',r.text)
        self.assertNotEqual(first,self.client.cookies[COOKIE])
    def test_quota_and_unknown_source(self):
        self.signup();uid=self.client.get('/api/auth/me').json()['user']['id']
        self.assertEqual(self.client.post('/api/jobs',json={'question':'Luas hutan?','sources':['legal']}).status_code,409)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        day=datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat()
        for _ in range(self.cfg.daily_limit):self.app.state.accounts.use(uid,day,self.cfg.daily_limit)
        r=self.client.post('/api/jobs',json={'question':'Luas hutan?'})
        self.assertEqual(r.status_code,429);self.assertIn('harian',r.text)
    def test_demo_without_account_uses_catalog_and_preserves_login_boundary(self):
        import json
        catalog=json.loads((Path(__file__).parent/'frontend/src/config/homeQuestions.json').read_text())
        entry=next(x for x in catalog if x['source']=='environment')
        self.assertEqual(self.client.post('/api/jobs',json={'question':'Arbitrary prompt'}).status_code,401)
        response=self.client.post('/api/demo/jobs',json={'question_id':entry['id']})
        self.assertEqual(response.status_code,202,response.text)
        for flag in ['HttpOnly','Secure','Path=/api/demo']:self.assertIn(flag,response.headers['set-cookie'])
        jid=response.json()['job_id']
        for _ in range(100):
            result=self.client.get('/api/demo/jobs/'+jid)
            if result.json()['status']=='completed':break
            time.sleep(.01)
        self.assertEqual(result.json()['result']['answer'],'Jawaban '+entry['question'])
        self.assertNotIn('fixture-model-key',result.text)
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.assertEqual(self.client.get('/api/jobs/'+jid).status_code,401)
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/demo/jobs/'+jid).status_code,401)
        self.client.post('/api/demo/jobs',json={'question_id':entry['id']})
        self.assertEqual(self.client.get('/api/demo/jobs/'+jid).status_code,404)
        with self.app.state.accounts.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)

    def test_demo_rejects_arbitrary_question_and_limits_requests(self):
        for payload in [{'question_id':101},{'question_id':True},{'question_id':41,'question':'override'}, {'question_id':41,'sources':['legal']}]:
            self.assertEqual(self.client.post('/api/demo/jobs',json=payload).status_code,422)
        self.assertEqual(self.client.post('/api/demo/jobs',json={'question_id':41},headers={'origin':'https://evil.example'}).status_code,403)
        for _ in range(3):self.client.post('/api/demo/jobs',json={'question_id':41})
        self.assertEqual(self.client.post('/api/demo/jobs',json={'question_id':41}).status_code,429)

    def test_configuration_rejects_insecure_public_origin(self):
        for origin in ['http://example.org','https://example.org/path','https://user:pass@example.org']:
            with self.assertRaises(ValueError):replace(self.cfg,origin=origin)
        self.assertNotIn(SECRET,repr(self.cfg));self.assertNotIn('fixture-model-key',repr(self.cfg))

class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_logout_cancel_worker_survives_and_expiry_removes_evidence(self):
        started=asyncio.Event()
        async def runner(key,q,*args):
            if q=='slow question':started.set();await asyncio.Event().wait()
            return {'answer':q}
        cfg=Config(Path('/unused'),ORIGIN,SECRET,'fixture')
        jobs=Jobs(cfg,runner);worker=asyncio.create_task(jobs.work())
        try:
            jid=jobs.submit('a',Question(question='slow question'));await asyncio.wait_for(started.wait(),1)
            with self.assertRaises(HTTPException):jobs.check_capacity('a')
            jobs.clear_user('a');await asyncio.sleep(.01)
            second=jobs.submit('b',Question(question='next question'));await asyncio.wait_for(jobs.queue.join(),1)
            self.assertEqual(jobs.get(second,'b')['status'],'completed')
            self.assertNotIn(jid,jobs.items)
            jobs.items[second]['expires']=0;jobs.prune();self.assertEqual(jobs.items,{})
        finally:worker.cancel();await asyncio.gather(worker,return_exceptions=True)
    async def test_timeout_and_bounded_queue(self):
        async def runner(*args):await asyncio.Event().wait()
        cfg=Config(Path('/unused'),ORIGIN,SECRET,'fixture',queue_size=1,timeout=.01)
        jobs=Jobs(cfg,runner);jid=jobs.submit('a',Question(question='slow question'))
        with self.assertRaises(HTTPException):jobs.check_capacity('b')
        worker=asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(),1)
            self.assertEqual(jobs.get(jid,'a')['status'],'failed')
        finally:worker.cancel();await asyncio.gather(worker,return_exceptions=True)

if __name__=='__main__':unittest.main()
