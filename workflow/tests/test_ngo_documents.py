import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ngo_corpus import listing, article, allowed, chunks, extract
from ngo_answer import requested, source_filter, render, anchor_quote, attribute_to_report, complete_passage, DocumentAnswer, Finding

class GeneralDocumentFallbackTests(unittest.IsolatedAsyncioTestCase):
 async def test_workflow_uses_reports_when_no_numeric_concept_matches(self):
  from unittest.mock import patch,AsyncMock
  from flow import CekDataWorkflow,Intent
  import ngo_answer
  class AI:
   llm=object()
   async def understand(self,*args):return Intent(kind='claim',areas=['Pulau Contoh'],indicator_ids=[])
  class Retriever:pass
  result={'answer':'Jawaban dari laporan','parsed':{'document_answer':True}}
  callback=AsyncMock(return_value=result)
  catalog=[{'indicator_id':'family','member_ids':['gfw-example']}]
  with patch('importlib.reload',side_effect=lambda module:module),patch.object(ngo_answer,'active',return_value={'status':'published'}),patch.object(ngo_answer,'requested',return_value=False),patch.object(ngo_answer,'answer_question',callback):
   workflow=CekDataWorkflow(AI(),Retriever(),catalog)
   answer=await workflow.run(question='Apakah satwa di Pulau Contoh masih terancam?',reference_date='2026-11-06')
  self.assertTrue(answer['parsed']['document_answer'])
  callback.assert_awaited_once()

class DocumentTests(unittest.TestCase):
 def test_excludes_invisible_neighbour_page_text(self):
  import tempfile
  from pypdf import PdfWriter
  from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
  writer=PdfWriter();page=writer.add_blank_page(width=420,height=595)
  # A shifted media box is valid PDF and must not cause footer cropping to fail.
  page.mediabox.lower_left=(0,6);page.mediabox.upper_right=(420,601)
  font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
  stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf -600 500 Td (INVISIBLE_NEIGHBOUR) Tj ET BT /F1 12 Tf 20 400 Td (Visible report content belongs to this page.) Tj ET')
  page[NameObject('/Contents')]=writer._add_object(stream)
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'test.pdf';writer.write(path)
   text=extract(path)[0]['text']
  self.assertIn('Visible report content',text)
  self.assertNotIn('INVISIBLE_NEIGHBOUR',text)
 def test_allowlist(self):
  self.assertTrue(allowed('https://satyabumi.org/report.pdf'))
  for url in ('http://127.0.0.1:6333/','https://satyabumi.org.evil.com/a','https://x:s@satyabumi.org/a','https://walhi.or.id:99/a'):
   self.assertFalse(allowed(url))
 def test_auriga_links(self):
  html='<li date-publish="2026-07-15"><h2 class="title">Report</h2><a href="/report/download/test.pdf">Download</a></li>'
  reports,_,_=listing('auriga',html,'https://auriga.or.id/resources/report')
  self.assertEqual(reports[0]['source_url'],'https://auriga.or.id/resources/report')
  self.assertEqual(reports[0]['publication_year_listed'],2026)
 def test_article_bytes_dedup(self):
  html=b'<main><a href="/report.pdf">Download</a><a href="/report.pdf#page=1">Preview</a><a href="https://evil.test/x.pdf">Bad</a></main>'
  docs=article({'source_url':'https://satyabumi.org/report/','title':'Report','provider':'satyabumi'},html)
  self.assertEqual(len(docs),1);self.assertEqual(docs[0]['download_url'],'https://satyabumi.org/report.pdf')
 def test_no_sidebar_sources(self):
  html='<main><a href="/real.pdf">Unduh</a><footer><a href="/wrong.pdf">Other</a></footer></main>'
  docs=article({'source_url':'https://trendasia.org/report/','title':'Report','provider':'trendasia'},html)
  self.assertEqual([r['download_url'] for r in docs],['https://trendasia.org/real.pdf'])
 def test_stats_route(self):
  for q in ['Berapa kehilangan tutupan pohon akibat kebakaran di Aceh tahun 2025?','Bandingkan luas hutan Aceh dan Riau','Bagaimana neraca karbon hutan Indonesia?','Jelaskan laporan Global Forest Watch']:
   self.assertFalse(requested(q),q)
  for q in ['Apa temuan Auriga tentang Raja Ampat?','Apa dampak tambang nikel di Kabaena?','Ringkas laporan WALHI tentang food estate']:
   self.assertTrue(requested(q),q)
  self.assertEqual(source_filter('Bandingkan Auriga dan Satya Bumi'),['auriga','satyabumi'])
 def test_model_comment_about_missing_evidence_is_not_a_citable_finding(self):
  from ngo_answer import supported_findings
  p=self.evidence()[0]
  f=Finding(text='Tidak ada bukti dalam data ini yang secara spesifik menyebutkan dampak kegiatan tersebut.',
            evidence_id='D1',support_quote='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.')
  self.assertFalse(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))
 def test_general_document_fallback_preserves_explicit_statistical_sources(self):
  from types import SimpleNamespace
  from ngo_answer import fallback_requested
  missing=SimpleNamespace(indicator_ids=[],clarification='')
  self.assertTrue(fallback_requested('Apakah badak Jawa di Ujung Kulon masih terancam perburuan?',missing))
  self.assertTrue(fallback_requested('Berapa jumlah rumah tangga yang perlu direlokasi di Pulau Contoh?',missing))
  self.assertFalse(fallback_requested('Berapa luas sawit menurut MapBiomas?',missing))
  self.assertFalse(fallback_requested('Jelaskan laporan Global Forest Watch',missing))
  self.assertFalse(fallback_requested('Berapa luas hutan?',SimpleNamespace(indicator_ids=['available'],clarification='')))
 def test_passage_preserves_geography_before_numeric_sentence(self):
  from ngo_answer import public_evidence,supported_findings
  page='Di wilayah lain, seperti Satu, Dua, dan Tiga di Provinsi Contoh, pengembangan proyek diproyeksikan mengurangi pendapatan. Air dan tenaga kerja beralih dari pertanian ke konstruksi. Produktivitas pertanian menurun. Pada dua tahun pertama operasi, kerugian diperkirakan Rp1,1 triliun. Dampak ini perlu diteliti lebih lanjut.'
  p={**self.evidence()[0],'page_text':page}
  public=public_evidence([p],'Apa risiko ekonomi proyek?')
  passage=next(x for x in public[0]['passages'] if 'Rp1,1' in x['text'])
  self.assertIn('Provinsi Contoh',passage['context'])
  finding=Finding(text='Kerugian ekonomi diperkirakan Rp1,1 triliun dalam dua tahun pertama operasi.',evidence_id='D1',passage_id=passage['passage_id'])
  accepted=supported_findings(DocumentAnswer(kind='question',answer='',findings=[finding]),[p])
  self.assertEqual(len(accepted),1)
  self.assertIn('Provinsi Contoh',accepted[0].support_context)
 def test_narrative_routing_does_not_require_a_publisher_project_or_commodity_allowlist(self):
  for q in ['Apa dampak proyek Rempang Eco City terhadap tempat tinggal dan mata pencaharian warga?',
            'Bagaimana risiko proyek panas bumi terhadap air dan penghidupan warga di Solok Selatan?',
            'Apakah proyek LNG menimbulkan risiko bagi nelayan di Teluk Bintuni?',
            'Bagaimana konflik lahan memengaruhi kehidupan petani Pundenrejo?',
            'Pembangunan kawasan industri menyebabkan penggusuran masyarakat pesisir.']:
   self.assertTrue(requested(q),q)
  for q in ['Berapa luas hutan di Solok Selatan 2024 menurut MapBiomas?',
            'Berapa luas kehilangan tutupan pohon akibat kebakaran di Aceh?',
            'Bandingkan luas sawit di Aceh dan Riau pada 2024']:
   self.assertFalse(requested(q),q)
 def test_chunks_cover_end(self):
  text='Kalimantan memiliki hutan dan habitat orangutan. '*60+'AKHIR DOKUMEN'
  parts=list(chunks(text));self.assertLessEqual(max(map(len,parts)),360);self.assertTrue(parts[-1].endswith('AKHIR DOKUMEN'))
 def evidence(self):
  return [{'evidence_id':'D1','sha256':'aaa','document_id':'doc','title':'Laporan Kabaena','host_organization':'Satya Bumi','source_url':'https://satyabumi.org/report','download_url':'https://satyabumi.org/r.pdf','pdf_page':6,'printed_page':'10','page_side':'left','page_text':'Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena. Perubahan ini diamati dalam berbagai aspek kehidupan masyarakat dan dijelaskan dalam laporan.'}]
 def test_sources_dedup_and_page(self):
  f=Finding(text='Menurut laporan, mata pencaharian berubah.',evidence_id='D1',support_quote='perubahan mata pencaharian masyarakat di Kabaena.')
  r=render(DocumentAnswer(kind='question',answer='Ada perubahan.',findings=[f,f]),self.evidence(),'Apa temuan?')
  self.assertEqual(len(r['parsed']['source_items']),1)
  self.assertNotIn('Rujukan:',r['parsed']['temuan_data'])
  self.assertIn('[1]',r['parsed']['temuan_data'])
  self.assertIn('[1] Sumber:',r['answer'])
  self.assertIn('halaman PDF 6',r['answer'])
  self.assertEqual(r['parsed']['source_items'][0]['page_locators'],[{'pdf_page':6,'printed_page':'10','page_side':'left'}])
  self.assertIn('https://satyabumi.org/report',r['answer'])
  self.assertIn('https://satyabumi.org/r.pdf',r['answer'])
  self.assertIn('- Mata pencaharian berubah. [1]',r['answer'])
  self.assertNotIn('Menurut laporan,',r['answer'])
  self.assertNotIn('Penilaian:',r['answer'])
 def test_fabricated_quote_rejected(self):
  f=Finding(text='Tambang sukses.',evidence_id='D1',support_quote='Kalimat ini tidak ada di sumber laporan.')
  r=render(DocumentAnswer(kind='claim',answer='Benar',verdict='Benar',findings=[f]),self.evidence(),'Klaim')
  self.assertEqual(r['parsed']['penilaian'],'Tidak dapat diverifikasi');self.assertEqual(r['parsed']['source_items'],[])
 def test_missing_data_message_is_plain_and_not_repeated_for_claim(self):
  for kind in ('claim','question'):
   r=render(DocumentAnswer(kind=kind,answer='Perjelas judul laporan.',insufficient=True),[], 'Klaim uji')
   self.assertEqual(r['answer'].count('Belum cukup data untuk memberikan jawaban.'),1)
   self.assertNotIn('Perjelas',r['answer'])
   self.assertNotIn('Bukti laporan',r['answer'])
   self.assertEqual(r['parsed']['source_items'],[])
   if kind=='claim':
    self.assertEqual(r['parsed']['penilaian'],'Tidak dapat diverifikasi')
    self.assertEqual(r['parsed']['kesimpulan'],'')
 def test_report_reference_names_its_own_source_without_changing_attributed_actor(self):
  from ngo_answer import name_report_source
  for org in ('Auriga','Satya Bumi','WALHI','Trend Asia'):
   page={**self.evidence()[0],'host_organization':org}
   text='Laporan ini mencatat perubahan mata pencaharian. Peneliti lain menilai dampaknya.'
   self.assertEqual(name_report_source(text,[page]),f'Laporan {org} mencatat perubahan mata pencaharian. Peneliti lain menilai dampaknya.')
   self.assertEqual(name_report_source(f'Laporan {org} mencatat perubahan.',[page]),f'Laporan {org} mencatat perubahan.')
  self.assertEqual(name_report_source('Laporan menyebut perubahan.',[{'host_organization':'Auriga'},{'host_organization':'WALHI'}]),'Laporan menyebut perubahan.')
 def test_render_names_report_in_finding_summary_reason_and_context(self):
  f=Finding(text='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.',evidence_id='D1',support_quote='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.')
  r=render(DocumentAnswer(kind='claim',answer='Laporan ini menunjukkan perubahan mata pencaharian.',findings=[f],verdict='Sebagian benar',reason='Menurut laporan, mata pencaharian berubah.',context='Laporan tersebut membahas Kabaena.'),self.evidence(),'Klaim')
  self.assertIn('Laporan Satya Bumi mencatat',r['parsed']['temuan_data'])
  self.assertIn('Laporan Satya Bumi menunjukkan',r['parsed']['kesimpulan'])
  self.assertIn('Menurut laporan Satya Bumi,',r['parsed']['alasan'])
  self.assertNotIn('Laporan ini',r['answer'])
 def test_unverified_measure_label_cannot_relabel_a_market_share_as_environmental_damage(self):
  page='Indonesia menguasai pangsa pasar nikel global sekitar 27 persen. Aktivitas industri juga menimbulkan dampak lingkungan yang perlu diteliti dengan ukuran berbeda.'
  evidence=[{**self.evidence()[0],'page_text':page}]
  f=Finding(text='Indonesia menguasai pangsa pasar nikel global sekitar 27 persen.',measure='Dampak lingkungan pertambangan',evidence_id='D1',support_quote=page,measure_validated=False)
  result=render(DocumentAnswer(kind='question',answer='Pangsa pasar berbeda dengan ukuran dampak.',findings=[f]),evidence,'Apa temuan?')
  self.assertIn('27 persen',result['parsed']['temuan_data'])
  self.assertIsNone(result['parsed']['findings_table'])
 def test_finding_cannot_add_an_uncited_location(self):
  from ngo_answer import supported_findings
  p=self.evidence()[0]
  f=Finding(text='Laporan mencatat perubahan mata pencaharian di Bombana.',evidence_id='D1',support_quote='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.')
  self.assertEqual(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]),[])
 def test_passage_ids_preserve_reported_percentages_and_local_scope(self):
  from ngo_answer import public_evidence, supported_findings
  p={**self.evidence()[0],'page_text':'Masyarakat di Pulau Kabaena diwawancarai. Pertambangan berdampak pada kerusakan lingkungan. Sekitar 54,1% rumah tangga menyampaikan hal tersebut. Mata pencaharian masyarakat berkurang. Sekitar 42,7% rumah tangga menyampaikan dampak itu.'}
  public=public_evidence([p],'Apa dampak tambang di Bombana?')
  passage=next(x for x in public[0]['passages'] if '54,1%' in x['text'])
  f=Finding(text='Sebanyak 54,1% rumah tangga di Pulau Kabaena melaporkan kerusakan lingkungan.',evidence_id='D1',passage_id=passage['passage_id'])
  accepted=supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p])
  self.assertEqual(len(accepted),1)
  self.assertIn('54,1%',accepted[0].support_quote)
  f.text=f.text.replace('54,1','99,9')
  self.assertFalse(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))
  f.passage_id='UNKNOWN'
  self.assertFalse(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))
 def test_numeric_windows_do_not_crowd_out_distinct_measures(self):
  from ngo_answer import passages_for
  p={**self.evidence()[0],'page_text':'Masyarakat di Kabaena mengalami perubahan. '+ ' '.join(f'Dampak kegiatan pada ukuran {i} dilaporkan masyarakat. Sekitar {i},1% rumah tangga menyampaikan hal tersebut.' for i in range(41,46))}
  windows=passages_for(p,'Dampak kegiatan masyarakat Kabaena')
  text=' '.join(x['text'] for x in windows)
  for i in range(41,46):self.assertIn(f'{i},1%',text)
 def test_unknown_id_rejected(self):
  f=Finding(text='Temuan',evidence_id='D99',support_quote='perubahan mata pencaharian masyarakat di Kabaena.')
  r=render(DocumentAnswer(kind='question',answer='Ada perubahan.',findings=[f]),self.evidence(),'Tanya')
  self.assertEqual(r['parsed']['records_used'],[])
 def test_near_quote_anchors_to_actual_text_and_rejects_changed_numbers(self):
  page='Hasil penelitian mencatat bahwa masyarakat di wilayah pesisir menerima 50 hektare lahan setelah pengukuran dan verifikasi lapangan selesai.'
  almost=page.replace('pengukuran dan verifikasi','pengukuran & verifikasi')
  self.assertEqual(anchor_quote(almost,page),page.casefold())
  self.assertFalse(anchor_quote(almost.replace('50 hektare','80 hektare'),page))
  self.assertFalse(anchor_quote(almost.replace('menerima','tidak menerima'),page))
 def test_host_organisation_is_not_inferred_as_author(self):
  text='Trend Asia menemukan perubahan mata pencaharian.'
  self.assertEqual(attribute_to_report(text,{'provider':'trendasia'},'Hasil penelitian mencatat perubahan.'),
                   'laporan ini menemukan perubahan mata pencaharian.')
  self.assertEqual(attribute_to_report(text,{'provider':'trendasia'},'Trend Asia menemukan perubahan.'),text)
  self.assertEqual(attribute_to_report('Laporan Trend Asia mencatat perubahan.',{'provider':'trendasia'},'Hasil penelitian mencatat perubahan.'),'Laporan Trend Asia mencatat perubahan.')
 def test_exact_percent_is_not_an_estimate_merely_because_study_is_around_a_mine(self):
  from ngo_answer import finding_text
  self.assertEqual(finding_text('Sekitar 45,8% rumah tangga melaporkan penurunan produksi.','Sebanyak 45,8% rumah tangga di sekitar tambang melaporkan penurunan produksi.'),'Sebanyak 45,8 persen rumah tangga melaporkan penurunan produksi.')
  self.assertTrue(finding_text('Sekitar 45,8% rumah tangga melaporkan dampak.','Sekitar 45,8% rumah tangga melaporkan dampak.').startswith('Sekitar'))
 def test_fallback_extends_fragment_to_sentence_boundary(self):
  page='Abstract\nHutan tanaman energi merugikan warga dari segi ekonomi dan sosial. Laporan ini memaparkan temuan.'
  self.assertEqual(complete_passage({'page_text':page,'text':page[:38]}),
                   'Hutan tanaman energi merugikan warga dari segi ekonomi dan sosial.')
 def test_insufficient_without_findings_cannot_publish_unattributed_fact(self):
  r=render(DocumentAnswer(kind='claim',answer='Hutan hilang 999 ha.',verdict='Benar',insufficient=True),[],'Klaim')
  self.assertNotIn('999',r['answer'])
  self.assertEqual(r['parsed']['penilaian'],'Tidak dapat diverifikasi')

class DocumentRouteTests(unittest.IsolatedAsyncioTestCase):
 async def test_combined_claim_retains_all_four_verdict_labels(self):
  from unittest.mock import AsyncMock, patch
  from ngo_answer import answer_question, SearchPlan, EvidenceReview, AnswerSummary
  from ngo_evidence_policy import EvidenceFit,FindingFit,ClaimAssessment
  for verdict in ('Benar','Salah','Sebagian benar','Tidak dapat diverifikasi'):
   with self.subTest(verdict=verdict):
    p=DocumentTests().evidence()[0]
    f=Finding(text='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.',evidence_id='D1',support_quote='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.')
    class AI:pass
    fit=FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=True,outcome_basis='measured_change',geography='same',activity='same',relation='direct_contradiction' if verdict=='Salah' else 'direct_support',explanation='Cocok.',supporting_sentence_ids=['S1'])
    decision=ClaimAssessment(verdict=verdict,reason='Bukti yang relevan mendasari penilaian.',supporting_finding_ids=[] if verdict=='Salah' else ['F1'],contradicting_finding_ids=['F1'] if verdict=='Salah' else [],supported_components=['Isi laporan'],missing_components=['Cakupan'] if verdict=='Sebagian benar' else [],coverage='partial' if verdict=='Sebagian benar' else 'complete',causal_support='not_required',contradiction_explanation='Isi laporan bertentangan dengan klaim.' if verdict=='Salah' else '')
    ai=AI();ai.astructured_predict=AsyncMock(side_effect=[SearchPlan(queries=[]),DocumentAnswer(kind='claim',verdict=verdict,answer='Penjelasan laporan.',reason='Berdasarkan bukti.',findings=[f]),EvidenceFit(items=[fit]),decision,AnswerSummary(answer='Temuan menjelaskan perubahan mata pencaharian.',verdict=verdict,reason='Bukti yang relevan mendasari penilaian.'),EvidenceReview(supported=True)])
    gfw={'summary':'Data GFW tersedia.','table':{'headers':['Tahun','ha'],'rows':[['2025','1']],'calculations':[]},'context':'Wilayah kabupaten.','parsed':{'source_items':[],'download_records':[]}}
    with patch('ngo_answer.search',return_value=[p]):
     result=await answer_question(ai,'Benarkah laporan membahas perubahan masyarakat?', '2026-11-05',gfw)
    self.assertEqual(result['parsed']['penilaian'],verdict)
    self.assertIn('Penilaian: '+verdict,result['answer'])

 async def test_combined_answer_adds_only_reviewed_findings_from_other_reports(self):
  from unittest.mock import AsyncMock, patch
  from ngo_answer import answer_question, SearchPlan, EvidenceReview, AnswerSummary
  from ngo_evidence_policy import EvidenceFit,FindingFit
  first=DocumentTests().evidence()[0]
  first['page_text']+=' Penelitian di Kabaena, Kabupaten Bombana membahas perubahan masyarakat.'
  second={**first,'evidence_id':'D2','sha256':'bbb','document_id':'doc2',
          'title':'Laporan lain','host_organization':'WALHI','source_url':'https://walhi.or.id/report',
          'download_url':'https://walhi.or.id/report.pdf',
          'page_text':'Laporan mencatat perubahan kualitas air di wilayah pesisir Kabupaten Bombana. Informasi tersebut dijelaskan lebih lanjut dalam laporan.'}
  f1=Finding(text='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.',evidence_id='D1',support_quote='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.')
  f2=Finding(text='Laporan mencatat perubahan kualitas air di wilayah pesisir Kabupaten Bombana.',evidence_id='D2',support_quote='Laporan mencatat perubahan kualitas air di wilayah pesisir Kabupaten Bombana.')
  class AI:pass
  fits=EvidenceFit(items=[FindingFit(finding_id='F'+str(i),faithful=True,same_event=True,measure_supported=True,outcome_basis='not_outcome',geography='same',activity='same',relation='context_only',explanation='Cocok.',supporting_sentence_ids=['S1']) for i in (1,2)])
  ai=AI();ai.astructured_predict=AsyncMock(side_effect=[SearchPlan(queries=[]),DocumentAnswer(kind='question',answer='Ada temuan.',findings=[f1]),DocumentAnswer(kind='question',answer='Ada temuan.',findings=[f2]),fits,AnswerSummary(answer='Laporan Satya Bumi dan WALHI menunjukkan perubahan mata pencaharian dan kualitas air.',context='Cakupan tiap laporan berbeda.'),EvidenceReview(supported=True)])
  gfw={'summary':'Data GFW tersedia.','table':{'headers':['Tahun','ha'],'rows':[['2025','1']],'calculations':[]},'context':'Wilayah kabupaten.','parsed':{'source_items':[],'download_records':[]}}
  with patch('ngo_answer.search',return_value=[first,second]):
   result=await answer_question(ai,'Apa dampak nikel di Bombana?', '2026-11-05',gfw)
  self.assertEqual(len(result['parsed']['source_items']),2)
  self.assertIn('Kabaena',result['parsed']['temuan_data'])
  self.assertIn('kualitas air',result['parsed']['temuan_data'])
  self.assertEqual(result['parsed']['gfw_context'],gfw)

 async def test_grouped_environment_catalog_routes_document_questions(self):
  from unittest.mock import AsyncMock, patch
  from flow import CekDataWorkflow
  import ngo_answer
  class AI:
   llm=object()
   async def understand(self,*args):
    raise AssertionError('Document question reached the statistical workflow')
  expected={'answer':'Laporan ditemukan','parsed':{'document_answer':True}}
  engine=CekDataWorkflow(AI(),object(),[{'indicator_id':'grouped-hash','member_ids':['gfw-tree-cover-loss']}])
  with patch('importlib.reload',side_effect=lambda module:module), patch.object(ngo_answer,'active',return_value={'status':'published'}), patch.object(ngo_answer,'answer_question',new=AsyncMock(return_value=expected)):
   result=await engine.run(question='Apa temuan WALHI tentang food estate?',reference_date='2026-11-05')
  self.assertEqual(result,expected)

 async def test_answer_review_receives_only_cited_passages(self):
  import json
  from unittest.mock import AsyncMock, patch
  from ngo_answer import answer_question, SearchPlan, EvidenceReview
  evidence=DocumentTests().evidence()
  text='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.'
  finding=Finding(text='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.',evidence_id='D1',support_quote=text)
  response=DocumentAnswer(kind='question',answer='Laporan mencatat perubahan mata pencaharian.',findings=[finding])
  class AI: pass
  ai=AI();ai.astructured_predict=AsyncMock(side_effect=[SearchPlan(queries=[]),response,EvidenceReview(supported=True)])
  with patch('ngo_answer.search',return_value=evidence):
   result=await answer_question(ai,'Apa temuan laporan?', '2026-11-05')
  reviewed=json.loads(ai.astructured_predict.await_args_list[-1].kwargs['evidence'])
  self.assertEqual(reviewed[0]['support_quote'],text)
  self.assertNotIn('page_text',reviewed[0])
  self.assertEqual(result['parsed']['source_items'][0]['pdf_pages'],[6])

 async def test_explicit_claim_retains_verdict_when_model_misclassifies(self):
  from unittest.mock import AsyncMock, patch
  from ngo_answer import answer_question, SearchPlan, EvidenceReview, ClaimDecision
  evidence=DocumentTests().evidence()
  quote='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.'
  finding=Finding(text=quote,evidence_id='D1',support_quote=quote)
  response=DocumentAnswer(kind='question',answer=quote,findings=[finding])
  class AI: pass
  ai=AI();ai.astructured_predict=AsyncMock(side_effect=[SearchPlan(queries=[]),response,ClaimDecision(verdict='Benar',reason=quote),EvidenceReview(supported=True)])
  with patch('ngo_answer.search',return_value=evidence):
   result=await answer_question(ai,'Benarkah laporan mencatat perubahan mata pencaharian?', '2026-11-05')
  self.assertEqual(result['parsed']['penilaian'],'Benar')
  self.assertEqual(result['kind'],'claim')

 async def test_failed_model_quote_falls_back_to_verbatim_retrieved_passage(self):
  from unittest.mock import AsyncMock, patch
  from ngo_answer import answer_question, SearchPlan, EvidenceReview
  evidence=DocumentTests().evidence()
  passage='Laporan mencatat perubahan mata pencaharian masyarakat di Kabaena.'
  evidence[0]['text']=passage
  finding=Finding(text=passage,evidence_id='D1',support_quote='Ini bukan kutipan yang benar-benar ada.')
  response=DocumentAnswer(kind='question',answer=passage,findings=[finding])
  class AI: pass
  ai=AI();ai.astructured_predict=AsyncMock(side_effect=[SearchPlan(queries=[]),response,response.model_copy(deep=True),EvidenceReview(supported=True)])
  with patch('ngo_answer.search',return_value=evidence):
   result=await answer_question(ai,'Apa temuan laporan?', '2026-11-05')
  self.assertIn('Laporan Satya Bumi mencatat perubahan mata pencaharian masyarakat di Kabaena.',result['parsed']['temuan_data'])
  self.assertEqual(len(result['parsed']['source_items']),1)

if __name__=='__main__':unittest.main()
