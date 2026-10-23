const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function verifiedSourcesFromClaims(claims, { pageHostname = globalThis.location?.hostname } = {}) {
  if (!Array.isArray(claims)) return [];
  const seen = new Set();
  const result = [];
  for (const claim of claims) {
    if (!String(claim?.evidence_id || '').trim() || !String(claim?.document_version_id || '').trim()
        || !/^[a-f0-9]{64}$/i.test(claim?.document_checksum || '')) continue;
    for (const citation of Array.isArray(claim?.citations) ? claim.citations : []) {
      const sourceUrl = safeHttpUrl(citation?.source_url);
      const downloadUrl = safeHttpUrl(citation?.download_url, LOOPBACK_HOSTS.has(pageHostname));
      const citationId = String(citation?.citation_id || "").trim();
      if (!citationId || !sourceUrl) continue;
      const key = `${claim.evidence_id}:${claim.document_version_id}:${citationId}:${sourceUrl}:${downloadUrl}`;
      if (seen.has(key)) continue;
      seen.add(key);
      result.push({
        citationId,
        locator: String(citation?.locator || "").trim(),
        sourceUrl,
        downloadUrl,
        evidenceId: String(claim?.evidence_id || "").trim(),
        documentVersionId: String(claim?.document_version_id || "").trim(),
        documentChecksum: String(claim?.document_checksum || "").trim(),
      });
    }
  }
  return result;
}

function safeHttpUrl(value, allowLocalSnapshot = false) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const url = new URL(raw);
    const localSnapshot = allowLocalSnapshot && url.protocol === "http:"
      && LOOPBACK_HOSTS.has(url.hostname)
      && /^\/connectors\/gfw\/snapshots\/[a-f0-9]{64}\.json$/.test(url.pathname)
      && !url.search && !url.hash;
    return (url.protocol === "https:" || localSnapshot) && !url.username && !url.password ? url.href : "";
  } catch {
    return "";
  }
}
