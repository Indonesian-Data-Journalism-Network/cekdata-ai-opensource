import unittest
from unittest.mock import patch
from datetime import date
from decimal import Decimal
from flow import Evidence, Intent, RequestState, SearchQuery, assess, observation_period, guard_temporal_scope, render, Analysis
from gfw_expansion import query, normalize, TREE_TYPES, validate


def period_record(**updates):
    values=dict(id='period',indicator_id='net',indicator='Rata-rata neraca karbon periode 2001–2025',
                area='Aceh',year=2025,value='-2',unit='ton CO2e/tahun',source='GFW',
                temporal_basis='model_period',aggregation_kind='period_mean',
                period_start='2001-01-01',period_end='2025-12-31',period_text='2001–2025 (rata-rata tahunan)',
                source_record_id='gfw:carbonflux_adm1_summary:v20260327:IDN:1.None:2025:t30:carbon-net-flux-period-mean')
    return Evidence(**{**values,**updates})


class ExpansionTests(unittest.TestCase):
    def test_full_carbon_period_fits_bounded_query(self):
        self.assertEqual(len(SearchQuery(text='karbon',years=list(range(2001,2026))).years),25)
        self.assertEqual(Intent(kind='trend',trend_years=25).trend_years,25)

    def state(self,question,record,**kwargs):
        intent=Intent(kind='lookup',areas=['Aceh'],indicator_ids=['net'],**kwargs)
        guard_temporal_scope(intent,question)
        state=RequestState(question=question,reference_date=date(2026,11,5),intent=intent,records=[record])
        state.assessment=assess(state)
        return state

    def test_model_period_is_not_single_year_or_partial_period(self):
        for q in ['Berapa neraca karbon Aceh pada 2025?','Berapa rata-rata neraca karbon Aceh 2021–2025?','Berapa neraca karbon Aceh tahun ini?']:
            state=self.state(q,period_record(),temporal='explicit',year=2025)
            self.assertFalse(state.assessment.primary,q)
        state=self.state('Berapa rata-rata neraca karbon Aceh 2001–2025?',period_record(),temporal='explicit',year=2025)
        self.assertFalse(state.assessment.gaps)
        answer=render(state,Analysis())
        self.assertIn('2001–2025',answer['parsed']['findings_table']['rows'][0][1])
        self.assertIn('penyerap karbon bersih',answer['parsed']['kesimpulan'])

    def test_map_version_is_not_observation_year(self):
        r=period_record(temporal_basis='map_version',year=2023,period_text='Peta gabungan (versi 2023)',aggregation_kind='extent')
        state=self.state('Berapa luas gambut Aceh pada 2023?',r,temporal='explicit',year=2023)
        self.assertFalse(state.assessment.primary)
        state=self.state('Berapa luas gambut Aceh versi 2023?',r,temporal='explicit',year=2023)
        self.assertTrue(state.assessment.primary)
        self.assertEqual(observation_period(r),'Peta gabungan (versi 2023)')

    def test_query_keeps_nonforest_land_and_filters_threshold_once(self):
        _,_,sql=query('summary','adm2',35)
        self.assertIn("adm1 = '35'",sql)
        where=sql.split(' WHERE ')[1].split(' GROUP BY ')[0]
        self.assertNotIn('is__flux_model_extent',where)
        self.assertEqual(sql.count('umd_tree_cover_density_2000__threshold = 30'),1)
        self.assertIn('THEN area__ha ELSE 0',sql)

    def test_normalization_preserves_negative_net_and_quarantines_invalid_removals(self):
        t={'kind':'summary','level':'adm2','dataset':'carbonflux_adm2_summary','version':'v20260327',
           'receipt':{'url':'https://example.org','sql':'SELECT'},
           'rows':[{'iso':'IDN','adm1':'23','adm2':'6','emissions':'25','removals':'-5','net':'30','peat_ha':'0','mangrove_ha':'0'}]}
        # This normalization test must not depend on a locally imported GFW archive.
        with patch('gfw_expansion.boundaries', return_value=({23: {'name': 'Provinsi Contoh'}},
                   {(23, 6): {'name': 'Kabupaten Contoh, Provinsi Contoh', 'type': 'Kabupaten', 'gid': 'IDN.23.6_1'}})):
            rows=normalize([t])
        means=[r for r in rows if r['indicator_id']=='gfw-carbon-emissions-period-mean']
        self.assertEqual(Decimal(means[0]['value']),Decimal(1))
        self.assertEqual(means[0]['period_start'],'2001-01-01')
        excluded=[r for r in rows if r.get('unusable_reason')]
        self.assertEqual(len(excluded),4)
        self.assertTrue(all(not r['usable'] for r in excluded))
        self.assertEqual(next(r for r in excluded if r['indicator_id']=='gfw-carbon-removals-period-total')['value'],'-5')

    def test_reconciliation_rejects_parent_child_mismatch(self):
        tables=[]
        for kind in ['summary','annual','plantations']:
            for level in ['iso','adm1','adm2']:
                row={'iso':'IDN','value':'2' if level=='iso' else '1'}
                if level!='iso':row['adm1']=1
                if level=='adm2':row['adm2']=1
                if kind=='annual':row['umd_tree_cover_loss__year']=2025
                tables.append({'kind':kind,'level':level,'rows':[row]})
        with self.assertRaisesRegex(ValueError,'Hierarchy mismatch'):validate(tables)


if __name__=='__main__':unittest.main()
