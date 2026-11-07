import React from 'react';
import { COLORS } from '../../ui/ui.jsx';

export default function FindingsTable({ table }) {
  const cell = { padding: '10px 12px', borderBottom: '1px solid #e8e3de', verticalAlign: 'top', textAlign: 'left' };
  const numeric = value => /^-?[\d.,]+(?:\s*(?:%|persen|ha|hektare|orang|rumah tangga))?$/.test(String(value));
  const numericColumn = index => index > 0 && table.rows.length > 0 && table.rows.every(row => numeric(row[index]));
  return <>
    {table.caption && <p style={{ margin: '0 0 10px', lineHeight: 1.6 }}>{table.caption}</p>}
    <div role="region" aria-label="Tabel Temuan Data" tabIndex={0} style={{ overflowX: 'auto', maxWidth: '100%' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 14 }}>
        <thead><tr>{table.headers.map((header, i) => <th key={i} scope="col" style={{ ...cell, background: COLORS.panel, textAlign: numericColumn(i) ? 'right' : 'left' }}>{header}</th>)}</tr></thead>
        <tbody>{table.rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j} style={{ ...cell,
          textAlign: numeric(value) && j > 0 ? 'right' : 'left', whiteSpace: numeric(value) ? 'nowrap' : undefined, fontVariantNumeric: 'tabular-nums' }}>{value}</td>)}</tr>)}</tbody>
      </table>
    </div>
    {table.calculations?.length > 0 && <table aria-label="Hasil perhitungan" style={{ borderCollapse: 'collapse', width: '100%', marginTop: 12, fontSize: 14 }}>
      <thead><tr><th scope="col" style={cell}>Perhitungan</th><th scope="col" style={{ ...cell, textAlign: 'right' }}>Nilai</th></tr></thead>
      <tbody>{table.calculations.map((calc, i) => <tr key={i}><td style={cell}>{calc.label}</td><td style={{ ...cell, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{calc.value} {calc.unit}</td></tr>)}</tbody>
    </table>}
  </>;
}
