import publicSources from './gfwPublicSources.json' with { type: 'json' };

const DATASET_PAGE = 'https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html';
const IDENTITY = /^gfw:gadm__tcl__(iso|adm1|adm2)_change:(v\d+):IDN:(None|\d+(?:\.\d+)?):(\d{4}):t30:(tree-cover-loss|tree-cover-loss-fire|primary-forest-loss)$/;
const EXPANSION = /^gfw:(?:carbonflux_(?:iso|adm1|adm2)_(?:summary|change)|gadm__tcl__(?:iso|adm1|adm2)_summary):v\d+:IDN:/;

// Upgrade only known local GFW source links, including saved conversations.
// Keep API download links and all statistical values unchanged.
export function upgradeGfwSources(result, registry = publicSources) {
  if (!result || typeof result !== 'object' || result.claims) return result;
  const replacements = new Map();
  function convert(item, field) {
    const match = IDENTITY.exec(item?.source_record_id || '');
    if (!match) return item;
    const [, level, version, code] = match;
    if ((level === 'iso' && code !== 'None') || (level === 'adm1' && !/^\d+$/.test(code))
        || (level === 'adm2' && !/^\d+\.\d+$/.test(code))) return item;
    const api = `https://data-api.globalforestwatch.org/dataset/gadm__tcl__${level}_change/${version}`;
    if (item[field] !== api) return item;
    const key = level === 'iso' ? 'iso:IDN' : `${level}:${code}`;
    const candidate = registry[key]?.url || '';
    const url = /^https:\/\/www\.globalforestwatch\.org\/dashboards\/country\/IDN\/(?:\d+\/){0,2}$/.test(candidate)
      ? candidate : DATASET_PAGE;
    if (!replacements.has(api)) replacements.set(api, new Set());
    replacements.get(api).add(url);
    return { ...item, [field]: url, methodology_url: DATASET_PAGE,
      [field === 'url' ? 'api_url' : 'api_source_url']: api };
  }
  const updated = { ...result };
  for (const name of ['evidence', 'context']) {
    if (Array.isArray(result[name])) updated[name] = result[name].map(item => convert(item, 'source_url'));
  }
  if (Array.isArray(result.sources)) updated.sources = result.sources.map(item => convert(item, 'url'));
  if (result.parsed) {
    updated.parsed = { ...result.parsed };
    if (Array.isArray(result.parsed.download_records)) {
      updated.parsed.download_records = result.parsed.download_records.map(item => convert(item, 'source_url'));
    }
    if (Array.isArray(result.parsed.source_items)) {
      updated.parsed.source_items = result.parsed.source_items.map(item => convert(item, 'url'));
    }
  }
  if (!replacements.size) return result;
  function replaceText(value) {
    if (typeof value !== 'string') return value;
    let text = value;
    for (const [api, urls] of replacements) {
      const escaped = api.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      // Do not rewrite the API prefix of a /download/json URL.
      text = text.replace(new RegExp(escaped + '(?=[\\s)\\]<>]|$)', 'g'), [...urls].join(' ; '));
    }
    if (!text.includes(DATASET_PAGE)) text += '\nDataset dasar dan metode (UMD 2000–2025): ' + DATASET_PAGE;
    return text;
  }
  updated.answer = replaceText(result.answer);
  if (updated.parsed) {
    updated.parsed.raw_answer = replaceText(result.parsed.raw_answer);
    const links = result.parsed.link_sumber;
    const fixed = [...new Set((Array.isArray(links) ? links : [links]).filter(Boolean)
      .flatMap(link => replacements.has(link) ? [...replacements.get(link)] : [link]))];
    updated.parsed.link_sumber = fixed.length === 1 ? fixed[0] : fixed;
  }
  return updated;
}

export function gfwEvidenceCsv(result) {
  const rows = [...(result?.evidence || []), ...(result?.context || []), ...(result?.parsed?.download_records || [])]
    .filter(row => IDENTITY.test(row?.source_record_id || '') || EXPANSION.test(row?.source_record_id || ''));
  if (!rows.length) return '';
  const unique = [...new Map(rows.map(row => [row.id || row.source_record_id, row])).values()];
  const fields = ['area','year','period_text','temporal_basis','period_start','period_end','aggregation_kind','indicator','value','unit','source','source_url','api_source_url',
    'download_url','methodology_url','source_record_id','definition','method','source_note'];
  const cell = (value, field) => {
    let text = String(value ?? '');
    if (/^[=+@\-\t\r\n]/.test(text) && !(field === 'value' && /^-?\d+(?:\.\d+)?$/.test(text))) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  return '\uFEFF' + [fields.map(cell).join(','), ...unique.map(row => fields.map(f => cell(row[f], f)).join(','))].join('\r\n') + '\r\n';
}

export function gfwSourceGroups(items) {
  const groups = new Map();
  for (const item of items) {
    const version = item.source_record_id?.split(':')[2] || '';
    const source = item.source || 'Global Forest Watch / UMD GLAD';
    const key = `${source}|${version}`;
    if (!groups.has(key)) groups.set(key, { source, version, items: [] });
    groups.get(key).items.push(item);
  }
  return [...groups.values()].map(group => {
    const links = [...new Map(group.items.filter(item => item.url).map(item => [item.url,
      { url: item.url, area: item.area || '' }])).values()];
    // Distinct regional dashboards are separate reading links, not a reason
    // to replace all of them with the generic methodology page.
    return { ...group, links, url: links.length === 1 ? links[0].url : undefined };
  });
}

export function gfwArchiveDownloads(result) {
  const links = new Map();
  for (const item of result?.parsed?.source_items || []) {
    const match = IDENTITY.exec(item?.source_record_id || '');
    if (!match || match[2] !== 'v20260424') continue;
    const [, level, , code] = match;
    const slug = level === 'iso' && code === 'None' ? 'iso-IDN'
      : level === 'adm1' && /^\d+$/.test(code) ? `adm1-${code}`
      : level === 'adm2' && /^\d+\.\d+$/.test(code) ? `adm2-${code.replace('.', '-')}` : '';
    if (slug) links.set(slug, `/gfw-evidence/${slug}.csv`);
  }
  return [...links.values()];
}
