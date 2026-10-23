import React, { useEffect, useState } from 'react';
import { requestJson } from '../../services/httpClient.js';
import { Button, COLORS, inputStyle } from '../../ui/ui.jsx';

export default function BPSArchiveSearch() {
  const [availability, setAvailability] = useState(null);
  const [query, setQuery] = useState('');
  const [year, setYear] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    requestJson('/search/bps/archive/status', { signal: controller.signal })
      .then(setAvailability).catch(() => {});
    return () => controller.abort();
  }, []);
  if (!availability?.available) return null;
  async function search(event) {
    event.preventDefault();
    setBusy(true); setError(''); setResult(null);
    try {
      setResult(await requestJson('/search/bps/archive', {
        method: 'POST', body: { query, year: year ? Number(year) : null, limit: 5 },
      }));
    } catch (err) { setError(typeof err.message === 'string' ? err.message : 'Pencarian gagal. Coba lagi.'); }
    finally { setBusy(false); }
  }
  return <details style={{ background: '#fff', border: '1px solid #dedede', borderRadius: 14, padding: 16 }}>
    <summary style={{ cursor: 'pointer', fontWeight: 700 }}>Cari tabel arsip BPS</summary>
    <p style={{ color: COLORS.muted, lineHeight: 1.6 }}>
      Telusuri {availability.matched_cells.toLocaleString('id-ID')} angka yang cocok dengan sel tabel arsip.
      Gunakan nama indikator, wilayah, dan tahun. Cakupan arsip masih terbatas.
    </p>
    <form onSubmit={search} style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      <input aria-label="Kata kunci arsip BPS" required minLength={2} maxLength={300}
        placeholder="Contoh: SIUP pembaharuan Juwangi" value={query}
        onChange={e => setQuery(e.target.value)} style={{ ...inputStyle, flex: '1 1 220px' }} />
      <input aria-label="Tahun arsip BPS" type="number" min="1800" max="2100" placeholder="Tahun"
        value={year} onChange={e => setYear(e.target.value)} style={{ ...inputStyle, width: 110 }} />
      <Button type="submit" disabled={busy}>{busy ? 'Mencocokkan…' : 'Cari arsip'}</Button>
    </form>
    <div aria-live="polite">
      {error && <p role="alert">{error}</p>}
      {result && <>
        <p style={{ color: COLORS.muted }}>{result.note}</p>
        {!result.results.length && <p>Belum ada sel arsip yang cocok. Coba nama indikator atau wilayah yang lebih spesifik.</p>}
        {result.results.map(row => {
          const cell = row.archive_evidence.cells[0];
          return <article key={row.id} style={{ borderTop: '1px solid #eee', padding: '14px 0', lineHeight: 1.6 }}>
            <strong>{row.title}</strong>
            <div>{row.indicator} · {row.area} · {row.year}{row.period ? ` · ${row.period}` : ''}</div>
            {row.breakdown?.[1] && <div>{row.breakdown.join(': ')}</div>}
            {row.subgroup?.[1] && <div>{row.subgroup.join(': ')}</div>}
            <div>Angka pada arsip: <strong>{cell.raw_value}</strong></div>
            <div style={{ color: COLORS.muted }}>Satuan metadata: {row.unit || 'tidak tersedia'} (belum diverifikasi)</div>
            <a href={row.archive_evidence.archive_url} target="_blank" rel="noopener noreferrer">Buka tabel sumber</a>
            <span> · baris {cell.row}, kolom {cell.column}</span>
          </article>;
        })}
        {result.has_more && <p>Masih ada hasil lain. Tambahkan kata kunci indikator atau wilayah untuk mempersempit pencarian.</p>}
        {result.excluded_candidates > 0 && <p>Beberapa kandidat tidak lolos pencocokan terbaru sehingga tidak ditampilkan.</p>}
      </>}
    </div>
  </details>;
}
