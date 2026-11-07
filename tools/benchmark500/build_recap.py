"""Build an auditable local benchmark report; never changes the engine."""
import json,pathlib,collections,hashlib,datetime,html
from audit_numeric import P
ROOT=pathlib.Path(__file__).resolve().parents[2]
GROUPS={'gfw':'GFW','mapbiomas':'MapBiomas','ngo':'Laporan NGO','gabungan':'Gabungan laporan + GFW'}
KINDS={'data':'Permintaan angka','tren':'Tren tahunan','perbandingan_tahun':'Perbandingan antar tahun','klaim_arah':'Klaim naik/turun','perbandingan_wilayah':'Perbandingan antar wilayah','rata_rata':'Rata-rata tahunan','periode_belum_tersedia':'Periode belum tersedia','cakupan_pulau':'Kehilangan tutupan pohon tingkat pulau','cakupan_belum_tersedia':'Cakupan/periode MapBiomas belum tersedia','laporan_data':'Temuan data laporan','laporan_dampak':'Penjelasan dampak laporan','klaim_statemen':'Klaim semua warga untung tanpa kerugian','gabungan_data':'Laporan + angka satu tahun','gabungan_tren':'Laporan + tren tiga tahun'}
LABELS={'akurat':'Akurat dan cukup lengkap','bermasalah':'Salah atau kurang tepat/lengkap','terbatas':'Terbatas: data/bukti belum mencukupi','gangguan':'Gangguan layanan','belum_diuji':'Belum diuji'}
CAUSES={
 'indikator_tidak_sesuai':('Indikator tertukar','Kawasan hutan administratif diubah menjadi tutupan hutan alam.'),
 'temuan_laporan_tidak_terambil':('Pencarian bukti laporan','Bukti relevan tersedia dalam koleksi, tetapi tidak ditemukan atau tidak digunakan.'),
 'wilayah_tidak_sesuai':('Wilayah/cakupan tertukar','Bukti daerah lain atau wilayah rekaan muncul dalam jawaban.'),
 'wilayah_bukti_tidak_sesuai':('Wilayah/cakupan tertukar','Bukti daerah lain atau wilayah rekaan muncul dalam jawaban.'),
 'wilayah_palsu':('Wilayah/cakupan tertukar','Nama biasa atau nama program dibaca sebagai wilayah administratif.'),
 'kegiatan_bukti_tidak_sesuai':('Kegiatan yang dibahas tertukar','Bukti kegiatan lain dipakai untuk menjawab kegiatan yang ditanyakan.'),
 'kesimpulan_melampaui_bukti':('Kesimpulan melampaui bukti','Risiko menjadi kejadian pasti atau temuan satu perusahaan diperluas.'),
 'label_klaim':('Label penilaian tidak selaras','Label tidak mengikuti angka atau bukti yang disajikan.'),
 'normalisasi_satuan':('Satuan/populasi/penyajian angka','Satuan yang setara dianggap berbeda atau arti angka berubah.'),
 'penyajian_satuan':('Satuan/populasi/penyajian angka','Angka luas disajikan sebagai jumlah atau satuan tidak sesuai.'),
 'penyajian_populasi':('Satuan/populasi/penyajian angka','Populasi pembagi persentase tidak dipertahankan.'),
 'jawaban_tidak_lengkap':('Jawaban tidak lengkap','Bagian penting yang diminta belum dijawab.'),
 'jenis_pertanyaan':('Jawaban tidak lengkap','Pertanyaan penjelasan salah diperlakukan sebagai klaim.'),
 'duplikasi_temuan':('Penyajian berulang','Temuan berulang tanpa menambah bukti.'),
 'kode_internal_tampil':('Penyajian berulang','Kode internal bukti tampil ke pengguna.'),
 'teks_berulang':('Penyajian berulang','Alasan dan kesimpulan berulang.'),
}
PRIORITY=['wilayah_tidak_sesuai','wilayah_bukti_tidak_sesuai','wilayah_palsu','kegiatan_bukti_tidak_sesuai','indikator_tidak_sesuai','kesimpulan_melampaui_bukti','normalisasi_satuan','penyajian_satuan','penyajian_populasi','label_klaim','temuan_laporan_tidak_terambil','jawaban_tidak_lengkap','jenis_pertanyaan','duplikasi_temuan','kode_internal_tampil','teks_berulang']
def pct(n,d):return f'{100*n/d:.1f}'.replace('.',',')+'%' if d else '—'
def main():
 plan=json.load((P/'plan.json').open());results=json.load((P/'results.json').open());manifest=json.load((P/'manifest.json').open())
 reviews=json.load((P/'manual-review.json').open());audits={r['id']:r for r in json.load((P/'numeric-audit.json').open())};rows=[]
 for r in results:
  review=reviews.get(str(r['id']))
  if review is None:
   assert audits[r['id']]['status']=='numeric_checks_passed',r['id']
   review={'status':'akurat','issues':[],'reason':'Angka, wilayah, indikator, periode dan perhitungan cocok dengan nilai referensi; arah tren/perbandingan dan label (bila diminta) sesuai.'}
  rows.append({'id':r['id'],'question':r['question'],'group':r['group'],'kind':r['kind'],**review})
 completed=len(results);counts=collections.Counter(r['status'] for r in rows)
 groups={g:dict(collections.Counter(r['status'] for r in rows if r['group']==g)) for g in GROUPS}
 kinds={k:dict(collections.Counter(r['status'] for r in rows if r['kind']==k)) for k in KINDS}
 failures=[r for r in rows if r['status']=='bermasalah'];primary=collections.Counter();overlap=collections.Counter()
 for r in failures:
  tags=r['issues'];chosen=next((t for t in PRIORITY if t in tags),None);assert chosen,r
  r['primary_issue']=CAUSES[chosen][0];primary[r['primary_issue']]+=1
  overlap.update(set(CAUSES[t][0] for t in tags if t in CAUSES))
 changed=[]
 for f,h in manifest['code_and_data_sha256'].items():
  path=ROOT/f
  if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=h:changed.append(f)
 plan_unchanged=hashlib.sha256((P/'plan.json').read_bytes()).hexdigest()==manifest['plan_sha256']
 assert not changed and plan_unchanged,(changed,plan_unchanged)
 assert len({r['question'] for r in plan})==500
 assert [r['id'] for r in results]==list(range(1,completed+1))
 assert all(r['question']==plan[r['id']-1]['question'] for r in results)
 snapshot={'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'planned':500,'completed':completed,'not_run':500-completed,'counts':dict(counts),'accuracy_completed':counts['akurat']/completed,'accuracy_planned':counts['akurat']/500,'gate': 'passed' if completed==500 and counts['akurat']>400 else 'not_passed' if completed==500 else 'pending','groups':groups,'kinds':kinds,'primary_failures':dict(primary),'overlapping_failures':dict(overlap),'integrity':{'frozen_files_checked':len(manifest['code_and_data_sha256']),'changed_files':changed,'plan_unchanged':plan_unchanged,'unique_questions':500},'first_response_only':True}
 (P/'assessments.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));(P/'summary.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
 title='BENCHMARK CEK DATA AI — 500 PERTANYAAN'
 lines=[title,'Pengujian 6–7 November 2026; satu versi mesin setelah tahap pertama perbaikan besar.','',f'Status: {completed}/500 pertanyaan telah diuji.']
 if completed<500:lines+=['LAPORAN SEMENTARA. Persentase di bawah memakai jawaban yang sudah diuji, bukan hasil final 500.']
 lines+=['','HASIL UTAMA']
 for s in ['akurat','bermasalah','terbatas','gangguan']:lines.append(f"{LABELS[s]}: {counts[s]} dari {completed} ({pct(counts[s],completed)}).")
 lines+=['',f"Ambang pengguna: lebih dari 80%, berarti minimal 401 dari 500 jawaban akurat dan cukup lengkap. Status: {snapshot['gate']}.",'Jawaban terbatas yang jujur tidak dimasukkan sebagai jawaban substantif akurat. Gangguan layanan juga tetap masuk penyebut.','', 'HASIL MENURUT SUMBER']
 for g,c in groups.items():
  n=sum(c.values());lines.append(f"{GROUPS[g]}: {c.get('akurat',0)}/{n} akurat ({pct(c.get('akurat',0),n)}); {c.get('bermasalah',0)} bermasalah; {c.get('terbatas',0)} terbatas; {c.get('gangguan',0)} gangguan.")
 lines+=['','HASIL MENURUT JENIS PERTANYAAN']
 for k,c in kinds.items():
  n=sum(c.values());lines.append(f"{KINDS[k]}: {c.get('akurat',0)}/{n} akurat ({pct(c.get('akurat',0),n)}); {c.get('bermasalah',0)} bermasalah; {c.get('terbatas',0)} terbatas; {c.get('gangguan',0)} gangguan.")
 lines+=['','POLA UTAMA JAWABAN BERMASALAH','Setiap jawaban ditempatkan pada satu masalah utama agar jumlah dan persentasenya tidak dihitung ganda. Jika ada beberapa masalah, prioritas klasifikasi: wilayah/kegiatan, indikator, kesimpulan, penyajian angka, label, pencarian bukti, kelengkapan.']
 for k,n in primary.most_common():lines.append(f'{k}: {n} dari {len(failures)} ({pct(n,len(failures))}).')
 lines+=['','CATATAN MASALAH YANG DAPAT TUMPANG TINDIH','Satu jawaban dapat memiliki lebih dari satu masalah; angka pada daftar berikut tidak boleh dijumlahkan sebagai jumlah jawaban.']
 for k,n in overlap.most_common():lines.append(f'{k}: {n} jawaban ({pct(n,len(failures))} dari jawaban bermasalah).')
 lines+=['','CONTOH YANG PERLU DIBACA',
 '#394 — Penurunan hutan rawa gambut Riau: angka benar, label Tidak dapat diverifikasi karena hectare dan ha dianggap berbeda.',
 '#403/#409/#427 — Klaim semua warga untung tanpa kerugian: jawaban menyajikan contoh kerugian, tetapi tetap Tidak dapat diverifikasi.',
 '#449–451 — Nama program 10 Bali Baru dibaca sebagai Bali dan Kabupaten Baru.',
 '#447 — Semua produk diekspor pada satu perusahaan diperluas menjadi seluruh industri pelet kayu Jawa Timur.',
 '#414/#426 — Tabel mengubah arti angka: luas menjadi jumlah izin; populasi pembagi persentase hilang.',
 '#431–433/#440–445/#454/#456–458 — Laporan relevan ada dalam koleksi, tetapi temuan tidak terambil.',
 '#468 — Pertanyaan gabungan tidak menjawab laporan maupun angka/tren yang tersedia.',
 '#469 — Sesi API key berakhir. Dicatat sebagai gangguan, tidak diganti dengan percobaan yang berhasil.',
 '#488 — Kawasan hutan seluas 493 ribu ha ditulis sebagai tutupan hutan alam; laporan menyebut tutupan alam hanya 78% dari kawasan itu.',
 '#499–500 — Perusahaan dalam proses penyelesaian legalitas ditulis seolah sebagian besar sudah memperoleh legalisasi.',
 '', 'APA YANG SUDAH KUAT',
 'Permintaan angka terstruktur, tren dengan tahun eksplisit, perbandingan antar tahun/wilayah, dan rata-rata. Angka diperiksa terhadap arsip yang dikunci, dengan perhitungan desimal independen.',
 '', 'BATAS KESIMPULAN',
 'Ini ukuran keberhasilan pada korpus uji ini, bukan jaminan akurasi seluruh pertanyaan jurnalis. 400 dari 500 soal berpusat pada data terstruktur; nilai total dapat menutupi kelemahan laporan dan klaim naratif.',
 'Mayoritas pertanyaan memakai indikator, wilayah, dan tahun yang jelas. Belum mewakili seluruh bahasa samar pejabat, pertanyaan lanjutan, salah eja, atau konflik antar sumber.',
 '500 teks pertanyaan berbeda, tetapi sejumlah pola kalimat dan tema digunakan berulang. Tema lama seperti Kabaena tetap ada. Ini bukan 500 kasus independen yang sama sekali belum pernah dikenal mesin.',
 'Cakupan rencana: 350 GFW, 50 MapBiomas, 60 laporan NGO, 40 gabungan; 34 provinsi batas GFW, 229 kabupaten/kota unik sesuai sumber, serta contoh pulau, nasional dan provinsi pemekaran melalui MapBiomas. Nama/batas sumber lama dapat berbeda dari administrasi terkini.',
 'Sampel kabupaten untuk soal angka dipilih dari wilayah yang punya seri total kehilangan 2020–2025. Periode/cakupan yang belum tersedia diuji terpisah. Ini membuat kelompok angka relatif lebih terjawab dibanding pertanyaan bebas.',
 'Penilaian laporan memeriksa kesetiaan terhadap halaman sumber, kecocokan konteks, kecukupan jawaban, dan label; bukan audit independen kebenaran seluruh temuan NGO atau akurasi penginderaan jauh.',
 'Audit dilakukan oleh satu penilai AI dengan pemeriksaan angka terprogram dan pembacaan halaman laporan. Sebelum publik, contoh kegagalan dan sebagian kelulusan sebaiknya ditinjau editor manusia.',
 'Persentase ini tidak digabung dengan 300 pertanyaan dari beberapa versi sebelumnya. Tidak dihitung sebagai estimasi acak populasi pertanyaan pengguna.',
 'Waktu pada bukti mentah mencakup jeda pemeriksaan dan pengambilan tampilan; tidak boleh dibaca sebagai waktu respons server murni.',
 '', 'INTEGRITAS PENGUJIAN',
 f"Rencana 500 pertanyaan dikunci sebelum tes; hash rencana tetap sama. {len(manifest['code_and_data_sha256'])} berkas kode/penanda data tetap sama. Tidak ada perbaikan mesin di tengah benchmark.",
 'Pengujian melalui antarmuka aplikasi lokal. Respons pertama disimpan; tidak memilih respons terbaik dari percobaan ulang. Pemulihan tampilan histori tidak mengirim pertanyaan ulang.',
 'Sesi tersambung kembali sebelum nomor 470. Gangguan nomor 469 tetap berada dalam denominator 500. Tidak ada kunci API disimpan dalam bukti pengujian.',
 'Bukti: plan.json, manifest.json, results.jsonl, assessments.json, numeric-audit.json, extra-gfw-audit.json, source-link-audit.json, manual-review.json, cited-evidence/.',
 '', 'MAKNA UNTUK RILIS',
 'Ambang >80% adalah gerbang total yang disepakati, bukan pengganti pemeriksaan per kemampuan. Klaim naratif dan jawaban laporan perlu dinilai tersendiri sebelum dipakai sebagai verifikasi otomatis omongan pejabat.',
 'Benchmark tidak melakukan push GitHub, membuka layanan ke internet, atau mengubah konfigurasi server.']
 (P/'rekap-benchmark.txt').write_text('\n'.join(lines)+'\n')
 # Portable offline report: full evidence is available per question without a network dependency.
 esc=html.escape;cards=[];byid={r['id']:r for r in results}
 for a in rows:
  r=byid[a['id']];links=''.join(f'<li><a href="{esc(l["href"],quote=True)}" target="_blank" rel="noopener noreferrer">{esc(l["text"])}</a></li>' for l in r['links'] if (l.get('href') or '').startswith('https://'))
  explanations=' '.join(dict.fromkeys(CAUSES[t][1] for t in a['issues'] if t in CAUSES)) or ('Jawaban sesuai bukti yang diperiksa.' if a['status']=='akurat' else 'Lihat alasan pemeriksaan dan respons asli di bawah.')
  cards.append(f'<details class="case" data-status="{a["status"]}" data-group="{a["group"]}"><summary><span class="tag {a["status"]}">{esc(LABELS[a["status"]])}</span> <b>#{a["id"]}</b> {esc(a["question"])}</summary><p>{esc(explanations)}</p><p class="audit">Catatan audit: {esc(a["reason"])}</p><pre>{esc(r["answer"])}</pre><ul>{links}</ul></details>')
 options=''.join(f'<option value="{s}">{esc(l)}</option>' for s,l in LABELS.items() if s!='belum_diuji')
 goptions=''.join(f'<option value="{s}">{esc(l)}</option>' for s,l in GROUPS.items())
 page='''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Benchmark Cek Data AI — 500 pertanyaan</title><style>body{font:16px/1.6 system-ui,sans-serif;background:#f6f5f2;color:#222;margin:0}main{max-width:1100px;margin:auto;padding:32px 24px}h1{font-size:30px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}section,details{background:white;padding:20px;border:1px solid #ddd;border-radius:10px;margin:12px 0}summary{cursor:pointer}.tag{font-size:12px;padding:4px 8px;border-radius:6px;display:inline-block}.akurat{background:#d8efe0}.bermasalah{background:#ffe2dc}.terbatas{background:#fff0c7}.gangguan{background:#e6e2f5}.audit{font-size:14px;color:#555}input,select{font:inherit;padding:10px;margin:4px;border:1px solid #aaa;border-radius:6px}a{color:#a41563}.filters{position:sticky;top:0;background:#f6f5f2;padding:8px;z-index:1}@media print{.filters{display:none}details{break-inside:avoid}}</style><main>'''
 stats=''.join(f'<div><strong style="font-size:32px">{pct(counts[s],completed)}</strong><br>{counts[s]} — {esc(LABELS[s])}</div>' for s in ['akurat','bermasalah','terbatas','gangguan'])
 group_rows=''.join(f'<tr><td>{esc(GROUPS[g])}</td><td>{c.get("akurat",0)}/{sum(c.values())}</td><td>{pct(c.get("akurat",0),sum(c.values()))}</td><td>{c.get("bermasalah",0)}</td><td>{c.get("terbatas",0)}</td><td>{c.get("gangguan",0)}</td></tr>' for g,c in groups.items())
 issue_rows=''.join(f'<tr><td>{esc(k)}</td><td>{n}</td><td>{pct(n,len(failures))}</td></tr>' for k,n in primary.most_common())
 page+='<style>.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}.stats div{padding:14px;background:#f7f5f3;border-radius:8px}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{text-align:left;padding:9px;border-bottom:1px solid #ddd;font-size:14px}@media(max-width:700px){.stats{grid-template-columns:repeat(2,1fr)}table{display:block;overflow:auto}}</style>'
 page+=f'<h1>{esc(title)}</h1><p>Arsip pengujian 6–7 November 2026 · {completed}/500 selesai · versi mesin tetap</p><section><div class="stats">{stats}</div><p><b>Ambang &gt;80%: {"terlewati" if snapshot["gate"]=="passed" else "belum ditetapkan" if completed<500 else "belum terlewati"}.</b> Jawaban terbatas dan gangguan tetap masuk penyebut, tanpa dihitung akurat.</p><p>Skor total didominasi pertanyaan angka. Kemampuan membaca laporan dan menilai klaim naratif masih perlu perbaikan sebelum dipakai sebagai verifikasi otomatis.</p></section><section><h2>Hasil per kelompok</h2><table><tr><th>Kelompok</th><th>Akurat</th><th>% akurat</th><th>Bermasalah</th><th>Terbatas</th><th>Gangguan</th></tr>{group_rows}</table></section><section><h2>Pola utama {len(failures)} jawaban bermasalah</h2><table><tr><th>Masalah utama</th><th>Jumlah</th><th>% dari kegagalan</th></tr>{issue_rows}</table><p>Setiap jawaban dihitung satu kali pada masalah utamanya. Daftar masalah yang tumpang tindih tersedia di metodologi.</p></section><details><summary><b>Rekap lengkap, metodologi, contoh dan batas hasil</b></summary><pre>{esc(chr(10).join(lines[3:]))}</pre></details><h2>Telusuri jawaban dan penilaian</h2><div class="filters"><input id="query" type="search" placeholder="Cari pertanyaan atau nomor"><select id="status"><option value="">Semua hasil</option>{options}</select><select id="group"><option value="">Semua sumber</option>{goptions}</select><span id="count"></span></div>'+''.join(cards)
 page+='''<script>const items=[...document.querySelectorAll('.case')];function filter(){const q=document.querySelector('#query').value.toLowerCase(),s=document.querySelector('#status').value,g=document.querySelector('#group').value;let n=0;for(const x of items){const visible=(!s||x.dataset.status===s)&&(!g||x.dataset.group===g)&&x.textContent.toLowerCase().includes(q);x.hidden=!visible;if(visible)n++;}document.querySelector('#count').textContent=n+' jawaban';}for(const id of ['query','status','group'])document.getElementById(id).addEventListener('input',filter);filter();</script></main></html>'''
 (P/'rekap-benchmark.html').write_text(page)
 print(json.dumps({'completed':completed,'counts':dict(counts),'gate':snapshot['gate'],'primary':dict(primary)},ensure_ascii=False))
if __name__=='__main__':main()
