"""Build a reproducible, source-scoped reference; never rewrite observations."""
import csv
import hashlib
import json
import re
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workflow/reference'
PROVINCE_ALIASES={
 'Aceh':['NAD','Nanggroe Aceh Darussalam'], 'Sumatera Utara':['Sumut'],
 'Sumatera Barat':['Sumbar'], 'Sumatera Selatan':['Sumsel'],
 'Bangka Belitung':['Babel','Kepulauan Bangka Belitung','Kep. Bangka Belitung'],
 'Kepulauan Riau':['Kepri','Kep. Riau'], 'Jakarta Raya':['Jakarta','DKI Jakarta','DK Jakarta'],
 'Jawa Barat':['Jabar'], 'Jawa Tengah':['Jateng'], 'Jawa Timur':['Jatim'],
 'Yogyakarta':['DIY','DI Yogyakarta','D.I. Yogyakarta','Daerah Istimewa Yogyakarta','Jogja'],
 'Nusa Tenggara Barat':['NTB'], 'Nusa Tenggara Timur':['NTT'],
 'Kalimantan Barat':['Kalbar'], 'Kalimantan Tengah':['Kalteng'], 'Kalimantan Selatan':['Kalsel'],
 'Kalimantan Timur':['Kaltim'], 'Kalimantan Utara':['Kaltara'],
 'Sulawesi Utara':['Sulut'], 'Sulawesi Tengah':['Sulteng'], 'Sulawesi Selatan':['Sulsel'],
 'Sulawesi Tenggara':['Sultra'], 'Sulawesi Barat':['Sulbar'], 'Maluku Utara':['Malut'],
 'Papua Barat':['Pabar'], 'Papua Barat Daya':['PBD'],
}
KALTARA='https://jdih.kaltaraprov.go.id/'
GADM='https://gadm.org/download_country.html'
MAP='https://platform.indonesia.mapbiomas.org/'
# Explicit reviewed expansions only. No acronym guessing from initials.
EXPANSIONS={
 'Tanjung Jabung T':('Tanjung Jabung Timur',['Tanjabtim','Tanjab Timur'],'https://tanjabtimkab.go.id/'),
 'Tanjung Jabung B':('Tanjung Jabung Barat',['Tanjabbar','Tanjab Barat'],'https://tanjabbarkab.go.id/'),
}

def slug(s): return re.sub(r'[^a-z0-9]+','-',s.casefold()).strip('-')
def build():
 provinces=json.loads((ROOT/'data/gfw/raw/provinces.json').read_text())
 districts=json.loads((ROOT/'data/gfw-adm2/raw/districts.json').read_text())
 entries=[]
 def add(id,name,level,aliases=(),bindings=(),**kw):
  aliases=list(dict.fromkeys([name,*aliases]))
  aliases += [a.replace('Sumatera','Sumatra') for a in aliases if 'Sumatera' in a]
  e=dict(id=id,name=name,level=level,aliases=list(dict.fromkeys(aliases)),source_bindings=list(bindings),**kw);entries.append(e);return e
 add('idn','Indonesia','nasional',['nasional','seluruh Indonesia','Republik Indonesia'],
     [dict(provider='gfw',area='Indonesia',boundary_version='GADM 4.1',code='IDN'),dict(provider='mapbiomas',area='Indonesia',boundary_version='collection-4.1')],source_url=GADM)
 for p in provinces:
  n=p['name_1']; add('prov:'+slug(n),n,'provinsi',PROVINCE_ALIASES.get(n,[]),
   [dict(provider='gfw',area=n,code=p['gid_1'],boundary_version='GADM 4.1'),dict(provider='mapbiomas',area=n,boundary_version='collection-4.1')],parent_id='idn',source_url=GADM)
 for n in ['Papua Selatan','Papua Tengah','Papua Pegunungan','Papua Barat Daya']:
  add('prov:'+slug(n),n,'provinsi',PROVINCE_ALIASES.get(n,[]),[dict(provider='mapbiomas',area=n,boundary_version='collection-4.1')],parent_id='idn',source_url=MAP,note='Tidak dipetakan ke angka provinsi induk GFW sebelum pemekaran.')
 excluded=[]
 for d in districts:
  kind=d['type_2'];short=d['name_2'];original=short;url=GADM
  if kind=='Water Body':excluded.append(d);continue
  if kind=='NA':kind='Kota' if short=='Tarakan' else 'Kabupaten';url=KALTARA
  old_short=short if short.casefold().startswith(kind.casefold()+' ') else kind+' '+short
  bare=re.sub(r'^(Kabupaten|Kota)\s+','',short,flags=re.I)
  aliases=[]
  if bare in EXPANSIONS:
   bare,aliases,url=EXPANSIONS[bare]
  display=kind+' '+bare
  area=old_short+', '+d['name_1'] if d['type_2']!='NA' else original+', '+d['name_1']
  add('gadm41:'+d['gid_2'],display,kind.casefold(),[bare,old_short,area,*aliases],
   [dict(provider='gfw',area=area,code=d['gid_2'],boundary_version='GADM 4.1')],
   parent_id='prov:'+slug(d['name_1']),parent_scope='GADM 4.1; hubungan induk mengikuti batas sumber, bukan otomatis batas terkini',
   source_url=url,original_name=original)
 # Statistical groups are taken from the actual MapBiomas workbook, not guessed.
 from mapbiomas_data import xlsx_rows,island_area
 groups={}
 for _,row in xlsx_rows(ROOT/'data/mapbiomas/raw/landcover-4.1.xlsx','COVERAGE'):
  if row.get('B')=='Indonesia' and row.get('C') and row.get('D'):
   groups.setdefault(island_area(row['C']),set()).add(row['D'])
 from mapbiomas_data import PROVINCE_NAMES
 for name,members in sorted(groups.items()):
  aliases={'Sumatera':['Sumatra'], 'Bali & Nusa Tenggara':['Bali dan Nusa Tenggara'],
           'Wilayah Papua (6 provinsi)':['Tanah Papua','wilayah Papua','seluruh provinsi di Papua']}.get(name,[])
  add('group:'+slug(name),name,'kelompok_pulau',aliases,[dict(provider='mapbiomas',area=name,boundary_version='collection-4.1')],
      parent_id='idn',member_ids=['prov:'+slug(PROVINCE_NAMES.get(n,n)) for n in sorted(members)],source_url=MAP,
      note='Agregat provinsi sesuai workbook MapBiomas; tidak identik dengan batas fisik satu pulau.')
 for name,aliases in [('Sumatera',['Pulau Sumatra']),('Jawa',[]),('Kalimantan',[]),('Sulawesi',[]),('Papua',[]),('Bali',[]),('Madura',[]),('Lombok',[]),('Sumbawa',[]),('Sumba',[]),('Flores',[]),('Timor',[]),('Halmahera',[]),('Seram',[]),('Buru',[]),('Kabaena',[])]:
  add('island:'+slug(name),'Pulau '+name,'pulau',aliases,[],source_url=GADM,
      note='Pengenalan nama pulau fisik saja. Tidak dipetakan otomatis ke provinsi atau agregat provinsi; memerlukan cakupan spasial yang sesuai.')
 known={e['id'] for e in entries}
 for e in entries:
  assert all(i in known for i in e.get('member_ids',[])),e
 meta={'schema_version':1,'built_from':{},'scope':'Referensi operasional katalog lokal; bukan daftar lengkap 514 kabupaten/kota administratif terkini.',
       'alias_policy':'Singkatan umum adalah alias pencarian, bukan kode resmi. Alias ambigu tetap memiliki beberapa kandidat.',
       'counts':dict(Counter(e['level'] for e in entries)),'excluded_water_bodies':len(excluded),'entries':entries}
 for f in ['data/gfw/raw/provinces.json','data/gfw-adm2/raw/districts.json','data/mapbiomas/raw/landcover-4.1.xlsx']:
  meta['built_from'][f]=hashlib.sha256((ROOT/f).read_bytes()).hexdigest()
 OUT.mkdir(exist_ok=True)
 (OUT/'geography.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
 with (OUT/'geography.tsv').open('w') as f:
  w=csv.writer(f,delimiter='\t');w.writerow(['ID','Nama','Tingkat','Induk','Cakupan induk','Alias','Pemetaan sumber','Sumber','Catatan'])
  for e in entries:w.writerow([e['id'],e['name'],e['level'],e.get('parent_id',''),e.get('parent_scope',''),'; '.join(e['aliases']),json.dumps(e['source_bindings'],ensure_ascii=False),e['source_url'],e.get('note','')])
 print(meta['counts'])
if __name__=='__main__':build()
