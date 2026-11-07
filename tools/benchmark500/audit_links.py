import json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[2];P=ROOT/'docs/test-evidence/20261106/benchmark500-v1'
rows={}
for l in (ROOT/'data/gfw-adm2/records.jsonl').open():
 r=json.loads(l)
 if r['indicator_id'] in ['gfw-tree-cover-loss','gfw-tree-cover-loss-fire','gfw-primary-forest-loss']:rows[(r['indicator_id'],r['area'],r['year'])]=r
out=[]
for q in json.load((P/'results.json').open()):
 if q['group'] not in ['gfw','gabungan']:continue
 expected=set()
 for a in q['areas']:
  for y in q['years']:
   r=rows.get((q['metric'],a,y))
   if r:
    s='/dashboards/country/IDN/'
    if r.get('adm1') is not None:s+=str(r['adm1'])+'/'
    if r.get('adm2') is not None:s+=str(r['adm2'])+'/'
    expected.add(s)
 urls=[l['href'] or '' for l in q['links']];missing=[s for s in expected if not any(s.rstrip('/')==u.split('?')[0].split('#')[0].replace('https://www.globalforestwatch.org','').replace('https://globalnaturewatch.org','').replace('https://www.globalnaturewatch.org','').rstrip('/') for u in urls)]
 out.append({'id':q['id'],'expected_paths':sorted(expected),'missing':missing,'dataset_fallback':bool(missing) and any('earthenginepartners-hansen/GFC-2025-v1.13/download.html' in u for u in urls)})
(P/'source-link-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('Source paths checked',len(out),'flags',[(r['id'],r['missing']) for r in out if r['missing']])
