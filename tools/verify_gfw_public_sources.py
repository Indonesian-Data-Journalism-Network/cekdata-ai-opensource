"""Verify public dashboard identities anonymously; preserve audit and publish link registry."""
import json,html,re,sys
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
def readrows(p):
 r=json.loads(p.read_text());return r.get('data') if isinstance(r,dict) else r
provinces=readrows(root/'data/gfw/raw/provinces.json')
districts=readrows(root/'data/gfw-adm2/raw/districts.json')
entries=[('iso:IDN','Indonesia','')]
for r in provinces:
 p=re.fullmatch(r'IDN\.(\d+)_\d+',r['gid_1'])[1]
 entries.append(('adm1:'+p,r['name_1'],p+'/'))
for r in districts:
 if r['type_2']=='Water Body':continue
 m=re.fullmatch(r'IDN\.(\d+)\.(\d+)(?:_\d+)?',r['gid_2'])
 entries.append(('adm2:'+m[1]+'.'+m[2],r['name_2'],m[1]+'/'+m[2]+'/'))
path=root/'data/gfw-public-sources.json'
result=json.loads(path.read_text()) if path.exists() else {}
def check(entry):
 key,name,route=entry
 if key in result and '--refresh' not in sys.argv:return key,result[key]
 url='https://www.globalforestwatch.org/dashboards/country/IDN/'+route
 info={'expected_name':name,'requested_url':url,'checked_at':datetime.now(timezone.utc).isoformat()}
 try:
  response=httpx.get(url,follow_redirects=True,timeout=25)
  title=re.search(r'<title[^>]*>(.*?)</title>',response.text,re.S)
  title=html.unescape(title.group(1)) if title else ''
  found=title.split(' Deforestation Rates')[0] if key=='iso:IDN' else title.split(', Indonesia')[0].strip()
  valid=response.status_code==200 and found.casefold()==name.casefold()
  info.update(status=response.status_code,title=title,final_url=str(response.url),verified_region=valid)
 except Exception as e:info.update(error=type(e).__name__,verified_region=False)
 info['public_url']=url if info['verified_region'] else 'https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html'
 return key,info
with ThreadPoolExecutor(max_workers=5) as pool:
 fs=[pool.submit(check,e) for e in entries]
 for i,f in enumerate(as_completed(fs),1):
  k,v=f.result();result[k]=v
  if i%25==0:
   path.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(i,'/',len(entries),'checked',flush=True)
path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('verified',sum(x['verified_region'] for x in result.values()),'of',len(result))
print('fallback',[(k,v['expected_name'],v.get('title',v.get('error'))) for k,v in result.items() if not v['verified_region']])
registry={k:{'name':v['expected_name'],'url':v['requested_url'],'checked_at':v['checked_at']}
          for k,v in sorted(result.items()) if v['verified_region']}
target=root/'web/frontend/src/config/gfwPublicSources.json'
temporary=target.with_suffix('.tmp')
temporary.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
temporary.replace(target)
