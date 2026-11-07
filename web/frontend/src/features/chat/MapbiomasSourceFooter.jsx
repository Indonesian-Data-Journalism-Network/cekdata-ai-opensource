import React from 'react';
import { COLORS } from '../../ui/ui.jsx';
import GfwSourceFooter from './GfwSourceFooter.jsx';
import { mapbiomasSourceGroups, mapbiomasGfwSubset } from './mapbiomasSources.js';

export default function MapbiomasSourceFooter({ result }) {
  const gfw = mapbiomasGfwSubset(result);
  const style = { color: COLORS.primaryDark, textDecoration: 'underline', overflowWrap: 'anywhere' };
  return <>
    {gfw.parsed.source_items.length > 0 && <GfwSourceFooter result={gfw} />}
    {mapbiomasSourceGroups(result).map(group => <div key={`${group.source}-${group.version}`}
      style={{ marginTop: 16, lineHeight: 1.8, textAlign: 'left' }}>
      <div>Sumber: <a href={group.url} target="_blank" rel="noopener noreferrer" style={style}>
        {group.source} — Koleksi {group.version}
      </a></div>
      <div>Unduh: <a href={group.downloadUrl} target="_blank" rel="noopener noreferrer" style={style}>
        {group.downloadName}
      </a></div>
    </div>)}
  </>;
}
