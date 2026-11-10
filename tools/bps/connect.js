document.getElementById('form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('save');
  const status = document.getElementById('status');
  const input = document.getElementById('key');
  button.disabled = true; status.textContent = 'Memeriksa koneksi ke BPS…';
  try {
    const response = await fetch('/api/save', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({api_key: input.value})});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Koneksi belum berhasil.');
    input.value = ''; status.textContent = 'Koneksi BPS berhasil disimpan. Beri tahu Codex agar pengambilan data bisa dilanjutkan.';
  } catch (error) {status.textContent = error.message;}
  finally {button.disabled = false;}
});
