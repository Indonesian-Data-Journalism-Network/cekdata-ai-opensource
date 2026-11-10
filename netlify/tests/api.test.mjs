import test from 'node:test';
import assert from 'node:assert/strict';
import {makeGateway} from '../functions/api.mjs';
const env={CEKDATA_API_ORIGIN:'https://server.example.org',CEKDATA_GATEWAY_SECRET:'test-secret-1234567890123456789012345'};
const request=(path='/api/health',method='GET',extra={})=>new Request('https://fixture.netlify.app'+path,{method,...(method==='POST'?{body:'{}',headers:{origin:'https://fixture.netlify.app','content-type':'application/json'}}:{}),...extra});
test('only approved API routes, methods and origins reach backend',async()=>{
 let count=0;const handle=makeGateway({getEnv:k=>env[k],fetchImpl:async()=>{count++;return Response.json({ok:true});}});
 for(const [r,status] of [[request('/api/admin'),404],[request('/api/auth/signup','GET'),405],[request('/api/jobs','POST',{headers:{origin:'https://evil.org','content-type':'application/json'}}),403],[request('/api/jobs','POST',{body:'x'.repeat(17000)}),413]])assert.equal((await handle(r)).status,status);
 assert.equal(count,0);
});
test('gateway credentials and IP cannot be spoofed; cookies work; response no-store',async()=>{
 let seen;const handle=makeGateway({getEnv:k=>env[k],fetchImpl:async(url,init)=>{seen={url,init};return Response.json({ok:true},{headers:{'set-cookie':'session=fixture; HttpOnly; Secure; Path=/api'}});}});
 const r=await handle(request('/.netlify/functions/api/auth/me','GET',{headers:{'x-cekdata-gateway':'spoof','x-cekdata-client':'spoof',cookie:'session=fixture',authorization:'unwanted'}}),{ip:'192.0.2.1'});
 assert.equal(seen.url.href,'https://server.example.org/api/auth/me');assert.equal(seen.init.headers['x-cekdata-gateway'],env.CEKDATA_GATEWAY_SECRET);
 assert.equal(seen.init.headers['x-cekdata-client'],'192.0.2.1');assert.equal(seen.init.headers.authorization,undefined);assert.equal(seen.init.redirect,'manual');
 assert.equal(r.headers.get('cache-control'),'no-store');assert.match(r.headers.get('set-cookie'),/HttpOnly/);assert.doesNotMatch(await r.text(),/test-secret/);
});
test('missing config, network errors and redirects fail closed',async()=>{
 for(const upstream of ['http://server.example.org','https://user:password@server.example.org','https://server.example.org/path',undefined]){
  const h=makeGateway({getEnv:k=>k==='CEKDATA_API_ORIGIN'?upstream:env[k],fetchImpl:()=>{throw Error('should not call');}});assert.equal((await h(request())).status,503);
 }
 for(const [result,status] of [[new Response('',{status:302,headers:{location:'https://evil.org'}}),502],[new Response('<html>error</html>'),502],[null,503]]){
  const h=makeGateway({getEnv:k=>env[k],fetchImpl:async()=>{if(!result)throw Error(env.CEKDATA_GATEWAY_SECRET);return result;}});const r=await h(request());assert.equal(r.status,status);assert.doesNotMatch(await r.text(),/test-secret/);
 }
});
test('trial routes forward guest cookie without opening other anonymous routes',async()=>{
 const seen=[];const handle=makeGateway({getEnv:k=>env[k],fetchImpl:async(url,init)=>{seen.push({url,init});return Response.json({ok:true});}});
 const id='guest-job-123456789012345';
 assert.equal((await handle(request('/api/demo/jobs','POST'))).status,200);
 assert.equal((await handle(request('/api/demo/jobs/'+id,'GET',{headers:{cookie:'cekdata_demo_session=fixture'}}))).status,200);
 assert.equal(seen[1].init.headers.cookie,'cekdata_demo_session=fixture');
 assert.equal((await handle(request('/api/demo/admin','POST'))).status,404);
});
