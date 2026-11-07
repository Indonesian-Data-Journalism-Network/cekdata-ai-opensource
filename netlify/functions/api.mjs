// Same-origin gateway. Secrets exist only in Netlify Functions runtime variables.
const routes = new Map([
  ['/api/health', ['GET']], ['/api/auth/me', ['GET']],
  ['/api/auth/signup', ['POST']], ['/api/auth/login', ['POST']],
  ['/api/auth/logout', ['POST']], ['/api/search/sources', ['GET']], ['/api/jobs', ['POST']],
]);
const json = (detail, status) => Response.json({detail}, {status, headers:{'cache-control':'no-store'}});
export function makeGateway({getEnv, fetchImpl = fetch}) {
  return async (request, context = {}) => {
    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/\.netlify\/functions\/api(?=\/)/, '/api');
    const methods = routes.get(path) || (/^\/api\/jobs\/[\w-]{20,64}$/.test(path) ? ['GET'] : []);
    if (!methods.length) return json('Alamat layanan tidak ditemukan.',404);
    if (!methods.includes(request.method)) return json('Metode tidak diizinkan.',405);
    const origin = request.headers.get('origin');
    if (request.method === 'POST' && origin !== url.origin) return json('Asal permintaan tidak diizinkan.',403);
    if (request.method === 'POST' && !request.headers.get('content-type')?.startsWith('application/json')) return json('Gunakan JSON.',415);
    const upstream = getEnv('CEKDATA_API_ORIGIN');
    const secret = getEnv('CEKDATA_GATEWAY_SECRET');
    let target;
    try {
      target = new URL(upstream);
      if (target.protocol !== 'https:' || target.username || target.password || target.search || target.hash || target.pathname !== '/') throw new Error();
    } catch { return json('Server belum terhubung. Silakan coba kembali nanti.',503); }
    if (!secret || secret.length < 32) return json('Server belum terhubung. Silakan coba kembali nanti.',503);
    let body;
    if (request.method === 'POST') {
      const reader = request.body?.getReader(); const chunks = []; let size = 0;
      if (reader) while (true) {
        const {done,value} = await reader.read(); if (done) break;
        size += value.byteLength;
        if (size > 16384) { await reader.cancel(); return json('Isian terlalu panjang.',413); }
        chunks.push(value);
      }
      body = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { body.set(chunk,offset); offset += chunk.byteLength; }
    }
    const headers = {'accept':'application/json','x-cekdata-gateway':secret,
      'x-cekdata-client':context.ip || 'unknown'};
    if (origin) headers.origin = origin;
    if (body) headers['content-type'] = 'application/json';
    if (request.headers.get('cookie')) headers.cookie = request.headers.get('cookie');
    try {
      const response = await fetchImpl(new URL(path,target), {method:request.method,headers,body,
        redirect:'manual',signal:AbortSignal.timeout(12000)});
      if (response.status >= 500) return json('Komputer server belum dapat dihubungi. Silakan coba kembali.',503);
      if (response.status >= 300 && response.status < 400) return json('Server belum tersedia.',502);
      if (!response.headers.get('content-type')?.includes('application/json')) return json('Server belum tersedia.',502);
      const output = new Headers({'content-type':'application/json','cache-control':'no-store',
        'x-content-type-options':'nosniff','referrer-policy':'no-referrer'});
      const cookies = response.headers.getSetCookie?.() || [response.headers.get('set-cookie')].filter(Boolean);
      for (const cookie of cookies) output.append('set-cookie',cookie);
      return new Response(response.body,{status:response.status,headers:output});
    } catch { return json('Komputer server belum dapat dihubungi. Silakan coba kembali.',503); }
  };
}
export default (request, context) => makeGateway({getEnv:key=>Netlify.env.get(key)})(request,context);
