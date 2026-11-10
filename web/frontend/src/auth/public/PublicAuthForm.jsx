import React, {useRef} from 'react';
import './PublicAuthForm.css';

export default function PublicAuthForm({signup, onModeChange, fields, onChange, onSubmit, busy, error, panelRef}) {
  const signInTab=useRef(null), signUpTab=useRef(null);
  function selectMode(next, focus=false) {
    if (busy) return;
    onModeChange(next);
    if (focus) (next?signUpTab:signInTab).current?.focus();
  }
  function tabKeys(event) {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    selectMode(event.key==='Home'?false:event.key==='End'?true:!signup, true);
  }
  return <section ref={panelRef} className="public-home-auth" aria-label="Masuk atau daftar Cek Data AI">
    <div className="public-auth-tabs" role="tablist" aria-label="Akses akun" onKeyDown={tabKeys}>
      <button ref={signInTab} type="button" id="public-signin-tab" role="tab" aria-selected={!signup}
        aria-controls="public-auth-panel" tabIndex={signup?-1:0} disabled={busy} onClick={()=>selectMode(false)}>Sign In</button>
      <button ref={signUpTab} type="button" id="public-signup-tab" role="tab" aria-selected={signup}
        aria-controls="public-auth-panel" tabIndex={signup?0:-1} disabled={busy} onClick={()=>selectMode(true)}>Sign Up</button>
    </div>
    <div id="public-auth-panel" role="tabpanel" aria-labelledby={signup?'public-signup-tab':'public-signin-tab'}>
      <form onSubmit={onSubmit} aria-busy={busy}>
        <div className="public-auth-fields">
          {signup&&<label htmlFor="public-name">Nama lengkap
            <input id="public-name" name="name" autoComplete="name" placeholder="Nama lengkap" value={fields.name} onChange={onChange} minLength={2} maxLength={100} required disabled={busy}/>
          </label>}
          <label htmlFor="public-email">Email
            <input id="public-email" type="email" name="email" autoComplete="email" placeholder="nama@media.com" value={fields.email} onChange={onChange} maxLength={254} required disabled={busy}/>
          </label>
          {signup&&<>
            <label htmlFor="public-organization">Media atau organisasi
              <input id="public-organization" name="organization" autoComplete="organization" placeholder="Nama media atau Freelance" value={fields.organization} onChange={onChange} minLength={2} maxLength={160} required disabled={busy}/>
            </label>
            <label htmlFor="public-beat">Bidang liputan
              <input id="public-beat" name="beat" placeholder="Misalnya: lingkungan, ekonomi" value={fields.beat} onChange={onChange} minLength={2} maxLength={200} required disabled={busy}/>
            </label>
          </>}
          <label htmlFor="public-password">Password
            <input id="public-password" type="password" name="password" autoComplete={signup?'new-password':'current-password'} placeholder={signup?'Minimal 12 karakter':'Masukkan password'} value={fields.password} onChange={onChange} minLength={12} maxLength={128} required disabled={busy}/>
          </label>
        </div>
        {signup&&<label className="public-auth-consent"><input type="checkbox" name="consent" checked={fields.consent} onChange={onChange} required disabled={busy}/>
          <span>Saya setuju profil saya disimpan untuk pengelolaan akun dan mengetahui pengguna layanan.</span>
        </label>}
        {error&&<p role="alert" className="workspace-error">{error}</p>}
        <button className="public-auth-submit" type="submit" disabled={busy}>{busy?'Memproses…':signup?'Daftar dan masuk':'Masuk'}</button>
        <details className="public-auth-privacy">
          <summary>Privasi data</summary>
          <p>Riwayat chat disimpan di browser ini. Pertanyaan dan bukti dikirim ke layanan AI untuk menyusun jawaban. Server menyimpan proses dan hasil sementara, lalu menghapusnya. Pengelola menyimpan profil dan jumlah pemakaian, bukan riwayat percakapan.</p>
        </details>
      </form>
    </div>
  </section>;
}
