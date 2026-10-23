import { verifiedSourcesFromClaims } from '../../config/verifiedSources.js';

function decimal(value) {
  if (typeof value !== 'string' || !/^-?\d{1,40}(?:\.\d{1,30})?$/.test(value)) return null;
  const [integer, fraction = ''] = value.split('.');
  return { value: BigInt(integer + fraction), scale: fraction.length };
}

function calculationsView(result) {
  if (result.calculations === undefined) return [];
  if (result.answer_origin !== 'registered-statistics-v1' || !Array.isArray(result.calculations)
      || result.calculations.length > 200) return null;
  const byId = new Map(result.claims.map(claim => [claim.evidence_id, claim]));
  if (byId.size !== result.claims.length) return null;
  const output = [];
  for (const item of result.calculations) {
    const baseline = byId.get(item.baseline_evidence_id);
    const target = byId.get(item.target_evidence_id);
    if (!baseline || !target || baseline === target || item.formula !== 'target - baseline') return null;
    const a = baseline.statistic, b = target.statistic;
    const av = decimal(a?.value), bv = decimal(b?.value), difference = decimal(item.value);
    if (!av || !bv || !difference || !a.unit || a.unit !== b.unit || !a.area_name || !b.area_name
        || !Number.isInteger(a.year) || !Number.isInteger(b.year)) return null;
    if ((a.month !== undefined || b.month !== undefined) && (!Number.isInteger(a.month)
        || !Number.isInteger(b.month) || a.month < 1 || a.month > 12 || b.month < 1 || b.month > 12)) return null;
    const unit = ['percent', 'persen', '%'].includes(b.unit.toLowerCase()) ? 'percentage_point' : b.unit;
    if (item.unit !== unit) return null;
    const scale = Math.max(av.scale, bv.scale, difference.scale);
    const scaled = number => number.value * 10n ** BigInt(scale - number.scale);
    if (scaled(bv) - scaled(av) !== scaled(difference)) return null;
    const period = point => point.month === undefined ? String(point.year) : `${point.year}-${String(point.month).padStart(2, '0')}`;
    output.push({ text: `Selisih dari ${a.area_name} (${period(a)}) ke ${b.area_name} (${period(b)}): ${item.value} ${item.unit}.`,
      citations: [...new Set([...baseline.citation_ids, ...target.citation_ids])] });
  }
  return output;
}

export function canonicalAnswerView(result) {
  if (!result || (!Object.hasOwn(result, 'claims') && !Object.hasOwn(result, 'abstained'))) return null;
  const unavailable = {
    status: 'unverified', title: 'Bukti belum cukup', claims: [], sources: [],
    message: 'Belum ada bukti terverifikasi yang cukup untuk menilai klaim ini. Sebutkan indikator, wilayah, dan periode yang lebih spesifik. Ini tidak berarti klaim tersebut salah.',
  };
  if (result.abstained === true) {
    const reason = String(result.abstention_reason || '');
    if (['explicit_month_required', 'explicit_continuous_month_range_required'].includes(reason)) {
      return { ...unavailable, title: 'Sebutkan bulan pengamatan',
        message: 'Seri ini memakai data bulanan. Tuliskan bulan dan tahun, misalnya Januari 2020, atau rentang Januari sampai Maret 2020.' };
    }
    if (reason.includes('unsupported_environment_period')) {
      return { ...unavailable, title: 'Perjelas periode pengamatan',
        message: 'Tuliskan satu bulan dan tahun, atau rentang tanggal lengkap, misalnya periode 2021-03-01 sampai 2021-03-31. Periode relatif belum dapat ditentukan dengan aman.' };
    }
    if (/timeout|capacity|unavailable|incomplete_retrieval|all_retrieval_channels_failed/.test(reason)) {
      return { ...unavailable, title: 'Pencarian belum selesai',
        message: 'Sebagian sumber belum dapat diperiksa. Coba kirim kembali; belum ada kesimpulan atas klaim ini.' };
    }
    const guide = result.clarification;
    if (guide?.kind === 'conversation_scope' && ['bps','environment','legal'].includes(guide.source)
        && typeof guide.prompt === 'string' && guide.prompt.length <= 500
        && Array.isArray(guide.choices) && guide.choices.length <= 1
        && guide.choices.every(c => typeof c.label === 'string' && c.label.length <= 350
          && typeof c.question === 'string' && c.question.length >= 3 && c.question.length <= 1600)) {
      return {...unavailable, title:'Perjelas pertanyaan lanjutan', message:guide.prompt,
        choices:guide.choices,source:guide.source,hasMore:false};
    }
    if (result.response_contract === 'primary-support-v1' && ['environment_period','environment_metric'].includes(guide?.kind)
        && guide.source === 'environment' && typeof guide.prompt === 'string' && guide.prompt.length <= 500
        && Array.isArray(guide.choices) && guide.choices.length <= 5
        && guide.choices.every(choice => typeof choice.label === 'string' && choice.label.length <= 350
          && typeof choice.question === 'string' && choice.question.length >= 3 && choice.question.length <= 1600)) {
      return { ...unavailable, status: 'needs_clarification', title: guide.kind === 'environment_metric' ? 'Perjelas indikator' : 'Pilih periode data',
        message: guide.prompt, choices: guide.choices, source: 'environment', hasMore: guide.has_more === true };
    }
    if (result.answer_origin === 'registered-statistics-v1' && guide?.kind === 'bps_series'
        && guide.source === 'bps' && typeof guide.prompt === 'string' && guide.prompt.length <= 500
        && Array.isArray(guide.choices) && guide.choices.length > 0 && guide.choices.length <= 5
        && guide.choices.every(choice => typeof choice.label === 'string' && choice.label.length <= 350
          && typeof choice.question === 'string' && choice.question.length >= 3 && choice.question.length <= 512)) {
      return { ...unavailable, status: 'needs_clarification', title: 'Pilih seri BPS',
        message: guide.prompt, choices: guide.choices, source: 'bps', hasMore: guide.has_more === true };
    }
    if (result.answer_origin === 'registered-statistics-v1' && guide?.kind === 'available_year'
        && typeof guide.prompt === 'string' && guide.prompt.length <= 500
        && Array.isArray(guide.choices) && guide.choices.length > 0 && guide.choices.length <= 5
        && guide.choices.every(choice => typeof choice.label === 'string' && /^\d{4}$/.test(choice.label)
          && typeof choice.question === 'string' && choice.question.length <= 512)) {
      return { ...unavailable, status: 'needs_clarification', title: 'Pilih periode data',
        message: guide.prompt, choices: guide.choices, source: 'bps', hasMore: guide.has_more === true };
    }
    return unavailable;
  }
  if (result.abstained !== false || !Array.isArray(result.claims) || !result.claims.length) return unavailable;
  for (const claim of result.claims) {
    const sources = verifiedSourcesFromClaims([claim]);
    const ids = claim?.citation_ids;
    if (typeof claim?.text !== 'string' || !claim.text.trim() || !sources.length
        || !Array.isArray(ids) || ids.length !== sources.length || new Set(ids).size !== ids.length
        || !ids.every(id => sources.some(source => source.citationId === id))
        || sources.length !== claim.citations.length) return unavailable;
  }
  if (result.response_contract === 'primary-support-v1') {
    const primary = result.claims.filter(claim => claim.evidence_role === 'primary');
    const primarySource = primary[0]?.source_domain;
    const selected = result.retrieval_scope?.requested_sources;
    if (!primary.length || !['bps', 'legal', 'environment'].includes(primarySource)
        || primary.some(claim => claim.source_domain !== primarySource)
        || (selected?.length === 1 && selected[0] !== primarySource)) return unavailable;
    for (const claim of result.claims) {
      if (!['primary', 'supporting'].includes(claim.evidence_role)) return unavailable;
      if (claim.evidence_role === 'supporting' && (
        !['bps', 'legal', 'environment'].includes(claim.source_domain) || claim.source_domain === primarySource
        || !Array.isArray(claim.relationships) || !claim.relationships.length
        || claim.relationships.some(link => !link.relationship_id || !link.intersection_version_id || !link.relationship_type
          || !primary.some(item => item.evidence_id === link.primary_evidence_id)
          || ![link.source_evidence_id, link.target_evidence_id].includes(claim.evidence_id)
          || ![link.source_evidence_id, link.target_evidence_id].includes(link.primary_evidence_id)
          || claim.evidence_id === link.primary_evidence_id))) return unavailable;
    }
  }
  const calculations = calculationsView(result);
  if (calculations === null) return unavailable;
  return { status: 'verified', title: 'Temuan utama',
    message: 'Temuan berikut merupakan bukti untuk menilai klaim; bukan otomatis vonis benar atau salah.',
    claims: result.claims, sources: verifiedSourcesFromClaims(result.claims), calculations };
}

export function canonicalCopyText(result) {
  const view = canonicalAnswerView(result);
  if (!view) return null;
  const preview = result.search_preview?.source === 'environment'
    ? 'Uji coba Environment: cakupan dan akurasi pencarian masih dievaluasi.\n\n' : '';
  if (view.status !== 'verified') return `${preview}${view.title}\n${view.message}`;
  return preview + [view.title, ...view.claims.map(claim => `${claim.evidence_role === 'supporting' ? 'Pendukung' : 'Utama'} (${claim.source_domain || 'sumber'}): ${claim.text} [${claim.citation_ids.join(', ')}]`),
    ...view.calculations.map(item => `${item.text} [${item.citations.join(', ')}]`),
    'Sumber terverifikasi', ...view.sources.map(source =>
      `[${source.citationId}] ${source.locator}\n${source.sourceUrl}${source.downloadUrl ? '\nUnduh: ' + source.downloadUrl : ''}`)].join('\n\n');
}

export function continuationQuestion(question, previousQuestion = '') {
  const current = question.trim();
  if (current.length < 3 || current.length > 1600) throw new Error('Tulis pertanyaan sepanjang 3–1.600 karakter.');
  // Previous scope is sent separately and resolved by the server; never append
  // old years/areas to a new question or treat earlier answer text as evidence.
  return current;
}
