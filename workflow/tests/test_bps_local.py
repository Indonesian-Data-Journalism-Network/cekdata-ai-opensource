"""Offline adapter checks with synthetic source metadata, no live model calls."""
import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from bps_local import evidence, BPSLocalRetriever, snapshot_manifest
from flow import SearchQuery
from tools.bps.observation import standardize


def fixture(**changes):
    p=dict(id='point',indicator_id='metric',source_record_id='raw',vertical_label='Wilayah Uji',
           vertical_id='11',vertical_axis='Provinsi',derived_label='Jumlah',derived_id='1',
           title='Indikator uji',source='Sumber simulasi',year=2026,source_url='https://example.org',
           notes='',source_snapshot_sha256='sha',domain='0000',variable_id='1',period_id='126',
           subperiod_id='32',source_cell='cell',subperiod_label='Triwulan II',unit='Persen',value='1.25')
    p.update(changes)
    return standardize(p,{'11':'Wilayah Uji'})


class BPSAdapterTests(unittest.TestCase):
    def test_current_snapshot_and_explicit_year_are_separate(self):
        with tempfile.TemporaryDirectory() as root:
            d=Path(root)
            (d/'qdrant-2026-manifest.json').write_text(json.dumps({'status':'verified','collection':'year-only'}))
            self.assertEqual(snapshot_manifest(d)['collection'],'year-only')
            (d/'qdrant-current-manifest.json').write_text(json.dumps({'status':'verified','collection':'historical'}))
            self.assertEqual(snapshot_manifest(d)['collection'],'historical')
            self.assertEqual(snapshot_manifest(d,2026)['collection'],'year-only')
            (d/'qdrant-current-manifest.json').write_text(json.dumps({'status':'importing'}))
            with self.assertRaises(ValueError):snapshot_manifest(d)
    def test_reads_standardized_payload_without_turning_quarter_into_month(self):
        e=evidence(fixture(),'Wilayah Uji')
        self.assertEqual(e.month,None)
        self.assertEqual(e.quarter,2)
        self.assertEqual(e.period,(2026,6))
        self.assertEqual(e.period_start,'2026-04-01')
        self.assertEqual(e.unit,'persen')
        self.assertEqual(e.source_locator['source_cell'],'cell')

    def test_monthly_question_cannot_retrieve_quarter_total(self):
        p=fixture()
        class Client:
            def scroll(self,*args,**kwargs):return [SimpleNamespace(payload=p)],None
        r=BPSLocalRetriever(Client(),'test',[{'indicator_id':'metric'}],'data April 2026')
        q=SearchQuery(text='data April',indicator_ids=['metric'],areas=['Wilayah Uji'],years=[2026],month=4)
        self.assertEqual(r._search(q).records,[])

    def test_source_label_is_not_reinterpreted_at_read_time(self):
        p=fixture();p['period_text']='Label tampilan berubah'
        e=evidence(p,'Wilayah Uji')
        self.assertEqual((e.quarter,e.period_start),(2,'2026-04-01'))
        p['schema_version']='bps-observation-v1'
        with self.assertRaises(ValueError):evidence(p,'Wilayah Uji')

if __name__=='__main__':unittest.main()
