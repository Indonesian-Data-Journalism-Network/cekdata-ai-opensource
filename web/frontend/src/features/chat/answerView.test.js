import test from 'node:test';
import assert from 'node:assert/strict';
import { canonicalAnswerView, canonicalCopyText, continuationQuestion } from './answerView.js';

test('catalog year choices are clarification, never verified evidence', () => {
  const result = { abstained: true, claims: [], answer_origin: 'registered-statistics-v1',
    abstention_reason: 'explicit_year_required', clarification: { kind: 'available_year',
      prompt: 'Pilih tahun', choices: [{ label: '2020', question: 'Truk Sampah Batang tahun 2020?' }] } };
  const view = canonicalAnswerView(result);
  assert.equal(view.status, 'needs_clarification');
  assert.deepEqual(view.sources, []);
  assert.equal(view.choices[0].label, '2020');
  assert.equal(canonicalAnswerView({ ...result, abstention_reason: 'service_unavailable' }).title, 'Pencarian belum selesai');
  assert.equal(canonicalAnswerView({ ...result, clarification: { ...result.clarification,
    choices: [{ label: '<script>', question: 'x' }] } }).status, 'unverified');
});

const fixture = () => ({ abstained: false, answer: 'Unsafe summary must not be the source of displayed facts', claims: [{
  text: 'Nilai indikator adalah 10,25 persen.', evidence_id: 'e1', document_version_id: 'v1',
  document_checksum: 'a'.repeat(64), citation_ids: ['c1'], citations: [{ citation_id: 'c1', locator: 'Tabel 1, baris 2',
    source_url: 'https://example.test/source', download_url: 'https://example.test/data.csv' }],
}] });

test('Environment preview notice survives copy and provider failure is incomplete search', () => {
  const value = fixture();
  value.search_preview = { source: 'environment', production_quality_approved: false };
  assert.match(canonicalCopyText(value), /^Uji coba Environment/);
  value.abstained = true;
  value.abstention_reason = 'all_retrieval_channels_failed';
  assert.equal(canonicalAnswerView(value).title, 'Pencarian belum selesai');
  assert.match(canonicalCopyText(value), /^Uji coba Environment/);
});

test('derived statistics preserve both sources and exact large Decimal subtraction', () => {
  const value = fixture();
  value.answer_origin = 'registered-statistics-v1';
  value.claims[0].statistic = { value: '9999999999999999999.25', unit: 'kg', area_name: 'A', year: 2020 };
  value.claims.push({ ...structuredClone(value.claims[0]), evidence_id: 'e2',
    statistic: { value: '9999999999999999998.24', unit: 'kg', area_name: 'A', year: 2021 } });
  value.calculations = [{ baseline_evidence_id: 'e1', target_evidence_id: 'e2',
    formula: 'target - baseline', value: '-1.01', unit: 'kg' }];
  assert.equal(canonicalAnswerView(value).status, 'verified');
  assert.match(canonicalCopyText(value), /-1.01 kg/);
  value.calculations[0].value = '-1.00';
  assert.equal(canonicalAnswerView(value).status, 'unverified');
  value.calculations[0].value = '-1.01';
  value.calculations[0].target_evidence_id = 'missing';
  assert.equal(canonicalAnswerView(value).status, 'unverified');
});

test('canonical answer binds displayed claims and copied source URLs', () => {
  const value = fixture();
  assert.equal(canonicalAnswerView(value).status, 'verified');
  assert.match(canonicalCopyText(value), /https:\/\/example.test\/source/);
  assert.doesNotMatch(canonicalCopyText(value), /Unsafe summary/);
});

for (const mutate of [
  value => value.claims[0].citation_ids.push('unknown'),
  value => value.claims[0].document_checksum = '',
  value => value.claims[0].citations[0].source_url = 'http://example.test/source',
  value => value.claims[0].citations[0].source_url = 'javascript:alert(1)',
  value => value.claims.push({ text: 'unsupported' }),
  value => value.claims = [],
  value => delete value.abstained,
]) test('malformed canonical answer cannot become verified', () => {
  const value = fixture(); mutate(value);
  assert.equal(canonicalAnswerView(value).status, 'unverified');
  assert.equal(canonicalAnswerView(value).claims.length, 0);
});

test('abstention discards contradictory claims and explains incomplete retrieval', () => {
  const value = { ...fixture(), abstained: true, abstention_reason: 'incomplete_retrieval_coverage' };
  assert.equal(canonicalAnswerView(value).title, 'Pencarian belum selesai');
  assert.deepEqual(canonicalAnswerView(value).sources, []);
});

test('legacy is separate from verified evidence', () => {
  assert.equal(canonicalAnswerView({ answer: 'legacy', parsed: {} }), null);
});

test('continuation preserves new question and remains within API bound', () => {
  const question = 'a'.repeat(1600);
  const built = continuationQuestion(question, 'b'.repeat(1000));
  assert.equal(built, question);
  assert.ok(built.length <= 2000);
  assert.throws(() => continuationQuestion('ab'));
  assert.throws(() => continuationQuestion('x'.repeat(1601)));
});

test('explicit primary/support contract rejects source substitution and unlinked context', () => {
  const value = fixture();
  value.response_contract = 'primary-support-v1';
  value.retrieval_scope = { requested_sources: ['legal'] };
  value.claims[0].source_domain = 'legal';
  value.claims[0].evidence_role = 'primary';
  assert.equal(canonicalAnswerView(value).status, 'verified');
  const support = structuredClone(value.claims[0]);
  support.evidence_id = 'e2'; support.source_domain = 'bps'; support.evidence_role = 'supporting';
  support.relationships = [{ relationship_id: 'r', intersection_version_id: 'iv', relationship_type: 'related_to',
    primary_evidence_id: 'e1', source_evidence_id: 'e2', target_evidence_id: 'e1' }];
  value.claims.push(support);
  assert.equal(canonicalAnswerView(value).status, 'verified');
  value.retrieval_scope.requested_sources = ['bps'];
  assert.equal(canonicalAnswerView(value).status, 'unverified');
  value.retrieval_scope.requested_sources = ['legal'];
  support.relationships = [];
  assert.equal(canonicalAnswerView(value).status, 'unverified');
});

test('Environment period guidance keeps its source and exposes no verified claims', () => {
  const result = { response_contract: 'primary-support-v1', abstained: true, claims: [],
    abstention_reason: 'environment_period_required', clarification: { kind: 'environment_period',
      source: 'environment', prompt: 'Pilih periode', choices: [{ label: '2021-01-01 – 2021-12-31',
        question: 'Deteksi hotspot kebakaran VIIRS Kota Sorong periode 2021-01-01 sampai 2021-12-31' }] } };
  const view = canonicalAnswerView(result);
  assert.equal(view.status, 'needs_clarification');
  assert.equal(view.source, 'environment');
  assert.deepEqual(view.claims, []);
  assert.deepEqual(view.sources, []);
  assert.equal(canonicalAnswerView({ ...result, clarification: { ...result.clarification, source: 'bps' } }).status, 'unverified');
  assert.equal(canonicalAnswerView({ ...result, clarification: { ...result.clarification, choices: [] } }).status, 'needs_clarification');
});

test('unsupported Environment period asks for an explicit calendar scope', () => {
  const view = canonicalAnswerView({ abstained: true, claims: [], abstention_reason: 'unsupported_environment_period' });
  assert.equal(view.title, 'Perjelas periode pengamatan');
  assert.match(view.message, /rentang tanggal lengkap/);
  assert.deepEqual(view.claims, []);
});

test('BPS semantic series choices are clarification without verified claims', () => {
  const result = { abstained: true, claims: [], answer_origin: 'registered-statistics-v1',
    clarification: { kind: 'bps_series', source: 'bps', prompt: 'Pilih seri',
      choices: [{ label: 'Produksi jamur 2019 (kg)', question: 'Produksi Jamur di Kabupaten Karanganyar tahun 2019' }] } };
  const view = canonicalAnswerView(result);
  assert.equal(view.title, 'Pilih seri BPS');
  assert.equal(view.source, 'bps');
  assert.deepEqual(view.claims, []);
  assert.deepEqual(view.sources, []);
  assert.equal(canonicalAnswerView({ ...result, clarification: { ...result.clarification, source: 'environment' } }).status, 'unverified');
});

test('monthly differences retain distinct months in the displayed calculation', () => {
  const value = fixture();
  value.answer_origin = 'registered-statistics-v1';
  value.claims[0].statistic = { value: '10', unit: 'mm', area_name: 'A', year: 2020, month: 1 };
  value.claims.push({ ...structuredClone(value.claims[0]), evidence_id: 'e2',
    statistic: { value: '12', unit: 'mm', area_name: 'A', year: 2020, month: 2 } });
  value.calculations = [{ baseline_evidence_id: 'e1', target_evidence_id: 'e2',
    formula: 'target - baseline', value: '2', unit: 'mm' }];
  assert.match(canonicalCopyText(value), /2020-01.*2020-02/);
  delete value.claims[1].statistic.month;
  assert.equal(canonicalAnswerView(value).status, 'unverified');
});


test('followup text does not mix old scope into retrieval text', () => {
  assert.equal(continuationQuestion('Kalau tahun 2021?', 'Luas hutan tahun 2020?'), 'Kalau tahun 2021?');
});

test('ambiguous followup presents scope clarification without a verified claim', () => {
  const result = {abstained:true,claims:[],clarification:{kind:'conversation_scope',source:'environment',
    prompt:'Sebutkan periode yang dimaksud.',choices:[{label:'Periksa sebelumnya',question:'Luas tutupan pohon 2000 di Bali tahun 2000?'}]}};
  const view = canonicalAnswerView(result);
  assert.equal(view.title,'Perjelas pertanyaan lanjutan');
  assert.equal(view.source,'environment');
  assert.equal(view.claims.length,0);
  assert.equal(view.choices.length,1);
});
