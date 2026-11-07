import test from 'node:test';
import assert from 'node:assert/strict';
import { compactDocumentReferences } from './documentReferences.js';

const sources = [
  { document_id: 'a', source: 'Satya Bumi', title: 'LAPORAN – Kabaena', display: 'Satya Bumi — LAPORAN – Kabaena', pdf_pages: [46,48], url: 'https://satyabumi.org/report', download_url: 'https://satyabumi.org/report.pdf' },
  { document_id: 'b', source: 'WALHI', title: 'Tinjauan lingkungan', display: 'WALHI — Tinjauan lingkungan', pdf_pages: [86], url: 'https://walhi.or.id/report', download_url: 'https://walhi.or.id/report.pdf' },
];
test('saved findings, table and copied answer use consistent short references', () => {
  const findings = 'Sebanyak 54,1% rumah tangga melaporkan kerusakan.\nRujukan: LAPORAN – Kabaena — halaman PDF 46.\n\nLaporan regional membahas dampak perempuan.\nRujukan: Tinjauan lingkungan — halaman PDF 86.';
  const table = {caption:'Angka yang disebutkan dalam laporan',headers:['Temuan','Nilai','Sumber'],rows:[['Kerusakan','54,1 %','LAPORAN – Kabaena — halaman PDF 46']],calculations:[]};
  const markdown = 'Angka yang disebutkan dalam laporan\n\n| Temuan | Nilai | Sumber |\n| --- | --- | --- |\n| Kerusakan | 54,1 % | LAPORAN – Kabaena — halaman PDF 46 |';
  const result = {answer:`Temuan Data\n${findings}\n\n${markdown}\n\nSumber: Satya Bumi — LAPORAN – Kabaena — halaman PDF 46, 48\nhttps://satyabumi.org/report\nUnduh: LAPORAN – Kabaena\nhttps://satyabumi.org/report.pdf`,parsed:{document_answer:true,temuan_data:findings,source_items:sources,findings_table:table}};
  const changed = compactDocumentReferences(result);
  assert.match(changed.parsed.temuan_data,/kerusakan\. \[1\]/);
  assert.match(changed.parsed.temuan_data,/perempuan\. \[2\]/);
  assert.doesNotMatch(changed.answer,/Rujukan:/);
  assert.match(changed.answer,/\[1\] Sumber: Satya Bumi/);
  assert.match(changed.answer,/https:\/\/satyabumi.org\/report.pdf/);
  assert.deepEqual(changed.parsed.findings_table.headers,['Temuan','Nilai']);
  assert.deepEqual(changed.parsed.findings_table.rows,[['Kerusakan','54,1 %']]);
  assert.match(changed.parsed.findings_table.caption,/Satya Bumi \[1\]/);
  assert.deepEqual(changed.parsed.source_items[0].pdf_pages,[46,48]);
  assert.match(result.parsed.temuan_data,/Rujukan:/);
  assert.deepEqual(compactDocumentReferences(changed),changed);
});

test('table using multiple PDFs retains only short source numbers per row', () => {
  const result={parsed:{document_answer:true,source_items:sources,findings_table:{caption:'Angka laporan',headers:['Temuan','Nilai','Sumber'],rows:[['A','54,1 %','LAPORAN – Kabaena — halaman PDF 46'],['B','10 ha','Tinjauan lingkungan — halaman PDF 86']]}}};
  const changed=compactDocumentReferences(result);
  assert.deepEqual(changed.parsed.findings_table.rows.map(row=>row[2]),['[1]','[2]']);
  assert.equal(changed.parsed.findings_table.headers[2],'Sumber');
});

test('unmatched references and unrelated answers are preserved', () => {
  const other={answer:'Rujukan: Data lain',parsed:{temuan_data:'Data BPS'}};
  assert.equal(compactDocumentReferences(other),other);
  const result={parsed:{document_answer:true,source_items:sources,temuan_data:'Temuan.\nRujukan: Laporan tidak dikenal — halaman PDF 8.'}};
  assert.equal(compactDocumentReferences(result).parsed.temuan_data,result.parsed.temuan_data);
});
