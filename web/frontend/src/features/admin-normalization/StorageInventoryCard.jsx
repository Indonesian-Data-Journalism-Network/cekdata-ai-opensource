import React, { useEffect, useRef, useState } from 'react';
import { Database, Layers3, RefreshCw } from 'lucide-react';
import { API_BASE } from '../../config/api';

const format = value => value == null ? '—' : Number(value).toLocaleString('id-ID');
const number = row => `${row.count_kind === 'estimate' ? '≈ ' : row.count_kind === 'lower_bound' ? '≥ ' : ''}${format(row.count)}`;
const cell = { textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid #ece6e1', verticalAlign: 'top' };

export default function StorageInventoryCard({ getToken, onAuthExpired }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const callbacks = useRef({ getToken, onAuthExpired });
  callbacks.current = { getToken, onAuthExpired };
  useEffect(() => {
    let disposed = false, timer, controller;
    async function refresh() {
      setLoading(true);
      controller = new AbortController();
      const deadline = setTimeout(() => controller.abort(), 20000);
      let interval = 60000;
      try {
        const token = callbacks.current.getToken();
        if (!token) throw new Error('Session missing');
        const response = await fetch(`${API_BASE}/admin/storage/inventory`, {
          headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
        });
        if (response.status === 401) callbacks.current.onAuthExpired?.();
        if (!response.ok) throw new Error('Inventory unavailable');
        const result = await response.json();
        if (!result.mysql || !Array.isArray(result.pinecone)) throw new Error('Invalid inventory');
        interval = result.refresh_seconds === 5 ? 5000 : 60000;
        if (!disposed) { setData(result); setError(false); }
      } catch {
        if (!disposed) setError(true);
      } finally {
        clearTimeout(deadline);
        if (!disposed) { setLoading(false); timer = setTimeout(refresh, interval); }
      }
    }
    refresh();
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); };
  }, [revision]);
  return <section aria-label="Inventori MySQL dan Pinecone" style={{ background: 'white', border: '1px solid #e2dcd6', borderRadius: 18, padding: 24 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <div><h2 style={{ fontSize: 21, margin: 0 }}>Data MySQL & Pinecone</h2>
        <p style={{ fontSize: 13, color: '#766f69', marginBottom: 0 }}>Jumlah record, indeks, dan namespace yang digunakan aplikasi.</p></div>
      <button type="button" disabled={loading} onClick={() => setRevision(value => value + 1)}
        style={{ display: 'flex', gap: 7, alignItems: 'center', background: '#f7f3ef', border: '1px solid #ddd6d0', borderRadius: 10, padding: '9px 12px', cursor: loading ? 'wait' : 'pointer' }}>
        <RefreshCw size={14} />{loading ? 'Memeriksa…' : 'Periksa lagi'}
      </button>
    </div>
    {error && <p role="alert">Inventori belum dapat diperbarui. {data && 'Data di bawah adalah hasil pemeriksaan sebelumnya.'}</p>}
    {!data && !error && <p role="status">Mengambil jumlah data dan namespace…</p>}
    {data && <>
      <p style={{ color: '#766f69', fontSize: 12 }}>Pemeriksaan: {data.checked_at ? new Date(data.checked_at).toLocaleString('id-ID') : 'sedang berlangsung'} · Cache maksimal 1 menit.</p>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Database size={18} /> MySQL {data.mysql.database && <code style={{ fontSize: 14 }}>{data.mysql.database}</code>}</h3>
      {data.mysql.status === 'ok' ? <>
        <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <caption style={{ textAlign: 'left', paddingBottom: 8, color: '#766f69' }}>Tabel pada database aplikasi. ≈ estimasi MySQL; ≥ batas minimum.</caption>
          <thead><tr><th style={cell}>Data / tabel</th><th style={{ ...cell, textAlign: 'right' }}>Jumlah baris</th><th style={cell}>Keterangan</th></tr></thead>
          <tbody>{(data.mysql.tables || []).map(row => <tr key={row.table}>
            <td style={cell}><strong>{row.label}</strong><div style={{ color: '#766f69', marginTop: 4 }}><code>{row.table}</code></div></td>
            <td style={{ ...cell, textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>{row.status === 'ok' ? number(row) : '—'}</td>
            <td style={cell}>{row.status === 'missing' ? 'Tabel belum tersedia' : row.note}</td>
          </tr>)}</tbody>
        </table></div>
        {data.mysql.shards_configured && <p role="status">Hitungan ini hanya mencakup database control; database data shard belum termasuk.</p>}
      </> : <p role="status">{data.mysql.status === 'loading' ? 'Memeriksa MySQL…' : 'Jumlah data MySQL belum dapat dibaca.'}</p>}
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 26 }}><Layers3 size={18} /> Pinecone</h3>
      {!data.pinecone.length && <p>Belum ada indeks Pinecone yang dikonfigurasi untuk aplikasi.</p>}
      {data.pinecone.map(index => <div key={index.index} style={{ border: '1px solid #e6dfda', borderRadius: 12, padding: 16, marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
          <strong style={{ overflowWrap: 'anywhere' }}>{index.index}</strong>
          {index.status === 'ok' && <span><strong>{format(index.count)}</strong> vektor · {format(index.namespace_count)} namespace</span>}
        </div>
        {index.status !== 'ok' ? <p role="status">{index.status === 'loading' ? 'Memeriksa indeks…' : 'Statistik indeks belum tersedia; bukan berarti kosong.'}</p> : <>
          <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10, fontSize: 13 }}>
            <thead><tr><th style={cell}>Namespace</th><th style={{ ...cell, textAlign: 'right' }}>Jumlah vektor</th></tr></thead>
            <tbody>{index.namespaces.map(namespace => <tr key={namespace.name}>
              <td style={{ ...cell, overflowWrap: 'anywhere' }}><code>{namespace.label}</code>
                {namespace.name === 'legacy-kresna-inbox-v1' && <div style={{ marginTop: 4, color: '#85551f' }}>Inbox impor Kresna · belum semuanya kanonis</div>}
              </td><td style={{ ...cell, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{format(namespace.count)}</td>
            </tr>)}</tbody>
          </table></div>
          {index.namespaces_truncated && <p role="status">Hanya 1.000 namespace pertama ditampilkan.</p>}
          {!index.namespaces.length && <p>Belum ada namespace berisi vektor yang dilaporkan.</p>}
        </>}
      </div>)}
      <p style={{ fontSize: 12, color: '#766f69', lineHeight: 1.6, marginBottom: 0 }}>Angka Pinecone berasal dari statistik provider dan dapat terlambat mengikuti impor. Jumlah vektor bukan jumlah fakta unik: satu fakta bisa mempunyai salinan di beberapa namespace. Baris antar tabel MySQL juga dapat merujuk fakta yang sama.</p>
    </>}
  </section>;
}
