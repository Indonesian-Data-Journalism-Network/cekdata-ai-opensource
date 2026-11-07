const isMap = item => item?.source_record_id?.startsWith('mapbiomas:landy:');

export function hasMapbiomasSources(result) {
  return (result?.parsed?.source_items || []).some(isMap);
}

export function mapbiomasSourceGroups(result) {
  const groups = new Map();
  for (const item of result?.parsed?.source_items || []) {
    if (!isMap(item)) continue;
    const version = item.dataset_version || item.source_record_id.split(':')[2];
    const key = `${item.source}|${version}|${item.url}|${item.download_url}`;
    if (!groups.has(key)) groups.set(key, {
      source: item.source || 'MapBiomas Indonesia', version,
      url: item.url, downloadUrl: item.download_url,
      downloadName: `Tutupan dan transisi lahan Indonesia — Koleksi ${version} (XLSX)`,
    });
  }
  return [...groups.values()];
}

export function mapbiomasGfwSubset(result) {
  const parsed = result?.parsed || {};
  return { ...result, parsed: { ...parsed,
    source_items: (parsed.source_items || []).filter(x => x.source_record_id?.startsWith('gfw:')),
    download_records: (parsed.download_records || []).filter(x => x.source_record_id?.startsWith('gfw:')),
  }};
}
