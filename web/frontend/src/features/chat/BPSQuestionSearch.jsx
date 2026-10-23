import React, { useEffect, useRef, useState } from 'react';
import { requestJson } from '../../services/httpClient.js';

export default function BPSQuestionSearch() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const active = useRef(null);
  const revision = useRef(0);
  useEffect(() => () => { revision.current += 1; active.current?.abort(); }, []);
  function change(value) {
    revision.current += 1;
    active.current?.abort();
    setQuestion(value); setResult(null); setError(false); setBusy(false);
  }
  async function submit(event) {
    event.preventDefault();
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    const version = ++revision.current;
    const timeout = setTimeout(() => controller.abort(), 20000);
    setBusy(true); setResult(null); setError(false);
    try {
      const data = await requestJson('/search/bps/statistics/question', {
        method: 'POST', body: { question }, signal: controller.signal,
      });
      if (version === revision.current && !controller.signal.aborted) setResult(data);
    } catch {
      if (version === revision.current) setError(true);
    } finally {
      clearTimeout(timeout);
      if (version === revision.current) setBusy(false);
    }
  }
  const complete = result?.complete === true && result?.abstained === false;
  return <section aria-label="Pertanyaan angka BPS" style={{ marginTop: 16 }}>
    <form onSubmit={submit}>
      <label htmlFor="bps-question">Pertanyaan BPS</label>
      <textarea id="bps-question" value={question} onChange={event => change(event.target.value)}
        maxLength={512} required rows={3} style={{ display: 'block', width: '100%', margin: '8px 0' }} />
      <p>Gunakan nama indikator dan wilayah dari pilihan di bawah, beserta tahun.
        Untuk tren, tulis “dari 2020 sampai 2023”.</p>
      <button type="submit" disabled={busy || !question.trim()}>{busy ? 'Memeriksa…' : 'Tanyakan angka'}</button>
    </form>
    {error && <p role="alert">Pertanyaan belum dapat diverifikasi. Silakan coba lagi.</p>}
    {result && !complete && <p role="status">Pertanyaan atau cakupan datanya belum dapat dipastikan.
      Gunakan nama sesuai katalog dan tahun yang eksplisit, atau gunakan formulir pilihan di bawah.</p>}
    {complete && <div aria-live="polite">
      <ul>{(result.observations || []).map(point => <li key={point.canonical.evidence_id}>
        {point.canonical.area_name} · {point.year}: <strong>{point.value} {point.unit}</strong>{' '}
        {(point.canonical.citations || []).filter(citation => /^https:\/\//i.test(citation.source_url)).map((citation, index) =>
          <a key={index} href={citation.source_url} target="_blank" rel="noopener noreferrer">Sumber {index + 1}</a>)}
      </li>)}</ul>
      {(result.derived || []).map((item, index) => <p key={index}>
        Selisih dari {item.baseline.canonical.area_name} ({item.baseline.year})
        {' '}ke {item.target.canonical.area_name} ({item.target.year}): {item.value} {item.unit}.
      </p>)}
    </div>}
  </section>;
}
