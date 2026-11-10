import test from 'node:test';
import assert from 'node:assert/strict';
import {askPublic,pause} from './publicJobs.js';
const id='fixture-job-123456789012345';
test('submits once, polls and reports queue progress',async()=>{
 const calls=[],progress=[];const replies=[{job_id:id,status:'queued',position:2},{job_id:id,status:'running'},{job_id:id,status:'completed',result:{answer:'data'}}];
 const result=await askPublic({question:'Berapa?',sources:['environment'],onProgress:x=>progress.push(x)},{wait:async()=>{},request:async(...args)=>{calls.push(args);return replies.shift();}});
 assert.equal(result.answer,'data');assert.equal(calls.length,3);assert.equal(calls[0][1].method,'POST');assert.equal(calls[1][0],'/jobs/'+id);assert.match(progress[0],/posisi 2/);assert.match(progress[1],/memeriksa/);
});
test('failed job and invalid response never become answer',async()=>{
 for(const job of [{job_id:id,status:'failed',error:'Gangguan'},{job_id:'../bad',status:'queued'},{job_id:id,status:'unexpected'}])await assert.rejects(askPublic({question:'Berapa?'},{request:async()=>job,wait:async()=>{}}));
});
test('aborted polling does not resubmit',async()=>{
 const controller=new AbortController();let calls=0;
 await assert.rejects(askPublic({question:'Berapa?',signal:controller.signal},{request:async()=>{calls++;return {job_id:id,status:'queued'};},wait:async()=>{controller.abort();}}),{name:'AbortError'});assert.equal(calls,2);
 await assert.rejects(pause(100,controller.signal),{name:'AbortError'});
});

test('homepage trial sends only catalog ID and polls the guest endpoint', async()=>{
 const calls=[];
 const replies=[{job_id:id,status:'queued'},{job_id:id,status:'completed',result:{answer:'Trial answer'}}];
 const result=await askPublic({demoId:41,question:'ignored',sources:['ignored']},{wait:async()=>{},request:async(...args)=>{calls.push(args);return replies.shift();}});
 assert.equal(result.answer,'Trial answer');
 assert.equal(calls[0][0],'/demo/jobs');
 assert.deepEqual(calls[0][1].body,{question_id:41});
 assert.equal(calls[1][0],'/demo/jobs/'+id);
});
