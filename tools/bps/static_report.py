"""Verify static archives against raw API snapshots and make an escaped local report."""
import hashlib,json
from collections import Counter
from html import escape
from pathlib import Path
from tools.bps.static import grids,TOPICS
from tools.bps.ingest import DEFAULT_DIR,ROOT,write_json


def report(directory=DEFAULT_DIR/'static',output=None):
 directory=Path(directory);m=json.loads((directory/'manifest.json').read_text())
 output=Path(output or ROOT/'docs/test-evidence/20261107/bps-static-2019-2026');output.mkdir(parents=True,exist_ok=True)
 errors=[];empty_grids=[];verified=0;totalcells=0;labelcounts=Counter();topics={t:{'archived':0,'with_year_labels':0,'with_2026_label':0} for t in TOPICS};entries=[]
 for item in m['documents']:
  doc=json.loads((directory/'documents'/(item['id']+'.json')).read_text());raw=(directory/'raw'/(doc['source_snapshot_sha256']+'.json')).read_bytes();body=json.loads(raw)['data']
  checks=[hashlib.sha256(raw).hexdigest()==doc['source_snapshot_sha256'],str(body['table_id'])==doc['table_id'],body.get('table','')==doc['html'],hashlib.sha256(doc['html'].encode()).hexdigest()==doc['html_sha256']]
  if not all(checks):errors.append(doc['id'])
  else:verified+=1

  if not doc['tables']:empty_grids.append(doc['id'])
  totalcells+=sum(len(t['cells']) for t in doc['tables']);labelcounts.update(doc['years_with_label_candidates'])
  for t in doc['topics']:
   topics[t]['archived']+=1;topics[t]['with_year_labels']+=bool(doc['years_with_label_candidates']);topics[t]['with_2026_label']+=2026 in doc['years_with_label_candidates']
  years=', '.join(map(str,doc['years_with_label_candidates'])) or 'Perlu pemeriksaan susunan tabel'
  local=output/(doc['id']+'.html')
  rendered=[]
  for t in doc['tables']:
   rendered.append('<table>'+''.join('<tr>'+''.join('<td>'+escape(t['cells'][i]['text'] if i is not None else '')+'</td>' for i in row)+'</tr>' for row in t['grid'])+'</table>')
  download_html=(' · <a href=\"'+escape(doc['download_url'],quote=True)+'\">Unduh dari BPS</a>') if doc['download_url'] else ' · Tautan unduh Excel tidak tersedia pada respons API'
  local.write_text('<!doctype html><meta charset="utf-8"><style>body{font:15px system-ui;margin:32px}td{padding:5px;border:1px solid #ddd}table{border-collapse:collapse;margin:20px 0}pre{white-space:pre-wrap}</style><h1>'+escape(doc['title'])+'</h1><p>Arsip tabel; belum diaktifkan untuk jawaban AI. Sel gabungan diulang untuk mempertahankan konteks.</p><p><a href="'+escape(doc['source_url'],quote=True)+'">Halaman publik BPS</a>'+download_html+'</p>'+''.join(rendered)+'<h2>Teks lengkap dan catatan</h2><pre>'+escape(doc['text'])+'</pre>')
  entries.append('<tr><td>'+escape(', '.join(doc['topics']))+'</td><td><a href="'+local.name+'">'+escape(doc['title'])+'</a></td><td>'+years+'</td><td>'+escape(str(doc['updated_at']))+'</td></tr>')
 summary={'requested_years':m['requested_years'],'catalog_tables':m['catalog_tables'],'candidates':m['candidates'],'topic_candidates':m.get('topic_candidates',m['candidates']),'excluded_before_period':len(m.get('excluded_before_period',[])),'archived':len(m['documents']),'verified_against_api':verified,'audit_errors':errors,'documents_without_html_table':empty_grids,'collection_errors':m['errors'],'source_cells_preserved':totalcells,'tables_by_candidate_year_label':dict(sorted(labelcounts.items())),'topics':topics,'qdrant_ingested':False,'pdf_downloads':0,'scope':'central BPS publisher 0000; catalogue keyword screening; not all regional publisher catalogues','audit_scope':'Every source response checksum and full HTML matched; grid parsing unit-tested, numeric dimensions not yet reviewed','coverage_note':'Year labels are candidates, not verified numerical coverage. Some are base years or values; missing labels do not prove missing periods.'}
 write_json(output/'summary.json',summary)
 topic_html='<h2>Cakupan per tema</h2><p>Satu tabel dapat masuk lebih dari satu tema. Label tahun masih perlu pemeriksaan dimensi.</p><table><tr><th>Tema</th><th>Tabel diarsipkan</th><th>Memuat label 2019–2026</th><th>Memuat label 2026</th></tr>'+''.join('<tr><td>'+escape(t.replace('_',' '))+'</td><td>'+str(c['archived'])+'</td><td>'+str(c['with_year_labels'])+'</td><td>'+str(c['with_2026_label'])+'</td></tr>' for t,c in topics.items())+'</table>'
 output.joinpath('rekap.html').write_text('<!doctype html><meta charset="utf-8"><title>Tabel statis BPS 2019–2026</title><style>body{font:15px system-ui;max-width:1400px;margin:32px auto;padding:16px;color:#233}td,th{border-bottom:1px solid #ddd;padding:10px;text-align:left}table{border-collapse:collapse;width:100%}a{color:#145ba0}</style><h1>Pengambilan tabel statis BPS — sasaran 2019–2026</h1><p>'+str(verified)+' entri katalog diverifikasi terhadap respons API ('+str(verified-len(empty_grids))+' berisi tabel HTML, '+str(len(empty_grids))+' tidak berisi tabel HTML); '+str(totalcells)+' sel sumber dipertahankan. PDF tidak diunduh. Belum masuk Qdrant atau jawaban publik.</p><p>Label tahun berikut merupakan petunjuk pemeriksaan, bukan jaminan semua angka atau wilayah tersedia pada tahun tersebut. Tanggal pembaruan bukan periode data. Tabel sumber lengkap dipertahankan, termasuk tahun di luar sasaran untuk konteks. Tautan publik dibentuk dari ID resmi dan belum diverifikasi satu per satu. Tautan unduh berasal dari API.</p>'+topic_html+'<h2>Daftar tabel</h2><table><thead><tr><th>Tema</th><th>Tabel dan salinan lokal</th><th>Label tahun 2019–2026 ditemukan</th><th>Diperbarui</th></tr></thead><tbody>'+''.join(entries)+'</tbody></table>')
 print(json.dumps(summary,ensure_ascii=False,indent=2));return summary

if __name__=='__main__':report()
