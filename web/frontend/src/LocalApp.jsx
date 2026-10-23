import React, { useEffect, useState } from 'react';
import { Header, ChatPage, AboutPage } from './App.jsx';
import { Button, COLORS, inputStyle } from './ui/ui.jsx';
import { requestJson } from './services/httpClient.js';

export default function LocalApp() {
  const [page, setPage] = useState('chat');
  const [configured, setConfigured] = useState(false);
  const [settings, setSettings] = useState(true);
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [recordCount, setRecordCount] = useState(null);
  useEffect(() => {
    requestJson('/local/session').then(data => {
      setConfigured(data.configured);
      setSettings(!data.configured);
      setRecordCount(data.sample_records);
    }).catch(() => setError('Layanan lokal belum terhubung. Jalankan server lokal sesuai README.'));
  }, []);

  async function connect(event) {
    event.preventDefault();
    if (busy || !key.trim()) return;
    setBusy(true); setError('');
    try {
      await requestJson('/local/session', { method: 'POST', body: { api_key: key.trim() } });
      setKey(''); setConfigured(true); setSettings(false);
    } catch (error) { setError(error.message || 'API key belum tersimpan untuk sesi ini.'); }
    finally { setBusy(false); }
  }
  async function disconnect() {
    try {
      await requestJson('/local/session', { method: 'DELETE' });
      setKey(''); setConfigured(false); setSettings(true); setPage('chat'); setError('');
    } catch { setError('Sesi belum berhasil diakhiri. Coba kembali.'); }
  }
  return <div style={{ background: COLORS.bg, color: COLORS.text, minHeight: '100vh', display: 'flex', flexDirection: 'column', fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' }}>
    <Header page={page} setPage={value => setPage(value === 'about' ? 'about' : 'chat')}
      isLoggedIn={true} isAdmin={false} handleSignOut={disconnect} />
    <div style={{ padding: '12px 24px', background: '#fff7fb', borderBottom: '1px solid rgba(239,91,156,.2)' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <div style={{ fontSize: 13, lineHeight: 1.7 }}>
          <strong style={{ color: COLORS.primaryDark }}>Uji coba lokal</strong>
          <span> · {recordCount === null ? 'Memeriksa data lokal…' : `${recordCount.toLocaleString('id-ID')} record lokal tersimpan untuk uji coba.`} Tautan sumber ditampilkan bila tersedia.</span>
        </div>
        <button onClick={() => setSettings(value => !value)} aria-expanded={settings}
          style={{ background: 'white', border: '1px solid #ead6df', borderRadius: 12, padding: '8px 12px', cursor: 'pointer', color: COLORS.text }}>
          Pengaturan API key
        </button>
      </div>
      {settings && <form onSubmit={connect} style={{ maxWidth: 700, margin: '18px auto 6px' }}>
        <label htmlFor="local-api-key" style={{ display: 'block', fontSize: 15, fontWeight: 700, marginBottom: 8 }}>OpenAI API key</label>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <input id="local-api-key" type="password" autoComplete="off" spellCheck={false} value={key}
            onChange={event => setKey(event.target.value)} disabled={busy} maxLength={512}
            placeholder={configured ? 'Masukkan key pengganti jika diperlukan' : 'Tempel API key di sini'}
            style={{ ...inputStyle, border: '1px solid #ead6df', flex: '1 1 260px', minWidth: 0 }} />
          <Button onClick={connect} disabled={busy || !key.trim()}>{busy ? 'Menyiapkan…' : 'Gunakan key'}</Button>
          {configured && <Button variant="outline" onClick={event => { event.preventDefault(); disconnect(); }}>Hapus key sesi</Button>}
        </div>
        <p style={{ fontSize: 12, color: COLORS.muted, lineHeight: 1.7, marginBottom: 0 }}>
          Key hanya disimpan di memori layanan lokal selama sesi. Pertanyaan dan bukti terpilih dikirim ke OpenAI; pemakaian API mengikuti biaya akunmu.
          Riwayat chat disimpan di browser ini.
        </p>
      </form>}
      {error && <p role="alert" style={{ color: '#9f1d1d', fontSize: 13 }}>{error}</p>}
    </div>
    {page === 'about' ? <AboutPage /> : <ChatPage localMode ready={configured} />}
  </div>;
}
