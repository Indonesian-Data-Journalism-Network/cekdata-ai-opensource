"""Frozen benchmark corpus; no production workflow imports or inferred missing zeros."""
import json, random, pathlib, hashlib, re, collections
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/test-evidence/20261106/benchmark500-v1'
rng=random.Random(20261106500)
rows=[json.loads(l) for l in (ROOT/'data/gfw-adm2/records.jsonl').open()]
idx={(r['indicator_id'],r['area'],r['year']):r for r in rows}
metrics=[('gfw-tree-cover-loss','kehilangan tutupan pohon'),('gfw-tree-cover-loss-fire','kehilangan tutupan pohon akibat kebakaran'),('gfw-primary-forest-loss','kehilangan tutupan pohon dalam hutan primer')]
provs=sorted({r['area'] for r in rows if r.get('dataset')=='gadm__tcl__adm1_change'})
dists=sorted({r['area'] for r in rows if r.get('dataset')=='gadm__tcl__adm2_change'})
dists=[a for a in dists if all(('gfw-tree-cover-loss',a,y) in idx for y in range(2020,2026))]
rng.shuffle(dists)
plan=[]
def add(q,kind,areas,metric,years,group='gfw',level=None,direction=None,**kw):
 if isinstance(areas,str):areas=[areas]
 values={a:{str(y):idx.get((metric,a,y),{}).get('value') for y in years} for a in areas}
 verdict=None
 if direction and len(areas)==1 and len(years)==2 and all(v is not None for v in values[areas[0]].values()):
  v=[Decimal(values[areas[0]][str(y)]) for y in years]; yes=v[-1]>v[0] if direction=='naik' else v[-1]<v[0]
  verdict='Benar' if yes else 'Salah'
 plan.append(dict(id=len(plan)+1,question=q,kind=kind,group=group,level=level or ('kabupaten/kota' if ',' in areas[0] else 'provinsi'),areas=areas,metric=metric,years=years,expected_values=values,expected_verdict=verdict,**kw))
def metric_for(a,i,years):
 for j in range(3):
  m,label=metrics[(i+j)%3]
  if all((m,a,y) in idx for y in years):return m,label
 return metrics[i%3]
# 120 lookups: all source provinces then 86 sampled districts.
for i,a in enumerate(provs+dists[:86]):
 y=[2020,2021,2022,2023,2024,2025][i%6];m,l=metric_for(a,i,[y]);add(f'Sebutkan luas {l} di {a} pada {y}, dalam hektare.','data',a,m,[y])
# 80 trends, varying interval, and 60 annual comparisons.
for i,a in enumerate(provs+dists[86:132]):
 yy=list(range([2020,2021,2022][i%3],2026));m,l=metric_for(a,i+1,yy);add(f'Tolong tampilkan tren tahunan {l} di {a} dari {yy[0]} sampai 2025.','tren',a,m,yy)
for i,a in enumerate(dists[132:192]):
 yy=[[2022,2023],[2023,2024],[2024,2025]][i%3];m,l=metric_for(a,i,yy);add(f'Apakah {l} di {a} lebih besar pada {yy[1]} atau {yy[0]}? Berapa selisih luasnya?','perbandingan_tahun',a,m,yy)
# 40 directional claims; truth chosen by evidence, not by phrasing.
for i,a in enumerate(provs[:20]+dists[192:212]):
 yy=[2024,2025] if i%2 else [2023,2024];m,l=metric_for(a,i,yy);dr='naik' if i%3 else 'turun';add(f'Klaim: {l.capitalize()} di {a} {dr} dari {yy[0]} ke {yy[1]}. Apakah sesuai data?','klaim_arah',a,m,yy,direction=dr)
for i in range(20):
 a,b=provs[i],provs[(i+11)%len(provs)];m,l=metrics[0];y=2024 if i%2 else 2025
 add(f'Mana yang kehilangan tutupan pohonnya lebih luas pada {y}, {a} atau {b}? Tampilkan kedua angkanya dan selisihnya.','perbandingan_wilayah',[a,b],m,[y])
for i,a in enumerate(dists[212:222]):
 yy=[2021,2022,2023,2024,2025];m,l=metric_for(a,i,yy);add(f'Berapa rata-rata per tahun {l} di {a} untuk periode 2021 sampai 2025? Sertakan angka setiap tahun.','rata_rata',a,m,yy)
for i,a in enumerate(['Papua Selatan','Papua Tengah','Papua Pegunungan','Papua Barat Daya']+provs[10:16]):
 m,l=metrics[i%3];add(f'Sudah berapa hektare {l} di {a} selama 2026 sampai bulan terakhir yang tersedia?','periode_belum_tersedia',a,m,[2026],expected_limitation='Tidak ada seri tahunan 2026 pada snapshot; dilarang mengganti tahun/cakupan atau membuat nol.')
for i,a in enumerate(['Pulau Sumatra','Pulau Kalimantan','Pulau Sulawesi','Pulau Jawa','Pulau Papua','Pulau Lombok','Pulau Flores','Pulau Sumbawa','Pulau Seram','Pulau Halmahera']):
 yy=[2023,2024,2025] if i%2 else [2025];m,l=metrics[i%3]
 q=f'Tampilkan {l} di {a} untuk '+('2023 sampai 2025.' if i%2 else 'tahun 2025.')
 add(q,'cakupan_pulau',a,m,yy,level='pulau',expected_limitation='Batas pulau tidak identik dengan satu provinsi. Agregasi harus membuktikan cakupan; klarifikasi/keterbatasan dicatat terpisah, bukan jawaban angka sukses.')
assert len(plan)==350,len(plan)
# 50 land-cover questions from the active independent snapshot.
for line in (ROOT/'data/mapbiomas/bbf674bc0f3d/records.jsonl').open():
 r=json.loads(line)
 if r.get('aggregation_kind')=='annual_stock':idx[(r['indicator_id'],r['area'],r['year'])]=r
mm=[('mapbiomas-extent-oil-palm','luas tutupan sawit'),('mapbiomas-extent-forest','luas tutupan hutan'),('mapbiomas-extent-mangrove','luas mangrove'),('mapbiomas-extent-peat-swamp-forest','luas hutan rawa gambut')]
# resolve only catalog-defined IDs; labels do not infer absent classes.
cat=json.load(open(ROOT/'data/mapbiomas/bbf674bc0f3d/catalog.json'))
print('Map extent IDs',[c['indicator_id'] for c in cat if c['indicator_id'].startswith('mapbiomas-extent-')])
mapareas=['Aceh','Sumatera Utara','Sumatera Barat','Riau','Jambi','Sumatera Selatan','Bengkulu','Lampung','Kalimantan Barat','Kalimantan Tengah','Kalimantan Selatan','Kalimantan Timur','Kalimantan Utara','Sulawesi Tengah','Sulawesi Selatan','Sulawesi Tenggara','Maluku','Maluku Utara','Papua Selatan','Papua Barat']
def mapmetric(a,i):
 for j in range(4):
  m,l=mm[(i+j)%4]
  if (m,a,2024) in idx:return m,l
 raise ValueError(a)
for i,a in enumerate(mapareas):
 m,l=mapmetric(a,i);y=2023 if i%2 else 2024;add(f'Saya ingin mengetahui {l} di {a} pada tahun {y}. Berapa hektare?','data',a,m,[y],group='mapbiomas')
for i,a in enumerate(['Sumatera','Kalimantan','Sulawesi','Jawa','Papua Selatan','Papua Tengah','Papua Barat Daya','Papua Pegunungan','Bali','Indonesia']):
 m,l=mapmetric(a,i);add(f'Bagaimana perubahan {l} di {a} setiap tahun dari 2020 sampai 2024?','tren',a,m,list(range(2020,2025)),group='mapbiomas',level='pulau' if a in ['Sumatera','Kalimantan','Sulawesi','Jawa'] else 'nasional' if a=='Indonesia' else 'provinsi')
for i,a in enumerate(mapareas[5:15]):
 m,l=mapmetric(a,i);add(f'Bandingkan {l} di {a} tahun 2022 dengan 2024. Mana yang lebih luas dan berapa selisihnya?','perbandingan_tahun',a,m,[2022,2024],group='mapbiomas')
for i,a in enumerate(mapareas[:5]):
 m,l=mapmetric(a,i);dr='turun' if i%2 else 'naik';add(f'Benarkah {l} di {a} {dr} dari 2022 ke 2023?','klaim_arah',a,m,[2022,2023],group='mapbiomas',direction=dr)
for i,a in enumerate(['Papua Selatan','Riau','Kalimantan Tengah','Kabupaten Siak, Riau','Kabupaten Ketapang, Kalimantan Barat']):
 m,l=mm[0];y=2025 if i<3 else 2024;add(f'Berapa hektare kebun sawit yang terpetakan di {a} pada {y}?','cakupan_belum_tersedia',a,m,[y],group='mapbiomas',expected_limitation='Snapshot stok sampai 2024 dan hanya provinsi/pulau/nasional; tidak boleh mengganti kabupaten atau tahun.')
assert len(plan)==400
# 20 substantive report topics; three simple standalone questions and two mixed questions each.
topics=[
('Pulau Kabaena','Kabupaten Bombana','pertambangan nikel','ae445b1792a0d6f16f1d','pendapatan dan mata pencaharian warga'),
('Raja Ampat','Kabupaten Raja Ampat','pertambangan nikel','d0a10908954131078c6e','hutan dan kehidupan nelayan'),
('Pulau Obi','Kabupaten Halmahera Selatan','industri nikel','1a0ba0269058486fcf3e','air bersih dan penghidupan warga'),
('Pomalaa','Kabupaten Kolaka','kawasan industri nikel','12184774efb93835aa08','lahan dan kehidupan warga'),
('Morowali','Kabupaten Morowali','industri nikel','454c60da005ecef5e278','keselamatan dan kondisi pekerja'),
('Halmahera Tengah','Kabupaten Halmahera Tengah','industri nikel','856000ba2c7a1c3f9b7a','lingkungan dan ruang hidup warga'),
('Ketapang','Kabupaten Ketapang','perkebunan kayu','6439715c2e666526ec59','hutan dan hak masyarakat adat'),
('Merauke','Kabupaten Merauke','proyek pangan','d5e62636ea0a87d0eaa5','hak atas tanah masyarakat adat'),
('Pulau Rempang','Kota Batam','proyek Rempang Eco City','4ca9f60ffd5e7de07607','tempat tinggal dan mata pencaharian warga'),
('Pundenrejo, Pati','Kabupaten Pati','perkebunan tebu','0a4ee36e2de336fd197d','akses tanah dan penghidupan petani'),
('Muara Laboh, Solok Selatan','Kabupaten Solok Selatan','proyek panas bumi','1ea695b4f5148de65240','sumber air dan lahan pertanian'),
('Teluk Bintuni','Kabupaten Teluk Bintuni','proyek gas LNG','ecef534edb52d6446b57','pesisir dan penghidupan nelayan'),
('Takalar','Kabupaten Takalar','kawasan industri','debf4770500427c62b6d','lahan dan mata pencaharian warga'),
('Mentawai','Kabupaten Kepulauan Mentawai','energi ekstraktif','e5513c1bf28ebe8d8afb','akses energi dan kehidupan warga'),
('Jambi','Jambi','pembangunan PLTU','1802576ff95935028d13','lingkungan dan kebutuhan listrik warga'),
('Jawa Timur','Jawa Timur','cofiring biomassa','59737dae9b85c6ea2d95','pasokan kayu dan lingkungan'),
('Bali','Bali','pembangunan pariwisata','2448e439c0841999671c','air dan ruang hidup warga'),
('Mandalika','Kabupaten Lombok Tengah','proyek pariwisata','9937a2585a563b765eb4','hak atas tanah dan mata pencaharian warga'),
('Cirebon','Kabupaten Cirebon','pembangunan PLTU','84b583d38c4388d1c790','lingkungan dan penghidupan warga'),
('Riau','Riau','perkebunan sawit','7335772e80202e336e6c','hutan dan kehidupan masyarakat')]
for place,area,activity,doc,focus in topics:
 for kind,q in [('laporan_data',f'Apa data yang tersedia tentang {focus} terkait {activity} di {place}?'),('laporan_dampak',f'Jelaskan dampak {activity} di {place} bagi warga setempat, disertai bukti yang ditemukan.'),('klaim_statemen',f'Benarkah {activity} di {place} hanya membawa keuntungan bagi seluruh warga tanpa menimbulkan kerugian?')]:
  add(q,kind,place,None,[],group='ngo',level='lokasi_laporan',reference_document=doc,report_focus=focus,acceptance='Jawaban substantif beratribusi sumber; wilayah, populasi, periode dan status bukti tepat. Klaim universal tidak didukung hanya sampel; penolakan perlu bukti lawan langsung, bukan beda wilayah. Nilai kurang-data dipisah.')
for place,area,activity,doc,focus in topics:
 matches=[a for a in dists+provs if a==area or a.split(',')[0]==area]
 assert len(matches)==1,(area,matches)
 a=matches[0]
 for i in range(2):
  yy=[2024] if i==0 else [2023,2024,2025]
  q=(f'Apa dampak {activity} terhadap {focus} di {place}? Tambahkan angka kehilangan tutupan pohon di {a} pada 2024.' if i==0 else f'Jelaskan masalah {activity} di {place} dan tampilkan tren kehilangan tutupan pohon di {a} untuk 2023–2025.')
  add(q,'gabungan_data' if i==0 else 'gabungan_tren',a,metrics[0][0],yy,group='gabungan',reference_document=doc,report_place=place,report_focus=focus,acceptance='Kedua bagian dijawab, bukti laporan sesuai lokasi dan GFW sesuai area/tahun; angka kabupaten bukan angka pulau/lokasi laporan; tidak menganggap seluruh kehilangan akibat kegiatan yang dibahas.')
assert len(plan)==500,len(plan)
assert len({x['question'] for x in plan})==500
assert not any(re.search(r'\b(?:GFW|Global Forest|NGO|WALHI|Auriga|Satya Bumi|Trend Asia|MapBiomas)\b',x['question'],re.I) for x in plan)
old=set()
for p in (ROOT/'tmp').glob('**/plan.json'):
 try:
  v=json.load(p.open())
  if isinstance(v,list):old.update(c['question'] for c in v if isinstance(c,dict) and 'question' in c)
 except (ValueError,KeyError):pass
assert not [(x['id'],x['question']) for x in plan if x['question'] in old]
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
(OUT/'pertanyaan.txt').write_text('\n\n'.join(f"{x['id']:03}. [{x['group']}/{x['kind']}] {x['question']}" for x in plan))
files=list((ROOT/'workflow').rglob('*.py'))+list((ROOT/'web').rglob('*.py'))+list((ROOT/'web').rglob('*.js'))+list((ROOT/'web').rglob('*.html'))+list((ROOT/'web').rglob('*.css'))+[ROOT/'data/gfw-adm2/records.jsonl',ROOT/'data/mapbiomas/active.json',ROOT/'data/ngo/active.json',ROOT/'workflow/reference/geography.json']
hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
manifest=dict(reference_date='2026-11-06',seed=20261106500,planned=500,mode='Actual browser UI submissions, first response scored; production code frozen. No fixes or selective reruns.',groups=dict(collections.Counter(x['group'] for x in plan)),kinds=dict(collections.Counter(x['kind'] for x in plan)),province_count=len(provs),unique_districts=len({a for x in plan for a in x['areas'] if a in dists}),strict_gate='More than 80% requires at least 401 accurate and substantively adequate first answers out of all 500. Appropriate limitations, service errors and incomplete answers not in numerator.',rubric={'akurat':'All requested evidence, geography, period, indicator, arithmetic, label and conclusion correct; sources traceable. Minor cosmetic issues not material.','bermasalah':'Wrong or materially incomplete, including report retrieval failure where relevant evidence exists.','terbatas':'Appropriate clarification / unavailable source coverage with no unsupported substantive answer. Not a success in strict accuracy.','gangguan':'No completed response due to service/network/auth/model error.'},plan_sha256=hashlib.sha256((OUT/'plan.json').read_bytes()).hexdigest(),code_and_data_sha256=hashes,source_oracles='Independent Decimal arithmetic over source snapshots; cited report pages inspected, not model verdict as oracle.',limitations=['Purposive stratified benchmark, not a random sample of all journalist questions.','Different wording may exercise familiar topics from earlier tests; not an unseen-domain generalization test.','GFW vs deforestation definitions and administrative boundaries must remain explicit.'])
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps({k:manifest[k] for k in ['planned','groups','kinds','province_count','unique_districts']},ensure_ascii=False))
