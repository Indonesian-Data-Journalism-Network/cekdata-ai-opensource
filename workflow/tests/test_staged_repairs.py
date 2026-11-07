"""General regressions for mixed requests and report evidence; synthetic data."""
import unittest
from datetime import date
from flow import Intent,RequestState,assess,guard_temporal_scope,render,Analysis
from test_flow import row
from test_gfw_expansion import period_record
from ngo_source_facts import quantities
from ngo_numeric_claim import eligible,compare,NumberMatch
from ngo_answer import Finding
from ngo_gfw_context import plan


class StagedNumericTests(unittest.TestCase):
    def test_wrapped_place_names_and_numbered_sections_keep_source_scope(self):
        from ngo_answer import DocumentAnswer,public_evidence,supported_findings
        from ngo_source_facts import event_scope_valid
        text=('1.2.1 Proyek di Kabupaten Solok Selatan\n'
              'Proyek di Kabupaten Solok\nSelatan membuka sekitar 650 hektar hutan alam. '
              'Pelaksanaan kegiatan ini dilaporkan berlangsung selama lima bulan.\n'
              '1.2.2 Proyek di Provinsi Papua\n'
              'Rencana pembangunan di Provinsi Papua mencakup 2500 hektar hutan.')
        p={'evidence_id':'D1','sha256':'x','title':'Kajian','page_text':text}
        public=public_evidence([p],'Pembukaan hutan di Kabupaten Solok Selatan')
        w=next(w for w in public[0]['passages'] if '650' in w['text'])
        self.assertNotIn('2500',w['text'])
        f=Finding(text='Proyek di Kabupaten Solok Selatan membuka sekitar 650 hektar hutan alam.',evidence_id='D1',passage_id=w['passage_id'])
        self.assertEqual(len(supported_findings(DocumentAnswer(kind='question',answer='',findings=[f]),[p])),1)
        self.assertTrue(event_scope_valid('Dampak di Kabupaten Solok Selatan?',f.text,w['text'],text))

    def test_report_sample_count_true_false_and_unit_separation(self):
        source='Seluruh 23 sampel ikan dari Desa Contoh mengandung merkuri.'
        f=Finding(text=source,evidence_id='D1',validated_source_text=source)
        m=NumberMatch(report_content_only=True,all_components_covered=True,finding_id='F1',
                      claim_quantity='C1',source_quantity='Q1',same_measure=True,same_population=True,
                      same_place=True,same_time=True)
        for count,expected in [(23,'Benar'),(230,'Salah')]:
            q=f'Benarkah laporan menyebut seluruh {count} sampel ikan dari Desa Contoh mengandung merkuri?'
            self.assertTrue(eligible(q));self.assertEqual(compare(m,q,f),expected)
        self.assertIsNone(compare(m,'Laporan menyebut 23 orang.',f))
        self.assertEqual(quantities('2026 halaman 16'),[])

    def result(self,q,i,records):
        guard_temporal_scope(i,q)
        s=RequestState(question=q,reference_date=date(2026,11,6),intent=i,records=records)
        s.assessment=assess(s)
        return s,render(s,Analysis())

    def test_trend_retains_middle_years_and_endpoint_change(self):
        for q in ['Tampilkan tren 2018–2022 serta selisih awal dan akhir.',
                  'Tampilkan 2018, 2019, 2020, 2021, 2022. Apakah selalu naik dan berapa perubahan awal–akhir?']:
            i=Intent(kind='trend',indicator_ids=['employment'],areas=['Indonesia'],endpoint_difference=True)
            records=[row(str(y),y,v,month=None) for y,v in zip(range(2018,2023),[100,90,85,95,110])]
            s,r=self.result(q,i,records)
            self.assertEqual([x.year for x in s.assessment.primary],list(range(2018,2023)))
            self.assertFalse(s.assessment.gaps)
            self.assertIn('turun',r['parsed']['kesimpulan']);self.assertIn('naik',r['parsed']['kesimpulan'])
            self.assertTrue(any(c.kind=='endpoint' and c.value=='10' for c in s.assessment.calculations))
            self.assertTrue(any(c['value']=='10,00' for c in r['parsed']['findings_table']['calculations']))

    def test_missing_middle_year_is_flagged_even_with_endpoint_request(self):
        i=Intent(kind='trend',indicator_ids=['employment'],areas=['Indonesia'],endpoint_difference=True)
        s,_=self.result('Tren 2018–2022 dan selisihnya?',i,[row('a',2018,100),row('b',2022,120)])
        self.assertIn('trend_incomplete',s.assessment.gaps)

    def test_carbon_period_explanation_uses_both_total_and_mean(self):
        records=[period_record(id='total',indicator_id='total',aggregation_kind='period_total',value='50',unit='ton CO2e'),
                 period_record(id='mean',indicator_id='mean',value='2')]
        i=Intent(kind='explanation',indicator_ids=['total','mean'],areas=['Aceh'],year=2025)
        s,r=self.result('Periode 2001–2025 penyerap atau sumber emisi bersih? Jelaskan total dan rata-rata tahunannya.',i,records)
        self.assertFalse(s.assessment.gaps)
        self.assertIn('sumber emisi bersih',r['parsed']['kesimpulan'])
        self.assertIn('dibagi 25 tahun',r['parsed']['konteks_penting'])
        self.assertFalse(r['parsed']['peringatan_editorial'])
        s,_=self.result('Bagaimana tren karbon setiap tahun selama 2001–2025?',i,records)
        self.assertIn('trend_incomplete',s.assessment.gaps)

    def test_district_reference_needs_one_explicit_antecedent(self):
        catalog=[{'indicator_id':'loss','member_ids':['gfw-tree-cover-loss'],
                  'areas':['Kabupaten Mawar, Provinsi Contoh','Kabupaten Melati, Provinsi Contoh'],
                  'area_aliases':{},'years':[2021,2022,2023,2024,2025]}]
        q='Dampak tambang di Kabupaten Mawar? Sertakan data kehilangan tutupan pohon kabupaten ini 2021–2025.'
        self.assertEqual(plan(q,catalog,date(2026,11,6)).areas,['Kabupaten Mawar, Provinsi Contoh'])
        self.assertIsNone(plan(q.replace('di Kabupaten Mawar','di Kabupaten Mawar dan Kabupaten Melati'),catalog,date(2026,11,6)))
        self.assertIsNone(plan('Kehilangan tutupan pohon kabupaten ini 2021–2025?',catalog,date(2026,11,6)))
        self.assertIsNone(plan(q.replace('Mawar','Mawar Selatan'),catalog,date(2026,11,6)))
