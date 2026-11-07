import test from 'node:test';
import assert from 'node:assert/strict';
import { upgradeContext } from './contextView.js';

test('old GFW boilerplate moves to source notes without fabricating analysis or dropping data', () => {
  const note='Luas kehilangan tutupan pohon tahunan; ambang kerapatan tajuk 30% pada tahun 2000. Batas wilayah GADM 4.1.';
  const answer=`Temuan data\nNilai asli 12,345.\n\nKonteks penting\n${note}\n\nSumber: GFW`;
  const result={answer,parsed:{konteks_penting:note,temuan_data:'Nilai asli 12,345.',raw_answer:answer}};
  const changed=upgradeContext(result);
  assert.equal(changed.parsed.konteks_penting,'');
  assert.deepEqual(changed.parsed.source_notes,[note]);
  assert.ok(changed.answer.includes('Nilai asli 12,345.'));
  assert.ok(changed.answer.includes('Sumber: GFW'));
  assert.ok(!changed.answer.includes('Konteks penting'));
  assert.equal(result.parsed.konteks_penting,note);
});

test('analytical context survives migration and copied heading changes', () => {
  const result={answer:'Konteks penting\n150 ÷ 5 = 30.',parsed:{konteks_penting:'150 ÷ 5 = 30.'}};
  const changed=upgradeContext(result);
  assert.equal(changed.parsed.konteks_penting,'150 ÷ 5 = 30.');
  assert.equal(changed.answer,'Konteks\n150 ÷ 5 = 30.');
});
