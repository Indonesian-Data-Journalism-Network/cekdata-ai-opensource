"""Check GFW tables/summaries added to report answers against archived records."""
import json,re,pathlib
from decimal import Decimal
from audit_numeric import P,norm,fmt,hasval
ROOT=pathlib.Path(__file__).resolve().parents[2]
index={}
for line in (ROOT/'data/gfw-adm2/records.jsonl').open():
 r=json.loads(line)
 if r['indicator_id']=='gfw-tree-cover-loss':index[(norm(r['area']),r['year'])]=Decimal(r['value'])
out=[]
for r in json.load((P/'results.json').open()):
 if r['id']<401:continue
 checks=[];issues=[]
 for area,lo,hi,total in re.findall(r'GFW mencatat kehilangan tutupan pohon di (.*?) selama (\d{4})[–-](\d{4}) sebesar ([\d.,]+) ha',r['answer']):
  vals=[index.get((norm(area),y)) for y in range(int(lo),int(hi)+1)]
  if any(v is None for v in vals):issues.append('unmatched_archive_area:'+area);continue
  expected=sum(vals)
  checks.append({'area':area,'years':[lo,hi],'total_expected':str(expected),'total_rendered':total})
  if total!=fmt(expected):issues.append('total_mismatch')
  tables=[t for t in r['tables'] if t and t[0]==['Tahun','Kehilangan (ha)']]
  if not tables:issues.append('table_missing')
  for y,v in zip(range(int(lo),int(hi)+1),vals):
   if not any(str(y)==row[0] and hasval(row[1:],v) for t in tables for row in t[1:]):issues.append('year_mismatch:'+str(y))
 out.append({'id':r['id'],'checks':checks,'issues':issues})
(P/'extra-gfw-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print('Answers checked:',sum(bool(x['checks']) for x in out),'flags:',[(x['id'],x['issues']) for x in out if x['issues']])
