import { requestJson } from "../../services/httpClient.js";

export async function askQuestion({ question, previousQuestion, sources, token, signal }) {
  const payload = { question };
  if (previousQuestion) payload.previous_question = previousQuestion;
  if (Array.isArray(sources) && sources.length) payload.sources = sources;
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) abort();
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 165000);
  try {
  const result = await requestJson("/ask", {
    method: "POST",
    body: payload,
    token,
    signal: controller.signal,
  });
  if (!result || typeof result !== 'object' || Array.isArray(result)
      || (!('claims' in result) && typeof result.answer !== 'string' && !result.parsed)) {
    throw new Error('Jawaban layanan tidak dapat dibaca. Silakan coba kembali.');
  }
  return result;
  } catch (error) {
    if (timedOut) throw new Error('Pencarian melewati batas waktu. Silakan coba kembali.');
    const messages = { 401: 'Sesi API key berakhir. Buka Pengaturan API key untuk memasukkannya kembali.',
      409: 'Sumber ini belum siap untuk pencarian publik. Pilih sumber lain atau coba kembali nanti.',
      429: 'Terlalu banyak permintaan. Tunggu satu menit sebelum mencoba kembali.',
      503: 'Layanan pencarian sedang tidak tersedia. Silakan coba kembali.',
      500: 'Pencarian mengalami gangguan. Silakan coba kembali.',
      422: 'Pertanyaan tidak valid. Periksa panjang dan isi pertanyaan.' };
    if (messages[error.status]) throw Object.assign(new Error(messages[error.status]), { status: error.status });
    if (error instanceof TypeError) throw new Error('Tidak dapat terhubung ke layanan. Periksa koneksi lalu coba kembali.');
    throw error;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

export function getPublicSearchSources({ signal } = {}) {
  return requestJson("/search/sources", { signal });
}
