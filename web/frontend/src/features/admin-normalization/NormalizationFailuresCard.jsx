import React, { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../config/api';

const count = n => n == null ? 'Belum tersedia' : Number(n).toLocaleString('id-ID');
const cell = { padding: 10, borderBottom: '1px solid #e6dfda', textAlign: 'left', verticalAlign: 'top' };
export default function NormalizationFailuresCard({ getToken, onAuthExpired }) {
  const callbacks = useRef({ getToken, onAuthExpired });
  callbacks.current = { getToken, onAuthExpired };
  const [data, setData] = useState(null), [error, setError] = useState(false), [loading, setLoading] = useState(true);
  const [after, setAfter] = useState(''), [reason, setReason] = useState(''), [revision, setRevision] = useState(0);
  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    setLoading(true); setError(false); setData(null);
    const params = new URLSearchParams({ after, reason, limit: '50' });
    fetch(`${API_BASE}/admin/normalization/failures?${params}`, {
      headers: { Authorization: `Bearer ${callbacks.current.getToken()}` }, signal: controller.signal,
    }).then(async response => {
      if (response.status === 401) callbacks.current.onAuthExpired?.();
      if (!response.ok) throw new Error('Unavailable');
      const result = await response.json();
      if (!Array.isArray(result.items)) throw new Error('Invalid response');
      if (!disposed) setData(result);
    }).catch(() => { if (!disposed) setError(true); })
      .finally(() => { clearTimeout(timer); if (!disposed) setLoading(false); });
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, [after, reason, revision]);
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'normalisasi-belum-selesai-halaman.json';
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section aria-label="Data belum dinormalisasi" style={{ background: 'white', border: '1px solid #e2dcd6', borderRadius: 18, padding: 24, minWidth: 0 }}>
    <h2 style={{ marginTop: 0 }}>Data belum berhasil dinormalisasi</h2>
    <p>Status terakhir pekerjaan normalisasi pada database aplikasi. Satu pekerjaan mewakili satu berkas dalam satu batch; jumlah ini bukan jumlah vektor atau seluruh baris di dalam berkas.</p>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
      <button disabled={loading} onClick={() => setRevision(n => n + 1)}>Perbarui log</button>
      <label>Alasan: <select aria-label="Filter alasan normalisasi" value={reason} disabled={loading}
        onChange={event => { setReason(event.target.value); setAfter(''); }}>
        <option value="">Semua alasan</option>
        {(data?.summary || []).filter(row => row.reason !== 'awaiting_archive_validation').map(row =>
          <option key={row.reason} value={row.reason}>{row.label} ({count(row.count)})</option>)}
        {reason && !data?.summary?.some(row => row.reason === reason) && <option value={reason}>{reason}</option>}
      </select></label>
      <button disabled={!data || loading} onClick={download}>Unduh JSON halaman ini</button>
    </div>
    {loading && <p role="status">Membaca log normalisasi…</p>}
    {error && <p role="alert">Log belum dapat dibaca. Coba perbarui lagi; kegagalan koneksi bukan berarti tidak ada data tertahan.</p>}
    {data && <>
      <p><strong>{count(data.unresolved_count)}</strong> pekerjaan perlu tindak lanjut · <strong>{count(data.waiting_count)}</strong> menunggu pemeriksaan pertama.</p>
      <p style={{ color: '#766f69', fontSize: 12 }}>Diperiksa: {new Date(data.checked_at).toLocaleString('id-ID')}. Ringkasan mencakup semua alasan; daftar mengikuti filter. Data dapat berubah saat worker berjalan.</p>
      {!data.summary_available && <p role="status">Total belum tersedia; daftar sumber yang berhasil dibaca tetap ditampilkan.</p>}
      <div style={{ overflowX: 'auto' }}><table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead><tr>{['Sumber / batch', 'Alasan', 'Status / percobaan', 'Kandidat baris', 'Pembaruan terakhir'].map(label => <th key={label} style={cell}>{label}</th>)}</tr></thead>
        <tbody>{data.items.map(row => <tr key={row.id}>
          <td style={{ ...cell, overflowWrap: 'anywhere' }}><strong>{row.source_file}</strong><div>{row.source_domain} · {row.batch_id}</div><details><summary>Identitas sumber</summary><div>ID: {row.id}</div><div>File ID: {row.file_id}</div>{row.source_checksum && <div>SHA-256: {row.source_checksum}</div>}</details></td>
          <td style={cell}>{row.reason_label}<div><code>{row.reason}</code></div>{row.error_type && <div>{row.error_type}</div>}
            {row.diagnostics?.length > 0 && <details><summary>Rincian pemeriksaan</summary>
              {row.reviewed_at && <p>Diperiksa ulang: {new Date(row.reviewed_at).toLocaleString('id-ID')}</p>}
              <ul>{row.diagnostics.map((item, index) => <li key={index}>
                <code>{item.adapter}: {item.status}</code>
                {item.candidate_count != null && <span> · {count(item.candidate_count)} kandidat sel, belum terverifikasi</span>}
                {item.row != null && <span> · baris {item.row}</span>}
                {item.column != null && <span> · kolom {item.column}</span>}
              </li>)}</ul>
            </details>}
          </td>
          <td style={cell}>{row.state === 'held' ? 'Ditahan; perlu metode/perbaikan lain' : 'Menunggu tindak lanjut / retry'}<div>{count(row.attempt_count)} percobaan</div></td>
          <td style={cell}>{row.candidate_records == null ? 'Belum diketahui' : count(row.candidate_records)}</td>
          <td style={cell}>{new Date(row.updated_at).toLocaleString('id-ID')}</td>
        </tr>)}</tbody>
      </table></div>
      {!data.items.length && <p>Tidak ada pekerjaan tertahan yang cocok dengan filter saat pemeriksaan ini.</p>}
      <p style={{ fontSize: 12, color: '#766f69' }}>Kandidat baris adalah hasil parser sebelum lolos kualitas, bukan total data yang gagal. Log ini hanya mencakup sumber yang sudah masuk antrean normalisasi; database shard dan sumber yang belum diimpor belum tercakup. Sumber yang kemudian berhasil akan keluar dari daftar.</p>
      <div style={{ display: 'flex', gap: 12 }}><button disabled={!after || loading} onClick={() => setAfter('')}>Halaman pertama</button>
        <button disabled={!data.next_after || loading} onClick={() => setAfter(data.next_after)}>Halaman berikutnya</button></div>
    </>}
  </section>;
}
