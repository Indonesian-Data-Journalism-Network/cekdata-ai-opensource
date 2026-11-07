// Compact the presentation of saved report answers without regenerating any facts.
export function compactDocumentReferences(result) {
  if (!result?.parsed?.document_answer) return result;
  const parsed = result.parsed;
  const sources = (parsed.source_items || []).map((item, index) => ({
    ...item, source_number: item.source_number || index + 1,
    reference_notes: [...(item.reference_notes || [])],
  }));
  const sourceFor = reference => {
    const matches = sources.filter(item => item.title &&
      (reference === item.title || reference.startsWith(`${item.title} — `)));
    return matches.length === 1 ? matches[0] : null;
  };

  function compactText(text) {
    if (typeof text !== 'string') return text;
    const lines = [];
    for (const line of text.split('\n')) {
      const match = line.match(/^Rujukan:\s*(.+)$/);
      const source = match && sourceFor(match[1]);
      const previous = lines.findLastIndex(value => value.trim());
      if (source && previous >= 0) {
        const marker = `[${source.source_number}]`;
        if (!lines[previous].endsWith(marker)) lines[previous] += ` ${marker}`;
        if (!source.reference_notes.includes(match[1])) source.reference_notes.push(match[1]);
        continue;
      }
      const footer = sources.find(item => line.startsWith(`Sumber: ${item.display}`));
      lines.push(footer ? `[${footer.source_number}] ${line}` : line);
    }
    return lines.join('\n');
  }

  const oldTable = parsed.findings_table;
  let table = oldTable;
  const column = oldTable?.headers?.indexOf('Sumber') ?? -1;
  if (column >= 0) {
    const rows = oldTable.rows.map(row => {
      const next = [...row];
      const source = sourceFor(String(row[column]));
      if (source) next[column] = `[${source.source_number}]`;
      return next;
    });
    const numbers = [...new Set(rows.map(row => row[column]))];
    const source = numbers.length === 1 && sources.find(item => numbers[0] === `[${item.source_number}]`);
    table = source ? { ...oldTable, caption: `Angka dalam laporan ${source.source} [${source.source_number}]`,
      headers: oldTable.headers.filter((_, i) => i !== column),
      rows: rows.map(row => row.filter((_, i) => i !== column)), source_numbers: [source.source_number],
    } : { ...oldTable, rows };
  }

  const markdown = value => {
    const cell = input => String(input).replaceAll('|', '\\|').replaceAll('\n', ' ');
    const lines = [value.caption || '', '', `| ${value.headers.map(cell).join(' | ')} |`,
      `| ${value.headers.map(() => '---').join(' | ')} |`,
      ...value.rows.map(row => `| ${row.map(cell).join(' | ')} |`)];
    if (value.calculations?.length) lines.push('', '| Perhitungan | Nilai |', '| --- | ---: |',
      ...value.calculations.map(item => `| ${cell(item.label)} | ${item.value} ${item.unit} |`));
    return lines.join('\n').trim();
  };
  function compactAnswer(text) {
    text = compactText(text);
    if (typeof text === 'string' && oldTable && table !== oldTable) {
      text = text.replace(markdown(oldTable), markdown(table));
    }
    return text;
  }
  const findings = compactText(parsed.temuan_data);
  const answer = compactAnswer(result.answer);
  const raw = compactAnswer(parsed.raw_answer);
  return { ...result, answer, parsed: { ...parsed, source_items: sources,
    temuan_data: findings, findings_table: table, raw_answer: raw } };
}
