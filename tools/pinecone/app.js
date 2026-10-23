const key = document.querySelector('#key'), index = document.querySelector('#index'), namespace = document.querySelector('#namespace');
const connect = document.querySelector('#connect'), download = document.querySelector('#export'), message = document.querySelector('#message');
let busy = false, attemptedTargets = new Set(), exporting = false;
const targetKey = () => JSON.stringify([index.value, namespace.value]);
function state(value) {
  busy = value; connect.disabled = value; key.disabled = value;
  index.disabled = value || index.options.length < 2;
  namespace.disabled = value || !index.value || !namespace.options.length;
  download.disabled = value || attemptedTargets.has(targetKey()) || !index.value || !namespace.options.length || !key.value.trim();
}
async function call(action) {
  const response = await fetch('/api/' + action, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:key.value.trim(),index:index.value,namespace:namespace.value})});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Isian belum valid.');
  return data;
}
function show(result) { message.textContent = `${result.status === 'complete' ? 'Selesai' : 'Pengambilan parsial/berhenti'}: ${result.records} record.\n${result.folder || ''}\n${result.error || ''}`; }
function selectionMessage() {
  message.textContent = attemptedTargets.has(targetKey()) ? 'Index dan namespace ini sudah diambil pada sesi ini. Pilih tujuan lain untuk pengambilan baru.' : 'Pilih namespace, lalu klik Ambil maksimal 10.000 record.';
}
connect.onclick = async () => {
  state(true); message.textContent = 'Memeriksa daftar index…'; index.replaceChildren(new Option('Pilih index', '')); namespace.replaceChildren();
  try {
    const data = await call('indexes');
    for (const item of data.indexes) { const option = new Option(item.name + (item.supported ? ` · ${item.dimension} dimensi` : ' · perlu jalur ekspor lain'),item.name); option.disabled = !item.supported; index.add(option); }
    message.textContent = 'Pilih index yang berisi data Cek Data AI.';
  } catch(error) { message.textContent = error.message; } finally {state(false);}
};
index.onchange = async () => {
  namespace.replaceChildren(); if (!index.value) {state(false); return;}
  state(true); message.textContent = 'Memeriksa namespace…';
  try {
    const data = await call('namespaces');
    for (const item of data.namespaces) {
      const count = item.count == null ? 'jumlah belum terbaca' : `${item.count.toLocaleString('id-ID')} record`;
      namespace.add(new Option(`${item.name || '(default)'} · ${count}`,item.name));
    }
    if(data.namespaces.length) selectionMessage();
    else message.textContent = 'Index ini tidak menampilkan namespace yang dapat diambil.';
  } catch(error) {message.textContent = error.message;} finally {state(false);}
};
namespace.onchange = () => { selectionMessage(); state(false); };
key.oninput = () => {index.replaceChildren(new Option('Periksa index kembali','')); namespace.replaceChildren(); state(false);};
download.onclick = async () => {
  if(download.disabled || busy) return;
  attemptedTargets.add(targetKey()); exporting = true; state(true);
  message.textContent = 'Mengambil maksimal 10.000 record dari namespace terpilih…';
  try {show(await call('export'));} catch(error) {message.textContent = error.message;}
  finally {exporting = false; key.value = ''; state(false);}
};
fetch('/api/status').then(r=>r.json()).then(data=>{
  attemptedTargets = new Set((data.attempted_targets || []).map(x=>JSON.stringify(x)));
  if(data.result) show(data.result);
  else if(data.running) message.textContent='Pengambilan masih berjalan. Tunggu sampai selesai.';
  exporting = data.running; state(data.running);
}).catch(()=>{message.textContent='Layanan pengunduh belum terhubung. Muat ulang halaman.';});
setInterval(async () => {
  if (!exporting) return;
  try {
    const data = await fetch('/api/status').then(r=>r.json());
    if(data.result) {show(data.result); exporting = false; state(false);}
    else if(data.running) message.textContent = `Mengambil data: ${data.progress.records.toLocaleString('id-ID')} dari maksimal ${data.progress.target.toLocaleString('id-ID')} record.`;
  } catch { /* The export request reports connection errors separately. */ }
}, 3000);
