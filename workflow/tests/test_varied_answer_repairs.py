"""Regressions from live varied-question audit; synthetic places and figures."""
import json
import unittest
from datetime import date
from unittest.mock import patch

from flow import (Intent, Predicate, RequestState, Analysis, assess, render,
                  guard_claim_kind, guard_temporal_scope)
from test_flow import row
from ngo_answer import Finding, DocumentAnswer, supported_findings
from ngo_evidence_policy import evidence_rows, sentence_support_valid, FindingFit
from ngo_combined import fallback_summary, summary_errors
from pilot_data import PilotAI, IndicatorSelection


class NumericRepairTests(unittest.TestCase):
    def result(self,question,intent,records):
        guard_claim_kind(intent,question);guard_temporal_scope(intent,question)
        state=RequestState(question=question,reference_date=date(2026,11,6),intent=intent,records=records)
        state.assessment=assess(state)
        return render(state,Analysis())

    def test_lower_than_prior_year_is_change_not_value_below_zero(self):
        q='Benarkah kehilangan di Wilayah Contoh pada 2025 lebih rendah dibandingkan 2024?'
        i=Intent(kind='claim',indicator_ids=['employment'],areas=['Wilayah Contoh'],year=2025,
                 predicate=Predicate(metric='value',operator='lt',threshold='0',unit='ha'))
        result=self.result(q,i,[row('a',2024,100,area='Wilayah Contoh',unit='ha'),row('b',2025,200,area='Wilayah Contoh',unit='ha')])
        self.assertEqual(result['verdict'],'Salah')
        self.assertIn('100 ha',result['reason']);self.assertIn('200 ha',result['reason'])
        self.assertNotIn('kurang dari 0',result['reason'])
        self.assertEqual(i.predicate.metric,'change')

    def test_single_year_scope_comparison_always_answers_requested_difference(self):
        q='Bandingkan luas di Wilayah Satu dan Wilayah Dua pada 2024. Berapa selisihnya?'
        i=Intent(kind='lookup',indicator_ids=['employment'],areas=['Wilayah Satu','Wilayah Dua'],year=2024,
                 requires_series=True,baseline_year=2023)
        result=self.result(q,i,[row('a',2024,'20.25',area='Wilayah Satu',unit='ha'),row('b',2024,'50.75',area='Wilayah Dua',unit='ha')])
        self.assertIn('30,50 ha',result['parsed']['kesimpulan'])
        self.assertEqual(len(result['evidence']),2)

    def test_explicit_noncontiguous_list_does_not_expand_or_shift_window(self):
        q='Berapa luas masing-masing tahun 2019, 2021, dan 2024?'
        i=Intent(kind='lookup',indicator_ids=['employment'],areas=['Indonesia'],year=2019,requires_series=True,trend_years=3)
        records=[row(str(y),y,y,month=None) for y in range(2017,2025)]
        result=self.result(q,i,records)
        self.assertEqual([r['year'] for r in result['evidence']],[2019,2021,2024])
        self.assertFalse(result['gaps'])
        self.assertNotIn('nilai akhir dikurangi',result['parsed']['konteks_penting'])

    def test_cross_source_aggregates_do_not_establish_entire_area_conversion(self):
        q='Apakah seluruh kehilangan tutupan pohon berubah menjadi kebun?'
        i=Intent(kind='claim',indicator_ids=['loss','conversion'],areas=['Indonesia'],causal=True,
                 temporal='explicit',year=2024)
        records=[row('a',2024,100,indicator_id='loss',unit='ha',month=None,source='GFW',source_record_id='gfw:gadm__tcl__adm1_change:test'),
                 row('b',2024,20,indicator_id='conversion',unit='ha',month=None,source='MapBiomas',source_record_id='mapbiomas:test',aggregation_kind='annual_flow')]
        state=RequestState(question=q,reference_date=date(2026,11,6),intent=i,records=records)
        state.assessment=assess(state)
        result=render(state,Analysis())
        self.assertEqual(result['verdict'],'Tidak dapat diverifikasi')
        self.assertIn('pencocokan lokasi',result['reason'])
        self.assertNotIn('tidak tersedia',result['reason'])
        self.assertNotIn('program',result['parsed']['konteks_penting'])

    def test_universal_proposition_stays_a_claim_despite_following_comparison_request(self):
        i=Intent(kind='trend',areas=['Riau'])
        guard_claim_kind(i,'Apakah seluruh kehilangan pohon berubah menjadi kebun? Bandingkan kedua sumber.')
        self.assertEqual(i.kind,'claim')


class PublisherSelectionTests(unittest.IsolatedAsyncioTestCase):
    def test_direction_rank_is_applied_before_shortlist_truncation(self):
        from environment_data import prioritize
        choices=[{'indicator_id':'reverse','member_ids':['mapbiomas-annual-transition-palm-to-forest'],
                  'label':'Luas transisi sawit menjadi hutan tahunan'},
                 {'indicator_id':'forward','member_ids':['mapbiomas-annual-transition-forest-to-palm'],
                  'label':'Luas transisi hutan menjadi sawit tahunan'}]
        self.assertEqual(prioritize(choices,'Konversi hutan menjadi sawit selama 2021–2024')[0]['indicator_id'],'forward')

    async def test_explicit_publishers_receive_independent_catalog_matching(self):
        catalog=[{'indicator_id':f'gfw-{n}','member_ids':[f'gfw-{n}'],'source':'Global Forest Watch / UMD GLAD',
                  'label':'Kehilangan tutupan pohon','areas':['Riau'],'years':[2024],'populations':['total'],'units':['ha']} for n in range(90)]
        catalog.append({'indicator_id':'mapbiomas-annual-transition-forest-to-oil-palm',
            'member_ids':['mapbiomas-annual-transition-forest-to-oil-palm'],'source':'MapBiomas Indonesia',
            'label':'Transisi hutan menjadi sawit tahunan','areas':['Riau'],'years':[2024],'populations':['total'],'units':['ha']})
        calls=[]
        class Model:
            async def astructured_predict(self,schema,prompt,**kwargs):
                if issubclass(schema,Intent):return Intent(kind='claim',areas=['Riau'],indicator_terms=['kehilangan tutupan pohon','konversi hutan menjadi sawit'])
                rows=json.loads(kwargs['catalog']);calls.append(rows)
                return IndicatorSelection(indicator_ids=[rows[0]['indicator_id']])
        ai=PilotAI(Model(),catalog)
        result=await ai.understand('Bandingkan kehilangan tutupan pohon GFW dan konversi hutan menjadi sawit MapBiomas di Riau.',date(2026,11,6),[])
        self.assertEqual(len(calls),2)
        self.assertTrue(all(len({c['source'] for c in group})==1 for group in calls))
        self.assertIn('mapbiomas-annual-transition-forest-to-oil-palm',result.indicator_ids)
        self.assertEqual(len(result.indicator_ids),2)


class ReportScopeRepairTests(unittest.TestCase):
    def fit(self,ids):
        return FindingFit(finding_id='F1',faithful=True,same_event=True,measure_supported=True,geography='same',activity='same',
                          relation='context_only',outcome_basis='reported_change',explanation='Source.',supporting_sentence_ids=ids)

    def test_caption_cannot_narrow_a_regional_number_to_one_village(self):
        f=Finding(text='Nelayan di Desa Mawar membutuhkan 20 liter bahan bakar.',evidence_id='D1')
        quote='Foto nelayan di Desa Mawar. Nelayan di Pulau Anggrek membutuhkan 20 liter bahan bakar.'
        rows=evidence_rows([f],lambda fs:[{'support_quote':quote}])
        self.assertFalse(sentence_support_valid(f,rows[0],self.fit(['S1','S2'])))
        f.text='Nelayan di Pulau Anggrek membutuhkan 20 liter bahan bakar.'
        self.assertTrue(sentence_support_valid(f,rows[0],self.fit(['S2'])))
        self.assertFalse(sentence_support_valid(f,rows[0],self.fit(['S999'])))

    def test_metadata_place_is_not_proof_for_a_different_original_passage(self):
        quote='Nelayan di Pulau Anggrek membutuhkan 20 liter bahan bakar untuk mencari ikan lebih jauh.'
        p={'evidence_id':'D1','title':'Laporan Desa Mawar','page_text':quote+' '+quote,
           'scope_context':'Laporan juga menyebut Desa Mawar.'}
        f=Finding(text='Nelayan di Desa Mawar membutuhkan 20 liter bahan bakar untuk mencari ikan lebih jauh.',
                  evidence_id='D1',support_quote=quote)
        self.assertFalse(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))

    def test_photo_name_is_not_the_scope_of_next_numbered_prose_block(self):
        f=Finding(text='Nelayan di Desa Mawar berhenti menjadi nelayan dan beralih menjadi kuli bangunan.',evidence_id='D1')
        page='Gambar 1. Nelayan di Desa Mawar mencari ikan.\nb. Beberapa Bajau berhenti menjadi nelayan dan beralih menjadi kuli bangunan.'
        rows=evidence_rows([f],lambda fs:[{'support_quote':page,'page_text':page}])
        self.assertFalse(sentence_support_valid(f,rows[0],self.fit([s['sentence_id'] for s in rows[0]['source_sentences']])))

    def test_multi_location_numeric_range_cannot_become_one_village_range(self):
        quote='Nickel concentrations in seawater from Mawar, Melati, and Anggrek ranged from 3.1 to 3.5 mg/L.'
        f=Finding(text='Konsentrasi nikel di Mawar mencapai 3,1 hingga 3,5 mg/L.',evidence_id='D1')
        rows=evidence_rows([f],lambda fs:[{'support_quote':quote}])
        self.assertFalse(sentence_support_valid(f,rows[0],self.fit(['S1'])))
        f.text='Konsentrasi nikel di Mawar, Melati, dan Anggrek mencapai 3,1 hingga 3,5 mg/L.'
        self.assertTrue(sentence_support_valid(f,rows[0],self.fit(['S1'])))

    def test_superlative_keeps_original_comparison_sector(self):
        quote='Pembukaan ini merupakan deforestasi terbesar yang dilakukan perkebunan kayu dalam satu dekade terakhir di Indonesia.'
        p={'evidence_id':'D1','title':'Laporan lingkungan','page_text':quote+' '+quote}
        f=Finding(text='Pembukaan ini merupakan deforestasi terbesar dalam satu dekade terakhir di Indonesia.',evidence_id='D1',support_quote=quote)
        self.assertFalse(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))
        f.text=quote
        self.assertTrue(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p]))

    def test_fallback_and_review_require_income_before_and_after(self):
        fs=[Finding(text='Sebelum kegiatan, pendapatan nelayan mencapai Rp600.000 sekali melaut.',evidence_id='D1'),
            Finding(text='Setelah kegiatan, pendapatan menjadi Rp150.000 sekali melaut.',evidence_id='D1')]
        q='Bagaimana dampaknya terhadap pendapatan nelayan?'
        text=fallback_summary(fs,{'D1':{'host_organization':'Organisasi Contoh'}},q)
        self.assertIn('Rp600.000',text);self.assertIn('Rp150.000',text)
        self.assertFalse(summary_errors(text,fs,{},q))
        self.assertTrue(summary_errors(fs[0].text,fs,{},q))

    def test_income_pair_is_not_displaced_by_a_generic_intro_or_implicit_income_wording(self):
        fs=[Finding(text='Kegiatan berdampak pada penghidupan masyarakat pesisir.',evidence_id='D1'),
            Finding(text='Sebelum kegiatan, pendapatan nelayan hingga Rp600.000 per melaut.',evidence_id='D1'),
            Finding(text='Setelah kegiatan, mereka hanya memperoleh sekitar Rp150.000 meski melaut lebih lama.',evidence_id='D1')]
        q='Apa dampaknya terhadap pendapatan nelayan?'
        text=fallback_summary(fs,{'D1':{'host_organization':'Organisasi Contoh'}},q)
        self.assertIn('Rp600.000',text);self.assertIn('Rp150.000',text)
        self.assertNotIn('berdampak pada penghidupan',text)
        self.assertTrue(summary_errors(fs[1].text,fs,{},q))

    def test_previous_original_page_is_supplied_as_context_not_a_new_quote(self):
        from ngo_answer import public_evidence
        p={'evidence_id':'D1','sha256':'x','document_id':'d','provider':'walhi','pdf_page':2,
           'title':'Laporan','page_text':'Air menjadi keruh dan hasil tangkapan berkurang. Warga melaporkan perubahan tersebut dalam wawancara.'}
        with patch('ngo_answer.source_pages',return_value=[{'pdf_page':1,'text':'Kegiatan ini terjadi di Pulau Anggrek.'}]):
            public=public_evidence([p],'Apa dampaknya?')
        self.assertIn('Pulau Anggrek',public[0]['preceding_page_context']['text'])
        self.assertNotIn('Pulau Anggrek',public[0]['passages'][0]['text'])

    def test_continued_page_preserves_subject_even_when_finding_omits_location(self):
        from ngo_answer import continuation_scope
        p={'title':'Policy Brief Energi','page_text':'Policy Brief\nikan ikut terpapar. Kondisi laut menjadi keruh dan hasil tangkapan menurun.',
           'preceding_page_context':{'pdf_page':1,'text':'Kegiatan di Pulau Anggrek telah mencemari pesisir. Sejumlah biota laut dan'}}
        scope=continuation_scope(p)
        self.assertEqual(scope['name'],'Anggrek')
        f=Finding(text='Kondisi laut menjadi keruh dan hasil tangkapan menurun.',evidence_id='D1')
        rows=evidence_rows([f],lambda fs:[{'support_quote':f.text,'continued_scope':scope}])
        self.assertFalse(sentence_support_valid(f,rows[0],self.fit(['S1'])))
        f.text='Di Pulau Anggrek, kondisi laut menjadi keruh dan hasil tangkapan menurun.'
        self.assertTrue(sentence_support_valid(f,rows[0],self.fit(['S1'])))

    def test_synthesis_preserves_regional_scope_next_to_quoted_numbers(self):
        f=Finding(text='Nelayan di sekitar Pulau Anggrek membutuhkan 20 liter bahan bakar.',evidence_id='D1')
        evidence={'reports':[{'title':'Laporan Pulau Anggrek','support_quote':f.text}]}
        self.assertTrue(summary_errors('Nelayan membutuhkan 20 liter bahan bakar di desa tersebut.',[f],evidence,'Apa dampak tambang bagi nelayan?'))
        self.assertFalse(summary_errors('Di Pulau Anggrek, nelayan membutuhkan 20 liter bahan bakar.',[f],evidence,'Apa dampak tambang bagi nelayan?'))

    def test_new_location_on_continued_page_replaces_previous_subject(self):
        from ngo_answer import continuation_scope
        p={'title':'Policy Brief Energi','page_text':'Policy Brief\nikan ikut terpapar. Di Desa Mawar, warga diwawancarai. Pendapatan nelayan mencapai Rp600.000.',
           'preceding_page_context':{'pdf_page':1,'text':'Kegiatan di Pulau Anggrek merusak lingkungan. Sejumlah biota laut dan'}}
        scope=continuation_scope(p)
        f=Finding(text='Pendapatan nelayan di Desa Mawar mencapai Rp600.000.',evidence_id='D1')
        rows=evidence_rows([f],lambda fs:[{'support_quote':'Pendapatan nelayan mencapai Rp600.000.','continued_scope':scope}])
        self.assertTrue(sentence_support_valid(f,rows[0],self.fit(['S1'])))

    def test_explicit_transition_parent_does_not_add_unrequested_component(self):
        from environment_data import prefer_requested_transitions
        selected=[{'source':'MapBiomas Indonesia','label':'Luas transisi hutan menjadi sawit tahunan'},
                  {'source':'MapBiomas Indonesia','label':'Luas transisi formasi hutan menjadi sawit tahunan'},
                  {'source':'Global Forest Watch / UMD GLAD','label':'Kehilangan tutupan pohon'}]
        filtered=prefer_requested_transitions(selected,'Bandingkan kehilangan pohon dan konversi hutan menjadi sawit.')
        self.assertEqual(filtered,[selected[0],selected[2]])
