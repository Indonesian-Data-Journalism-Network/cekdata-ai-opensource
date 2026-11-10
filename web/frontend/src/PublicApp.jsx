import React, {useEffect,useRef,useState} from 'react';
import {ChatPage,Header,HomePage,AboutPage} from './App.jsx';
import HomeFooter from './ui/HomeFooter.jsx';
import TeamPage from './ui/TeamPage.jsx';
import PublicAuthForm from './auth/public/PublicAuthForm.jsx';
import WorkspaceDialog from './features/chat/WorkspaceDialog.jsx';
import {requestJson} from './services/httpClient.js';

export default function PublicApp() {
  const [user,setUser]=useState(null),[page,setPage]=useState('home'),[dialog,setDialog]=useState(false);
  const [signup,setSignup]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const gate=useRef(false);
  const authPanel=useRef(null);
  const [focusRequest,setFocusRequest]=useState(0);
  const [homeQuestion,setHomeQuestion]=useState(null);
  const [fields,setFields]=useState({name:'',email:'',password:'',organization:'',beat:'',consent:false});
  useEffect(()=>{
    const controller=new AbortController();
    requestJson('/auth/me',{signal:controller.signal}).then(x=>{setUser(x.user);setPage('chat');})
      .catch(e=>{if(!controller.signal.aborted && e.status!==401)setError('Server belum dapat dihubungi. Coba kembali sebentar lagi.');});
    return ()=>controller.abort();
  },[]);
  useEffect(()=>{
    if (!focusRequest || user || page!=='home') return;
    authPanel.current?.scrollIntoView({behavior:'smooth',block:'center'});
    authPanel.current?.querySelector('input')?.focus({preventScroll:true});
  },[focusRequest,page,user]);
  function open(question){
    if(question?.question)setHomeQuestion(question);
    setError('');
    if(user)setPage('chat');
    else {setPage('home');setFocusRequest(value=>value+1);}
  }
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
    try{await requestJson('/auth/logout',{method:'POST',body:{}});setUser(null);setPage('home');setDialog(false);setSignup(false);setHomeQuestion(null);setFields({name:'',email:'',password:'',organization:'',beat:'',consent:false});}
    catch{setError('Belum berhasil keluar. Coba kembali.');setDialog(true);}
    finally{gate.current=false;setBusy(false);}
  }
  const home=['home','home-about','home-team'].includes(page);
  function publicNavigate(destination){
    setPage(destination==='about'?'home-about':destination==='team'?'home-team':'home');
    window.scrollTo({top:0,behavior:'instant'});
  }
  const change=e=>setFields({...fields,[e.target.name]:e.target.type==='checkbox'?e.target.checked:e.target.value});
  return <div className={home?'local-workspace local-home':'chat-app-shell local-workspace'}>
    {home&&<><Header hideSignIn hideAbout page={page==='home-about'?'about':'home'} setPage={p=>['home','about','team'].includes(p)?publicNavigate(p):open()} isLoggedIn={!!user} isAdmin={false} handleSignOut={signout}/>
      {page==='home-team'?<TeamPage onBack={()=>publicNavigate('home')}/>:page==='home-about'?<><div className="local-home-back"><button className="workspace-button" onClick={()=>publicNavigate('home')}>Kembali ke Home</button></div><AboutPage/></>:<HomePage localMode publicMode onStart={open}>
        {!user&&<PublicAuthForm signup={signup} onModeChange={value=>{setSignup(value);setError('');}}
          fields={fields} onChange={change} onSubmit={authenticate} busy={busy} error={error} panelRef={authPanel}/>}
      </HomePage>}
      {error&&!dialog&&(user||page==='home-about')&&<p role="alert" className="workspace-error">{error}</p>}<HomeFooter onNavigate={publicNavigate}/></>}
    {user&&<div className="chat-app-content" hidden={home}><ChatPage key={user.id} localMode ready={!busy}
      initialQuestion={homeQuestion} onInitialQuestionConsumed={()=>setHomeQuestion(null)}
      historyNamespace={`cekdata_chat_${user.id}`} navigation={{page,onNavigate:setPage,userName:user.name,configured:true,
      publicMode:true,sessionBusy:busy,onSettings:()=>setDialog(true),onSignOut:signout,
      onSessionExpired:()=>{setUser(null);setPage('home');setDialog(false);setSignup(false);setFields(x=>({...x,password:''}));setFocusRequest(value=>value+1);setError('Sesi berakhir. Silakan masuk kembali.');}}}/></div>}
    <WorkspaceDialog open={dialog&&!!user} onClose={close} title="Akun saya" busy={busy}>
      {user&&<><p>{user.name} · {user.organization}</p><p>{user.email}</p><p>Bidang liputan: {user.beat}</p>
        <p className="workspace-session-note">Riwayat chat tersimpan di browser perangkat ini. Data profil disimpan oleh pengelola.</p>
        {error&&<p role="alert" className="workspace-error">{error}</p>}
        <button className="workspace-button" disabled={busy} onClick={signout}>Sign out</button></>}
    </WorkspaceDialog>
  </div>;
}
