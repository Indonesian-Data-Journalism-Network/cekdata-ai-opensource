import json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[2];P=ROOT/'docs/test-evidence/20261106/benchmark500-v1';out=P/'cited-evidence';out.mkdir(exist_ok=True)
docs=json.load((ROOT/'data/ngo/manifest.json').open())['documents']
for r in json.load((P/'results.json').open()):
 if r['group'] not in ['ngo','gabungan']:continue
 sources=[]
 for line in r['answer'].splitlines():
  if 'Sumber:' not in line or 'halaman PDF ' not in line:continue
  matches=[d for d in docs if d['title'] in line]
  if not matches:continue
  d=max(matches,key=lambda d:len(d['title']));nums=[int(n) for n in re.findall(r'\d+',line.split('halaman PDF ')[-1])];path=ROOT/'data/ngo/extractions/ngo-pdf-v3'/d['provider']/d['id']/'pages.json'
  if not path.exists():continue
  pages=json.load(path.open());sources.append(dict(title=d['title'],provider=d['provider'],document_id=d['id'],source_url=d['source_url'],download_url=d['download_url'],pages=[x for x in pages if x['pdf_page'] in nums]))
 (out/f"{r['id']:03}.json").write_text(json.dumps(sources,ensure_ascii=False,indent=2))
print('Cited evidence packets',len(list(out.glob('*.json'))))
