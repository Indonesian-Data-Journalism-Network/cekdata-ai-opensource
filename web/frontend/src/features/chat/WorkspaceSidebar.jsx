import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, Info, KeyRound, LogOut, Trash2 } from 'lucide-react';
import WorkspaceDialog from './WorkspaceDialog.jsx';

export default function WorkspaceSidebar({ navigation, items, selectedId, loading, onSelect, onClear }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const account = useRef(null);
  const profileButton = useRef(null);
  const userName = navigation.userName || 'Pengguna lokal';
  useEffect(() => {
    if (!menuOpen) return;
    const outside = event => { if (!account.current?.contains(event.target)) setMenuOpen(false); };
    const escape = event => {
      if (event.key === 'Escape') {
        event.preventDefault(); event.stopPropagation();
        setMenuOpen(false); profileButton.current?.focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape, true);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape, true); };
  }, [menuOpen]);
  const navigate = page => { setMenuOpen(false); navigation.onNavigate(page); };
  return <>
    <div className="workspace-sidebar">
      <button type="button" className="workspace-logo" onClick={() => navigate('chat')} aria-label="Cek Data AI, kembali ke chat"><span>cekdata</span>.ai</button>
      <div className="workspace-history" aria-label="Riwayat pertanyaan">
        <div className="workspace-history-label">Riwayat</div>
        {!items.length && <p className="workspace-empty-history">Belum ada riwayat pertanyaan.</p>}
        {items.map(item => <button type="button" key={item.id} className="workspace-history-item"
          aria-current={selectedId === item.id && navigation.page === 'chat' ? 'true' : undefined}
          disabled={loading} title={item.question} onClick={() => { setMenuOpen(false); onSelect(item); }}>
          <span>{item.question}</span>
        </button>)}
      </div>
      <footer className="workspace-account" ref={account}>
        <button type="button" className="workspace-about-link" aria-current={navigation.page === 'about' ? 'page' : undefined}
          onClick={() => navigate('about')}><Info size={17} />About Cek Data AI</button>
        <div className="workspace-person-row">
          <button ref={profileButton} type="button" className="workspace-person" aria-label={`Menu pengguna: ${userName}`}
            aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}>
            <span className="workspace-avatar" aria-hidden="true">{userName.charAt(0).toUpperCase()}</span>
            <span className="workspace-username">{userName}</span><ChevronDown size={14} />
          </button>
          <button type="button" className="workspace-icon workspace-signout" title="Sign out" aria-label="Sign out"
            disabled={navigation.sessionBusy || !navigation.configured} onClick={() => { setMenuOpen(false); navigation.onSignOut(); }}><LogOut size={18} /></button>
        </div>
        {menuOpen && <div className="workspace-user-menu" role="region" aria-label="Menu pengguna">
          <strong>{userName}</strong>
          <p>Uji coba lokal · {navigation.recordCount === null ? 'Memeriksa data…' : `${navigation.recordCount.toLocaleString('id-ID')} catatan data`}</p>
          <p>{navigation.configured ? 'Sesi aktif' : 'Sesi belum terhubung'}</p>
          <button type="button" disabled={navigation.sessionBusy} onClick={() => { setMenuOpen(false); navigation.onSettings(); }}><KeyRound size={16} />{navigation.publicMode ? "Akun saya" : "Pengaturan API key"}</button>
          <button type="button" disabled={loading || !items.length} onClick={() => { setMenuOpen(false); setConfirmClear(true); }}><Trash2 size={16} />Hapus semua riwayat</button>
          <small>Menyimpan 20 riwayat terakhir di browser ini.</small>
        </div>}
      </footer>
    </div>
    <WorkspaceDialog open={confirmClear} onClose={() => setConfirmClear(false)} title="Hapus semua riwayat?">
      <p>Semua riwayat pertanyaan di browser ini akan dihapus. Tindakan ini tidak dapat dibatalkan.</p>
      <div className="workspace-dialog-actions">
        <button type="button" className="workspace-button" autoFocus onClick={() => setConfirmClear(false)}>Batal</button>
        <button type="button" className="workspace-button workspace-danger" disabled={loading} onClick={() => { onClear(); setConfirmClear(false); }}>Hapus riwayat</button>
      </div>
    </WorkspaceDialog>
  </>;
}
