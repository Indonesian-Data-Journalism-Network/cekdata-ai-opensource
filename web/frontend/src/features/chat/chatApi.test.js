import test from 'node:test';
import assert from 'node:assert/strict';
import { askQuestion } from './chatApi.js';

test('expired sessions retain status so the workspace can reopen session settings', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail: 'expired' }), {
    status: 401, headers: { 'content-type': 'application/json' },
  }));
  await assert.rejects(askQuestion({ question: 'test' }), error => error.status === 401 && /Sesi API key berakhir/.test(error.message));
});

test('chat handles transport errors and rejects non-answer success payloads', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail: 'internal provider error' }), {
    status: 503, headers: { 'content-type': 'application/json' },
  }));
  await assert.rejects(askQuestion({ question: 'test' }), /sedang tidak tersedia/);
  globalThis.fetch = async () => new Response('<html>proxy</html>', { headers: { 'content-type': 'text/html' } });
  await assert.rejects(askQuestion({ question: 'test' }), /tidak dapat dibaca/);
});

test('chat forwards caller cancellation and source selection', async (t) => {
  const controller = new AbortController();
  let received;
  t.mock.method(globalThis, 'fetch', async (_, options) => {
    received = options;
    if (options.signal.aborted) throw new DOMException('Aborted', 'AbortError');
    return new Response(JSON.stringify({ abstained: true, claims: [], answer: 'Tidak cukup bukti' }),
      { headers: { 'content-type': 'application/json' } });
  });
  await askQuestion({ question: 'test', sources: ['bps'], signal: controller.signal });
  assert.deepEqual(JSON.parse(received.body).sources, ['bps']);
  controller.abort();
  await assert.rejects(askQuestion({ question: 'test', signal: controller.signal }), { name: 'AbortError' });
});

test('timeout aborts the request and returns an actionable message', async (t) => {
  let expire;
  t.mock.method(globalThis, 'setTimeout', callback => { expire = callback; return 1; });
  t.mock.method(globalThis, 'clearTimeout', () => {});
  t.mock.method(globalThis, 'fetch', (_, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
  }));
  const pending = askQuestion({ question: 'test' });
  expire();
  await assert.rejects(pending, /melewati batas waktu/);
});

test('previous question is transmitted separately from current question', async () => {
  const originalFetch = globalThis.fetch;
  let body;
  globalThis.fetch = async (_url, options) => {
    body = JSON.parse(options.body);
    return new Response(JSON.stringify({ claims: [], abstained: true }), { status: 200, headers: {'content-type':'application/json'} });
  };
  try {
    await askQuestion({question:'Kalau tahun 2021?',previousQuestion:'Luas hutan tahun 2020?'});
    assert.equal(body.question,'Kalau tahun 2021?');
    assert.equal(body.previous_question,'Luas hutan tahun 2020?');
  } finally { globalThis.fetch = originalFetch; }
});
