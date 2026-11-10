import copy
from datetime import date
from decimal import Decimal
import unittest

from unit_reading import read_unit, convert_unit
from pinecone_data import map_record, PineconeEvidenceRetriever
from flow import assess, RequestState, Intent, Predicate, SearchQuery, guard_claim_kind
from test_pinecone_data import record


class UnitReadingTests(unittest.TestCase):
    def test_numeric_claim_fallback_keeps_explicit_unit(self):
        for literal, number, unit in [('12.220 jiwa', '12220', 'jiwa'),
                                      ('12,22 jiwa', '12.22', 'jiwa'),
                                      ('12,22 ribu jiwa', '12.22', 'ribu jiwa'),
                                      ('1,5 juta rupiah', '1.5', 'juta rupiah'),
                                      ('1.234.567 orang', '1234567', 'orang')]:
            i = Intent(kind='claim')
            guard_claim_kind(i, f'Benarkah nilainya pada 2023 sebesar {literal}?')
            self.assertIsNotNone(i.predicate)
            self.assertEqual(i.predicate.threshold, number)
            self.assertEqual(i.predicate.unit, unit)

    def test_metadata_takes_precedence_unchanged(self):
        for unit in ('Persen', 'Ribu Jiwa', 'Rp/kapita/bulan'):
            self.assertEqual(read_unit({'unit': unit, 'title': 'Contoh (Ton)'}), (unit, {}, ''))

    def test_explicit_literal_overrides_generic_model_dimension_without_changing_operators(self):
        i = Intent(kind='claim', predicate=Predicate(metric='value', operator='eq', threshold='12220', unit='count'))
        guard_claim_kind(i, 'Benarkah jumlah penduduk pada 2023 sebesar 12,22 ribu jiwa?')
        self.assertEqual((i.predicate.threshold, i.predicate.unit), ('12.22', 'ribu jiwa'))
        for q in ['Benarkah nilainya setidaknya sebesar 12,22 ribu jiwa?',
                  'Benarkah nilainya sebesar 12,22 ribu jiwa dan naik?']:
            i = Intent(kind='claim', predicate=Predicate(metric='value', operator='ge', threshold='12220', unit='jiwa'))
            guard_claim_kind(i, q)
            self.assertEqual(i.predicate.operator, 'ge')
            self.assertEqual(i.predicate.unit, 'jiwa')

    def test_explicit_scaled_labels_only(self):
        for label, base, scale in [('Ribu Jiwa', 'jiwa', 1000),
                                    ('Juta Rupiah', 'rupiah', 1000000),
                                    ('Ribu Ton', 'ton', 1000)]:
            for field, text in [('title', f'Ukuran ({label}) Menurut Wilayah'),
                                ('unit_note', f'Satuan: {label}')]:
                unit, info, reason = read_unit({field: text})
                self.assertEqual(reason, '')
                self.assertEqual((info['base_unit'], info['scale']), (base, scale))
                self.assertEqual(info['field'], field)
        for title in ('Jumlah penduduk miskin', 'Pendapatan juta orang',
                      'Penduduk (2019–2026)', 'Persentase penduduk miskin',
                      'Pengeluaran (Rp/kapita/bulan)'):
            self.assertEqual(read_unit({'title': title})[2], 'missing_unit')
        self.assertEqual(read_unit({'title': 'Penduduk (Ribu Jiwa)',
                                   'series_label': 'Persentase (Persen)'})[2], 'conflicting_unit_labels')

    def test_mapping_is_read_only_and_preserves_value_and_provenance(self):
        r = record(title='Jumlah Penduduk (Ribu Jiwa)', unit='', value='12.22')
        before = copy.deepcopy(r)
        row, reason = map_record(r)
        self.assertEqual(reason, '')
        self.assertEqual(row.value, '12.22')
        self.assertEqual(row.unit, 'ribu jiwa')
        self.assertEqual(row.source_locator['unit_reading']['scale'], 1000)
        self.assertEqual(r, before)
        complete, _ = map_record(record(unit='ribu jiwa', title=r['metadata']['title'], value='12.22'))
        self.assertEqual(row.indicator_id, complete.indicator_id)
        self.assertNotIn('unit_reading', complete.source_locator)

    def test_scale_conversion_and_incompatible_units(self):
        self.assertEqual(convert_unit('12.22', 'ribu jiwa', 'orang'), Decimal('12220'))
        self.assertEqual(convert_unit('12220', 'jiwa', 'ribu jiwa'), Decimal('12.22'))
        self.assertEqual(convert_unit('1.2', 'juta rupiah', 'ribu rupiah'), Decimal('1200'))
        self.assertEqual(convert_unit('2', 'ribu ton', 'ton'), Decimal('2000'))
        for a, b in [('persen', 'poin persentase'), ('jiwa', 'rumah tangga'),
                     ('rupiah', 'jiwa'), ('Rp/kapita/bulan', 'rupiah')]:
            self.assertIsNone(convert_unit('1', a, b))

    def test_claim_converts_threshold_without_rescaling_evidence(self):
        row, _ = map_record(record(unit='', title='Jumlah penduduk (Ribu Jiwa)', value='12.22'))
        for value, verdict in [('12220', 'Benar'), ('12.22', 'Salah')]:
            i = Intent(kind='claim', indicator_ids=[row.indicator_id], areas=[row.area],
                       temporal='explicit', year=2025,
                       predicate=Predicate(metric='value', operator='eq', threshold=value, unit='jiwa'))
            out = assess(RequestState(question='Klaim angka', reference_date=date(2026, 11, 7),
                                      intent=i, records=[row]))
            self.assertEqual(out.verdict, verdict)
            self.assertIn('12,22 ribu jiwa', out.reason)
            self.assertEqual(out.primary[0].value, '12.22')

    def test_fallback_gets_separate_window_and_no_invented_unit_filter(self):
        missing = record(unit='', title='Penduduk (Ribu Jiwa)', value='12.22')
        del missing['metadata']['unit']
        valid = record(unit='ribu jiwa', title='Penduduk (Ribu Jiwa)', value='13', year=2024)
        valid['id'] = 'older'
        class Client:
            calls = []
            def query(self, vector, **kwargs):
                self.calls.append(kwargs)
                return {'matches': [valid] if len(self.calls) == 1 else [missing] if len(self.calls) == 2 else [valid, missing]}
        c = Client()
        r = PineconeEvidenceRetriever(c, [.1])
        catalog = r.discover(['Kabupaten Wilayah A'])
        self.assertEqual(len(c.calls), 2)
        self.assertEqual(len(catalog), 1)
        result = r._search(SearchQuery(text='data', indicator_ids=[catalog[0]['indicator_id']],
                            areas=['Kabupaten Wilayah A'], years=[2024, 2025]))
        self.assertEqual(len(result.records), 2)
        self.assertEqual({v.value for v in result.records}, {'12.22', '13'})
        self.assertEqual(c.calls[-1]['filters']['$and'][2]['$or'],
                         [{'unit': {'$eq': 'ribu jiwa'}}, {'unit': {'$exists': False}}, {'unit': {'$eq': ''}}])


if __name__ == '__main__':
    unittest.main()
