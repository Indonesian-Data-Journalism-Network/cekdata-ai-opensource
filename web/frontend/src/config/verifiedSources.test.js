import assert from "node:assert/strict";
import test from "node:test";

import { verifiedSourcesFromClaims } from "./verifiedSources.js";

test("verified sources expose canonical download metadata", () => {
  const result = verifiedSourcesFromClaims([{ evidence_id: "e1", document_version_id: "v1", document_checksum: "a".repeat(64), citations: [{ citation_id: "c1", locator: "Tabel 1", source_url: "https://example.test/source", download_url: "https://example.test/file.csv" }] }]);

  assert.equal(result[0].evidenceId, "e1");
  assert.equal(result[0].downloadUrl, "https://example.test/file.csv");
  assert.equal(result[0].documentChecksum.length, 64);
});

test("verified sources reject non-http URLs and duplicate citations", () => {
  const citation = { citation_id: "c1", source_url: "javascript:alert(1)" };
  assert.deepEqual(verifiedSourcesFromClaims([{ citations: [citation, citation] }]), []);
});

test("local GFW snapshot downloads work only from a local app", () => {
  const download = `http://127.0.0.1:8001/connectors/gfw/snapshots/${'a'.repeat(64)}.json`;
  const claims = [{ evidence_id: 'e1', document_version_id: 'v1', document_checksum: 'a'.repeat(64),
    citations: [{ citation_id: 'c1', source_url: 'https://data-api.globalforestwatch.org/dataset/test', download_url: download }] }];
  assert.equal(verifiedSourcesFromClaims(claims, { pageHostname: 'localhost' })[0].downloadUrl, download);
  assert.equal(verifiedSourcesFromClaims(claims, { pageHostname: 'cekdata.example' })[0].downloadUrl, '');
  for (const invalid of [download.replace('127.0.0.1', 'localhost.evil.test'), 'http://127.0.0.1:8001/admin', download + '?token=x']) {
    claims[0].citations[0].download_url = invalid;
    assert.equal(verifiedSourcesFromClaims(claims, { pageHostname: 'localhost' })[0].downloadUrl, '');
  }
});
