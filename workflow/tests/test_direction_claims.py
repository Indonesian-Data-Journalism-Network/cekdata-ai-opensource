"""Directional claims, using synthetic data; explicit magnitudes stay distinct."""
import unittest
from datetime import date
from flow import Intent, Predicate, RequestState, assess, direction_only_claim, guard_claim_kind
from test_flow import row


def evaluate(question, values, *, operator='lt', threshold='0', unit='persen',
             continuous=False, negated=False, relative=False, causal=False):
    records = [row(str(y), y, v, unit='persen') for y, v in values]
    i = Intent(kind='claim', areas=['Indonesia'], indicator_ids=['employment'],
               temporal='explicit', baseline_year=values[0][0], year=values[-1][0],
               continuous=continuous, requires_series=True, relative_change=relative,
               causal=causal, predicate=Predicate(metric='change', operator=operator,
                   threshold=threshold, unit=unit, negated=negated))
    state = RequestState(question=question, reference_date=date(2026, 11, 7), intent=i, records=records)
    return assess(state), i


class DirectionClaimsTests(unittest.TestCase):
    def test_stated_magnitude_locks_sign_operator_and_relative_basis(self):
        for text, unit, value, relative in [('turun 0,36 poin persentase', 'poin persentase', '-0.36', False),
                                          ('turun 0,36 persen', 'persen', '-0.36', True),
                                          ('naik sebesar 1,5 persen', 'persen', '1.5', True),
                                          ('berkurang 1.200 jiwa', 'jiwa', '-1200', False)]:
            for op, threshold in [('lt','-0.36'), ('eq','0.36')]:
                i = Intent(kind='claim', predicate=Predicate(metric='change', operator=op,
                           threshold=threshold, unit=unit))
                guard_claim_kind(i, f'Benarkah nilainya {text} dari 2024 ke 2025?')
                self.assertEqual((i.predicate.operator,i.predicate.threshold,i.predicate.unit), ('eq',value,unit))
                self.assertEqual(i.relative_change,relative)

    def test_literal_percent_and_points_get_different_verdicts(self):
        for suffix, verdict in [('poin persentase','Benar'),('persen','Salah')]:
            q=f'Benarkah persentasenya turun 0,36 {suffix} dari 2024 ke 2025?'
            i=Intent(kind='claim', areas=['Indonesia'], indicator_ids=['employment'],
                     temporal='explicit', baseline_year=2024, year=2025, requires_series=True)
            guard_claim_kind(i,q)
            out=assess(RequestState(question=q,reference_date=date(2026,11,7),intent=i,
                       records=[row('a',2024,'5.54',unit='persen'),row('b',2025,'5.18',unit='persen')]))
            self.assertEqual(out.verdict,verdict)

    def test_decline_rise_and_equal_values(self):
        for end, op, verb, verdict in [('5.18', 'lt', 'turun', 'Benar'),
                                       ('5.18', 'gt', 'naik', 'Salah'),
                                       ('5.9', 'gt', 'naik', 'Benar'),
                                       ('5.54', 'lt', 'turun', 'Salah'),
                                       ('5.54', 'gt', 'naik', 'Salah')]:
            out, i = evaluate(f'Benarkah persentasenya {verb} dari 2024 ke 2025?',
                              [(2024, '5.54'), (2025, end)], operator=op)
            self.assertEqual(out.verdict, verdict)
            self.assertEqual(i.predicate.unit, 'persen')
            self.assertEqual(out.calculations[0].unit, 'poin persentase')

    def test_negated_and_continuous_direction(self):
        out, _ = evaluate('Benarkah persentasenya tidak turun dari 2024 ke 2025?',
                          [(2024, '5.54'), (2025, '5.18')], negated=True)
        self.assertEqual(out.verdict, 'Salah')
        for middle, verdict in [('5.3', 'Benar'), ('5.8', 'Salah')]:
            out, _ = evaluate('Benarkah persentasenya terus turun setiap tahun selama 2023–2025?',
                              [(2023, '5.54'), (2024, middle), (2025, '5.18')], continuous=True)
            self.assertEqual(out.verdict, verdict)

    def test_explicit_magnitude_still_requires_correct_measure(self):
        out, _ = evaluate('Benarkah persentasenya turun 5 persen dari 2024 ke 2025?',
                          [(2024, '10'), (2025, '9.5')], operator='eq', threshold='-5')
        self.assertEqual(out.verdict, 'Tidak dapat diverifikasi')
        out, _ = evaluate('Benarkah persentasenya turun 5 persen dari 2024 ke 2025?',
                          [(2024, '10'), (2025, '9.5')], operator='eq', threshold='-5', relative=True)
        self.assertEqual(out.verdict, 'Benar')
        out, _ = evaluate('Benarkah persentasenya turun 0,5 poin persentase dari 2024 ke 2025?',
                          [(2024, '10'), (2025, '9.5')], operator='eq', threshold='-0.5', unit='poin persentase')
        self.assertEqual(out.verdict, 'Benar')

    def test_bad_zero_parse_does_not_erase_numeric_or_compound_claim(self):
        p = Predicate(metric='change', operator='lt', threshold='0', unit='persen')
        for q in ['Turun 5 persen dari 2024 ke 2025', 'Turun lima persen pada 2025',
                  'Turun separuh pada 2025', 'Turun 0 persen pada 2025',
                  'Turun dan lapangan kerja bertambah pada 2025']:
            self.assertFalse(direction_only_claim(q, p))

    def test_causality_and_missing_comparator_still_block(self):
        out, _ = evaluate('Berkat program, persentasenya turun dari 2024 ke 2025',
                          [(2024, '5.54'), (2025, '5.18')], causal=True)
        self.assertEqual(out.verdict, 'Tidak dapat diverifikasi')
        out, _ = evaluate('Benarkah persentasenya turun dari 2024 ke 2025?', [(2025, '5.18')])
        self.assertEqual(out.verdict, 'Tidak dapat diverifikasi')


if __name__ == '__main__':
    unittest.main()
