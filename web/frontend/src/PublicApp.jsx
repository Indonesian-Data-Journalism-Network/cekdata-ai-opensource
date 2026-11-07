import React, {useEffect,useRef,useState} from 'react';
import {ChatPage,Header,HomePage,AboutPage} from './App.jsx';
import HomeFooter from './ui/HomeFooter.jsx';
import WorkspaceDialog from './features/chat/WorkspaceDialog.jsx';
import {requestJson} from './services/httpClient.js';

export default function PublicApp() {
  const [user,setUser]=useState(null),[page,setPage]=useState('home'),[dialog,setDialog]=useState(false);
  const [signup,setSignup]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const gate=useRef(false);
  const [fields,setFields]=useState({name:'',email:'',password:'',organization:'',beat:'',consent:false});
  useEffect(()=>{
    const controller=new AbortController();
    requestJson('/auth/me',{signal:controller.signal}).then(x=>{setUser(x.user);setPage('chat');})
      .catch(e=>{if(!controller.signal.aborted && e.status!==401)setError('Server belum dapat dihubungi. Coba kembali sebentar lagi.');});
    return ()=>controller.abort();
  },[]);
  function open(){setError('');if(user)setPage('chat');else setDialog(true);}
  function close(){if(!gate.current){setDialog(false);setFields(x=>({...x,password:''}));}}
  async function authenticate(e){
    e.preventDefault();if(gate.current)return;gate.current=true;setBusy(true);setError('');
    try {
      const body=signup?fields:{email:fields.email,password:fields.password};
      const result=await requestJson('/auth/'+(signup?'signup':'login'),{method:'POST',body});
      setUser(result.user);setFields({...fields,password:''});setDialog(false);setPage('chat');
    } catch(e){setError(e.message || 'Belum berhasil masuk.');}
    finally{gate.current=false;setBusy(false);}
  }
  async function signout(){
    if(gate.current)return;gate.current=true;setBusy(true);setError('');
    try{await requestJson('/auth/logout',{method:'POST',body:{}});setUser(null);setPage('home');setDialog(false);}
    catch{setError('Belum berhasil keluar. Coba kembali.');setDialog(true);}
    finally{gate.current=false;setBusy(false);}
  }
  const home=page==='home'||page==='home-about';
  const change=e=>setFields({...fields,[e.target.name]:e.target.type==='checkbox'?e.target.checked:e.target.value});
  return <div className={home?'local-workspace local-home':'chat-app-shell local-workspace'}>
    {home&&<><Header page={page==='home-about'?'about':'home'} setPage={p=>p==='home'?setPage('home'):p==='about'?setPage('home-about'):open()} isLoggedIn={!!user} isAdmin={false} handleSignOut={signout}/>
      {page==='home-about'?<AboutPage/>:<HomePage localMode publicMode onStart={open}/>}
      {error&&!dialog&&<p role="alert" className="workspace-error">{error}</p>}<HomeFooter/></>}
    {user&&<div className="chat-app-content" hidden={home}><ChatPage key={user.id} localMode ready={!busy}
      historyNamespace={`cekdata_chat_${user.id}`} navigation={{page,onNavigate:setPage,userName:user.name,configured:true,
      publicMode:true,sessionBusy:busy,onSettings:()=>setDialog(true),onSignOut:signout,
      onSessionExpired:()=>{setUser(null);setPage('home');setDialog(true);setError('Sesi berakhir. Silakan masuk kembali.');}}}/></div>}
    <WorkspaceDialog open={dialog} onClose={close} title={user?'Akun saya':signup?'Daftar':'Sign in'} busy={busy}>
      {user?<><p>{user.name} · {user.organization}</p><p>{user.email}</p><p>Bidang liputan: {user.beat}</p>
        <p className="workspace-session-note">Riwayat chat tersimpan di browser perangkat ini. Data profil disimpan oleh pengelola.</p>
        {error&&<p role="alert" className="workspace-error">{error}</p>}
        <button className="workspace-button" disabled={busy} onClick={signout}>Sign out</button></>:
      <form onSubmit={authenticate}>
        {signup&&<><label className="workspace-field-label" htmlFor="public-name">Nama</label><input id="public-name" className="workspace-input" name="name" autoComplete="name" value={fields.name} onChange={change} minLength={2} maxLength={100} required disabled={busy}/>
          <label className="workspace-field-label" htmlFor="public-organization">Media atau organisasi (isi “Freelance” bila mandiri)</label><input id="public-organization" className="workspace-input" name="organization" autoComplete="organization" value={fields.organization} onChange={change} minLength={2} maxLength={160} required disabled={busy}/>
          <label className="workspace-field-label" htmlFor="public-beat">Bidang liputan</label><input id="public-beat" className="workspace-input" name="beat" value={fields.beat} onChange={change} minLength={2} maxLength={200} required disabled={busy}/></>}
        <label className="workspace-field-label" htmlFor="public-email">Email</label><input id="public-email" className="workspace-input" type="email" name="email" autoComplete="email" value={fields.email} onChange={change} maxLength={254} required disabled={busy}/>
        <label className="workspace-field-label" htmlFor="public-password">Kata sandi (minimal 12 karakter)</label><input id="public-password" className="workspace-input" type="password" name="password" autoComplete={signup?'new-password':'current-password'} value={fields.password} onChange={change} minLength={12} maxLength={128} required disabled={busy}/>
        {signup&&<label style={{display:'flex',gap:8,marginTop:16,fontSize:13}}><input type="checkbox" name="consent" checked={fields.consent} onChange={change} required disabled={busy}/>Saya setuju profil saya disimpan untuk pengelolaan akun dan mengetahui pengguna layanan.</label>}
        <p className="workspace-session-note">Riwayat chat disimpan di browser ini. Pertanyaan dan bukti dikirim ke layanan AI untuk menyusun jawaban. Server menyimpan proses dan hasil sementara, lalu menghapusnya. Pengelola menyimpan profil dan jumlah pemakaian, bukan riwayat percakapan.</p>
        {error&&<p role="alert" className="workspace-error">{error}</p>}
        <div className="workspace-dialog-actions"><button className="workspace-button" type="button" disabled={busy} onClick={()=>{setSignup(!signup);setError('');}}>{signup?'Sudah punya akun':'Buat akun'}</button>
        <button className="workspace-button workspace-primary" type="submit" disabled={busy}>{busy?'Memproses…':signup?'Daftar dan masuk':'Masuk'}</button></div>
      </form>}
    </WorkspaceDialog>
  </div>;
}
