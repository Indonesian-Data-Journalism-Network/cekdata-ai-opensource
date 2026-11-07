"""Independent benchmark checks. Flags remain reviewable; no production imports."""
import json,re,pathlib,collections
from decimal import Decimal,ROUND_HALF_UP
P=pathlib.Path(__file__).resolve().parents[2]/'docs/test-evidence/20261106/benchmark500-v1'
D=Decimal

def fmt(x):
 x=D(str(x)); v=x.quantize(D('.01'),rounding=ROUND_HALF_UP)
 if x and not v: v=x.quantize(D(1).scaleb(x.adjusted()-1),rounding=ROUND_HALF_UP)
 s=f'{v:,.{max(2,-v.as_tuple().exponent)}f}';return s.replace(',','~').replace('.',',').replace('~','.')
def norm(s):return re.sub(r'\s+',' ',s.casefold().replace('sumatra','sumatera').replace('d.i. yogyakarta','yogyakarta').replace('dki jakarta','jakarta raya')).strip()
def hasval(cells,v):
 token=fmt(v)
 return any(re.search(r'(?<![\d.,])'+re.escape(token)+r'(?![\d.,])',c) for c in cells)
def audit(r):
 ans=r['answer'].removeprefix(r['question']).strip(); a=norm(ans);issues=[];notes=[]; checks=[]
 if 'proses belum berhasil' in a or 'sesi api key berakhir' in a:return dict(id=r['id'],status='gangguan',issues=['gangguan_layanan'])
 if r['group']=='ngo':return dict(id=r['id'],status='review_laporan',issues=[])
 if r['kind'] in ['periode_belum_tersedia','cakupan_belum_tersedia','cakupan_pulau']:return dict(id=r['id'],status='review_keterbatasan',issues=[])
 tables=r.get('tables',[]); body=[row for t in tables for row in t[1:]]
 missing=[]
 for area,values in r['expected_values'].items():
  for year,v in values.items():
   if v is None:notes.append(f'Nilai sumber tidak tersedia: {area} {year}');continue
   match=[row for row in body if year in row and any(norm(area)==norm(c) for c in row)]
   # Single-area report tables can omit area column, while heading retains scope.
   if not match and len(r['areas'])==1 and norm(area).split(',')[0] in a:match=[row for row in body if year in row]
   for table in tables:
    if not table:continue
    for col,header in enumerate(table[0]):
     if norm(header).removesuffix(' (ha)')==norm(area):
      match.extend([[row[col]] for row in table[1:] if year in row and len(row)>col])
   if not any(hasval(row,v) for row in match):missing.append(f'{area} {year}: {fmt(v)}')
 if missing:issues.append('angka_tabel_tidak_cocok_atau_tidak_lengkap')
 expected_verdict=r.get('expected_verdict');actual_verdict=None
 m=re.search(r'penilaian\s*:\s*(tidak dapat diverifikasi|sebagian benar|benar|salah)',ans,re.I)
 if m:actual_verdict=m.group(1).capitalize()
 if expected_verdict and norm(expected_verdict)!=norm(actual_verdict or ''):issues.append('label_klaim_tidak_sesuai')
 # Dataset identity checked against output title/source, not the echoed question.
 metric=r['metric'] or ''
 if metric=='gfw-tree-cover-loss-fire' and 'akibat kebakaran' not in a:issues.append('indikator_tidak_terkonfirmasi')
 if metric=='gfw-primary-forest-loss' and 'primer' not in a:issues.append('indikator_tidak_terkonfirmasi')
 if metric=='gfw-tree-cover-loss' and ('primer' in a[:300] or 'akibat kebakaran' in a[:300]):issues.append('indikator_mungkin_tertukar')
 vals=[D(v) for aa in r['expected_values'].values() for v in aa.values() if v is not None]
 extra=[]
 if r['kind'] in ['perbandingan_tahun','perbandingan_wilayah'] and len(vals)==2:
  expected=abs(vals[1]-vals[0]);checks.append({'calculation':'absolute_difference','expected':str(expected)})
  if not hasval([ans],expected):issues.append('selisih_tidak_ditemukan')
  if r['kind']=='perbandingan_tahun':
   dr='naik' if vals[1]>vals[0] else 'turun' if vals[1]<vals[0] else 'tetap'
   lead=a.split('temuan data')[0]
   if dr!='tetap' and '('+dr+')' not in lead and dr not in lead:issues.append('arah_perbandingan_perlu_review')
   for t in tables:
    for rr in t[1:]:
     if rr and rr[0].startswith('Perubahan') and len(rr)>1:
      if (vals[1]<vals[0]) != rr[1].startswith('-'):issues.append('tanda_selisih_keliru')
 if r['kind']=='perbandingan_wilayah' and len(vals)==2 and vals[0]!=vals[1]:
  winner=r['areas'][0] if vals[0]>vals[1] else r['areas'][1]
  if norm(winner)+' lebih tinggi' not in a.split('temuan data')[0]:issues.append('peringkat_wilayah_perlu_review')
 if r['kind']=='rata_rata' and len(vals)==len(r['years']):
  expected=sum(vals)/D(len(vals));checks.append({'calculation':'annual_mean','expected':str(expected)})
  if not hasval([ans],expected):issues.append('rata_rata_tidak_ditemukan')
  for t in tables:
   for row in t[1:]:
    if row and row[0].startswith('Total') and not hasval(row[1:],sum(vals)):issues.append('total_tidak_sesuai')
 if r['kind']=='tren' and len(r['areas'])==1 and all(v is not None for aa in r['expected_values'].values() for v in aa.values()):
  vv=r['expected_values'][r['areas'][0]];pairs={(y,z):('naik' if D(vv[str(z)])>D(vv[str(y)]) else 'turun' if D(vv[str(z)])<D(vv[str(y)]) else 'tetap') for y,z in zip(r['years'],r['years'][1:])};covered=set()
  segments=re.findall(r'(naik|turun|tetap) pada (20\d{2})[–-](20\d{2})',a.split('temuan data')[0])
  for dr,lo,hi in segments:
   for y,z in pairs:
    if int(lo)<=y and z<=int(hi):
     covered.add((y,z))
     if dr!=pairs[(y,z)]:issues.append('kesimpulan_tren_keliru')
  if not segments or covered!=set(pairs):issues.append('kesimpulan_tren_perlu_review')
  end='lebih tinggi' if vals[-1]>vals[0] else 'lebih rendah' if vals[-1]<vals[0] else 'sama'
  if ('lebih tinggi' in a or 'lebih rendah' in a) and end not in a:issues.append('arah_awal_akhir_keliru')
 if not any((l.get('href') or '').startswith('https://') for l in r['links']):issues.append('tautan_sumber_tidak_ada')
 if notes:issues.append('pembanding_sumber_tidak_lengkap')
 return dict(id=r['id'],status='review' if issues or r['group']=='gabungan' else 'numeric_checks_passed',issues=issues,missing=missing,notes=notes,checks=checks,expected_verdict=expected_verdict,actual_verdict=actual_verdict)
if __name__=='__main__':
 results=json.load((P/'results.json').open());out=[audit(r) for r in results];(P/'numeric-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print('Completed',len(out),dict(collections.Counter(x['status'] for x in out)))
 print('Flags',[(x['id'],x['issues']) for x in out if x['issues']][:80])
