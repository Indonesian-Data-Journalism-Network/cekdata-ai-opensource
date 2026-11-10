"""Audit every selected national cell against its API snapshot; export a review bundle."""
import csv,hashlib,json,sqlite3
from collections import Counter,defaultdict
from html import escape
from pathlib import Path
from tools.bps.ingest import DEFAULT_DIR,ROOT,write_json,normalize
from tools.bps.national import country_scope,public_url,national_rows


def report(root=DEFAULT_DIR/'national-2019-2026',out=None):
 root=Path(root);out=Path(out or ROOT/'docs/test-evidence/20261107/bps-national-2019-2026');out.mkdir(parents=True,exist_ok=True)
 plan=json.loads((root/'plan.json').read_text());manifest=json.loads((root/'manifest.json').read_text())
 write_json(out/'acquisition-plan.json',plan)
 tables={t['variable_id']:t for t in plan['tables']}
 c=sqlite3.connect(root/'bps.sqlite3');errors=[];verified=0;records=[]
 for var,pid,sha,retrieved,url in c.execute('select variable_id,period_id,sha256,retrieved_at,source_url from imports'):
  raw=(root/'raw'/(sha+'.json')).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=sha:errors.append(f'checksum:{var}/{pid}');continue
  data=json.loads(raw,parse_float=str)
  decoded,_=normalize(data,'0000',var,pid,max_combinations=2000000)
  expected=national_rows(decoded,data,tables[var],{'sha256':sha,'retrieved_at':retrieved},url)
  actual=[json.loads(r[0]) for r in c.execute('select record from observations where variable_id=? and period_id=?',(var,pid))]
  if {r['id']:r for r in expected}!={r['id']:r for r in actual}:errors.append(f'payload:{var}/{pid}')
  else:verified+=len(actual)
  if any(r['area']!='Indonesia' or r['geographic_level']!='adm0' or not plan['start_year']<=r['year']<=plan['end_year'] for r in actual):errors.append(f'scope:{var}/{pid}')
  records.extend(actual)
 c.close()
 numeric=[r for r in records if r['value'] is not None]
 ready=[r for r in numeric if r['status']=='observed' and r['period_status']=='mapped']
 pervar=defaultdict(list)
 for r in records:pervar[r['variable_id']].append(r)
 fields=['indicator','year','period','area','population_scope','category_axis','category','derived_category','value','unit','status','period_status','data_status','data_status_note','period_ended_at_retrieval','source_url','source_snapshot_sha256','notes']
 def export(path,rows):
  with open(path,'w',newline='',encoding='utf-8-sig') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for r in rows:
    item={'indicator':r['variable'],'year':r['year'],'period':r['subperiod_label'],'area':r['area'],'population_scope':r['population_scope'],'category_axis':r['vertical_axis'],
      'category':r['vertical_label'],'derived_category':r['derived_label'],'value':r['value'],'unit':r['unit'],'status':r['status'],
      'period_status':r['period_status'],'data_status':r['data_status'],'data_status_note':r['data_status_note'],'period_ended_at_retrieval':r['period_ended_at_retrieval'],'source_url':r['source_url'],'source_snapshot_sha256':r['source_snapshot_sha256'],'notes':r.get('notes','')}
    # Keep numeric value exact. Escape spreadsheet formulas only in text fields.
    for k,v in item.items():
     if k not in ['value','year'] and isinstance(v,str) and v[:1] in '=+-@':item[k]="'"+v
    w.writerow(item)
 export(out/'bps-nasional-2019-2026.csv',records)
 inventory=[];body=[]
 for var,table in tables.items():
  rr=pervar[var];years=sorted({r['year'] for r in rr});yy26=sorted({r['subperiod_label'] for r in rr if r['year']==2026})
  missing=sorted(set(range(plan['start_year'],plan['end_year']+1))-set(years))
  item={'variable_id':var,'title':table['title'],'topics':table['topics'],'national_records':len(rr),'numeric_values':sum(r['value'] is not None for r in rr),'years':years,'missing_national_years':missing,'subperiods_2026':yy26,'source_url':public_url(var,table['title'])}
  inventory.append(item)
  download='—'
  if rr:
   name=f'bps-national-{var}.csv';export(out/name,rr);download=f'<a href="{name}">CSV angka nasional</a>'
  holds=[h for h in manifest['holds'] if h['variable_id']==var]
  notes='; '.join(sorted({h['reason'] for h in holds}))
  body.append('<tr><td>'+escape(', '.join(table['topics']))+'</td><td><a href="'+escape(item['source_url'],quote=True)+'">'+escape(table['title'])+'</a></td><td>'+escape(', '.join(map(str,years)) or 'Belum ada baris nasional yang lolos')+'</td><td>'+str(len(rr))+'</td><td>'+escape(', '.join(yy26) or 'Belum tersedia pada hasil nasional')+'</td><td>'+download+'</td><td>'+escape(notes)+'</td></tr>')
 topics={theme:{'tables_with_records':sum(bool(pervar[t['variable_id']]) for t in tables.values() if theme in t['topics']),
   'records':sum(1 for r in records if theme in r['topics']),
   'numeric_values':sum(1 for r in numeric if theme in r['topics']),
   'records_2026':sum(1 for r in records if theme in r['topics'] and r['year']==2026)} for theme in sorted({x for t in tables.values() for x in t['topics']})}
 summary={'scope':'Indonesia/national only','requested_years':[plan['start_year'],plan['end_year']],'tables_requested':len(tables),'tables_with_national_records':len([v for v in pervar.values() if v]),
 'national_records':len(records),'numeric_values':len(numeric),'numeric_with_unit_and_mapped_period':len(ready),'statuses':dict(Counter(r['status'] for r in records)),
 'records_by_year':dict(sorted(Counter(r['year'] for r in records).items())),'topics':topics,'verified_records':verified,'audit_errors':errors,'held_table_years':len(manifest['holds']),
 'data_statuses':dict(Counter(r['data_status'] for r in records)),
 'period_not_ended_at_retrieval':sum(r['period_ended_at_retrieval'] is False for r in records),
 'missing_units_by_table':dict(Counter(r['variable_id'] for r in records if r['status']=='missing_unit')),
 'qdrant_ingested':False,'public_provider_changed':False,'source_pages_individually_verified':False,'notes':['Numeric with unit and period is not yet equivalent to verified AI answer evidence.','No provinces summed to manufacture country totals.','CSV is a local export of API evidence, not an official BPS download file.','Source method/series and category dimensions retained; series not stitched across definitions.']}
 write_json(out/'summary.json',summary);write_json(out/'inventory.json',inventory)
 topic_html=''.join('<tr><td>'+escape(k.replace('_',' '))+'</td><td>'+str(v['tables_with_records'])+'</td><td>'+str(v['numeric_values'])+'</td><td>'+str(v['records_2026'])+'</td></tr>' for k,v in topics.items())
 (out/'rekap.html').write_text('<!doctype html><meta charset="utf-8"><title>BPS nasional 2019–2026</title><style>body{font:15px system-ui;max-width:1500px;margin:30px auto;padding:20px;color:#234}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}table{border-collapse:collapse;width:100%}a{color:#1762a8}</style><h1>BPS nasional — pengambilan 2019–2026</h1><p>'+str(len(numeric))+' nilai numerik, '+str(len(records))+' rekaman termasuk nilai kosong/ditahan, dari '+str(summary['tables_with_national_records'])+' tabel dengan data nasional. '+str(verified)+' rekaman cocok dengan sumber; '+str(len(errors))+' perbedaan audit.</p><p>Data nasional diambil langsung dari anggota dimensi Indonesia/Nasional, atau tabel nasional yang cakupannya telah ditinjau. Tidak menjumlahkan persentase/indeks provinsi. Paket awal '+str(len(tables))+' tabel inti, bukan seluruh katalog. Tahun yang tidak muncul bukan berarti nol. Label tahunan pada tahun berjalan belum berarti realisasi setahun penuh; status akhir periode saat pengambilan disimpan terpisah. Angka potensi pertanian ditandai potential, terpisah dari angka sementara.</p><p><strong>Belum dimasukkan ke Qdrant atau jawaban publik.</strong> Satuan yang belum jelas dan periode yang belum terpetakan tetap ditandai. Tautan halaman BPS dibentuk dari ID resmi, belum diverifikasi satu per satu. CSV merupakan salinan lokal angka API beserta bukti sumber.</p><p><a href="bps-nasional-2019-2026.csv">Unduh seluruh data nasional (CSV)</a></p><h2>Cakupan tema</h2><table><tr><th>Tema</th><th>Tabel berisi data nasional</th><th>Nilai numerik</th><th>Rekaman 2026</th></tr>'+topic_html+'</table><h2>Inventaris tabel dan periode</h2><table><tr><th>Tema</th><th>Sumber BPS</th><th>Tahun tersedia nasional</th><th>Rekaman</th><th>Periode 2026</th><th>Unduh lokal</th><th>Catatan tinjauan</th></tr>'+''.join(body)+'</table>')
 print(json.dumps(summary,ensure_ascii=False,indent=2));return summary

if __name__=='__main__':report()
