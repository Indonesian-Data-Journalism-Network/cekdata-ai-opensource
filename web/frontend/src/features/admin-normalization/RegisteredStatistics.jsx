import React, { useEffect, useRef, useState } from "react";
import { requestJson } from "../../services/httpClient.js";

const readable = (value) => String(value).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
const initialRange = (years) => {
  const values = [...new Set(years)].sort((a, b) => a - b);
  if (!values.length) return ["", ""];
  const last = values[values.length - 1];
  return [String(last - values[0] + 1 === values.length ? values[0] : last), String(last)];
};

export default function RegisteredStatistics({ getToken, onAuthExpired, base = "/admin/cell-search/statistics" }) {
  const callbacks = useRef({ getToken, onAuthExpired });
  callbacks.current = { getToken, onAuthExpired };
  const [series, setSeries] = useState([]);
  const [selected, setSelected] = useState("");
  const [points, setPoints] = useState([]);
  const [area, setArea] = useState("");
  const [comparisonArea, setComparisonArea] = useState("");
  const [analysis, setAnalysis] = useState("auto");
  const [catalogAfter, setCatalogAfter] = useState("");
  const [catalogNext, setCatalogNext] = useState(null);
  const [coverageAfter, setCoverageAfter] = useState(null);
  const [coverageNext, setCoverageNext] = useState(null);
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const pending = useRef(null);
  const revision = useRef(0);
  const request = (path, options = {}) => requestJson(path, {
    token: callbacks.current.getToken?.(), ...options,
  });
  const fail = (err) => {
    if (err.status === 401) callbacks.current.onAuthExpired?.();
    setError("Data belum dapat dimuat. Silakan coba lagi.");
  };
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setSeries([]); setSelected(""); setPoints([]); setResult(null); setError("");
    request(`${base}/series?after=${encodeURIComponent(catalogAfter)}`, { signal: controller.signal }).then((data) => {
      if (controller.signal.aborted) return;
      const annual = data.series.filter((item) => item.period_grain === "annual");
      setCatalogNext(data.next_cursor || null); setCoverageAfter(null); setCoverageNext(null);
      setSeries(annual); setSelected(annual[0]?.id || "");
      if (!annual.length) setLoading(false);
    }).catch((err) => { if (!controller.signal.aborted) { fail(err); setLoading(false); } });
    return () => { controller.abort(); pending.current?.abort(); };
  }, [base, catalogAfter]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    revision.current += 1; pending.current?.abort(); setBusy(false);
    setLoading(true); setError(""); setPoints([]); setResult(null);
    const cursor = coverageAfter ? `?${new URLSearchParams(coverageAfter)}` : "";
    request(`${base}/series/${encodeURIComponent(selected)}/coverage${cursor}`, { signal: controller.signal }).then((data) => {
      if (controller.signal.aborted) return;
      setPoints(data.points); setArea(data.points[0]?.area_id || "");
      setComparisonArea("");
      setCoverageNext(data.next_cursor || null);
      const years = data.points.filter((p) => p.area_id === data.points[0]?.area_id).map((p) => p.year);
      const range = initialRange(years); setFirst(range[0]); setLast(range[1]);
      setLoading(false);
    }).catch((err) => { if (!controller.signal.aborted) { fail(err); setLoading(false); } });
    return () => controller.abort();
  }, [base, selected, coverageAfter]);
  function invalidate() {
    revision.current += 1; pending.current?.abort(); setBusy(false); setResult(null); setError("");
  }
  function chooseArea(value) {
    invalidate(); setArea(value);
    const years = points.filter((p) => p.area_id === value).map((p) => p.year);
    const range = initialRange(years); setFirst(range[0]); setLast(range[1]);
  }
  async function search(event) {
    event.preventDefault(); invalidate();
    const version = revision.current;
    const controller = new AbortController(); pending.current = controller;
    setBusy(true);
    try {
      const data = await request(`${base}/registered`, { method: "POST", signal: controller.signal,
        body: { operation: analysis === "compare" ? "compare" : first === last ? "lookup" : "trend", annual: {
          indicator_id: selected, area_ids: analysis === "compare" ? [area, comparisonArea] : [area],
          first_year: Number(first), last_year: Number(analysis === "compare" ? first : last),
        } },
      });
      if (!controller.signal.aborted && version === revision.current) setResult(data);
    } catch (err) { if (!controller.signal.aborted && version === revision.current) fail(err); }
    finally { if (version === revision.current) setBusy(false); }
  }
  const areas = [...new Map(points.map((p) => [p.area_id, p])).values()];
  const years = [...new Set(points.filter((p) => p.area_id === area).map((p) => p.year))].sort();
  const field = { display: "grid", gap: 6, flex: "1 1 180px", minWidth: 0 };
  return <section className="registered-statistics" aria-label="Pencarian angka BPS" style={{ minWidth: 0, padding: 20, border: "1px solid #d6e1dc", borderRadius: 16, background: "white" }}>
    <style>{'.registered-statistics select { width: 100%; min-width: 0; }'}</style>
    <h3 style={{ marginTop: 0 }}>Cari angka BPS</h3>
    <p>Pilih indikator, wilayah, dan tahun untuk melihat angka beserta sumbernya.</p>
    {(catalogNext || coverageNext || catalogAfter || coverageAfter) && <p role="status">Pilihan data ditampilkan bertahap. Gunakan halaman berikutnya untuk melihat pilihan lain.</p>}
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
      {catalogNext && <button disabled={loading || busy} onClick={() => { invalidate(); setCatalogAfter(catalogNext); }}>Indikator berikutnya</button>}
      {catalogAfter && <button disabled={loading || busy} onClick={() => { invalidate(); setCatalogAfter(""); }}>Indikator awal</button>}
      {coverageNext && <button disabled={loading || busy} onClick={() => { invalidate(); setCoverageAfter(coverageNext); }}>Wilayah/periode berikutnya</button>}
      {coverageAfter && <button disabled={loading || busy} onClick={() => { invalidate(); setCoverageAfter(null); }}>Wilayah/periode awal</button>}
    </div>
    <form onSubmit={search} style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "end" }}>
      <label style={field}>Jenis pencarian<select value={analysis} onChange={(e) => { invalidate(); setAnalysis(e.target.value); }}>
        <option value="auto">Angka dan tren</option><option value="compare">Bandingkan wilayah</option>
      </select></label>
      <label style={field}>Indikator<select value={selected} disabled={!series.length} onChange={(e) => { invalidate(); setSelected(e.target.value); setCoverageAfter(null); }}>
        {series.map((s) => <option key={s.id} value={s.id}>{s.label} ({s.unit})</option>)}
      </select></label>
      {analysis === "compare" && <label style={field}>Wilayah pembanding<select value={comparisonArea} disabled={loading} onChange={(e) => { invalidate(); setComparisonArea(e.target.value); }}>
        <option value="">Pilih wilayah</option>
        {areas.filter((p) => p.area_id !== area).map((p) => <option key={p.area_id} value={p.area_id}>{p.area_name}</option>)}
      </select></label>}
      <label style={field}>Wilayah<select value={area} disabled={loading || !areas.length} onChange={(e) => chooseArea(e.target.value)}>
        {areas.map((p) => <option key={p.area_id} value={p.area_id}>{p.area_name}</option>)}
      </select></label>
      <label style={field}>Tahun awal<select value={first} disabled={loading || !years.length} onChange={(e) => { invalidate(); setFirst(e.target.value); }}>
        {years.map((y) => <option key={y}>{y}</option>)}
      </select></label>
      <label style={field}>Tahun akhir<select value={analysis === "compare" ? first : last} disabled={analysis === "compare" || loading || !years.length} onChange={(e) => { invalidate(); setLast(e.target.value); }}>
        {years.map((y) => <option key={y}>{y}</option>)}
      </select></label>
      <button type="submit" disabled={loading || busy || !area || !first || (analysis === "compare" ? !comparisonArea || comparisonArea === area : Number(first) > Number(last))}>{busy ? "Memeriksa sumber…" : "Cari angka"}</button>
    </form>
    {loading && <p role="status">Memuat pilihan data…</p>}
    {!loading && !error && !points.length && <p>Belum ada data yang tersedia untuk pilihan ini.</p>}
    {error && <p role="alert">{error}</p>}
    {result?.abstained && <p role="status">Data untuk seluruh pilihan belum lengkap atau belum konsisten. Angka tidak ditampilkan.</p>}
    {result?.complete && !result.abstained && <div style={{ overflowX: "auto", marginTop: 18 }}>
      <table style={{ width: "100%", textAlign: "left" }}><thead><tr><th>Wilayah</th><th>Tahun</th><th>Angka</th><th>Satuan</th><th>Sumber</th></tr></thead>
        <tbody>{result.observations.map((p) => <tr key={`${p.area_id}-${p.year}`}>
          <td>{areas.find((a) => a.area_id === p.area_id)?.area_name}</td>
          <td>{p.year}</td><td>{readable(p.value)}</td><td>{p.unit}</td>
          <td>{p.canonical.citations.filter((c) => c.source_url?.startsWith("https://")).map((c, i) =>
            <a key={i} href={c.source_url} target="_blank" rel="noopener noreferrer" style={{ marginRight: 8 }}>Sumber {i + 1}</a>)}</td>
        </tr>)}</tbody></table>
      {result.derived?.map((p, i) => <p key={i}>{analysis === "compare"
        ? `Selisih ${areas.find((a) => a.area_id === p.target.area_id)?.area_name} dikurangi ${areas.find((a) => a.area_id === p.baseline.area_id)?.area_name} (${p.target.year})`
        : `Perubahan ${p.baseline.year}–${p.target.year}`}: <strong>{readable(p.value)} {p.unit}</strong>.</p>)}
      {result.note && <p>{result.note}</p>}
    </div>}
  </section>;
}
