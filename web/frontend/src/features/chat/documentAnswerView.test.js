import test from 'node:test';
import assert from 'node:assert/strict';
import { upgradeContext } from './contextView.js';
const source = (number,org) => ({source_number:number,source:org,display:`${org} — Studi ${number}`,title:`Studi ${number}`,document_id:String(number),url:`https://example.org/${number}`,download_url:`https://example.org/${number}.pdf`,pdf_pages:[number+4]});

test('interleaved sources group by organization, preserve numbers and put synthesis last in copy', () => {
  const result={parsed:{document_answer:true,source_items:[source(1,'Auriga'),source(2,'WALHI'),source(3,'Auriga')],
    penilaian:'Sebagian benar',claim:'Klaim pengguna',alasan:'Alasan penilaian.',
    jawaban_utama:'Kesimpulan berdasarkan bukti.',konteks_penting:'Wilayah survei berbeda.',
    temuan_data:'Menurut laporan, sebanyak 12,3% responden melaporkan dampak. [1]\n\nTemuan regional. [2]\n\nTemuan tambahan. [3]',
    findings_table:{headers:['Temuan','Nilai','Sumber'],rows:[['Responden','12,3 %','[1]'],['Luas','8 ha','[2]']],calculations:[]},
    gfw_context:{summary:'Kehilangan tutupan pohon.',table:{headers:['Tahun','ha'],rows:[['2025','20']],calculations:[{label:'Total',value:'20',unit:'ha'}]},parsed:{source_items:[{display:'GFW',url:'https://globalforestwatch.org/'}]}},
    peringatan_editorial:'Perlu data penyebab.'}};
  const changed=upgradeContext(result),p=changed.parsed;
  assert.deepEqual(p.finding_groups.map(g=>g.source),['Auriga','WALHI']);
  assert.deepEqual(p.finding_groups[0].source_numbers,[1,3]);
  assert.equal(p.finding_groups[0].findings.length,2);
  assert.match(p.finding_groups[0].findings[0],/^Sebanyak 12,3 persen/);
  assert.deepEqual(p.finding_groups[0].table.rows,[['Responden','12,3 %','[1]']]);
  assert.equal(p.penilaian,'Sebagian benar');
  for(const [a,b] of [['Penilaian: Sebagian benar','Temuan Data Auriga'],['Temuan Data Auriga','Temuan Data WALHI'],['Temuan Data WALHI','Temuan Data Global Forest Watch'],['Temuan Data Global Forest Watch','Kesimpulan'],['Kesimpulan','Peringatan Editorial'],['Peringatan Editorial','[1] Sumber:']]) assert.ok(changed.answer.indexOf(a)<changed.answer.indexOf(b),a);
  assert.equal(changed.answer.match(/https:\/\/example.org\/1.pdf/g).length,1);
  assert.equal(changed.parsed.raw_answer,changed.answer);
  assert.deepEqual(upgradeContext(changed),changed);
  assert.equal(result.parsed.finding_groups,undefined);
});

test('unattributed historical data are not assigned a guessed source',()=>{
  const r={parsed:{document_answer:true,temuan_data:'Temuan tanpa sumber.',source_items:[source(1,'WALHI')]}};
  assert.equal(upgradeContext(r).parsed.finding_groups,undefined);
});

test('no-data claim keeps its verdict and shows the explanation once',()=>{
  const message='Belum cukup data untuk memberikan jawaban.';
  const result={parsed:{document_answer:true,finding_groups:[],source_items:[],claim:'Klaim uji',
    penilaian:'Tidak dapat diverifikasi',alasan:message,jawaban_utama:message,kesimpulan:''}};
  const changed=upgradeContext(result);
  assert.equal(changed.parsed.kesimpulan,'');
  assert.equal(changed.answer.split(message).length-1,1);
  assert.match(changed.answer,/Penilaian: Tidak dapat diverifikasi/);
  assert.doesNotMatch(changed.answer,/Kesimpulan/);
});

test('new grouped answers preserve all findings, tables, verdicts and source metadata',()=>{
  for(const verdict of ['Benar','Salah','Sebagian benar','Tidak dapat diverifikasi']) {
    const r={parsed:{document_answer:true,penilaian:verdict,alasan:'Bukti tersedia.',kesimpulan:'Kesimpulan terbatas.',source_items:[source(1,'Trend Asia')],finding_groups:[{source:'Trend Asia',source_numbers:[1],findings:['Temuan langsung. [1]'],table:null}]}};
    const changed=upgradeContext(r);
    assert.equal(changed.parsed.penilaian,verdict);
    assert.deepEqual(changed.parsed.finding_groups,r.parsed.finding_groups);
    assert.deepEqual(changed.parsed.source_items[0].pdf_pages,[5]);
    assert.doesNotMatch(changed.answer,/Peringatan Editorial/);
    assert.ok(changed.answer.indexOf('Temuan Data Trend Asia')<changed.answer.indexOf('Kesimpulan'));
  }
});

test('a truncated historical thousands value is repaired only from its unique cited finding',()=>{
  const table={headers:['Temuan','Nilai','Sumber'],rows:[['Ancaman hutan','567,54 hektar','[1]'],['Data lain','567,54 hektar','[2]']],calculations:[]};
  const r={parsed:{document_answer:true,source_items:[source(1,'WALHI'),source(2,'Auriga')],temuan_data:'Ancaman seluas 3.204.567,54 hektar. [1]\n\nTemuan berbeda tanpa angka. [2]',findings_table:table}};
  const changed=upgradeContext(r);
  assert.equal(changed.parsed.finding_groups[0].table.rows[0][1],'3.204.567,54 hektar');
  assert.equal(changed.parsed.finding_groups[1].table.rows[0][1],'567,54 hektar');
  assert.equal(changed.parsed.findings_table.rows[0][1],'3.204.567,54 hektar');
  assert.deepEqual(upgradeContext(changed),changed);
});
