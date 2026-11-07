// Reorder existing, cited evidence only. Saved chats do not trigger new generation.
export function groupedDocumentAnswer(result) {
  if (!result?.parsed?.document_answer) return result;
  const p = result.parsed;
  const sources = p.source_items || [];
  let groups = p.finding_groups;
  if (!Array.isArray(groups)) {
    const points = (p.temuan_data || '').split(/\n\n+/).filter(Boolean);
    const mapped = points.map(text => {
      const match = text.match(/\[(\d+)\]\s*$/);
      const source = match && sources.find(item => item.source_number === Number(match[1]));
      return { text, source };
    });
    // Do not guess the provenance of old findings without a source marker.
    if (!mapped.length || mapped.some(item => !item.source)) return result;
    const bySource = new Map();
    for (const {text, source} of mapped) {
      if (!bySource.has(source.source)) bySource.set(source.source, {source:source.source, source_numbers:[], findings:[], table:null});
      const group = bySource.get(source.source);
      let point = text.replace(/^[-*]\s+/, '').replace(/^Menurut laporan,?\s*/i, '');
      point = point.charAt(0).toUpperCase() + point.slice(1);
      point = point.replace(/(\d)\s*%/g, '$1 persen');
      group.findings.push(point);
      if (!group.source_numbers.includes(source.source_number)) group.source_numbers.push(source.source_number);
    }
    groups = [...bySource.values()];
    const table = p.findings_table;
    if (table) {
      const column = table.headers.indexOf('Sumber');
      for (const group of groups) {
        const rows = table.rows.filter(row => column >= 0
          ? group.source_numbers.some(number => String(row[column]) === `[${number}]`)
          : table.source_numbers?.length && table.source_numbers.every(number => group.source_numbers.includes(number)));
        if (rows.length) group.table = {...table, rows};
      }
    }
  }
  // Older numeric tables could lose leading thousands groups. Restore only a
  // unique full quantity already printed in the same cited finding, never infer
  // a new value or borrow another report's number.
  function fullQuantities(table, points, sourceNumbers = []) {
    if (!table) return table;
    const column = table.headers.indexOf('Sumber');
    return {...table, rows:table.rows.map(row => {
      const value = String(row[1]);
      const match = value.match(/^(\d+(?:[.,]\d+)*)\s+(.+)$/);
      if (!match) return row;
      const references = column >= 0 ? [String(row[column])] : (table.source_numbers || sourceNumbers).map(n=>`[${n}]`);
      const relevant = points.filter(point=>references.length === 1 && point.endsWith(references[0]));
      const candidates = new Set();
      for (const point of relevant) for (const quantity of point.matchAll(/(?<![\w.,])(\d+(?:[.,]\d+)*)\s+((?:(?:ribu|juta|miliar)\s+)?(?:persen|%|hektare|hektar|ha|orang|rumah tangga))(?!\w)/gi)) {
        if (quantity[2] === match[2] && quantity[1].endsWith(`.${match[1]}`)) candidates.add(`${quantity[1]} ${quantity[2]}`);
      }
      if (candidates.size !== 1) return row;
      const changed = [...row]; changed[1] = [...candidates][0]; return changed;
    })};
  }
  groups = groups.map(group=>({...group,table:fullQuantities(group.table,group.findings,group.source_numbers)}));
  const table = fullQuantities(p.findings_table,groups.flatMap(group=>group.findings));
  const conclusion = p.kesimpulan ?? [...new Set([p.jawaban_utama, p.konteks_penting].filter(Boolean))].join('\n\n');
  const parsed = {...p, finding_groups:groups, findings_table:table, kesimpulan:conclusion, konteks_penting:''};
  const cell = value => String(value).replaceAll('|','\\|').replaceAll('\n',' ');
  const markdown = table => [table.caption || '', '', `| ${table.headers.map(cell).join(' | ')} |`,
    `| ${table.headers.map(()=>'---').join(' | ')} |`, ...table.rows.map(row=>`| ${row.map(cell).join(' | ')} |`),
    ...(table.calculations?.length ? ['', '| Perhitungan | Nilai |', '| --- | ---: |',
      ...table.calculations.map(item=>`| ${cell(item.label)} | ${cell(item.value)} ${cell(item.unit)} |`)] : [])].join('\n').trim();
  const sections = [];
  if (p.claim) sections.push(`Klaim\n${p.claim}`);
  if (p.penilaian) sections.push(`Penilaian: ${p.penilaian}\n\n${p.alasan || ''}`);
  for (const group of groups) sections.push(`Temuan Data ${group.source}\n${group.findings.map(point=>`- ${point}`).join('\n')}${group.table ? `\n\n${markdown(group.table)}` : ''}`);
  if (p.gfw_context) sections.push(`Temuan Data Global Forest Watch\n${p.gfw_context.summary}\n\n${markdown(p.gfw_context.table)}`);
  if (conclusion) sections.push(`Kesimpulan\n${conclusion}`);
  if (p.peringatan_editorial) sections.push(`Peringatan Editorial\n${p.peringatan_editorial}`);
  for (const source of sources) sections.push(`[${source.source_number}] Sumber: ${source.display}${source.pdf_pages?.length ? ` — halaman PDF ${source.pdf_pages.join(', ')}` : ''}\n${source.url}\nUnduh: ${source.title} (PDF)\n${source.download_url}`);
  const seen = new Set();
  for (const source of p.gfw_context?.parsed?.source_items || []) {
    if (!seen.has(source.url)) {sections.push(`Sumber: ${source.display}\n${source.url}`); seen.add(source.url);}
  }
  const answer = sections.join('\n\n');
  return {...result, answer, parsed:{...parsed,raw_answer:answer}};
}
