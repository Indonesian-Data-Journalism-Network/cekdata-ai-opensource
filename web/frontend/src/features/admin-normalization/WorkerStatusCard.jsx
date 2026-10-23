import React, { useEffect, useRef, useState } from "react";
import { API_BASE } from "../../config/api";

const labels = {
  starting: "Sinkronisasi sedang dimulai",
  processing: "Sinkronisasi sedang memproses data",
  running: "Sinkronisasi berjalan",
  idle: "Sinkronisasi aktif, menunggu data berikutnya",
  retrying: "Sinkronisasi sedang mencoba ulang data yang gagal",
  failed_items: "Ada data yang gagal disinkronkan",
  error: "Worker sinkronisasi mengalami kesalahan",
  stopped: "Worker sinkronisasi berhenti",
  stale: "Worker tidak melaporkan kemajuan tepat waktu",
  unavailable: "Status worker belum tersedia",
};

export default function WorkerStatusCard({ getToken, onAuthExpired }) {
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(false);
  const [afterShard, setAfterShard] = useState('');
  const callbacks = useRef({ getToken, onAuthExpired });
  callbacks.current = { getToken, onAuthExpired };
  useEffect(() => {
    let disposed = false;
    let timer;
    let controller;
    async function refresh() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const token = callbacks.current.getToken();
        if (!token) throw new Error("Session missing");
        const response = await fetch(`${API_BASE}/admin/multisource/workers${afterShard ? '?after_shard=' + encodeURIComponent(afterShard) : ''}`, {
          headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
        });
        if (response.status === 401) callbacks.current.onAuthExpired?.();
        if (!response.ok) throw new Error("Worker status unavailable");
        const data = await response.json();
        if (!disposed) { setSnapshot(data); setError(false); }
      } catch {
        if (!disposed) setError(true);
      } finally {
        clearTimeout(timeout);
        if (!disposed) timer = setTimeout(refresh, 30000);
      }
    }
    refresh();
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); };
  }, [afterShard]);
  const state = snapshot?.dense_worker?.state;
  const attention = error || snapshot?.degraded || (snapshot && !state);
  const text = error ? "Pemantauan terputus; kondisi worker belum dapat dipastikan"
    : labels[state] || (snapshot ? "Pemantauan proses sinkronisasi belum diaktifkan" : "Memeriksa sinkronisasi indeks…");
  const queue = snapshot?.canonical_outbox || {};
  const failure = snapshot?.dense_worker?.last_failure;
  const capped = Object.values(snapshot?.counts_capped || {}).some(values => values.length > 0);
  return (
    <section aria-label="Status sinkronisasi indeks" role={attention ? "alert" : "status"}
      style={{ padding: 20, borderRadius: 16, border: `1px solid ${attention ? "#f0c36c" : "#b8dbc5"}`,
        background: attention ? "#fff8e8" : "#f2faf5", color: "#25382d" }}>
      <strong>{text}</strong>
      {snapshot && !error && <p style={{ margin: "8px 0 0", lineHeight: 1.6 }}>
        Antrean: {Number(queue.pending || 0) + Number(queue.retry || 0)} menunggu · {queue.processing || 0} diproses · {queue.failed || 0} gagal.
        {snapshot.degraded && " Ada proses yang perlu diperiksa."}
        {capped && " Hitungan antrean dibatasi; angka yang ditampilkan adalah batas minimum."}
      </p>}
      {['lexical_worker', 'cleanup_worker', 'withdrawal_worker', 'kresna_normalization_worker'].map(key => snapshot?.[key] && !error && <p key={key} style={{ margin: '8px 0 0' }}>
        {{ lexical_worker: 'Indeks teks', cleanup_worker: 'Pembersihan indeks', withdrawal_worker: 'Penarikan data', kresna_normalization_worker: 'Normalisasi arsip Kresna' }[key]}:
        {' '}{labels[snapshot[key].state] || 'Status belum tersedia'}.
        {snapshot[key].unresolved_failed_items && ' Ada pekerjaan gagal yang masih menunggu pemulihan.'}
      </p>)}
      {snapshot?.queue_scope === 'control_database_only' && <p>Antrean data shard belum tercakup dalam pemantauan ini.</p>}
      {snapshot?.legacy_import_worker && !error && <p style={{ margin: '8px 0 0' }}>
        Impor BPS Kresna: {labels[snapshot.legacy_import_worker.state] || 'Status belum tersedia'}.
        {' '}{Number(snapshot.legacy_import_worker.totals?.completed || 0).toLocaleString('id-ID')} record tersalin ke inbox;
        normalisasi sumber diperiksa terpisah.
      </p>}
      {snapshot?.data_shards && !error && <div aria-label="Antrean pemilik shard">
        <p>{snapshot.data_shards.queue_coverage_complete ? 'Seluruh antrean shard terkonfigurasi telah dibaca.'
          : 'Cakupan antrean shard belum lengkap pada hasil ini.'}</p>
        {snapshot.data_shards.owners.map(owner => <div key={owner.shard_id} style={{ marginTop: 8 }}>
          <strong>Shard {owner.shard_id}</strong>: {owner.queue_read_complete ? 'Antrean berhasil dibaca.' : 'Antrean belum dapat diperiksa.'}
          {Object.entries(owner.workers || {}).map(([component, worker]) => <div key={component}>
            {{dense:'Pinecone',lexical:'Typesense',cleanup:'Cleanup'}[component]}: {labels[worker.state] || 'Status belum tersedia'}.
          </div>)}
          {owner.queues?.degraded && <div>Ada masalah pada antrean atau cakupan scanner shard ini.</div>}
        </div>)}
        {snapshot.data_shards.next_after_shard && <button onClick={() => {
          setAfterShard(snapshot.data_shards.next_after_shard); setSnapshot(null);
        }}>Shard berikutnya</button>}
        {afterShard && <button onClick={() => { setAfterShard(''); setSnapshot(null); }}>Kembali ke shard pertama</button>}
      </div>}
      {snapshot?.connector_worker && !error && <p style={{ margin: "8px 0 0", lineHeight: 1.6 }}>
        Impor terdistribusi: {labels[snapshot.connector_worker.state] || "Status belum tersedia"}.
        {snapshot.connector_worker.unresolved_failed_batches && " Ada batch gagal yang masih menunggu pemulihan."}
      </p>}
      <small style={{ display: "block", marginTop: 8 }}>Status sinkronisasi indeks diperiksa otomatis setiap 30 detik.</small>
      {failure && <p role="status" style={{ margin: "8px 0 0", lineHeight: 1.6 }}>
        Kegagalan terakhir: {new Date(failure.at).toLocaleString("id-ID")}.
        {failure.recovered_at ? " Worker kembali merespons; lihat antrean untuk status data yang tersisa." : " Worker belum melaporkan pemulihan."}
      </p>}
    </section>
  );
}
