import React, { useEffect, useMemo, useState } from 'react';
import { gfwEvidenceCsv, gfwArchiveDownloads, gfwSourceGroups } from '../../config/gfwPublicLinks.js';
import { COLORS } from '../../ui/ui.jsx';

export function hasGfwSources(result) {
  const items = result?.parsed?.source_items;
  return Array.isArray(items) && items.length > 0 && items.every(item => item.source_record_id?.startsWith('gfw:'));
}

export default function GfwSourceFooter({ result }) {
  const csv = useMemo(() => gfwEvidenceCsv(result), [result]);
  const [downloadUrl, setDownloadUrl] = useState('');
  useEffect(() => {
    if (!csv) { setDownloadUrl(''); return; }
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    setDownloadUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [csv]);
  const items = result.parsed.source_items;
  const groups = gfwSourceGroups(items);
  const rows = result.parsed.download_records || [];
  const areas = [...new Set(rows.map(row => row.area).filter(Boolean))];
  const years = [...new Set(rows.map(row => row.year).filter(Boolean))].sort((a,b) => a-b);
  const periods = [...new Set(rows.filter(row => row.temporal_basis && row.temporal_basis !== 'annual').map(row => row.period_text).filter(Boolean))];
  const names = [...new Set(items.map(item => (item.title || item.display || '').split(' — ')[0]).filter(Boolean))];
  const dataName = [names.join('; ') || 'Data GFW', areas.join(' dan '),
    periods.length ? periods.join('; ') : years.length ? (years.length === 1 ? years[0] : `${years[0]}–${years.at(-1)}`) : ''].filter(Boolean).join(' — ');
  const style = { color: COLORS.primaryDark, overflowWrap: 'anywhere', textDecoration: 'underline' };
  const archives = csv ? [] : gfwArchiveDownloads(result);
  return <div style={{ marginTop: 16, lineHeight: 1.8, textAlign: 'left' }}>
    <div>Sumber: {groups.map(({ source, version, url, links }, index) => {
      const label = `${source} — versi ${version}`;
      return <React.Fragment key={`${source}|${version}`}>{index > 0 && '; '}{url ? <a href={url} target="_blank" rel="noopener noreferrer" style={style}>{label}</a> : <>{label}{links.length > 0 && ' · '}{links.map((link, n) => <React.Fragment key={link.url}>{n > 0 && ' · '}<a href={link.url} target="_blank" rel="noopener noreferrer" style={style}>{link.area || `Halaman sumber ${n + 1}`}</a></React.Fragment>)}</>}</React.Fragment>;
    })}</div>
    {downloadUrl && <div>Unduh: <a href={downloadUrl} download="cekdata-bukti-gfw.csv" style={style}>{dataName} (CSV)</a></div>}
    {archives.map((url, index) => <div key={url}>Unduh: <a href={url} download style={style}>
      {names.join('; ') || 'Data GFW'} — tabel arsip wilayah{archives.length > 1 ? ` ${index + 1}` : ''} (CSV)
    </a></div>)}
  </div>;
}
