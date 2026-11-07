import React from 'react';
import { COLORS } from '../../ui/ui.jsx';

export default function SourceLinks({ value, title = '', items }) {
  if (Array.isArray(items) && items.length) {
    return <div style={{ display: 'grid', gap: 8 }}>
      {items.map((item, index) => <div key={`${item.display}-${index}`}>
        {item.methodology_url && item.methodology_url === item.url ? <>
          <div>{item.display}</div>
          <SourceLinks title="Dataset dasar dan metode · UMD 2000–2025" value={item.url} />
          <div style={{ fontSize: 12, marginTop: 4 }}>Rincian angka wilayah tersedia dalam unduhan CSV.</div>
        </> : <SourceLinks title={item.display} value={item.url} />}
        {item.methodology_url && item.methodology_url !== item.url && <div style={{ fontSize: 13, marginTop: 4 }}>
          <SourceLinks title="Dataset dasar dan metode · UMD 2000–2025" value={item.methodology_url} />
        </div>}
      </div>)}
    </div>;
  }
  const links = [...new Set((Array.isArray(value) ? value : [value]).filter(link => {
    try { return ['https:', 'http:'].includes(new URL(link).protocol); }
    catch { return false; }
  }))];
  if (!links.length) return title || null;
  // Only bind a title to a URL when the legacy response is unambiguous.
  // Multiple sources have separate lists, so do not infer pairs by position.
  if (title && !title.includes(';') && links.length === 1) {
    return <a href={links[0]} target="_blank" rel="noopener noreferrer"
      style={{ color: COLORS.primaryDark, overflowWrap: 'anywhere', textDecoration: 'underline', textUnderlineOffset: 3 }}>
      {title}
    </a>;
  }
  if (title) return <>{title}<br /><SourceLinks value={links} /></>;
  return <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
    {links.map((link, index) => <a key={link} href={link} target="_blank" rel="noopener noreferrer"
      style={{ color: COLORS.primaryDark, overflowWrap: 'anywhere', fontSize: 14 }}>
      Buka sumber{links.length > 1 ? ` ${index + 1}` : ''} · {new URL(link).hostname}
    </a>)}
  </div>;
}
