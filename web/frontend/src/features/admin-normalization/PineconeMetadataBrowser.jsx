import React, { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../config/api';

const num = n => n == null ? '—' : Number(n).toLocaleString('id-ID');
const style = { padding: 12, border: '1px solid #ded6d0', borderRadius: 10, background: 'white', maxWidth: '100%' };
export default function PineconeMetadataBrowser({ getToken, onAuthExpired }) {
  const callbacks = useRef({ getToken, onAuthExpired }); callbacks.current = { getToken, onAuthExpired };
  const [inventory, setInventory] = useState(null), [index, setIndex] = useState(''), [namespace, setNamespace] = useState('');
  const [data, setData] = useState(null), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [cursor, setCursor] = useState(''), [history, setHistory] = useState([]), [revision, setRevision] = useState(0);
  const [query, setQuery] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 20000);
    fetch(`${API_BASE}/admin/storage/inventory`, { headers: { Authorization: `Bearer ${callbacks.current.getToken()}` }, signal: controller.signal })
      .then(async response => {
        if (response.status === 401) callbacks.current.onAuthExpired?.();
        if (!response.ok) throw new Error();
        const result = await response.json();
        if (!Array.isArray(result.pinecone)) throw new Error();
        if (controller.signal.aborted) return;
        setInventory(result);
        setIndex(current => current || result.pinecone.find(row => row.index === 'cekdata-dev-bps')?.index || result.pinecone[0]?.index || '');
      }).catch(() => { if (!controller.signal.aborted) setError('Statistik indeks belum tersedia. Tekan Refresh Data untuk mencoba lagi.'); })
      .finally(() => clearTimeout(deadline));
    return () => { clearTimeout(deadline); controller.abort(); };
  }, [revision]);
  useEffect(() => {
    if (!index) return;
    const controller = new AbortController(); let disposed = false;
    const timer = setTimeout(() => controller.abort(), 45000);
    setLoading(true); setError(''); setData(null);
    fetch(`${API_BASE}/admin/pinecone/metadata-page`, { method: 'POST',
      headers: { Authorization: `Bearer ${callbacks.current.getToken()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ index, namespace, cursor, limit: 20 }), signal: controller.signal,
    }).then(async response => {
      if (response.status === 401) callbacks.current.onAuthExpired?.();
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (!Array.isArray(result.records)) throw new Error();
      if (!disposed) setData(result);
    }).catch(() => { if (!disposed) setError('Metadata belum dapat dibaca dan disimpan lengkap ke MySQL. Tekan Refresh Data untuk mencoba halaman ini lagi.'); })
      .finally(() => { clearTimeout(timer); if (!disposed) setLoading(false); });
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, [index, namespace, cursor, revision]);
  const selected = inventory?.pinecone?.find(row => row.index === index);
  const selectedNamespace = selected?.namespaces?.find(row => (row.name === '__default__' ? '' : row.name) === namespace);
  function changeIndex(value) {
    const scopes = inventory?.pinecone?.find(row => row.index === value)?.namespaces || [];
    const preferred = scopes.some(row => !row.name || row.name === '__default__') ? '' : scopes[0]?.name || '';
    setIndex(value); setNamespace(preferred); setCursor(''); setHistory([]); setQuery('');
  }
  const rows = (data?.records || []).filter(row => JSON.stringify(row).toLowerCase().includes(query.toLowerCase()));
  return <section aria-label="Daftar metadata Pinecone" style={{ background: 'white', border: '1px solid #e2dcd6', borderRadius: 18, padding: 28, minWidth: 0 }}>
    <h2 style={{ marginTop: 0 }}>Daftar data Pinecone per indeks</h2>
    <p>Halaman dibaca dari Pinecone, metadata disimpan dan dibaca kembali dari MySQL. Pilih indeks dan namespace untuk melihat isi datanya.</p>
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      <label>Indeks<br /><select style={style} aria-label="Indeks metadata Pinecone" value={index} onChange={e => changeIndex(e.target.value)}>
        {!inventory && <option value="">Memuat indeks…</option>}
        {inventory?.pinecone?.map(row => <option key={row.index} value={row.index}>{row.index}</option>)}
      </select></label>
      <label>Namespace<br /><select style={style} aria-label="Namespace metadata Pinecone" value={namespace} onChange={e => { setNamespace(e.target.value); setCursor(''); setHistory([]); }}>
        <option value="">(default)</option>
        {selected?.namespaces?.filter(row => row.name && row.name !== '__default__').map(row => <option key={row.name} value={row.name}>{row.name}</option>)}
      </select></label>
      <button style={style} disabled={loading} onClick={() => setRevision(n => n + 1)}>Refresh Data</button>
    </div>
    <p><strong>{index || '—'}</strong> · namespace <strong>{namespace || '(default)'}</strong></p>
    <p>Total indeks: <strong>{selected?.status === 'ok' ? num(selected.count) : 'Belum tersedia'}</strong> vektor · Namespace terpilih: <strong>{selected?.status === 'ok' ? num(selectedNamespace?.count ?? 0) : 'Belum tersedia'}</strong> vektor.</p>
    {namespace === 'legacy-kresna-inbox-v1' && <p style={{ color: '#85551f' }}>Inbox impor Kresna: metadata sumber belum semuanya dinormalisasi atau layak untuk jawaban angka.</p>}
    {index === 'cekdata-ai-kresna' && <p>Indeks sumber Kresna. Membuka daftar ini tidak memindahkan atau mengubah vektor sumber.</p>}
    <p style={{ color: '#766f69', fontSize: 13 }}>Total berasal dari statistik Pinecone dan dapat terlambat mengikuti impor. Tabel MySQL <code>pinecone_metadata_inventory</code> menyimpan halaman yang sudah dibaca; belum merupakan mirror lengkap seluruh indeks. Status metadata bukan bukti akurasi atau kesiapan pencarian.</p>
    <label>Cari pada halaman ini <input style={style} value={query} onChange={e => setQuery(e.target.value)} placeholder="Judul, wilayah, sumber, atau ID" /></label>
    {loading && <p role="status">Membaca metadata dan menyimpan halaman ke MySQL…</p>}
    {error && <p role="alert">{error}</p>}
    {data && <>
      <p>Halaman {history.length + 1} · {data.page_count} metadata tersimpan · {rows.length} ditampilkan · {new Date(data.checked_at).toLocaleString('id-ID')}</p>
      {rows.map(row => {
        const meta = row.metadata || {};
        return <article key={row.vector_id} style={{ padding: 16, border: '1px solid #e4dcd6', borderRadius: 12, marginTop: 12, overflowWrap: 'anywhere' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', color: '#86536d', fontSize: 12 }}><strong>{row.index}</strong><span>{row.namespace || '(default)'}</span></div>
          <h3 style={{ fontSize: 16 }}>{String(meta.title || meta.series_label || meta.indicator || meta.statement || meta.source_file || row.vector_id)}</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, fontSize: 13 }}>
            <div><strong>Indikator:</strong> {String(meta.series_label || meta.parameter_name || meta.indicator_code || '—')}</div>
            <div><strong>Wilayah:</strong> {String(meta.area_name || '—')}</div>
            <div><strong>Periode:</strong> {String(meta.period || meta.year || meta.period_start || '—')}</div>
            <div><strong>Satuan:</strong> {String(meta.unit || '—')}</div>
            <div><strong>Sumber:</strong> {String(meta.source || meta.source_domain || '—')}</div>
            <div><strong>Berkas:</strong> {String(meta.source_file || meta.source_filename_original || '—')}</div>
          </div>
          <p style={{ fontSize: 13 }}>ID: {row.vector_id}</p>
          <details><summary>Lihat semua metadata</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: 12 }}>{JSON.stringify(meta, null, 2)}</pre></details>
        </article>;
      })}
      {!rows.length && <p>{data.page_count ? 'Tidak ada kecocokan pada halaman ini.' : 'Tidak ada vektor pada halaman namespace ini.'}</p>}
      <div style={{ display: 'flex', gap: 12, marginTop: 18 }}>
        <button style={style} disabled={loading || !history.length} onClick={() => { setCursor(history[history.length - 1]); setHistory(h => h.slice(0, -1)); }}>Sebelumnya</button>
        <button style={style} disabled={loading || !data.next_cursor} onClick={() => { setHistory(h => [...h, cursor]); setCursor(data.next_cursor); }}>Berikutnya</button>
      </div>
    </>}
  </section>;
}
