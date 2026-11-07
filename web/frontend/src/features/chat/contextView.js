// Keep saved answers intact while separating the old GFW source boilerplate.
// Never invent an analysis for a historical answer that did not contain one.
import { compactDocumentReferences } from './documentReferences.js';
import { groupedDocumentAnswer } from './documentAnswerView.js';
export function upgradeContext(result) {
  if (!result?.parsed || result.claims) return result;
  const old = result.parsed.konteks_penting || '';
  const paragraphs = old.split(/\n\n+/).filter(Boolean);
  const technical = paragraphs.filter(text => text.startsWith('Luas kehilangan tutupan pohon tahunan; ambang kerapatan tajuk 30% pada tahun 2000.'));
  const context = paragraphs.filter(text => !technical.includes(text)).join('\n\n');
  const notes = [...new Set([...(result.parsed.source_notes || []), ...technical])];
  function updateText(text) {
    if (typeof text !== 'string') return text;
    if (technical.length) {
      for (const label of ['Konteks penting', 'Konteks']) {
        text = text.replace(`${label}\n${old}`, context ? `Konteks\n${context}` : '');
      }
    }
    return text.replace(/^Konteks penting$/gm, 'Konteks').replace(/\n{3,}/g, '\n\n');
  }
  return groupedDocumentAnswer(compactDocumentReferences({ ...result, answer: updateText(result.answer), parsed: { ...result.parsed,
    konteks_penting: context, source_notes: notes, raw_answer: updateText(result.parsed.raw_answer) } }));
}
