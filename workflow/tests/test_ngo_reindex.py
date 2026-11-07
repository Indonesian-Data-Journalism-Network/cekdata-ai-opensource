import sys,unittest,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ngo_metadata import Gazetteer,metadata,explicit_places,document_metadata,SCHEMA
from ngo_reindex import prepare_document,child_spans,parent_spans,contextual_embedding

class Tokenizer:
 def encode(self,text):
  class Enc:pass
  e=Enc();e.ids=list(range(len(text.split())+2));return e

class ReindexTests(unittest.TestCase):
 def page(self,text,number=1):return {'pdf_page':number,'page_side':'full','printed_page':str(number),'text':text,'status':'readable'}
 def gaz(self):return Gazetteer([{'name':'Seram','kind':'island','id':None,'aliases':['Seram'],'parent_id':None,'parent_name':None,'reference':'test'},
                                 {'name':'Riau','kind':'province','id':'IDN.24_1','aliases':['Riau'],'parent_id':'IDN','parent_name':'Indonesia','reference':'test'},
                                 {'name':'Maluku','kind':'province','id':'IDN.19_1','aliases':['Maluku'],'parent_id':'IDN','parent_name':'Indonesia','reference':'test'}])
 def doc(self):return {'id':'a'*20,'sha256':'b'*64,'provider':'walhi','host_organization':'WALHI','title':'Kajian','source_url':'https://walhi.or.id/report','download_url':'https://walhi.or.id/a.pdf','publication_year_listed':2026}
 def test_direct_geography_does_not_leak_from_distant_parts(self):
  page=self.page('Penelitian dilakukan di Pulau Seram. '+('Masyarakat menjelaskan kondisi sumber penghidupan dan akses air. '*40)+'Contoh lain terjadi di Riau.')
  doc,parents,points=prepare_document(self.doc(),[page],self.gaz(),Tokenizer())
  first=points[0]['payload'];last=points[-1]['payload']
  self.assertIn('seram',first['location_names']);self.assertNotIn('riau',first['location_names'])
  self.assertIn('riau',last['location_names']);self.assertNotIn('seram',last['location_names'])
  self.assertEqual(first['metadata']['locations'][0]['reference_parent_id'],None)
 def test_publication_is_not_observation_period(self):
  p=self.page('Hasil survei pada 2021 menunjukkan perubahan. Rencana kegiatan pada 2028 perlu diperiksa.')
  meta=metadata(p,0,len(p['text']),self.gaz());d=document_metadata(self.doc(),[p])
  self.assertIsNone(d['observation_period']);self.assertEqual(d['publication_year_listed'],2026)
  self.assertEqual([x['role'] for x in meta['periods']],['observation_year_candidate','projection_year'])
 def test_quantities_preserve_status_scale_population_and_quote(self):
  p=self.page('Rencana seluas sekitar 2,68 juta hektar di Pulau Seram. Sebanyak 54,1 persen rumah tangga melaporkan penurunan pendapatan. Kawasan seluas 3.204.567,54 hektar terancam.')
  meta=metadata(p,0,len(p['text']),self.gaz());q=meta['quantities']
  self.assertEqual(q[0]['value_text'],'2,68');self.assertEqual(q[0]['magnitude_text'],'juta')
  self.assertIn('projection',q[0]['status']);self.assertIn('estimate',q[0]['status'])
  self.assertEqual(q[1]['population_text'],'rumah tangga');self.assertIn('survey_response',q[1]['status'])
  self.assertEqual(q[2]['value_text'],'3.204.567,54');self.assertIn('threat_or_potential',q[2]['status'])
  for category in ('locations','quantities','periods','topics'):
   for item in meta[category]:
    e=item['evidence'];self.assertEqual(p['text'][e['start']:e['end']],e['quote'])
 def test_embedding_budget_keeps_entire_child_and_has_no_fabricated_hint(self):
  text='kata '*98;p=self.page('Pulau Seram.');context=metadata(p,0,len(p['text']),self.gaz())
  value=contextual_embedding(text,{'text':'Judul yang sangat panjang '*20},context,Tokenizer())
  self.assertTrue(value.endswith(text));self.assertLessEqual(len(Tokenizer().encode(value).ids),126)
 def test_all_nonwhitespace_text_is_covered_and_ids_are_deterministic(self):
  text='Hutan di Pulau Seram. '+('Masyarakat memiliki mata pencaharian lokal dan akses air bersih. '*220)+'AKHIR'
  p=self.page(text);a,parents,points=prepare_document(self.doc(),[p],self.gaz(),Tokenizer())
  _,_,again=prepare_document(self.doc(),[p],self.gaz(),Tokenizer())
  covered=set()
  for point in points:
   payload=point['payload'];self.assertEqual(payload['text'],text[payload['start']:payload['end']]);covered.update(range(payload['start'],payload['end']))
   self.assertLessEqual(len(Tokenizer().encode(point['embedding_text']).ids),126)
  self.assertTrue(all(i in covered for i,c in enumerate(text) if not c.isspace()))
  self.assertEqual([p['id'] for p in points],[p['id'] for p in again])
  self.assertEqual(parents[0]['next_parent_id'],parents[1]['parent_id'])
 def test_ambiguous_name_has_no_forced_administrative_assignment(self):
  gaz=self.gaz();gaz=Gazetteer(gaz.entries+[{'name':'Riau','kind':'island','id':None,'aliases':['Riau'],'reference':'test'}])
  p=self.page('Riau dibahas sebagai contoh.');m=metadata(p,0,len(p['text']),gaz)
  self.assertIsNone(m['locations'][0]['reference_id']);self.assertEqual(m['locations'][0]['resolution'],'unresolved_or_ambiguous')
 def test_unknown_authorship_is_not_hosting_organization(self):
  d=document_metadata(self.doc(),[self.page('Kajian lingkungan hidup nasional.')])
  self.assertIsNone(d['verified_authors']);self.assertEqual(d['source_independence'],'not_verified')
 def test_unreadable_parts_stay_in_inventory_without_searchable_claims(self):
  p=self.page('Gambar',2);p['status']='needs_ocr_or_visual_review'
  doc,parents,points=prepare_document(self.doc(),[self.page('Hutan di Pulau Seram.'),p],self.gaz(),Tokenizer())
  self.assertEqual(len(doc['unreadable_parts']),1);self.assertTrue(all(x['payload']['pdf_page']==1 for x in points))
 def test_type_and_subject_do_not_imply_enclosing_district(self):
  p=self.page('Survei di Desa Lelilef dan Kecamatan Wasile. Pulau Seram menjadi latar kajian.')
  m=metadata(p,0,len(p['text']),self.gaz())
  self.assertEqual({x['kind'] for x in m['locations']},{'village','subdistrict','island'})
  self.assertTrue(all(x['reference_parent_id'] is None for x in m['locations']))

if __name__=='__main__':unittest.main()

class RetrievalMetadataTests(unittest.TestCase):
 def test_unverified_common_words_do_not_become_query_geography(self):
  from ngo_retrieval import grounded_query_place
  q='Hak masyarakat adat di pulau seram'
  def hit(word,**fields):return {'name':word,'start':q.index(word),'recognition':'name_reference_match','reference_id':None,**fields}
  self.assertFalse(grounded_query_place(hit('adat'),q))
  self.assertTrue(grounded_query_place(hit('seram'),q))
  self.assertTrue(grounded_query_place(hit('adat',recognition='explicit_type'),q))
  self.assertTrue(grounded_query_place(hit('adat',reference_id='known'),q))
  q='Apa risiko bagi badak Jawa di kawasan konservasi?'
  self.assertFalse(grounded_query_place({'name':'Jawa','start':q.index('Jawa'),'recognition':'name_reference_match','reference_id':None},q))
 def test_source_diversity_does_not_force_an_unrelated_low_score_publisher(self):
  from ngo_retrieval import select_pages
  points=[{'sha256':'a','pdf_page':1,'page_side':'full','provider':'one','score':.9},
          {'sha256':'b','pdf_page':2,'page_side':'full','provider':'two','score':.82},
          {'sha256':'c','pdf_page':3,'page_side':'full','provider':'irrelevant','score':.4}]
  self.assertEqual({x['provider'] for x in select_pages(points)},{'one','two'})
 def test_local_scope_precedes_unrelated_publisher_diversity(self):
  from ngo_retrieval import select_pages
  points=[{'sha256':'a','pdf_page':1,'page_side':'full','provider':'national','score':.95,'scope_strength':0},
          {'sha256':'b','pdf_page':2,'page_side':'full','provider':'local-one','score':.90,'scope_strength':2},
          {'sha256':'c','pdf_page':3,'page_side':'full','provider':'local-two','score':.82,'scope_strength':1}]
  self.assertEqual({p['provider'] for p in select_pages(points)},{'local-one','local-two'})
 def test_indexed_scope_keeps_finer_geography_and_its_own_page(self):
  from ngo_retrieval import scope_evidence
  p=ReindexTests().page('Pulau Seram secara administrasi terbagi dalam Kabupaten A dan Kabupaten B.',14)
  meta=metadata(p,0,len(p['text']),ReindexTests().gaz())
  document={'parents':[{'parent_id':'parent','pdf_page':14,'page_side':'full','start':0,'text':p['text'],'metadata':meta}]}
  selected=scope_evidence(document,['seram'])
  self.assertEqual(selected[0]['pdf_page'],14)
  self.assertIn('Kabupaten A dan Kabupaten B',selected[0]['text'])
 def test_lexical_common_nouns_do_not_become_bare_place_tags(self):
  # Even a typed name learned elsewhere cannot label every lowercase noun.
  gaz=Gazetteer([{'name':'Tahun','kind':'village','id':None,'aliases':['Tahun'],'reference':'unverified'},
                 {'name':'Seram','kind':'island','id':None,'aliases':['Seram'],'reference':'unverified'}])
  p=ReindexTests().page('Pada tahun lalu penelitian dilaksanakan di Seram. Tahun berikutnya hasil dibahas.')
  self.assertEqual([x['name'] for x in gaz.mentions(p['text'],p)],['Seram'])
 def test_context_type_is_an_aid_not_an_inherited_fact(self):
  from ngo_answer import public_evidence
  p=ReindexTests().page('Rumah tangga melaporkan perubahan kondisi lingkungan akibat kegiatan industri di wilayah studi. Sebanyak 45,8 persen responden menyatakan produksi menurun.')
  p.update(evidence_id='D1',sha256='x',title='Studi',host_organization='NGO',page_text=p['text'],
           context_parents=[{'text':p['text']}],metadata={'locations':[]},context_metadata={'locations':[],'periods':[]},index_schema_version=SCHEMA)
  public=public_evidence([p],'Apa temuan studi?')
  self.assertEqual(public[0]['indexed_context']['chunk_locations'],[])
  self.assertIsNone(public[0]['indexed_context']['observation_period'])
  self.assertIn('bukan periode observasi',public[0]['indexed_context']['note'])

class EditionMetadataTests(unittest.TestCase):
 def test_only_language_marked_identical_filename_stems_group(self):
  from ngo_editions import edition_candidates
  docs=[{'id':'one','provider':'org','download_url':'https://example.org/ENG_11-Sept-2026_Laporan_Pembangunan.pdf'},
        {'id':'two','provider':'org','download_url':'https://example.org/IND_11-Sept-2026_Laporan_Pembangunan.pdf'},
        {'id':'third','provider':'org','download_url':'https://example.org/IND_11-Sept-2025_Laporan_Pembangunan.pdf'},
        {'id':'fourth','provider':'other','download_url':'https://example.org/ENG_11-Sept-2026_Laporan_Pembangunan.pdf'}]
  groups=edition_candidates(docs)
  self.assertEqual(len(groups),1)
  self.assertEqual({m['document_id'] for m in groups[0]['members']},{'one','two'})
  self.assertFalse(groups[0]['independent_corroboration'])
 def test_same_title_without_filename_evidence_does_not_prove_translation(self):
  from ngo_editions import edition_candidates
  self.assertEqual(edition_candidates([{'id':'a','provider':'org','title':'Studi','download_url':'https://example.org/a.pdf'},
                                      {'id':'b','provider':'org','title':'Studi','download_url':'https://example.org/b.pdf'}]),[])

class CompoundGeographyTests(unittest.TestCase):
 def test_unknown_compound_place_is_never_shortened_to_known_province(self):
  gaz=Gazetteer([{'name':'Papua','kind':'province','id':'IDN.23_1','aliases':['Papua'],'reference':'GADM old snapshot'}])
  p=ReindexTests().page('Penelitian dilakukan di Provinsi Papua Selatan dan Desa Telaga Besar.')
  found=gaz.mentions(p['text'],p)
  self.assertEqual(found[0]['name'],'Papua Selatan')
  self.assertIsNone(found[0]['reference_id'])
  self.assertEqual(found[1]['name'],'Telaga Besar')
 def test_gfw_unknown_new_administrative_scope_does_not_use_old_prefix(self):
  from ngo_gfw_context import plan
  from datetime import date
  catalog=[{'indicator_id':'family','member_ids':['gfw-tree-cover-loss'],'areas':['Papua','Indonesia'],'years':list(range(2021,2026))}]
  for question in ['Dampak tambang di Provinsi Papua Selatan 2021–2025','Dampak tambang di provinsi papua selatan pada 2025','Perkebunan sawit di Papua Selatan meningkatkan kesejahteraan masyarakat adat.']:
   self.assertIsNone(plan(question,catalog,date(2026,11,6)))
  self.assertEqual(plan('Dampak tambang di Provinsi Papua pada 2025',catalog,date(2026,11,6)).areas,['Papua'])
