import React from 'react';
import { canonicalAnswerView } from './answerView.js';

export default function CanonicalAnswer({ result, onClarify, clarificationDisabled = false }) {
  const view = canonicalAnswerView(result);
  if (!view) return null;
  return <section aria-label="Hasil pemeriksaan" style={{ lineHeight: 1.7, overflowWrap: 'anywhere', paddingTop: 24 }}>
    {result.search_preview?.source === 'environment' && <p role="status">
      Uji coba Environment: cakupan dan akurasi pencarian masih dievaluasi.
    </p>}
    {result.conversation_scope?.resolved && result.conversation_scope.resolved_question !== result.conversation_scope.original_question && <p role="note">
      Pencarian lanjutan: {result.conversation_scope.resolved_question}
    </p>}
    <h3 style={{ margin: '0 0 8px' }}>{view.title}</h3>
    <p role={view.status === 'verified' ? undefined : 'status'}>{view.message}</p>
    {view.status === 'verified' && result.answer_origin === 'registered-statistics-v1' && result.source_table_coverage === 'partial' && <p role="note">
      Sebagian sel tabel sumber belum dapat ditafsirkan. Jawaban hanya mencakup angka yang terverifikasi, bukan total seluruh komponen.
    </p>}
    {view.choices && <div aria-label={view.source === 'environment' || result.clarification?.kind === 'bps_series' ? 'Pilihan pencarian' : 'Pilihan tahun yang tersedia'} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {view.choices.map(choice => <button type="button" key={choice.question}
        disabled={clarificationDisabled || !onClarify} onClick={() => onClarify(choice.question, view.source)}>{choice.label}</button>)}
      {view.hasMore && <p>Katalog memiliki pilihan lain. Anda juga dapat memperjelas pertanyaan yang diinginkan.</p>}
    </div>}
    {['primary', 'supporting'].map(role => <React.Fragment key={role}>
    {role === 'supporting' && view.claims.some(claim => claim.evidence_role === role) && <h3>Temuan pendukung lintas sumber</h3>}
    {view.claims.filter(claim => (claim.evidence_role || 'primary') === role).map((claim, index) => <div key={`${claim.evidence_id}:${index}`} style={{ marginTop: 16 }}>
      {claim.source_domain && <strong>{({ bps: 'BPS', legal: 'Legal', environment: 'Environment' })[claim.source_domain]}</strong>}
      <p style={{ whiteSpace: 'pre-wrap', marginBottom: 4 }}>{claim.text}</p>
      <small>Rujukan: {claim.citation_ids.join(', ')}</small>
      {role === 'supporting' && claim.relationships?.map(link => <p key={link.relationship_id} style={{ fontSize: 13 }}>
        Hubungan: {link.relationship_type}. {link.rationale}
        <br />Arah: {link.source_evidence_id} → {link.target_evidence_id}
      </p>)}
    </div>)}
    </React.Fragment>)}
    {view.calculations?.length > 0 && <section aria-label="Perhitungan dari data sumber">
      <h4>Perhitungan dari data sumber</h4>
      {view.calculations.map((item, index) => <div key={index}>
        <p>{item.text}</p><small>Rujukan kedua nilai: {item.citations.join(', ')}</small>
      </div>)}
    </section>}
    {view.status === 'verified' && ['not_found', 'unavailable'].includes(result.support_status) && <p role="status">
      {result.support_status === 'unavailable' ? 'Sumber pendukung belum dapat diperiksa. Temuan utama tetap tersedia.'
        : 'Belum ditemukan hubungan lintas sumber yang memenuhi verifikasi dalam batas pencarian ini.'}
    </p>}
    {view.sources.length > 0 && <section aria-label="Sumber terverifikasi">
      <h4>Sumber terverifikasi</h4>
      {view.sources.map((source, index) => <article key={`${source.evidenceId}:${source.citationId}:${index}`} style={{ border: '1px solid #ddd', borderRadius: 12, padding: 12, marginTop: 10 }}>
        <strong>{source.locator || source.citationId}</strong>
        <div style={{ fontSize: 13 }}>{new URL(source.sourceUrl).hostname}</div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
          <a href={source.sourceUrl} target="_blank" rel="noopener noreferrer">Buka sumber</a>
          {source.downloadUrl && <a href={source.downloadUrl} target="_blank" rel="noopener noreferrer">Unduh file</a>}
        </div>
        <details style={{ marginTop: 8, fontSize: 12 }}><summary>Detail rujukan</summary>
          <div>ID rujukan: {source.citationId}</div><div>Evidence: {source.evidenceId}</div>
          <div>Versi: {source.documentVersionId}</div><div>Checksum: {source.documentChecksum}</div>
        </details>
      </article>)}
    </section>}
  </section>;
}
