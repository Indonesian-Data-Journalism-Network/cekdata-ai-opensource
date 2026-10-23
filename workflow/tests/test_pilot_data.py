import unittest
from pilot_data import convert, select_catalog
from flow import Evidence, observation_period

class PilotTests(unittest.TestCase):
    def record(self, **updates):
        m = dict(dataset_id='school',title='Jumlah murid menurut jenjang pendidikan',series_label='SD',
                 year=2024,area_name='Brebes',unit='orang',value='1234.50',source='BPS',period='',breakdown_value='')
        m.update(updates)
        return {'id':'original','metadata':m}

    def test_series_are_distinct_and_values_links_preserved(self):
        _, sd = convert(self.record(source_url='https://example.org/table',download_url='https://example.org/file'))
        _, smp = convert(self.record(series_label='SMP'))
        self.assertNotEqual(sd['indicator_id'],smp['indicator_id'])
        self.assertEqual(sd['value'],'1234.50')
        self.assertEqual(sd['source_url'],'https://example.org/table')
        self.assertEqual(sd['download_url'],'https://example.org/file')
        self.assertEqual(sd['population'],'total')
        self.assertTrue(sd['usable'])

    def test_invalid_originals_retained_without_inventing_evidence(self):
        for changes in [dict(year=0),dict(area_name='93,21'),dict(value='NaN')]:
            r=self.record(**changes);_, p=convert(r)
            self.assertFalse(p['usable'])
            self.assertEqual(p['original_metadata'],r['metadata'])
        _,p=convert(self.record())
        self.assertEqual(p['source_url'],'')

    def test_period_text_retained(self):
        _,p=convert(self.record(period='akhir tahun'))
        self.assertEqual(observation_period(Evidence.model_validate(p)),'akhir tahun 2024')

    def test_catalog_prefers_concept_and_category(self):
        entries=[]
        for s in ['SD','SMP','SMK']:
            _,p=convert(self.record(series_label=s))
            entries.append(dict(indicator_id=p['indicator_id'],label=p['indicator'],areas=['Brebes']))
        chosen=select_catalog('Berapa jumlah murid SMK di Brebes?',entries,limit=1)
        self.assertTrue(chosen[0]['label'].endswith('SMK'))
        self.assertEqual(select_catalog('Berapa suhu laut?',entries),[])


class TemporalGuardTests(unittest.TestCase):
    def test_year_request_does_not_inherit_reference_month(self):
        from flow import Intent, guard_current_year_month
        intent=Intent(kind='claim',temporal='this_year',month=10)
        guard_current_year_month(intent,'Benarkah kemiskinan Aceh turun tahun ini?')
        self.assertIsNone(intent.month)

    def test_explicit_month_is_retained(self):
        from flow import Intent, guard_current_year_month
        for question in ['Kemiskinan Aceh Oktober tahun ini?', 'Kemiskinan Aceh bulan ini?']:
            intent=Intent(kind='lookup',temporal='this_year',month=10)
            guard_current_year_month(intent,question)
            self.assertEqual(intent.month,10)

if __name__=='__main__':unittest.main()
