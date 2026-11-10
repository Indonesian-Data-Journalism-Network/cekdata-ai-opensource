"""Cross-route type identity regression, isolated from other imported test fixtures."""
import subprocess
import sys
import unittest
from pathlib import Path

class RouteReloadTests(unittest.TestCase):
    def test_general_after_repeated_environment_reload(self):
        script = r'''
import asyncio,sys,importlib
from unittest.mock import patch
sys.path[:0]=['web','workflow']
import server, general_data
async def fake_run(key,question,reference):
    import flow,bps_local,pinecone_data,general_data
    values=dict(id='test',indicator_id='test',indicator='Test',area='Test',year=2025,value='1',unit='jiwa',source='BPS')
    for module in (bps_local,pinecone_data):
        row=module.Evidence(**values)
        assert len(general_data.SearchBatch(records=[row]).records)==1
        assert module.Evidence is flow.Evidence
    return {'ok':True}
real_reload=importlib.reload
def reload(module):
    out=real_reload(module)
    if module.__name__=='general_data':out.run=fake_run;out.available=lambda:True
    return out
async def main():
    with patch('importlib.reload',side_effect=reload):
        for _ in range(3):
            server.reload_statistical_engine() # same reload as Environment
            assert (await server.run_workflow('test','test','2026-11-08'))['ok']
asyncio.run(main())
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
