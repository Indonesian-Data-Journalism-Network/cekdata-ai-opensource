import test from 'node:test';
import assert from 'node:assert/strict';
import { hasMapbiomasSources, mapbiomasSourceGroups, mapbiomasGfwSubset } from './mapbiomasSources.js';

test('one source and original download for many yearly observations; mixed GFW stays separate', () => {
  const rows = [2022, 2023, 2024].map(year => ({ source: 'MapBiomas Indonesia', dataset_version: '4.1',
    url: 'https://landy.mapbiomas.id/en/statistics', download_url: 'https://landy.mapbiomas.id/data.xlsx',
    source_record_id: `mapbiomas:landy:4.1:hash:province:Aceh:extent:oil-palm:${year}-${year}` }));
  rows.push({source_record_id: 'gfw:data:v20260424:IDN:1', source: 'Global Forest Watch'});
  const result = {parsed: {source_items: rows, download_records: rows}};
  assert.equal(hasMapbiomasSources(result), true);
  assert.equal(mapbiomasSourceGroups(result).length, 1);
  assert.equal(mapbiomasSourceGroups(result)[0].version, '4.1');
  assert.equal(mapbiomasGfwSubset(result).parsed.source_items.length, 1);
  assert.equal(mapbiomasGfwSubset(result).parsed.download_records.length, 1);
});
