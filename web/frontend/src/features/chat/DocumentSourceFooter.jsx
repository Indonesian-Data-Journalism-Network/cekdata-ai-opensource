import React from 'react';
import { COLORS } from '../../ui/ui.jsx';

export default function DocumentSourceFooter({ result }) {
  const items = result?.parsed?.source_items || [];
  const valid = value => { try { return ['http:', 'https:'].includes(new URL(value).protocol); } catch { return false; } };
  const style = { color: COLORS.primaryDark, overflowWrap: 'anywhere', textDecoration: 'underline' };
  return <div aria-label="Sumber laporan" style={{ marginTop: 16, lineHeight: 1.8 }}>
    {items.map((item, index) => <div key={item.document_id} style={{ marginTop: 10 }}>
      <div>[{item.source_number || index + 1}] Sumber: {valid(item.url) ? <a href={item.url} target="_blank" rel="noopener noreferrer" style={style}>{item.display}</a> : item.display}
        {item.pdf_pages?.length ? ` — halaman PDF ${item.pdf_pages.join(', ')}` : ''}</div>
      {valid(item.download_url) && <div>Unduh: <a href={item.download_url} target="_blank" rel="noopener noreferrer" style={style}>{item.title} (PDF)</a></div>}
    </div>)}
  </div>;
}
