import {requestJson} from '../../services/httpClient.js';
export function pause(ms, signal) {
  return new Promise((resolve,reject)=>{
    if(signal?.aborted){reject(new DOMException('Aborted','AbortError'));return;}
    const abort=()=>{clearTimeout(timer);reject(new DOMException('Aborted','AbortError'));};
    const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},ms);
    signal?.addEventListener('abort',abort,{once:true});
  });
}
export async function askPublic({question,sources,demoId,signal,onProgress}, {request=requestJson,wait=pause}={}) {
  const base=demoId === undefined ? '/jobs' : '/demo/jobs';
  const body=demoId === undefined ? {question,sources} : {question_id:demoId};
  let job=await request(base,{method:'POST',body,signal});
  if(!job?.job_id || !/^[\w-]{20,64}$/.test(job.job_id))throw new Error('Respons proses tidak dapat dibaca.');
  const id=job.job_id;
  while(true){
    if(signal?.aborted)throw new DOMException('Aborted','AbortError');
    if(job.status==='completed')return job.result;
    if(job.status==='failed')throw new Error(job.error||'Proses belum berhasil. Silakan coba kembali.');
    if(!['queued','running'].includes(job.status))throw new Error('Status proses tidak dapat dibaca.');
    onProgress?.(job.status==='queued'?`Menunggu antrean${job.position?` · posisi ${job.position}`:''}…`:'Sedang memeriksa data…');
    await wait(1500,signal);
    job=await request(base+'/'+encodeURIComponent(id),{signal});
  }
}
