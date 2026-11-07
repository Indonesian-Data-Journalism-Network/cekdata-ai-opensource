import sys,unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flow import Evidence,SearchBatch
from ngo_gfw_context import plan,retrieve
from ngo_answer import DocumentAnswer,Finding,render,requested

CATALOG=[{'indicator_id':'family','member_ids':['gfw-tree-cover-loss'],
          'areas':['Aceh','Kabupaten Bombana, Sulawesi Tenggara'], 'years':list(range(2021,2026))}]

class CombinedTests(unittest.IsolatedAsyncioTestCase):
 def test_a_claim_verb_after_a_known_administrative_name_is_not_part_of_its_name(self):
  query=plan('Pertambangan di Kabupaten Bombana membuat pendapatan warga meningkat.',CATALOG,date(2026,11,6))
  self.assertEqual(query.areas,['Kabupaten Bombana, Sulawesi Tenggara'])
 def test_no_substitution_of_island_with_district(self):
  self.assertIsNone(plan('Dampak nikel di Pulau Kabaena, Kabupaten Bombana',CATALOG,date(2026,11,5)))
  self.assertTrue(requested('Apa dampak nikel dan kehilangan tutupan pohon di Aceh?'))
  catalog=[{**CATALOG[0],'areas':['Aceh','Kabupaten Aceh Timur, Aceh'],
            'area_aliases':{'aceh timur':'Kabupaten Aceh Timur, Aceh'}}]
  self.assertEqual(plan('Dampak nikel di Aceh Timur pada 2021–2025',catalog,date(2026,11,5)).areas,
                   ['Kabupaten Aceh Timur, Aceh'])

 def test_geography_guard_uses_report_metadata_for_any_place(self):
  for place,kind in [('Seram','Pulau'),('Wasile','Kecamatan'),('Lelilef','Desa')]:
   with self.subTest(place=place):
    evidence=[{'title':f'Studi {kind} {place}','page_text':''}]
    self.assertIsNone(plan(f'Dampak tambang di {place}, Kabupaten Bombana',CATALOG,date(2026,11,5),evidence))
    query=plan(f'Dampak tambang di {place}? Sertakan data GFW di Kabupaten Bombana 2021–2025',CATALOG,date(2026,11,5),evidence)
    self.assertEqual(query.areas,['Kabupaten Bombana, Sulawesi Tenggara'])
    self.assertEqual(query.years,list(range(2021,2026)))
  self.assertIsNone(plan('Dampak tambang di Desa Lelilef di Kabupaten Bombana',CATALOG,date(2026,11,5)))
  self.assertEqual(plan('Dampak tambang di Kabupaten Bombana',CATALOG,date(2026,11,5),[{'title':'Studi Kecamatan Bombana'}]).areas,['Kabupaten Bombana, Sulawesi Tenggara'])

 async def test_complete_gfw_series_has_total_and_original_records(self):
  rows=[Evidence(id=str(y),indicator_id='family',indicator='Kehilangan tutupan pohon',area='Aceh',year=y,
                 value=str(v),unit='ha',source='Global Forest Watch',source_url='https://www.globalforestwatch.org/',source_record_id='gfw:'+str(y))
        for y,v in [(2021,1),(2022,2),(2023,3),(2024,4),(2025,5)]]
  class Retriever:pass
  r=Retriever();r.search=AsyncMock(return_value=SearchBatch(records=rows))
  result=await retrieve('Dampak pertambangan di Aceh 2021–2025',CATALOG,date(2026,11,5),r)
  self.assertEqual(len(result['table']['rows']),5)
  self.assertEqual(Decimal(result['table']['calculations'][0]['value'].replace('.','').replace(',','.')),Decimal(15))
  self.assertIn('naik setiap tahun',result['summary'])
  self.assertEqual(len(result['parsed']['download_records']),5)
  r.search.return_value=SearchBatch(records=rows[:-1])
  self.assertIsNone(await retrieve('Dampak pertambangan di Aceh 2021–2025',CATALOG,date(2026,11,5),r))

 def test_projected_and_threatened_quantities_cannot_be_reported_as_actual_conversion(self):
  from ngo_answer import preserves_quantity_status
  quote='Lokasi proyek dalam luasan sekitar 2,68 juta hektar diproyeksi berada di beberapa kabupaten.'
  self.assertFalse(preserves_quantity_status('Proyek mengkonversi hutan seluas 2,68 juta hektar.',quote))
  self.assertTrue(preserves_quantity_status('Proyek diproyeksikan seluas sekitar 2,68 juta hektar.',quote))
  quote='Proyek mengancam kawasan hutan seluas 3.204.567,54 hektar.'
  self.assertFalse(preserves_quantity_status('Proyek menghilangkan hutan seluas 3.204.567,54 hektar.',quote))
  self.assertTrue(preserves_quantity_status('Kawasan hutan seluas 3.204.567,54 hektar terancam proyek.',quote))

 def test_report_table_preserves_all_thousands_separators_and_magnitude(self):
  page='Proyek mengancam kawasan hutan seluas 3.204.567,54 hektar di Papua. Cakupan rencana adalah sekitar 2,68 juta hektar di Papua. Kedua ukuran memiliki cakupan berbeda dan tidak dijumlahkan.'
  p={'evidence_id':'D1','sha256':'x','document_id':'d','title':'Studi','host_organization':'Organisasi','source_url':'https://satyabumi.org/a','download_url':'https://satyabumi.org/a.pdf','pdf_page':1,'page_side':'full','page_text':page}
  findings=[Finding(text='Proyek mengancam kawasan hutan seluas 3.204.567,54 hektar di Papua.',evidence_id='D1',support_quote=page.split('. Cakupan')[0]+'.'),
            Finding(text='Cakupan rencana adalah sekitar 2,68 juta hektar di Papua.',evidence_id='D1',support_quote='Cakupan rencana adalah sekitar 2,68 juta hektar di Papua.')]
  result=render(DocumentAnswer(kind='question',answer='Ukuran rencana berbeda.',findings=findings),[p],'Apa cakupan rencana?')
  self.assertEqual([r[1] for r in result['parsed']['findings_table']['rows']],['3.204.567,54 hektar','Sekitar 2,68 juta hektar'])
  self.assertIn('sekitar 2,68 juta', result['answer'])

 def test_report_numeric_table_requires_numbers_in_supporting_quote(self):
  page='Hasil survei menunjukkan 54,1% rumah tangga menyatakan kerusakan lingkungan. Sebanyak 42,7% rumah tangga menyatakan berkurangnya mata pencaharian.'
  p={'evidence_id':'D1','sha256':'x','document_id':'d','title':'Studi','host_organization':'Organisasi','source_url':'https://satyabumi.org/a','download_url':'https://satyabumi.org/a.pdf','pdf_page':1,'page_side':'full','page_text':page}
  f1=Finding(text='Sebanyak 54,1% rumah tangga menyatakan kerusakan lingkungan.',evidence_id='D1',support_quote='Hasil survei menunjukkan 54,1% rumah tangga menyatakan kerusakan lingkungan.')
  f2=Finding(text='Sebanyak 42,7% rumah tangga melaporkan hilangnya mata pencaharian.',evidence_id='D1',support_quote='Sebanyak 42,7% rumah tangga menyatakan berkurangnya mata pencaharian.')
  result=render(DocumentAnswer(kind='question',answer='Dampak dilaporkan warga.',findings=[f1,f2]),[p],'Apa dampaknya?')
  self.assertEqual(len(result['parsed']['findings_table']['rows']),2)
  f2.text='Sebanyak 99,9% rumah tangga melaporkan hilangnya mata pencaharian.'
  result=render(DocumentAnswer(kind='question',answer='Dampak dilaporkan warga.',findings=[f1,f2]),[p],'Apa dampaknya?')
  self.assertIsNone(result['parsed']['findings_table'])

if __name__=='__main__':unittest.main()
