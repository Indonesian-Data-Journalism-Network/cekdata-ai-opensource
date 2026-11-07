import React, { useRef, useEffect, useState } from 'react';
import { ChatPage, Header, HomePage, AboutPage } from './App.jsx';
import HomeFooter from './ui/HomeFooter.jsx';
import WorkspaceDialog from './features/chat/WorkspaceDialog.jsx';
import { requestJson } from './services/httpClient.js';

export default function LocalApp() {
  const [page, setPage] = useState('chat');
  const [configured, setConfigured] = useState(false);
  const [settings, setSettings] = useState(false);
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [recordCount, setRecordCount] = useState(null);
  const [userName, setUserName] = useState('Pengguna lokal');
  useEffect(() => {
    const controller = new AbortController();
    requestJson('/local/session', { signal: controller.signal }).then(data => {
      setConfigured(data.configured);
      setSettings(false);
      if (!data.configured) setPage('home');
      setRecordCount(data.sample_records ?? null);
      if (typeof data.display_name === 'string' && data.display_name.trim()) setUserName(data.display_name.trim());
    }).catch(() => {
      if (!controller.signal.aborted) {
        setSettings(true);
        setError('Layanan lokal belum terhubung. Pastikan server lokal sudah berjalan.');
      }
    });
    return () => controller.abort();
  }, []);

  async function connect(event) {
    event.preventDefault();
    if (busyRef.current || !key.trim()) return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      await requestJson('/local/session', { method: 'POST', body: { api_key: key.trim() } });
      setKey(''); setConfigured(true); setSettings(false); setPage('chat');
    } catch (error) { setError(error.message || 'API key belum tersimpan untuk sesi ini.'); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function disconnect() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      await requestJson('/local/session', { method: 'DELETE' });
      setKey(''); setConfigured(false); setSettings(false); setPage('home');
    } catch {
      setError('Sesi belum berhasil diakhiri. Coba kembali.'); setSettings(true);
    } finally { busyRef.current = false; setBusy(false); }
  }
  function closeSettings() { if (!busyRef.current) { setSettings(false); setKey(''); } }
  function sessionExpired() {
    setConfigured(false); setSettings(true); setKey('');
    setError('Sesi API key berakhir. Masukkan kembali key untuk melanjutkan.');
  }
  const publicPage = page === 'home' || page === 'home-about';
  function startChat() {
    setError('');
    if (configured) setPage('chat');
    else setSettings(true);
  }
  function publicNavigate(destination) {
    if (destination === 'home') setPage('home');
    else if (destination === 'about') setPage('home-about');
    else startChat();
  }
  return <div className={publicPage ? 'local-workspace local-home' : 'chat-app-shell local-workspace'}>
    {publicPage && <>
      <Header page={page === 'home-about' ? 'about' : 'home'} setPage={publicNavigate} isLoggedIn={false} isAdmin={false} />
      {page === 'home-about' ? <>
        <div className="local-home-back"><button className="workspace-button" onClick={() => setPage('home')}>Kembali ke Home</button></div>
        <AboutPage />
      </> : <HomePage localMode onStart={startChat} />}
    </>}
    <div className="chat-app-content" hidden={publicPage}>
    <ChatPage localMode ready={configured && !busy} navigation={{
      page, onNavigate: setPage, userName, recordCount, configured, sessionBusy: busy,
      onSettings: () => setSettings(true), onSignOut: disconnect, onSessionExpired: sessionExpired,
    }} />
    </div>
    {publicPage && <HomeFooter />}
    <WorkspaceDialog open={settings} onClose={closeSettings} title="Pengaturan API key" busy={busy}>
      <p className="workspace-session-status">{configured ? 'Sesi aktif' : 'Hubungkan sesi untuk mulai bertanya'}</p>
      <form onSubmit={connect}>
        <label className="workspace-field-label" htmlFor="local-api-key">OpenAI API key</label>
        <input id="local-api-key" className="workspace-input" type="password" autoComplete="off" spellCheck={false} value={key}
          onChange={event => setKey(event.target.value)} disabled={busy} maxLength={512}
          placeholder={configured ? 'Masukkan key pengganti jika diperlukan' : 'Tempel API key di sini'} />
        {error && <p role="alert" className="workspace-error">{error}</p>}
        <div className="workspace-dialog-actions">
          <button className="workspace-button" type="button" disabled={busy} onClick={closeSettings}>Tutup</button>
          {configured && <button className="workspace-button" type="button" disabled={busy} onClick={disconnect}>Hapus key sesi</button>}
          <button className="workspace-button workspace-primary" type="submit" disabled={busy || !key.trim()}>{busy ? 'Memproses…' : 'Gunakan key'}</button>
        </div>
        <p className="workspace-session-note">Key hanya disimpan di memori layanan lokal selama sesi. Pertanyaan dan bukti terpilih dikirim ke OpenAI; pemakaian API mengikuti biaya akunmu. Riwayat chat disimpan di browser ini.</p>
      </form>
    </WorkspaceDialog>
  </div>;
}
