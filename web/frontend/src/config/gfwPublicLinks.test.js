import test from 'node:test';
import assert from 'node:assert/strict';
import { upgradeGfwSources, gfwEvidenceCsv, gfwArchiveDownloads, gfwSourceGroups } from './gfwPublicLinks.js';

const api = 'https://data-api.globalforestwatch.org/dataset/gadm__tcl__adm2_change/v20260424';
const url = 'https://www.globalforestwatch.org/dashboards/country/IDN/1/5/';
const identity = 'gfw:gadm__tcl__adm2_change:v20260424:IDN:1.5:2025:t30:tree-cover-loss';

test('carbon CSV preserves negative numbers and period while credits stay distinct', () => {
  const carbon = { source_record_id: 'gfw:carbonflux_adm1_summary:v20260327:IDN:1.None:2025:t30:carbon-net-flux-period-total',
    value: '-123.456789', period_text: '2001–2025 (total periode)', temporal_basis: 'model_period',
    source: 'Global Forest Watch / WRI', url: 'https://example.org/carbon' };
  const csv = gfwEvidenceCsv({ evidence: [carbon] });
  assert.ok(csv.includes('"-123.456789"'));
  assert.ok(csv.includes('2001–2025 (total periode)'));
  const groups = gfwSourceGroups([carbon, carbon, {...carbon, source: 'Global Forest Watch / Global Mangrove Watch', url: 'https://example.org/mangrove'}]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].source, 'Global Forest Watch / WRI');
  assert.equal(groups[1].url, 'https://example.org/mangrove');
});

test('saved GFW source links and copied answers use public pages, preserving API downloads', () => {
  const download = api + '/download/json?sql=original';
  const answer = `Nilai: 3781.42822450286826391\nLink sumber: ${api}\nUnduh data: ${download}`;
  const source = { source_record_id: identity, url: api, download_url: download };
  const original = { answer, sources: [source], evidence: [{ source_record_id: identity,
    source_url: api, value: '3781.42822450286826391' }],
    parsed: { raw_answer: answer, source_items: [source], link_sumber: api, unduh_data: download } };
  const updated = upgradeGfwSources(original, { 'adm2:1.5': { url } });
  assert.equal(updated.parsed.source_items[0].url, url);
  assert.equal(updated.sources[0].api_url, api);
  assert.equal(updated.evidence[0].source_url, url);
  assert.equal(updated.evidence[0].value, original.evidence[0].value);
  assert.equal(updated.parsed.link_sumber, url);
  assert.equal(updated.parsed.unduh_data, download);
  assert.ok(updated.answer.includes(`Link sumber: ${url}`));
  assert.ok(updated.answer.includes(`Unduh data: ${download}`));
  assert.equal(updated.parsed.raw_answer, updated.answer);
  assert.equal(original.sources[0].url, api);
  assert.equal(upgradeGfwSources(updated), updated);
});

test('unverified district links use dataset page; other providers remain unchanged', () => {
  const original = { sources: [{ url: api, source_record_id: identity }] };
  assert.equal(upgradeGfwSources(original, {}).sources[0].url,
    'https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html');
  const other = { sources: [{ url: 'https://example.org', source_record_id: 'other' }] };
  assert.equal(upgradeGfwSources(other, {}), other);
});

test('offline CSV preserves exact decimals and source identity, excluding unrelated evidence', () => {
  const row = { id: 'one', source_record_id: identity, value: '3781.42822450286826391',
    area: 'Aceh Selatan, Aceh', source_url: url, download_url: api + '/download/json?sql=original' };
  const csv = gfwEvidenceCsv({ evidence: [row, { source_record_id: 'unrelated', value: '999' }], context: [row] });
  assert.ok(csv.includes('"3781.42822450286826391"'));
  assert.ok(csv.includes('"Aceh Selatan, Aceh"'));
  assert.ok(csv.includes(identity));
  assert.ok(csv.includes(url));
  assert.equal(csv.split('\r\n').length, 3);
  assert.equal(gfwEvidenceCsv({ evidence: [] }), '');
  assert.ok(gfwEvidenceCsv({ parsed: { download_records: [row] } }).includes(row.value));
});

test('legacy answers link only to the matching published region archive', () => {
  const result = { parsed: { source_items: [{ source_record_id: identity }, { source_record_id: identity }] } };
  assert.deepEqual(gfwArchiveDownloads(result), ['/gfw-evidence/adm2-1-5.csv']);
  assert.deepEqual(gfwArchiveDownloads({ parsed: { source_items: [
    { source_record_id: identity.replace('1.5', '../secret') },
    { source_record_id: identity.replace('v20260424', 'v20270101') }] } }), []);
});

test('two regional sources stay linked separately, deduplicated across years', () => {
  const aceh = {source: 'Global Forest Watch / UMD GLAD', source_record_id: identity,
    area: 'Aceh', url: 'https://www.globalforestwatch.org/dashboards/country/IDN/1/', methodology_url: 'https://example.org/method'};
  const riau = {...aceh, area: 'Riau', url: 'https://www.globalforestwatch.org/dashboards/country/IDN/24/'};
  const [group] = gfwSourceGroups([aceh,aceh,riau,riau]);
  assert.equal(group.url, undefined);
  assert.deepEqual(group.links.map(x => x.area), ['Aceh','Riau']);
  assert.deepEqual(group.links.map(x => x.url), [aceh.url,riau.url]);
  assert.equal(gfwSourceGroups([aceh,aceh])[0].url, aceh.url);
});
