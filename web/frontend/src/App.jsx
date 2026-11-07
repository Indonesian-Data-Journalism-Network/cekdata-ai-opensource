import React, { useEffect, useMemo, useState, useRef, useLayoutEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Search, Link2, ThumbsUp, ThumbsDown, CircleHelp, LogIn, MessageSquare, Send, Info, Copy, Check, Shield, FolderUp, Database, BarChart3, RefreshCw, ChevronDown, Layers3, ArrowLeft } from "lucide-react";
import HomeFooter from "./ui/HomeFooter.jsx";
import AdminLoginPage from "./auth/admin/AdminLoginPage";
import UserLoginPage from "./auth/user/UserLoginPage";
import { API_BASE } from "./config/api";
import { askQuestion, getPublicSearchSources } from "./features/chat/chatApi.js";
import { verifiedSourcesFromClaims } from "./config/verifiedSources.js";
import { upgradeGfwSources } from "./config/gfwPublicLinks.js";
import CanonicalAnswer from "./features/chat/CanonicalAnswer.jsx";
import SourcePicker from "./features/chat/SourcePicker.jsx";
import "./features/chat/ChatLayout.css";
import WorkspaceSidebar from "./features/chat/WorkspaceSidebar.jsx";
import WorkspaceDialog from "./features/chat/WorkspaceDialog.jsx";
import SourceLinks from "./features/chat/SourceLinks.jsx";
import FindingsTable from "./features/chat/FindingsTable.jsx";
import GfwSourceFooter, { hasGfwSources } from "./features/chat/GfwSourceFooter.jsx";
import MapbiomasSourceFooter from "./features/chat/MapbiomasSourceFooter.jsx";
import { hasMapbiomasSources } from "./features/chat/mapbiomasSources.js";
import DocumentSourceFooter from "./features/chat/DocumentSourceFooter.jsx";
import { upgradeContext } from "./features/chat/contextView.js";
import BPSArchiveSearch from "./features/chat/BPSArchiveSearch.jsx";
import BPSStatisticsSearch from "./features/chat/BPSStatisticsSearch.jsx";
import WorkerStatusCard from "./features/admin-normalization/WorkerStatusCard.jsx";
import StorageInventoryCard from "./features/admin-normalization/StorageInventoryCard.jsx";
import NormalizationFailuresCard from "./features/admin-normalization/NormalizationFailuresCard.jsx";
import PineconeMetadataBrowser from "./features/admin-normalization/PineconeMetadataBrowser.jsx";
import RegisteredStatistics from "./features/admin-normalization/RegisteredStatistics.jsx";
import { canonicalAnswerView, canonicalCopyText, continuationQuestion } from "./features/chat/answerView.js";
import { publicSourceOptions, sourcesForRequest } from "./config/sourceSelection";
import { Button, Card, COLORS, Pill, inputStyle, pStyle } from "./ui/ui";

// Global style reset — hapus margin/padding default browser
if (typeof document !== "undefined") {
  const style = document.createElement("style");
  style.textContent = "html, body, #root { margin: 0; padding: 0; width: 100%; min-height: 100vh; }";
  document.head.appendChild(style);
}

function getStoredAuthToken() {
  try {
    return localStorage.getItem("cekdata_auth_token") || "";
  } catch (e) {
    console.error("Gagal membaca auth token", e);
    return "";
  }
}

function getStoredRole() {
  try {
    return localStorage.getItem("cekdata_role") || "";
  } catch (e) {
    console.error("Gagal membaca role", e);
    return "";
  }
}

const demoQuestions = [
  "Berapa persentase penduduk miskin Indonesia pada Maret 2025?",
  "Berapa persentase penduduk miskin Indonesia pada September 2025?",
  "Berapa jumlah penduduk miskin Indonesia pada September 2025?",
  "Berapa jumlah penduduk miskin Indonesia pada September 2024?",
  "Berapa garis kemiskinan Indonesia pada Maret 2025?",
  "Berapa garis kemiskinan Indonesia di perkotaan pada Maret 2025?",
  "Berapa garis kemiskinan Indonesia di perdesaan pada Maret 2025?",
  "Berapa persentase penduduk miskin Aceh pada Maret 2025?",
  "Berapa persentase penduduk miskin Aceh pada September 2025?",
  "Berapa persentase penduduk miskin Sumatera Barat di perdesaan pada Maret 2024?",

  "Bandingkan persentase penduduk miskin Indonesia pada Maret 2024 dan Maret 2025.",
  "Bandingkan persentase penduduk miskin Indonesia pada September 2024 dan September 2025.",
  "Bandingkan jumlah penduduk miskin Indonesia pada September 2024 dan September 2025.",
  "Bandingkan garis kemiskinan Indonesia pada Maret 2024 dan Maret 2025.",
  "Bandingkan persentase penduduk miskin Aceh pada Maret 2024 dan Maret 2025.",
  "Bandingkan persentase penduduk miskin Aceh pada September 2024 dan September 2025.",
  "Bandingkan jumlah penduduk miskin Indonesia di perdesaan pada September 2024 dan September 2025.",
  "Bandingkan garis kemiskinan Indonesia di perkotaan pada Maret 2024 dan Maret 2025.",

  "Bagaimana tren kemiskinan Indonesia dalam lima tahun terakhir?",
  "Bagaimana tren jumlah penduduk miskin Indonesia dalam lima tahun terakhir?",
  "Bagaimana tren jumlah penduduk miskin Indonesia di perdesaan dalam lima tahun terakhir?",
  "Bagaimana tren persentase penduduk miskin Indonesia dalam beberapa tahun terakhir?",
  "Bagaimana tren kemiskinan Aceh dalam beberapa tahun terakhir?",
  "Bagaimana tren garis kemiskinan Indonesia dalam lima tahun terakhir?",
  "Benarkah lima tahun terakhir kemiskinan Indonesia menurun?",
  "Benarkah dalam beberapa tahun terakhir angka kemiskinan nasional cenderung membaik?",
  "Benarkah tren kemiskinan Indonesia dalam lima tahun terakhir tidak selalu lurus turun?",
  "Benarkah dalam lima tahun terakhir jumlah penduduk miskin Indonesia cenderung menurun?",

  "Benarkah tahun ini kemiskinan Indonesia turun?",
  "Benarkah tahun ini jumlah penduduk miskin Indonesia menurun?",
  "Benarkah tahun ini angka kemiskinan nasional membaik?",
  "Benarkah tahun ini persentase penduduk miskin Indonesia lebih rendah dibanding tahun lalu?",
  "Benarkah kondisi kemiskinan Indonesia tahun ini lebih baik dibanding tahun sebelumnya?",
  "Benarkah tahun ini kemiskinan Aceh turun?",
  "Benarkah tahun ini angka kemiskinan Aceh masih di atas rata rata nasional?",
  "Benarkah tahun ini penduduk miskin di Indonesia lebih banyak berada di perdesaan daripada di perkotaan?",

  "Pemerintah menyebut tahun ini kemiskinan turun karena programnya berhasil. Apakah klaim ini benar?",
  "Pemerintah menyebut penurunan kemiskinan tahun ini membuktikan kebijakan mereka berhasil. Apakah klaim ini benar?",
  "Pejabat mengatakan angka kemiskinan yang turun tahun ini adalah bukti program pemerintah efektif. Apakah klaim ini benar?",
  "Benarkah penurunan angka kemiskinan saja belum cukup untuk membuktikan satu program pemerintah berhasil?",

  "Berapa persentase penduduk miskin Indonesia pada September 2025?",
  "Berapa jumlah penduduk miskin Indonesia pada September 2025?",
  "Berapa garis kemiskinan Indonesia di perdesaan pada Maret 2025?",
  "Bandingkan persentase penduduk miskin Aceh pada Maret 2024 dan Maret 2025.",
  "Bandingkan jumlah penduduk miskin Indonesia di perdesaan pada September 2024 dan September 2025.",
  "Bandingkan garis kemiskinan Indonesia pada Maret 2024 dan Maret 2025.",
  "Bagaimana tren persentase penduduk miskin Indonesia dalam beberapa tahun terakhir?",
  "Bagaimana tren jumlah penduduk miskin Indonesia di perdesaan dalam lima tahun terakhir?",
  "Bagaimana tren kemiskinan Aceh dalam beberapa tahun terakhir?",
  "Benarkah tahun ini angka kemiskinan Aceh masih di atas rata rata nasional?",
  "Benarkah tahun ini penduduk miskin di Indonesia lebih banyak berada di perdesaan daripada di perkotaan?",
  "Benarkah kondisi kemiskinan Indonesia tahun ini lebih baik dibanding tahun sebelumnya?",
  "Benarkah tahun ini jumlah penduduk miskin Indonesia menurun?",
  "Pemerintah menyebut penurunan kemiskinan tahun ini membuktikan kebijakan mereka berhasil. Apakah klaim ini benar?",
  "Prabowo mengklaim program MBG berhasil menambah 1 juta pekerja di Indonesia pada 2025. Apakah klaim ini benar?"
];



function renderReadableText(text) {
  const raw = String(text || "").trim();
  if (!raw) return null;

  // Preserve paragraphs and lists even when an answer mixes both.
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length > 1 || /^[-*]\s+/.test(raw)) {
    const blocks = [];
    for (const line of lines) {
      if (/^[-*]\s+/.test(line)) {
        if (blocks.at(-1)?.type !== "list") blocks.push({ type: "list", items: [] });
        blocks.at(-1).items.push(line.replace(/^[-*]\s+/, ""));
      } else {
        blocks.push({ type: "paragraph", text: line });
      }
    }
    return (
      <div style={{ display: "grid", gap: 12, lineHeight: 1.8 }}>
        {blocks.map((block, index) => block.type === "list" ? (
          <ul key={index} style={{ margin: 0, paddingLeft: 22 }}>
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex} style={{ marginBottom: itemIndex < block.items.length - 1 ? 8 : 0 }}>{item}</li>
            ))}
          </ul>
        ) : <p key={index} style={{ margin: 0 }}>{block.text}</p>)}
      </div>
    );
  }

  const yearMatches = [
    ...raw.matchAll(/((?:19|20)\d{2}):\s*([^]+?)(?=(?:\s*-\s*(?:19|20)\d{2}:)|$)/g),
  ];

  if (yearMatches.length >= 2) {
    const beforeFirst = raw.slice(0, yearMatches[0].index).trim();

    const cleanedMatches = yearMatches.map((m, idx) => {
      let valueText = m[2].trim();
      let trailing = "";

      if (idx === yearMatches.length - 1) {
        const splitMatch = valueText.match(/^(.*?)(\s+(Perubahan total.*|Pola:.*))$/i);
        if (splitMatch) {
          valueText = splitMatch[1].trim();
          trailing = splitMatch[2].trim();
        }
      }

      return {
        year: m[1],
        valueText,
        trailing,
      };
    });

    const trailingText = cleanedMatches
      .map((x) => x.trailing)
      .filter(Boolean)
      .join(" ")
      .trim();

    return (
      <div style={{ lineHeight: 1.8 }}>
        {beforeFirst ? <p style={{ marginTop: 0, marginBottom: 12 }}>{beforeFirst}</p> : null}

        <div style={{ display: "grid", gap: 8 }}>
          {cleanedMatches.map((m, idx) => (
            <div
              key={idx}
              style={{
                display: "grid",
                gridTemplateColumns: "64px 1fr",
                gap: 8,
                alignItems: "start",
              }}
            >
              <div style={{ fontWeight: 700 }}>{m.year}</div>
              <div>{m.valueText}</div>
            </div>
          ))}
        </div>

        {trailingText ? (
          <p style={{ marginTop: 12, marginBottom: 0 }}>{trailingText}</p>
        ) : null}
      </div>
    );
  }

  const bulletParts = raw
    .split(/\s+-\s+/)
    .map((x) => x.trim())
    .filter(Boolean);

  if (bulletParts.length >= 3) {
    return (
      <div style={{ display: "grid", gap: 8 }}>
        {bulletParts.map((item, idx) => (
          <div key={idx} style={{ lineHeight: 1.8 }}>
            • {item}
          </div>
        ))}
      </div>
    );
  }

  return <p style={{ margin: 0, textAlign: "left", lineHeight: 1.8 }}>{raw}</p>;
}

function DownloadLinks({ value }) {
  if (!value) return null;

  const links = Array.isArray(value) ? value.filter(Boolean) : [value].filter(Boolean);
  if (!links.length) return null;

  function toAbsoluteUrl(link) {
    if (!link) return "#";
    if (/^https?:\/\//i.test(link)) return link;
    if (link.startsWith("/")) return API_BASE + link;
    return API_BASE + "/" + link;
  }

  function labelFromLink(link) {
    try {
      const url = new URL(link);
      if (url.hostname === 'data-api.globalforestwatch.org' && url.pathname.endsWith('/download/json')) {
        return 'Data terfilter GFW (JSON/API)';
      }
      // Google Drive URL: ambil nama file dari parameter &filename=
      if (link.includes("drive.google.com") && link.includes("filename=")) {
        const match = link.match(/filename=([^&]+)/);
        if (match) return decodeURIComponent(match[1]);
      }
      const raw = link.split("/").pop() || link;
      const decoded = decodeURIComponent(raw);
      return decoded.replace(/\.csv$/i, ".csv");
    } catch (e) {
      return link;
    }
  }

  return (
    <div style={{ marginTop: 12 }}>
      <div
        style={{
          marginBottom: 8,
          fontSize: 15,
          fontWeight: 700,
          color: COLORS.primaryDark,
        }}
      >
        Unduh data
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {links.map((link, idx) => (
          <a
            key={idx}
            href={toAbsoluteUrl(link)}
            target="_blank"
            rel="noreferrer"
            style={{
              color: COLORS.primaryDark,
              fontWeight: 700,
              textDecoration: "none",
              wordBreak: "break-word",
              lineHeight: 1.5,
            }}
          >
            {labelFromLink(link)}
          </a>
        ))}
      </div>
    </div>
  );
}

function VerifiedSources({ claims }) {
  const sources = verifiedSourcesFromClaims(claims);
  if (!sources.length) return null;
  return (
    <Section title="Sumber terverifikasi">
      <div style={{ display: "grid", gap: 10 }}>
        {sources.map((source) => (
          <div key={`${source.citationId}:${source.sourceUrl}`} style={{ border: "1px solid rgba(17,17,17,0.08)", borderRadius: 12, padding: 12 }}>
            <div style={{ fontWeight: 700 }}>{source.locator || source.citationId}</div>
            <div style={{ color: COLORS.muted, fontSize: 12, wordBreak: "break-all", marginTop: 4 }}>
              Evidence {source.evidenceId} · Version {source.documentVersionId}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
              <a href={source.sourceUrl} target="_blank" rel="noreferrer">Buka sumber</a>
              {source.downloadUrl ? <a href={source.downloadUrl} target="_blank" rel="noreferrer">Unduh file</a> : null}
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginTop: 16, textAlign: "left" }}>
      <div
        style={{
          marginBottom: 6,
          fontSize: 13,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: 0.6,
          color: COLORS.muted,
        }}
      >
        {title}
      </div>
      {React.isValidElement(children) ? <div style={{ lineHeight: 1.8 }}>{children}</div> : renderReadableText(children)}
    </div>
  );
}

function verdictTone(verdict) {
  const v = (verdict || "").toLowerCase();
  if (v === "benar") return { bg: "#dcfce7", color: "#166534" };
  if (v.includes("sebagian")) return { bg: "#fef3c7", color: "#92400e" };
  if (v.includes("menyesatkan")) return { bg: "#ffe4e6", color: "#be123c" };
  return { bg: "#e2e8f0", color: "#475569" };
}

function feedbackChipStyle(active) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    borderRadius: 9999,
    border: active ? `1px solid ${COLORS.primary}` : "1px solid rgba(17,17,17,0.12)",
    background: active ? "#fff1f7" : "white",
    color: active ? COLORS.primaryDark : COLORS.text,
    padding: "10px 14px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  };
}

export function Header({ page, setPage, isLoggedIn, isAdmin, handleSignOut }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 640);
  useEffect(() => {
    const resize = () => setIsMobile(window.innerWidth <= 640);
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  return (
    <div style={{ borderBottom: `1px solid ${COLORS.border}`, position: "relative" }}>
      <div
        style={{
          width: "100%",
          padding: "12px 28px",
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: 16,
          boxSizing: "border-box",
        }}
      >
        <div style={{ justifySelf: "start" }}>
          {!isMobile && isLoggedIn ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button variant="outline" onClick={() => setPage("chat")}>Open Chat</Button>
              {isAdmin ? (
                <Button variant="outline" onClick={() => setPage("admin")}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <Shield size={16} />
                    Admin
                  </span>
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>

        <button
          onClick={() => {
            setPage("home");
            setMenuOpen(false);
          }}
          style={{
            background: "transparent",
            border: "none",
            cursor: "pointer",
            fontSize: isMobile ? 24 : 32,
            fontWeight: 900,
            justifySelf: "center",
          }}
        >
          <span style={{ color: COLORS.primary }}>cekdata</span>
          <span style={{ color: "#111111" }}>.ai</span>
        </button>

        {isMobile ? (
          <div style={{ justifySelf: "end", position: "relative" }}>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              style={{
                border: "none",
                background: "transparent",
                width: 32,
                height: 32,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                padding: 0,
                color: COLORS.text,
              }}
            >
              <Menu size={22} />
            </button>

            {menuOpen ? (
              <div
                style={{
                  position: "absolute",
                  top: 44,
                  right: 0,
                  width: 220,
                  background: "white",
                  border: "1px solid rgba(17,17,17,0.08)",
                  borderRadius: 18,
                  boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
                  padding: 10,
                  zIndex: 50,
                }}
              >
                <button
                  onClick={() => {
                    setPage("about");
                    setMenuOpen(false);
                  }}
                  style={mobileMenuButtonStyle}
                >
                  About Cek Data AI
                </button>

                {!isLoggedIn ? (
                  <button
                    onClick={() => {
                      setPage("signin");
                      setMenuOpen(false);
                    }}
                    style={mobileMenuButtonStyle}
                  >
                    Sign In
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => {
                        setPage("chat");
                        setMenuOpen(false);
                      }}
                      style={mobileMenuButtonStyle}
                    >
                      Open Chat
                    </button>
                    {isAdmin ? (
                      <button
                        onClick={() => {
                          setPage("admin");
                          setMenuOpen(false);
                        }}
                        style={mobileMenuButtonStyle}
                      >
                        Admin
                      </button>
                    ) : null}
                    <button
                      onClick={() => {
                        handleSignOut();
                        setMenuOpen(false);
                      }}
                      style={mobileMenuButtonStyle}
                    >
                      Sign Out
                    </button>
                  </>
                )}
              </div>
            ) : null}
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: 8, justifySelf: "end" }}>
            {page !== "about" ? (
              <Button variant="outline" onClick={() => setPage("about")}>
                About Cek Data AI
              </Button>
            ) : null}

            {!isLoggedIn && page !== "signin" ? (
              <Button variant="outline" onClick={() => setPage("signin")}>
                Sign In
              </Button>
            ) : null}

            {isLoggedIn ? (
              <>
                {isAdmin && page !== "admin" ? (
                  <Button variant="outline" onClick={() => setPage("admin")}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <Shield size={16} />
                      Admin
                    </span>
                  </Button>
                ) : null}
                <Button variant="outline" onClick={handleSignOut}>
                  Sign Out
                </Button>
              </>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

const mobileMenuButtonStyle = {
  width: "100%",
  textAlign: "left",
  border: "none",
  background: "transparent",
  padding: "12px 12px",
  borderRadius: 12,
  cursor: "pointer",
  fontSize: 15,
  fontWeight: 600,
  color: COLORS.text,
};

const secondaryButtonStyle = {
  border: "1px solid rgba(17,17,17,0.12)",
  background: "white",
  color: COLORS.text,
  borderRadius: 16,
  padding: "12px 18px",
  fontSize: 15,
  fontWeight: 700,
  cursor: "pointer",
};

export function HomePage({ setPage, localMode = false, onStart }) {
  const [demoQuestion, setDemoQuestion] = useState(demoQuestions[0]);
  const [showDemoAnswer, setShowDemoAnswer] = useState(false);
  const [demoResult, setDemoResult] = useState(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState("");

  useEffect(() => {
    const pick = demoQuestions[Math.floor(Math.random() * demoQuestions.length)];
    setDemoQuestion(pick);
  }, []);

  function refreshDemoQuestion() {
    let next = demoQuestion;
    while (demoQuestions.length > 1 && next === demoQuestion) {
      next = demoQuestions[Math.floor(Math.random() * demoQuestions.length)];
    }
    setDemoQuestion(next);
    setShowDemoAnswer(false);
    setDemoResult(null);
    setDemoError("");
  }

  async function handleDemoAsk() {
    if (localMode) { onStart?.(); return; }
    try {
      setDemoLoading(true);
      setDemoError("");
      setShowDemoAnswer(false);
      setDemoResult(null);

      const data = await askQuestion({ question: demoQuestion, sources: ['bps'] });

      setDemoResult(data);
      setShowDemoAnswer(true);
    } catch (err) {
      setDemoError(err.message || "Terjadi kesalahan");
    } finally {
      setDemoLoading(false);
    }
  }

  const verdict = verdictTone(demoResult?.parsed?.penilaian || "");

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "40px 24px 56px" }}>
      <div
        style={{
          maxWidth: 920,
          margin: "0 auto",
          textAlign: "center",
          padding: "0 12px",
          boxSizing: "border-box",
        }}
      >
        <p
          style={{
            maxWidth: 760,
            margin: "0 auto",
            fontSize: 20,
            lineHeight: 1.8,
            color: COLORS.muted,
          }}
        >
          Cek Data AI adalah alat bantu bagi jurnalis untuk memverifikasi klaim data dan mengujinya dengan sumber resmi serta terpercaya.
        </p>
      </div>

      <div
        style={{
          maxWidth: 980,
          margin: "56px auto 0",
          padding: "0 12px",
          boxSizing: "border-box",
        }}
      >
        <Card>
          <div style={{ padding: 24 }}>
            <div
              style={{
                marginBottom: 18,
                fontSize: 14,
                fontWeight: 700,
                color: COLORS.muted,
                textTransform: "uppercase",
                letterSpacing: 0.6,
                textAlign: "center",
              }}
            >
              Coba versi demo
            </div>

            <div style={{ display: "grid", gap: 16 }}>
              <div style={{ display: "flex", justifyContent: "center" }}>
                <div
                  style={{
                    width: "100%",
                    maxWidth: "100%",
                    borderRadius: 28,
                    padding: "18px 20px",
                    background: COLORS.primary,
                    color: "white",
                    textAlign: "left",
                    fontSize: 16,
                    lineHeight: 1.7,
                  }}
                >
                  {demoQuestion}
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap" }}>
                <Button onClick={handleDemoAsk} disabled={demoLoading}>
                  {demoLoading ? "Memverifikasi..." : localMode ? "Masuk untuk verifikasi" : "Verifikasi"}
                </Button>
                <Button variant="outline" onClick={refreshDemoQuestion} disabled={demoLoading}>
                  Refresh
                </Button>
              </div>

              {demoError ? (
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <div
                    style={{
                      width: "100%",
                      maxWidth: 760,
                      borderRadius: 20,
                      padding: 16,
                      background: "#fff1f1",
                      color: "#9f1d1d",
                      textAlign: "left",
                    }}
                  >
                    {demoError}
                  </div>
                </div>
              ) : null}

              {showDemoAnswer && canonicalAnswerView(demoResult) ? <CanonicalAnswer result={demoResult} /> : null}
              {showDemoAnswer && !canonicalAnswerView(demoResult) && !demoResult?.parsed && demoResult?.answer
                ? <p style={{ whiteSpace: 'pre-wrap' }}>{demoResult.answer}</p> : null}
              {showDemoAnswer && !canonicalAnswerView(demoResult) && demoResult?.parsed ? (
                <div style={{ display: "flex", justifyContent: "flex-start" }}>
                  <div
                    style={{
                      maxWidth: "100%",
                      borderRadius: 28,
                      padding: 20,
                      background: "white",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                      textAlign: "left",
                    }}
                  >
                    <div style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 10 }}>
                      <Pill style={{ background: COLORS.primary, color: "white" }}>Demo jawaban</Pill>
                      {demoResult.parsed.penilaian ? (
                        <Pill style={{ background: verdict.bg, color: verdict.color }}>
                          {demoResult.parsed.penilaian}
                        </Pill>
                      ) : null}
                    </div>

                    {!demoResult.parsed.temuan_data &&
                    !demoResult.parsed.konteks_penting &&
                    !demoResult.parsed.penilaian &&
                    !demoResult.parsed.alasan &&
                    !demoResult.parsed.peringatan_editorial &&
                    !demoResult.parsed.sumber &&
                    demoResult.answer ? (
                      <p
                        style={{
                          margin: 0,
                          lineHeight: 1.8,
                          color: COLORS.text,
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {demoResult.answer}
                      </p>
                    ) : null}

                    {demoResult.parsed.temuan_data ? (
                      <Section title="Temuan data">{demoResult.parsed.temuan_data}</Section>
                    ) : null}
                    {demoResult.parsed.kesimpulan ? (
                      <Section title="Kesimpulan">{demoResult.parsed.kesimpulan}</Section>
                    ) : null}
                    {demoResult.parsed.konteks_penting ? (
                      <Section title="Konteks">{demoResult.parsed.konteks_penting}</Section>
                    ) : null}
                    {demoResult.parsed.penilaian ? (
                      <Section title="Penilaian">{demoResult.parsed.penilaian}</Section>
                    ) : null}
                    {demoResult.parsed.alasan ? (
                      <Section title="Alasan">{demoResult.parsed.alasan}</Section>
                    ) : null}

                    {demoResult.parsed.peringatan_editorial ? (
                      <div
                        style={{
                          marginTop: 16,
                          borderRadius: 20,
                          padding: 16,
                          background: "#fff7fb",
                          border: "1px solid rgba(239,91,156,0.25)",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: 8,
                            fontSize: 13,
                            fontWeight: 700,
                            color: COLORS.primaryDark,
                            textTransform: "uppercase",
                          }}
                        >
                          Peringatan editorial
                        </div>
                        <p style={{ margin: 0, lineHeight: 1.7 }}>
                          {demoResult.parsed.peringatan_editorial}
                        </p>
                      </div>
                    ) : null}

                    {demoResult.parsed.followup_prompt ? (
                      <div
                        style={{
                          marginTop: 16,
                          borderRadius: 20,
                          padding: 16,
                          background: "#f0f4ff",
                          border: "1px solid rgba(41,128,185,0.25)",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: 8,
                            fontSize: 13,
                            fontWeight: 700,
                            color: "#2980b9",
                            textTransform: "uppercase",
                          }}
                        >
                          Bantu kami membantu kamu
                        </div>
                        <p style={{ margin: 0, lineHeight: 1.7 }}>
                          {demoResult.parsed.followup_prompt}
                        </p>
                      </div>
                    ) : null}

                    {demoResult.parsed.sumber ? (
                      <Section title="Sumber">{demoResult.parsed.sumber}</Section>
                    ) : null}

                    {demoResult.parsed.unduh_data ? (
                      <DownloadLinks value={demoResult.parsed.unduh_data} />
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </Card>

        <div
          style={{
            marginTop: 18,
            textAlign: "center",
            color: COLORS.muted,
            lineHeight: 1.7,
            fontSize: 14,
            maxWidth: 760,
            marginLeft: "auto",
            marginRight: "auto",
            padding: "0 12px",
            boxSizing: "border-box",
          }}
        >
          {localMode ? 'Buka chat dan hubungkan sesi untuk memeriksa data. Riwayat sebelumnya tetap tersimpan di browser ini.' : 'Akses penuh ke fitur chat saat ini hanya tersedia bagi pengguna uji coba yang telah memperoleh akun dari admin. Untuk mencoba versi penuh, silakan hubungi admin.'}
        </div>
      </div>
    </div>
  );
}

export function AboutPage() {
  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "40px 24px 56px" }}>
      <Card>
        <div style={{ padding: 32, textAlign: "left" }}>
          <div
            style={{
              marginBottom: 10,
              fontSize: 14,
              fontWeight: 700,
              color: COLORS.muted,
              textTransform: "uppercase",
              letterSpacing: 0.6,
            }}
          >
            About Cek Data AI
          </div>

          <p style={pStyle}>
            Cek Data AI adalah prototipe yang membantu jurnalis memeriksa klaim menggunakan data resmi. Sistem ini dirancang untuk mendukung proses verifikasi awal agar klaim publik, terutama yang berkaitan dengan angka dan statistik, tidak langsung diterima begitu saja tanpa pemeriksaan data.
          </p>

          <p style={pStyle}>
            Cek Data AI dikembangkan oleh tim{" "}
            <a
              href="https://idjnetwork.org"
              target="_blank"
              rel="noreferrer"
              style={{ color: COLORS.primaryDark, fontWeight: 700, textDecoration: "none" }}
            >
              Indonesia Data Journalism Network (IDJN)
            </a>{" "}
            sebagai bagian dari upaya memperkuat praktik jurnalisme berbasis data dan verifikasi berbasis bukti di Indonesia.
          </p>

          <div
            style={{
              marginTop: 28,
              marginBottom: 14,
              fontSize: 14,
              fontWeight: 700,
              color: COLORS.muted,
              textTransform: "uppercase",
              letterSpacing: 0.6,
            }}
          >
            Methodology
          </div>

          <p style={pStyle}>
            Cek Data AI membantu jurnalis memeriksa klaim menggunakan data resmi. Sistem ini bekerja dengan mencari data yang paling relevan dari basis pengetahuan yang sudah disiapkan, lalu menggunakan AI untuk membantu menyusun jawaban.
          </p>

          <p style={pStyle}>
            Pada tahap ini, basis pengetahuan Cek Data AI memuat sekitar 10.000 tabel data resmi dari BPS. Sebelum digunakan, data tersebut terlebih dahulu dibersihkan dan disusun ulang agar lebih rapi, lebih konsisten, dan lebih mudah dicari oleh sistem.
          </p>

          <p style={pStyle}>
            Saat pengguna mengajukan pertanyaan, sistem mencoba mengenali topik, wilayah, dan periode waktu yang dimaksud, lalu mencari data yang paling sesuai. Jawaban kemudian disusun berdasarkan data yang ditemukan. Jika data yang relevan belum tersedia, sistem seharusnya menyatakan keterbatasan itu secara terbuka.
          </p>

          <p style={{ ...pStyle, marginBottom: 0 }}>
            Sebagai prototipe, Cek Data AI masih dalam tahap pengujian terbatas. Cakupan data dan kualitas sistem akan terus diperbaiki seiring proses uji coba. Untuk saat ini, akses penuh ke fitur chat hanya tersedia bagi pengguna yang telah memperoleh akun uji coba dari admin.
          </p>

          <div
            style={{
              marginTop: 28,
              marginBottom: 14,
              fontSize: 14,
              fontWeight: 700,
              color: COLORS.muted,
              textTransform: "uppercase",
              letterSpacing: 0.6,
            }}
          >
            Editorial Review
          </div>

          <p style={pStyle}>
            Cek Data AI tidak hanya mencocokkan klaim dengan angka, tetapi juga membantu membaca apakah data yang ditemukan benar benar cukup untuk mendukung sebuah klaim. Karena itu, hasil verifikasi tidak berhenti pada temuan data, tetapi juga dilengkapi dengan penilaian dan catatan editorial.
          </p>

          <p style={pStyle}>
            <strong>Benar</strong> digunakan ketika klaim didukung oleh data yang relevan, sebanding, dan cukup jelas.
          </p>

          <p style={pStyle}>
            <strong>Salah</strong> digunakan ketika data yang tersedia secara langsung bertentangan dengan klaim yang diajukan.
          </p>

          <p style={pStyle}>
            <strong>Sebagian benar</strong> digunakan ketika klaim memakai sebagian data yang benar, tetapi kesimpulan yang ditarik berlebihan, tidak utuh, atau melompat lebih jauh daripada yang bisa dibuktikan data.
          </p>

          <p style={pStyle}>
            <strong>Tidak dapat diverifikasi</strong> digunakan ketika data yang tersedia belum cukup untuk mendukung penilaian tegas, misalnya karena pembanding tidak lengkap, periode tidak setara, indikator yang dipakai tidak tepat, atau data yang tersedia belum cukup untuk membuktikan klaim.
          </p>

          <p style={pStyle}>
            <strong>Peringatan editorial</strong> ditampilkan ketika data yang ditemukan perlu dibaca dengan kehati-hatian tambahan. Fitur ini penting terutama untuk klaim sebab-akibat, klaim keberhasilan program, atau klaim yang melompat dari perubahan angka ke kesimpulan politik atau kebijakan. Dalam situasi seperti ini, Cek Data AI membantu menunjukkan batas pembacaan data dan memunculkan pertanyaan kritis yang bisa dipakai untuk tindak lanjut jurnalistik.
          </p>

          <p style={{ ...pStyle, marginBottom: 0 }}>
            Secara sederhana, data yang ditemukan belum tentu otomatis membuktikan sebuah klaim. Di situlah penilaian dan editorial review membantu pengguna membedakan antara angka, konteks, dan kesimpulan.
          </p>
        </div>
      </Card>
    </div>
  );
}


function AdminPage({ isAdmin, onAuthExpired }) {
  const initialPineconeLimit = 10;
  const initialActivityLimit = 10;
  const [defaultSourceUrl, setDefaultSourceUrl] = useState("");
  const [defaultDownloadUrl, setDefaultDownloadUrl] = useState("");
  const [uploadSourceDomain, setUploadSourceDomain] = useState("bps");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [users, setUsers] = useState([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersLimit, setUsersLimit] = useState(10);
  const [usersOffset, setUsersOffset] = useState(0);
  const [usersSearch, setUsersSearch] = useState("");
  const [usersRoleFilter, setUsersRoleFilter] = useState("");
  const [usersStatusFilter, setUsersStatusFilter] = useState("");
  const [usersLoading, setUsersLoading] = useState(false);
  const [batches, setBatches] = useState([]);
  const [ingestionHistory, setIngestionHistory] = useState({ records: [], total: 0 });
  const [activityHistory, setActivityHistory] = useState({ auth_sessions: [], chat_messages: [], auth_total: 0, chat_total: 0, limit: initialActivityLimit });
  const [activityUserEmail, setActivityUserEmail] = useState("");
  const [activityLoading, setActivityLoading] = useState(false);
  const [activeBatch, setActiveBatch] = useState(null);
  const [recordInspector, setRecordInspector] = useState(null);
  const [publishPreview, setPublishPreview] = useState(null);
  const [pineconeSummary, setPineconeSummary] = useState(null);
  const [pineconeRecords, setPineconeRecords] = useState({ records: [], total: 0, limit: initialPineconeLimit, offset: 0 });
  const [pineconeSearch, setPineconeSearch] = useState("");
  const [pineconeFilters, setPineconeFilters] = useState({
    province: "",
    province_code: "",
    regency: "",
    regency_code: "",
    district: "",
    district_code: "",
    village: "",
    village_code: "",
    year_value: "",
    area_level: "",
    doc_type: "",
    source_file: "",
    source: "",
    period: "",
    topic_primary: "",
    topic_secondary: "",
    breakdown_value: "",
    subgroup_value: "",
    source_code_region: "",
    batch_id: "",
    dataset_id: "",
    series_label: "",
  });
  const [pineconeOffset, setPineconeOffset] = useState(0);
  const [selectedPineconeIds, setSelectedPineconeIds] = useState([]);
  const [bulkPineconeEdit, setBulkPineconeEdit] = useState({
    source: "",
    province: "",
    province_code: "",
    regency: "",
    regency_code: "",
    district: "",
    district_code: "",
    village: "",
    village_code: "",
    year_value: "",
    series_label: "",
    topic_primary: "",
    subgroup_label: "",
  });
  const [bulkPineconeSaving, setBulkPineconeSaving] = useState(false);
  const [pineconeScanCursor, setPineconeScanCursor] = useState("");
  const [pineconeLoading, setPineconeLoading] = useState(false);
  const [pineconeScan, setPineconeScan] = useState(null);
  const [pineconeScanLoading, setPineconeScanLoading] = useState(false);
  const [editingPineconeRecord, setEditingPineconeRecord] = useState(null);
  const [regionOptions, setRegionOptions] = useState({ provinces: [], regencies: [], districts: [], villages: [] });
  const [regionLoading, setRegionLoading] = useState(false);
  const [selectedRecordId, setSelectedRecordId] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [newUserOrganization, setNewUserOrganization] = useState("");
  const [newUserPhone, setNewUserPhone] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserRole, setNewUserRole] = useState("trial");
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [publishLoading, setPublishLoading] = useState("");
  const [recordLoading, setRecordLoading] = useState("");
  const [normalizationDrafts, setNormalizationDrafts] = useState({});
  const [normalizationForms, setNormalizationForms] = useState({});
  const [normalizationLoading, setNormalizationLoading] = useState("");
  const [createUserLoading, setCreateUserLoading] = useState(false);
  const [confirmationLoadingEmail, setConfirmationLoadingEmail] = useState("");
  const [userActionLoading, setUserActionLoading] = useState("");
  const [confirmationStatusByEmail, setConfirmationStatusByEmail] = useState({});
  const [gmailSetting, setGmailSetting] = useState(null);
  const [gmailSettingLoading, setGmailSettingLoading] = useState(false);
  const [adminTab, setAdminTab] = useState("ingestion");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function fetchAdminJson(path, options = {}) {
    const token = getStoredAuthToken();
    if (!token) {
      onAuthExpired?.();
      throw new Error("Session admin tidak ditemukan. Silakan login ulang.");
    }

    const headers = {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    };
    const res = await fetch(API_BASE + path, {
      ...options,
      headers,
    });
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
    if (res.status === 401) {
      onAuthExpired?.();
      throw new Error(data?.detail || "Session admin sudah berakhir. Silakan login ulang.");
    }
    if (!res.ok) {
      throw new Error(data?.detail || "Permintaan admin gagal.");
    }
    return data;
  }

  async function inspectBatchFile(batchId, fileId) {
    const data = await fetchAdminJson(`/admin/batches/${batchId}/files/${fileId}/records?limit=80`);
    setRecordInspector(data);
    setSelectedRecordId(data.records?.[0]?.id || "");
    return data;
  }

  async function openNormalizationReview(batchId, fileId) {
    const key = `${batchId}:${fileId}`;
    try {
      setNormalizationLoading(key);
      setError("");
      const draft = await fetchAdminJson(`/admin/batches/${batchId}/files/${fileId}/normalization-review`);
      setNormalizationDrafts((prev) => ({ ...prev, [key]: draft }));
      setNormalizationForms((prev) => ({
        ...prev,
        [key]: {
          source_url: draft.form?.source_url || "",
          download_url: draft.form?.download_url || "",
          dataset_title: draft.form?.dataset_title || "",
          domain_payload: JSON.stringify(draft.form?.domain_payload || {}, null, 2),
          approved: false,
        },
      }));
    } catch (err) {
      setError(err.message || "Gagal membuka draft normalisasi.");
    } finally {
      setNormalizationLoading("");
    }
  }

  function updateNormalizationForm(key, field, value) {
    setNormalizationForms((prev) => ({
      ...prev,
      [key]: { ...(prev[key] || {}), [field]: value },
    }));
  }

  async function approveNormalization(batchId, fileId) {
    const key = `${batchId}:${fileId}`;
    const draft = normalizationDrafts[key];
    const form = normalizationForms[key] || {};
    if (!form.approved) {
      setError("Centang persetujuan sebelum menyimpan dan meneruskan data.");
      return;
    }
    let domainPayload = {};
    try {
      domainPayload = draft?.source_domain === "bps" ? {} : JSON.parse(form.domain_payload || "{}");
    } catch (err) {
      setError("Payload domain harus berupa JSON yang valid.");
      return;
    }
    try {
      setNormalizationLoading(key);
      setError("");
      await fetchAdminJson(`/admin/batches/${batchId}/files/${fileId}/normalization-review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved: true,
          source_url: form.source_url || "",
          download_url: form.download_url || "",
          dataset_title: form.dataset_title || "",
          domain_payload: domainPayload,
        }),
      });
      setSuccess("Review disimpan. Data disetujui, masuk canonical MySQL, dan antre ke Pinecone.");
      setNormalizationDrafts((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      await loadOverview(batchId);
    } catch (err) {
      setError(err.message || "Gagal menyimpan persetujuan normalisasi.");
    } finally {
      setNormalizationLoading("");
    }
  }

  async function loadPublishPreview(batchId) {
    if (!batchId) {
      setPublishPreview(null);
      return null;
    }
    const data = await fetchAdminJson(`/admin/batches/${batchId}/publish-preview?limit=6`);
    setPublishPreview(data);
    return data;
  }

  async function maybeAutoInspect(batch) {
    const readyFile = (batch?.files || []).find((item) => item.parse_status === "ready");
    if (!batch?.id || !readyFile?.id) {
      setRecordInspector(null);
      setPublishPreview(null);
      setSelectedRecordId("");
      return;
    }
    await loadPublishPreview(batch.id);
    await inspectBatchFile(batch.id, readyFile.id);
  }

  function updateEditingRegionField(field, value) {
    setEditingPineconeRecord((prev) => prev ? { ...prev, [field]: value } : prev);
  }

  async function handleRegionAutocomplete(kind, value) {
    const optionKey = kind === "province" ? "provinces" : kind === "regency" ? "regencies" : kind === "district" ? "districts" : "villages";
    const nameField = kind === "province" ? "province" : kind === "regency" ? "regency" : kind === "district" ? "district" : "village";
    const codeField = `${nameField}_code`;
    const selected = (regionOptions[optionKey] || []).find((item) => String(item.name || "").toLowerCase() === String(value || "").toLowerCase());

    setEditingPineconeRecord((prev) => prev ? { ...prev, [nameField]: value, [codeField]: selected?.id || prev[codeField] || "" } : prev);
    if (selected?.id) {
      await handleRegionSelect(kind, selected.id);
    }
  }

  async function loadGmailSetting() {
    setGmailSettingLoading(true);
    try {
      const data = await fetchAdminJson("/admin/email/gmail/status");
      setGmailSetting(data);
    } catch (err) {
      setError(err.message || "Gagal memuat setting Gmail API.");
    } finally {
      setGmailSettingLoading(false);
    }
  }

  async function startGmailOAuthConnect() {
    setGmailSettingLoading(true);
    try {
      const data = await fetchAdminJson("/admin/email/gmail/auth-url");
      setGmailSetting((prev) => ({ ...(prev || {}), redirect_uri: data.redirect_uri }));
      if (data.auth_url) {
        window.open(data.auth_url, "_blank", "noopener,noreferrer");
        setSuccess("Auth URL Gmail dibuka. Setelah consent selesai, klik Refresh Status Gmail API.");
      }
    } catch (err) {
      setError(err.message || "Gagal membuat auth URL Gmail API.");
    } finally {
      setGmailSettingLoading(false);
    }
  }

  async function loadRegions(kind, parentId = "") {
    const path =
      kind === "provinces"
        ? "/admin/regions/provinces"
        : kind === "regencies"
          ? `/admin/regions/regencies/${parentId}`
          : kind === "districts"
            ? `/admin/regions/districts/${parentId}`
            : `/admin/regions/villages/${parentId}`;
    const data = await fetchAdminJson(path);
    setRegionOptions((prev) => ({ ...prev, [kind]: data.regions || [] }));
    return data.regions || [];
  }

  async function startEditPineconeRecord(record) {
    setEditingPineconeRecord({
      pinecone_id: record.pinecone_id || "",
      province: record.metadata?.scan_province || record.metadata?.provinsi || record.metadata?.province || "",
      province_code: record.metadata?.scan_province_code || record.metadata?.province_code || record.metadata?.kode_provinsi || "",
      regency: record.metadata?.scan_regency || record.metadata?.kabupaten_kota || record.metadata?.kabupaten || record.metadata?.kota || "",
      regency_code: record.metadata?.scan_regency_code || record.metadata?.regency_code || record.metadata?.kode_kabupaten || record.metadata?.kode_kota || "",
      district: record.metadata?.scan_district || record.metadata?.kecamatan || record.metadata?.district || "",
      district_code: record.metadata?.scan_district_code || record.metadata?.district_code || record.metadata?.kode_kecamatan || "",
      village: record.metadata?.scan_village || record.metadata?.kelurahan || record.metadata?.desa || record.metadata?.village || "",
      village_code: record.metadata?.scan_village_code || record.metadata?.village_code || record.metadata?.kode_kelurahan || record.metadata?.kode_desa || "",
    });
    try {
      setRegionLoading(true);
      await loadRegions("provinces");
    } catch (err) {
      setError(err.message || "Gagal memuat data provinsi.");
    } finally {
      setRegionLoading(false);
    }
  }

  async function handleRegionSelect(kind, idValue) {
    const optionKey = kind === "province" ? "provinces" : kind === "regency" ? "regencies" : kind === "district" ? "districts" : "villages";
    const selected = (regionOptions[optionKey] || []).find((item) => String(item.id) === String(idValue));
    const name = selected?.name || "";
    setEditingPineconeRecord((prev) => {
      if (!prev) return prev;
      if (kind === "province") {
        return { ...prev, province: name, province_code: idValue, regency: "", regency_code: "", district: "", district_code: "", village: "", village_code: "" };
      }
      if (kind === "regency") {
        return { ...prev, regency: name, regency_code: idValue, district: "", district_code: "", village: "", village_code: "" };
      }
      if (kind === "district") {
        return { ...prev, district: name, district_code: idValue, village: "", village_code: "" };
      }
      return { ...prev, village: name, village_code: idValue };
    });
    try {
      setRegionLoading(true);
      if (kind === "province" && idValue) {
        setRegionOptions((prev) => ({ ...prev, regencies: [], districts: [], villages: [] }));
        await loadRegions("regencies", idValue);
      } else if (kind === "regency" && idValue) {
        setRegionOptions((prev) => ({ ...prev, districts: [], villages: [] }));
        await loadRegions("districts", idValue);
      } else if (kind === "district" && idValue) {
        setRegionOptions((prev) => ({ ...prev, villages: [] }));
        await loadRegions("villages", idValue);
      }
    } catch (err) {
      setError(err.message || "Gagal memuat data wilayah.");
    } finally {
      setRegionLoading(false);
    }
  }

  async function savePineconeRecordRegion() {
    if (!editingPineconeRecord?.pinecone_id) return;
    try {
      setRegionLoading(true);
      setError("");
      await fetchAdminJson(`/admin/pinecone/records/${encodeURIComponent(editingPineconeRecord.pinecone_id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editingPineconeRecord),
      });
      setSuccess("Wilayah data Pinecone berhasil diperbarui di MySQL.");
      setEditingPineconeRecord(null);
      await loadPineconeData(pineconeSearch, pineconeOffset, pineconeFilters);
    } catch (err) {
      setError(err.message || "Gagal menyimpan wilayah data Pinecone.");
    } finally {
      setRegionLoading(false);
    }
  }

  async function loadPineconeData(searchValue = pineconeSearch, offsetValue = pineconeOffset, filterValue = pineconeFilters, limitValue = 50) {
    setPineconeLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(limitValue), offset: String(Math.max(0, offsetValue || 0)) });
      const trimmed = searchValue.trim();
      if (trimmed) params.set("search", trimmed);
      Object.entries(filterValue || {}).forEach(([key, value]) => {
        if (key.endsWith("_code")) return;
        const clean = String(value || "").trim();
        if (clean) params.set(key, clean);
      });
      const [summaryRes, recordsRes] = await Promise.all([
        fetchAdminJson("/admin/pinecone/summary"),
        fetchAdminJson(`/admin/pinecone/records?${params.toString()}`),
      ]);
      setPineconeSummary(summaryRes);
      setPineconeRecords(recordsRes);
      setPineconeOffset(recordsRes.offset || 0);
      setSelectedPineconeIds([]);
    } finally {
      setPineconeLoading(false);
    }
  }

  async function scanPineconeIndex({ resetCursor = false } = {}) {
    setPineconeScanLoading(true);
    try {
      setError("");
      const cursor = resetCursor ? "" : pineconeScanCursor;
      const params = new URLSearchParams({ limit: "100", max_pages: "5" });
      if (cursor) params.set("cursor", cursor);
      const data = await fetchAdminJson(`/admin/pinecone/scan?${params.toString()}`);
      setPineconeScan(data);
      setPineconeScanCursor(data.next_cursor || "");
      await loadPineconeData(pineconeSearch, 0, pineconeFilters);
      const mirrored = data.mirrored_records ?? 0;
      const skipped = data.skipped_existing ?? 0;
      const moreText = data.has_more ? " Masih ada data berikutnya, klik Lanjut Scan." : " Semua halaman yang tersedia sudah discan.";
      setSuccess(
        `Scan Pinecone selesai untuk ${data.ids_seen ?? 0} ID. ${mirrored} metadata baru masuk MySQL, ${skipped} sudah ada dan dilewati.${moreText}`
      );
    } catch (err) {
      setError(err.message || "Gagal scan index Pinecone.");
    } finally {
      setPineconeScanLoading(false);
    }
  }

  async function loadUsers({
    search = usersSearch,
    role = usersRoleFilter,
    status = usersStatusFilter,
    offset = usersOffset,
    limit = usersLimit,
  } = {}) {
    setUsersLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
      });
      const cleanSearch = String(search || "").trim();
      if (cleanSearch) params.set("search", cleanSearch);
      if (role) params.set("role", role);
      if (status) params.set("status", status);

      const data = await fetchAdminJson(`/admin/users?${params.toString()}`);
      setUsers(data.users || []);
      setUsersTotal(Number(data.total || 0));
      setUsersLimit(Number(data.limit || limit));
      setUsersOffset(Number(data.offset || offset));
      return data;
    } finally {
      setUsersLoading(false);
    }
  }

  async function loadActivityHistory(userEmail = activityUserEmail, limitValue = initialActivityLimit) {
    setActivityLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(limitValue) });
      const cleanEmail = String(userEmail || "").trim();
      if (cleanEmail) params.set("user_email", cleanEmail);
      const data = await fetchAdminJson(`/admin/activity/history?${params.toString()}`);
      setActivityHistory(data);
      return data;
    } finally {
      setActivityLoading(false);
    }
  }

  function emptyActivityHistory(activityError = "") {
    return {
      auth_sessions: [],
      chat_messages: [],
      auth_total: 0,
      chat_total: 0,
      limit: initialActivityLimit,
      chat_per_user_limit: 5,
      activity_error: activityError,
    };
  }

  function emptyPineconeSummary(summaryError = "") {
    return {
      status: "ok",
      mysql_operational_store: false,
      total_records: 0,
      batch_count: 0,
      dataset_count: 0,
      indicator_count: 0,
      area_count: 0,
      with_download_url: 0,
      summary_error: summaryError,
    };
  }

  function emptyPineconeRecords(recordsError = "") {
    return {
      status: "ok",
      mysql_operational_store: false,
      total: 0,
      limit: initialPineconeLimit,
      offset: 0,
      records: [],
      records_error: recordsError,
    };
  }

  async function loadOverview(preferredBatchId = "") {
    try {
      setLoadingOverview(true);
      const [metricsRes, usersRes, batchesRes, ingestionHistoryRes, activityHistoryRes, pineconeSummaryRes, pineconeRecordsRes] = await Promise.all([
        fetchAdminJson("/admin/metrics"),
        fetchAdminJson("/admin/users?limit=10&offset=0"),
        fetchAdminJson("/admin/batches"),
        fetchAdminJson("/admin/ingestion/history?limit=12"),
        fetchAdminJson(`/admin/activity/history?limit=${initialActivityLimit}`).catch((err) => emptyActivityHistory(err.message || "Gagal memuat history user.")),
        fetchAdminJson("/admin/pinecone/summary").catch((err) => emptyPineconeSummary(err.message || "Gagal memuat ringkasan Pinecone.")),
        fetchAdminJson(`/admin/pinecone/records?limit=${initialPineconeLimit}&offset=0`).catch((err) => emptyPineconeRecords(err.message || "Gagal memuat list Pinecone.")),
      ]);
      setMetrics(metricsRes);
      setUsers(usersRes.users || []);
      setUsersTotal(Number(usersRes.total || 0));
      setUsersLimit(Number(usersRes.limit || 10));
      setUsersOffset(Number(usersRes.offset || 0));
      setBatches(batchesRes.batches || []);
      setIngestionHistory(ingestionHistoryRes);
      setActivityHistory(activityHistoryRes);
      setPineconeSummary(pineconeSummaryRes);
      setPineconeRecords(pineconeRecordsRes);

      const targetBatchId = preferredBatchId || activeBatch?.id || (batchesRes.batches?.[0]?.id ?? "");
      if (targetBatchId) {
        const batchRes = await fetchAdminJson(`/admin/batches/${targetBatchId}`);
        setActiveBatch(batchRes.batch || null);
        await maybeAutoInspect(batchRes.batch || null);
      } else {
        setActiveBatch(null);
        setPublishPreview(null);
        setRecordInspector(null);
        setSelectedRecordId("");
      }
    } catch (err) {
      setError(err.message || "Gagal memuat dashboard admin.");
    } finally {
      setLoadingOverview(false);
    }
  }

  useEffect(() => {
    if (!isAdmin) return;
    loadOverview();
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin || adminTab !== "pinecone") return;
    if ((pineconeRecords.records || []).length === 0 && !pineconeLoading) {
      loadPineconeData(pineconeSearch, 0, pineconeFilters, initialPineconeLimit).catch((err) => {
        setError(err.message || "Gagal memuat contoh data Pinecone.");
      });
    }
  }, [isAdmin, adminTab]);

  useEffect(() => {
    if (!isAdmin || adminTab !== "activity") return;
    if ((activityHistory.auth_sessions || []).length === 0 && (activityHistory.chat_messages || []).length === 0 && !activityLoading) {
      loadActivityHistory(activityUserEmail, initialActivityLimit).catch((err) => {
        setError(err.message || "Gagal memuat contoh history user.");
      });
    }
  }, [isAdmin, adminTab]);

  useEffect(() => {
    if (!isAdmin || adminTab !== "settings") return;
    loadGmailSetting();
  }, [isAdmin, adminTab]);

  async function handlePreviewSubmit() {
    if (!selectedFiles.length || previewLoading) return;

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append("files", file);
    });
    formData.append("default_source_url", defaultSourceUrl.trim());
    formData.append("default_download_url", defaultDownloadUrl.trim());
    formData.append("source_domain", uploadSourceDomain);

    try {
      setPreviewLoading(true);
      setError("");
      setSuccess("");
      const token = getStoredAuthToken();
      const res = await fetch(API_BASE + "/admin/batches/preview", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Preview batch gagal.");
      }
      setActiveBatch(data.batch || null);
      await maybeAutoInspect(data.batch || null);
      setSelectedFiles([]);
      setDefaultSourceUrl("");
      setDefaultDownloadUrl("");
      const input = document.getElementById("admin-batch-files");
      if (input) input.value = "";
      await loadOverview(data.batch?.id || "");
      setAdminTab("batch");
      setSuccess("Preview batch berhasil dibuat.");
    } catch (err) {
      setError(err.message || "Preview batch gagal.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handlePublish(batchId) {
    if (!batchId || publishLoading) return;
    try {
      setPublishLoading(batchId);
      setError("");
      setSuccess("");
      await fetchAdminJson(`/admin/batches/${batchId}/publish`, {
        method: "POST",
      });
      await loadOverview(batchId);
      setSuccess("Batch berhasil dipublish ke Pinecone.");
    } catch (err) {
      setError(err.message || "Publish batch gagal.");
    } finally {
      setPublishLoading("");
    }
  }

  async function handleCreateUser() {
    if (!newUserName.trim() || !newUserOrganization.trim() || !newUserPhone.trim() || !newUserEmail.trim() || !newUserPassword.trim()) {
      setError("Masukkan nama, media/organisasi, nomor handphone, email, dan password user baru.");
      return;
    }
    try {
      setCreateUserLoading(true);
      setError("");
      setSuccess("");
      await fetchAdminJson("/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newUserName.trim(),
          media_organization: newUserOrganization.trim(),
          phone: newUserPhone.trim(),
          email: newUserEmail.trim(),
          password: newUserPassword,
          role: newUserRole,
        }),
      });
      setNewUserName("");
      setNewUserOrganization("");
      setNewUserPhone("");
      setNewUserEmail("");
      setNewUserPassword("");
      setNewUserRole("trial");
      await loadUsers({ offset: 0 });
      setSuccess("User baru berhasil dibuat.");
    } catch (err) {
      setError(err.message || "Gagal membuat user baru.");
    } finally {
      setCreateUserLoading(false);
    }
  }

  async function updateUserAccess(email, role) {
    try {
      setError("");
      setSuccess("");
      await fetchAdminJson(`/admin/users/${encodeURIComponent(email)}/access`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      await loadUsers();
      setSuccess(`Akses ${email} berhasil diubah menjadi ${role}.`);
    } catch (err) {
      setError(err.message || "Gagal mengubah akses user.");
    }
  }

  async function updateUserStatus(email, status) {
    if (!email || userActionLoading) return;
    try {
      setUserActionLoading(`${email}:status`);
      setError("");
      setSuccess("");
      await fetchAdminJson(`/admin/users/${encodeURIComponent(email)}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await loadUsers();
      setSuccess(`Status ${email} berhasil diubah menjadi ${status === "inactive" ? "nonaktif" : "aktif"}.`);
    } catch (err) {
      setError(err.message || "Gagal mengubah status user.");
    } finally {
      setUserActionLoading("");
    }
  }

  async function deleteUser(email) {
    if (!email || userActionLoading) return;
    if (!window.confirm(`Hapus user ${email}? Tindakan ini tidak bisa dibatalkan.`)) return;
    try {
      setUserActionLoading(`${email}:delete`);
      setError("");
      setSuccess("");
      await fetchAdminJson(`/admin/users/${encodeURIComponent(email)}`, {
        method: "DELETE",
      });
      await loadUsers({ offset: usersOffset });
      setSuccess(`User ${email} berhasil dihapus.`);
    } catch (err) {
      setError(err.message || "Gagal menghapus user.");
    } finally {
      setUserActionLoading("");
    }
  }

  function confirmationChannelText(channel, result) {
    if (!result) return "";
    const status = result?.status || "";
    if (!status) return "";
    if (status === "sent") return `${channel}: terkirim`;
    if (status === "skipped") return `${channel}: belum terkirim (${result?.reason || "konfigurasi belum lengkap"})`;
    if (status === "error") return `${channel}: gagal (${result?.error || "provider menolak request"})`;
    return `${channel}: ${status}`;
  }

  function confirmationStatusTone(result) {
    const statuses = [result?.email?.status, result?.whatsapp?.status].filter(Boolean);
    if (statuses.includes("sent")) return { background: "#eefbf3", color: "#166534", border: "rgba(22,101,52,0.18)" };
    if (statuses.includes("error")) return { background: "#fff1f1", color: "#9f1d1d", border: "rgba(159,29,29,0.18)" };
    return { background: "#fff8e8", color: "#9a6700", border: "rgba(154,103,0,0.18)" };
  }

  async function resendUserConfirmation(email) {
    if (!email || confirmationLoadingEmail) return;
    try {
      setConfirmationLoadingEmail(email);
      setError("");
      setSuccess("");
      const data = await fetchAdminJson(`/admin/users/${encodeURIComponent(email)}/resend-confirmation?channel=email`, {
        method: "POST",
      });
      const emailDelivery = data.delivery?.email?.status || "";
      const whatsappDelivery = data.delivery?.whatsapp?.status || "";
      setConfirmationStatusByEmail((prev) => ({
        ...prev,
        [email]: {
          email: data.delivery?.email || null,
          whatsapp: data.delivery?.whatsapp || null,
        },
      }));
      await loadUsers();
      const deliveryMessage = `Link konfirmasi untuk ${email}: email ${emailDelivery || "unknown"}${whatsappDelivery ? `, WhatsApp ${whatsappDelivery}` : ""}.`;
      if (emailDelivery === "sent" || whatsappDelivery === "sent") {
        setSuccess(deliveryMessage);
      } else {
        const emailError = data.delivery?.email?.error || data.delivery?.email?.reason || "";
        setError(
          `${deliveryMessage} Pastikan EMAIL_DELIVERY_PROVIDER=gmail_api dan konfigurasi Gmail API refresh token sudah benar di Railway.${emailError ? ` Detail: ${emailError}` : ""}`
        );
      }
    } catch (err) {
      setConfirmationStatusByEmail((prev) => ({
        ...prev,
        [email]: {
          email: { status: "error", error: err.message || "Gagal mengirim ulang link konfirmasi user." },
          whatsapp: null,
        },
      }));
      setError(err.message || "Gagal mengirim ulang link konfirmasi user.");
    } finally {
      setConfirmationLoadingEmail("");
    }
  }

  async function handleOpenBatch(batchId) {
    if (!batchId) return;
    try {
      setError("");
      const data = await fetchAdminJson(`/admin/batches/${batchId}`);
      setActiveBatch(data.batch || null);
      await maybeAutoInspect(data.batch || null);
      setAdminTab("batch");
    } catch (err) {
      setError(err.message || "Gagal mengubah akses user.");
    }
  }

  async function updateUserStatus(email, status) {
    if (!email || userActionLoading) return;
    try {
      setUserActionLoading(`${email}:status`);
      setError("");
      setSuccess("");
      await fetchAdminJson(`/admin/users/${encodeURIComponent(email)}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await loadUsers();
      setSuccess(`Status ${email} berhasil diubah menjadi ${status === "inactive" ? "nonaktif" : "aktif"}.`);
    } catch (err) {
      setError(err.message || "Gagal mengubah status user.");
    } finally {
      setUserActionLoading("");
    }
  }

  async function deleteUser(email) {
    if (!email || userActionLoading) return;
    if (!window.confirm(`Hapus user ${email}? Tindakan ini tidak bisa dibatalkan.`)) return;
    try {
      setUserActionLoading(`${email}:delete`);
      setError("");
      setSuccess("");
      await fetchAdminJson(`/admin/users/${encodeURIComponent(email)}`, {
        method: "DELETE",
      });
      await loadUsers({ offset: usersOffset });
      setSuccess(`User ${email} berhasil dihapus.`);
    } catch (err) {
      setError(err.message || "Gagal menghapus user.");
    } finally {
      setUserActionLoading("");
    }
  }

  function confirmationChannelText(channel, result) {
    if (!result) return "";
    const status = result?.status || "";
    if (!status) return "";
    if (status === "sent") return `${channel}: terkirim`;
    if (status === "skipped") return `${channel}: belum terkirim (${result?.reason || "konfigurasi belum lengkap"})`;
    if (status === "error") return `${channel}: gagal (${result?.error || "provider menolak request"})`;
    return `${channel}: ${status}`;
  }

  function confirmationStatusTone(result) {
    const statuses = [result?.email?.status, result?.whatsapp?.status].filter(Boolean);
    if (statuses.includes("sent")) return { background: "#eefbf3", color: "#166534", border: "rgba(22,101,52,0.18)" };
    if (statuses.includes("error")) return { background: "#fff1f1", color: "#9f1d1d", border: "rgba(159,29,29,0.18)" };
    return { background: "#fff8e8", color: "#9a6700", border: "rgba(154,103,0,0.18)" };
  }

  async function resendUserConfirmation(email) {
    if (!email || confirmationLoadingEmail) return;
    try {
      setConfirmationLoadingEmail(email);
      setError("");
      setSuccess("");
      const data = await fetchAdminJson(`/admin/users/${encodeURIComponent(email)}/resend-confirmation?channel=email`, {
        method: "POST",
      });
      const emailDelivery = data.delivery?.email?.status || "";
      const whatsappDelivery = data.delivery?.whatsapp?.status || "";
      setConfirmationStatusByEmail((prev) => ({
        ...prev,
        [email]: {
          email: data.delivery?.email || null,
          whatsapp: data.delivery?.whatsapp || null,
        },
      }));
      await loadUsers();
      const deliveryMessage = `Link konfirmasi untuk ${email}: email ${emailDelivery || "unknown"}${whatsappDelivery ? `, WhatsApp ${whatsappDelivery}` : ""}.`;
      if (emailDelivery === "sent" || whatsappDelivery === "sent") {
        setSuccess(deliveryMessage);
      } else {
        const emailError = data.delivery?.email?.error || data.delivery?.email?.reason || "";
        setError(
          `${deliveryMessage} Pastikan EMAIL_DELIVERY_PROVIDER=gmail_api dan konfigurasi Gmail API refresh token sudah benar di Railway.${emailError ? ` Detail: ${emailError}` : ""}`
        );
      }
    } catch (err) {
      setConfirmationStatusByEmail((prev) => ({
        ...prev,
        [email]: {
          email: { status: "error", error: err.message || "Gagal mengirim ulang link konfirmasi user." },
          whatsapp: null,
        },
      }));
      setError(err.message || "Gagal mengirim ulang link konfirmasi user.");
    } finally {
      setConfirmationLoadingEmail("");
    }
  }

  async function handleOpenBatch(batchId) {
    if (!batchId) return;
    try {
      setError("");
      const data = await fetchAdminJson(`/admin/batches/${batchId}`);
      setActiveBatch(data.batch || null);
      await maybeAutoInspect(data.batch || null);
      setAdminTab("batch");
    } catch (err) {
      setError(err.message || "Gagal memuat detail batch.");
    }
  }

  async function handleInspectFile(file) {
    if (!activeBatch?.id || !file?.id || recordLoading) return;
    try {
      setRecordLoading(file.id);
      setError("");
      await inspectBatchFile(activeBatch.id, file.id);
    } catch (err) {
      setError(err.message || "Gagal memuat record hasil parsing.");
    } finally {
      setRecordLoading("");
    }
  }

  async function handlePineconeSearchSubmit(e) {
    e.preventDefault();
    try {
      setError("");
      setPineconeOffset(0);
      await loadPineconeData(pineconeSearch, 0, pineconeFilters);
    } catch (err) {
      setError(err.message || "Gagal memuat daftar data Pinecone.");
    }
  }

  function updatePineconeFilter(field, value) {
    setPineconeFilters((prev) => ({ ...prev, [field]: value }));
  }

  async function handleFilterRegionSelect(kind, idValue) {
    const optionKey = kind === "province" ? "provinces" : kind === "regency" ? "regencies" : kind === "district" ? "districts" : "villages";
    const selected = (regionOptions[optionKey] || []).find((item) => String(item.id) === String(idValue));
    const name = selected?.name || "";
    try {
      if (kind === "province") {
        setPineconeFilters((prev) => ({
          ...prev,
          province: name,
          province_code: idValue,
          regency: "",
          regency_code: "",
          district: "",
          district_code: "",
          village: "",
          village_code: "",
        }));
        setRegionOptions((prev) => ({ ...prev, regencies: [], districts: [], villages: [] }));
        if (idValue) await loadRegions("regencies", idValue);
      } else if (kind === "regency") {
        setPineconeFilters((prev) => ({
          ...prev,
          regency: name,
          regency_code: idValue,
          district: "",
          district_code: "",
          village: "",
          village_code: "",
        }));
        setRegionOptions((prev) => ({ ...prev, districts: [], villages: [] }));
        if (idValue) await loadRegions("districts", idValue);
      } else if (kind === "district") {
        setPineconeFilters((prev) => ({
          ...prev,
          district: name,
          district_code: idValue,
          village: "",
          village_code: "",
        }));
        setRegionOptions((prev) => ({ ...prev, villages: [] }));
        if (idValue) await loadRegions("villages", idValue);
      } else {
        setPineconeFilters((prev) => ({ ...prev, village: name, village_code: idValue }));
      }
    } catch (err) {
      setError(err.message || "Gagal memuat dropdown wilayah filter.");
    }
  }

  async function resetPineconeFilters() {
    const emptyFilters = {
      province: "",
      province_code: "",
      regency: "",
      regency_code: "",
      district: "",
      district_code: "",
      village: "",
      village_code: "",
      year_value: "",
      area_level: "",
      doc_type: "",
      source_file: "",
      source: "",
      period: "",
      topic_primary: "",
      topic_secondary: "",
      breakdown_value: "",
      subgroup_value: "",
      source_code_region: "",
      batch_id: "",
      dataset_id: "",
      series_label: "",
    };
    try {
      setError("");
      setPineconeSearch("");
      setPineconeFilters(emptyFilters);
      setPineconeOffset(0);
      await loadPineconeData("", 0, emptyFilters);
    } catch (err) {
      setError(err.message || "Gagal mereset filter data Pinecone.");
    }
  }

  function togglePineconeRecordSelection(pineconeId) {
    setSelectedPineconeIds((prev) => (
      prev.includes(pineconeId)
        ? prev.filter((item) => item !== pineconeId)
        : [...prev, pineconeId]
    ));
  }

  function toggleAllVisiblePineconeRecords() {
    const visibleIds = (pineconeRecords.records || []).map((record) => record.pinecone_id).filter(Boolean);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedPineconeIds.includes(id));
    setSelectedPineconeIds(allSelected ? [] : visibleIds);
  }

  async function handleBulkRegionSelect(kind, idValue) {
    const optionKey = kind === "province" ? "provinces" : kind === "regency" ? "regencies" : kind === "district" ? "districts" : "villages";
    const selected = (regionOptions[optionKey] || []).find((item) => String(item.id) === String(idValue));
    const name = selected?.name || "";
    try {
      if (kind === "province") {
        setBulkPineconeEdit((prev) => ({
          ...prev,
          province: name,
          province_code: idValue,
          regency: "",
          regency_code: "",
          district: "",
          district_code: "",
          village: "",
          village_code: "",
        }));
        setRegionOptions((prev) => ({ ...prev, regencies: [], districts: [], villages: [] }));
        if (idValue) await loadRegions("regencies", idValue);
      } else if (kind === "regency") {
        setBulkPineconeEdit((prev) => ({
          ...prev,
          regency: name,
          regency_code: idValue,
          district: "",
          district_code: "",
          village: "",
          village_code: "",
        }));
        setRegionOptions((prev) => ({ ...prev, districts: [], villages: [] }));
        if (idValue) await loadRegions("districts", idValue);
      } else if (kind === "district") {
        setBulkPineconeEdit((prev) => ({
          ...prev,
          district: name,
          district_code: idValue,
          village: "",
          village_code: "",
        }));
        setRegionOptions((prev) => ({ ...prev, villages: [] }));
        if (idValue) await loadRegions("villages", idValue);
      } else {
        setBulkPineconeEdit((prev) => ({ ...prev, village: name, village_code: idValue }));
      }
    } catch (err) {
      setError(err.message || "Gagal memuat dropdown wilayah edit cepat.");
    }
  }

  async function saveBulkPineconeEdit() {
    if (selectedPineconeIds.length === 0) {
      setError("Pilih minimal satu data Pinecone untuk diedit cepat.");
      return;
    }
    const provinceName = bulkPineconeEdit.province.trim();
    const selectedProvince = (regionOptions.provinces || []).find((item) => String(item.name || "").toLowerCase() === provinceName.toLowerCase());
    const payload = {
      pinecone_ids: selectedPineconeIds,
      source: bulkPineconeEdit.source.trim(),
      province: provinceName,
      province_code: selectedProvince?.id || bulkPineconeEdit.province_code || "",
      regency: bulkPineconeEdit.regency.trim(),
      regency_code: bulkPineconeEdit.regency_code || "",
      district: bulkPineconeEdit.district.trim(),
      district_code: bulkPineconeEdit.district_code || "",
      village: bulkPineconeEdit.village.trim(),
      village_code: bulkPineconeEdit.village_code || "",
      year_value: bulkPineconeEdit.year_value.trim(),
      series_label: bulkPineconeEdit.series_label.trim(),
      topic_primary: bulkPineconeEdit.topic_primary.trim(),
      subgroup_label: bulkPineconeEdit.subgroup_label.trim(),
    };
    if (!payload.source && !payload.province && !payload.regency && !payload.district && !payload.village && !payload.year_value && !payload.series_label && !payload.topic_primary && !payload.subgroup_label) {
      setError("Isi minimal Source, wilayah, Tahun, series_label, topic_primary, atau subgroup_label sebelum menyimpan edit cepat.");
      return;
    }
    try {
      setBulkPineconeSaving(true);
      setError("");
      const result = await fetchAdminJson("/admin/pinecone/records/bulk-update", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setSuccess(`Edit cepat selesai. ${result.updated ?? 0} dari ${result.requested ?? selectedPineconeIds.length} record diperbarui.`);
      setSelectedPineconeIds([]);
      setBulkPineconeEdit({ source: "", province: "", province_code: "", regency: "", regency_code: "", district: "", district_code: "", village: "", village_code: "", year_value: "", series_label: "", topic_primary: "", subgroup_label: "" });
      await loadPineconeData(pineconeSearch, pineconeOffset, pineconeFilters);
    } catch (err) {
      setError(err.message || "Gagal menyimpan edit cepat data Pinecone.");
    } finally {
      setBulkPineconeSaving(false);
    }
  }

  const usersPageStart = usersTotal === 0 ? 0 : usersOffset + 1;
  const usersPageEnd = Math.min(usersOffset + users.length, usersTotal);
  const canPrevUsers = usersOffset > 0;
  const canNextUsers = usersOffset + usersLimit < usersTotal;

  if (!isAdmin) {
    return (
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "40px 24px 56px" }}>
        <Card>
          <div style={{ padding: 32, textAlign: "center" }}>
            <div style={{ marginBottom: 12, fontSize: 28, fontWeight: 700 }}>Admin Only</div>
            <p style={{ margin: 0, color: COLORS.muted, lineHeight: 1.8 }}>
              Halaman ini hanya tersedia untuk akun admin.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  const metricCards = [
    { label: "Total batch", value: metrics?.batch_total ?? 0, icon: <FolderUp size={18} /> },
    { label: "Total file", value: metrics?.file_total ?? 0, icon: <Database size={18} /> },
    { label: "Preview siap", value: metrics?.preview_ready_batches ?? 0, icon: <Check size={18} /> },
    { label: "Quality pass", value: metrics?.quality_pass_files ?? 0, icon: <Check size={18} /> },
    { label: "Quality review", value: metrics?.quality_review_files ?? 0, icon: <Search size={18} /> },
    { label: "Quality fail", value: metrics?.quality_fail_files ?? 0, icon: <CircleHelp size={18} /> },
    { label: "Published", value: metrics?.published_batches ?? 0, icon: <BarChart3 size={18} /> },
    { label: "Atomic records", value: metrics?.atomic_record_total ?? 0, icon: <Database size={18} /> },
  ];
  const selectedRecord = recordInspector?.records?.find((item) => item.id === selectedRecordId) || recordInspector?.records?.[0] || null;
  const selectedRecordPineconePayload =
    selectedRecord?.pinecone_payload_preview
    || publishPreview?.sample_prepared_records?.find((item) => item.id === selectedRecord?.id)
    || null;
  const adminTabs = [
    { id: "ingestion", label: "Ingestion", helper: "Upload & batch" },
    { id: "settings", label: "Email Settings", helper: "Gmail API" },
    { id: "pinecone", label: "List Data", helper: "Mirror Pinecone" },
    { id: "activity", label: "History User", helper: `${activityHistory.chat_total || 0} chat` },
    { id: "batch", label: "Batch Detail", helper: activeBatch?.id || "Pilih batch" },
    { id: "users", label: "Users", helper: `${users.length} akun` },
  ];

  function formatAdminDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("id-ID", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  function getAuditTone(status) {
    if (status === "healthy") {
      return { background: "#eefbf3", color: "#166534", label: "Sehat" };
    }
    if (status === "invalid") {
      return { background: "#fff1f1", color: "#9f1d1d", label: "Bermasalah" };
    }
    return { background: "#fff8e8", color: "#9a6700", label: "Perlu cek" };
  }

  function getQualityTone(status) {
    if (status === "pass") {
      return { background: "#eefbf3", color: "#166534", label: "Pass" };
    }
    if (status === "fail") {
      return { background: "#fff1f1", color: "#9f1d1d", label: "Fail" };
    }
    if (status === "review") {
      return { background: "#fff8e8", color: "#9a6700", label: "Review" };
    }
    return { background: "#f4f0ec", color: COLORS.muted, label: "Pending" };
  }

  function renderPipelinePills(file) {
    const steps = [
      { label: "Upload diterima", done: true },
      { label: file.storage_mode === "disabled" ? "Storage nonaktif" : `Storage ${file.storage_mode}`, done: file.storage_mode !== "local" ? true : !!file.stored_path },
      { label: `Parse ${file.parse_status}`, done: file.parse_status === "ready" },
      { label: `${file.atomic_record_count} atomic record`, done: Number(file.atomic_record_count || 0) > 0 },
      {
        label: file.normalization_status === "normalized"
          ? "Normalisasi selesai"
          : `Pending: ${file.normalization_reason || "menunggu normalisasi"}`,
        done: file.normalization_status === "normalized",
      },
      {
        label: file.canonical_status === "completed" ? "MySQL + outbox siap" : "Publikasi pending",
        done: file.canonical_status === "completed",
      },
    ];

    return (
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {steps.map((step) => (
          <Pill
            key={`${file.id}-${step.label}`}
            style={{
              background: step.done ? "#eefbf3" : "#f4f0ec",
              color: step.done ? "#166534" : COLORS.muted,
              border: "1px solid rgba(17,17,17,0.06)",
            }}
          >
            {step.label}
          </Pill>
        ))}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "32px 24px 56px" }}>
      <div style={{ display: "grid", gap: 24 }}>
        <WorkerStatusCard getToken={getStoredAuthToken} onAuthExpired={onAuthExpired} />
        <StorageInventoryCard getToken={getStoredAuthToken} onAuthExpired={onAuthExpired} />
        <NormalizationFailuresCard getToken={getStoredAuthToken} onAuthExpired={onAuthExpired} />
        <RegisteredStatistics getToken={getStoredAuthToken} onAuthExpired={onAuthExpired} />
        <Card>
          <div style={{ padding: 28 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
              <div>
                <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                  Admin Console
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, lineHeight: 1.2 }}>Bulk Ingestion Preview</div>
                <p style={{ marginTop: 10, marginBottom: 0, color: COLORS.muted, lineHeight: 1.8, maxWidth: 760 }}>
                  Upload banyak dataset sekaligus, cek preview hasil parsing atomic record, lalu publish ke Pinecone saat sudah yakin datanya bersih.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <Button variant="outline" onClick={() => setAdminTab("settings")}>
                  Email Settings
                </Button>
                <Button variant="outline" onClick={() => loadOverview(activeBatch?.id || "")}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <RefreshCw size={16} />
                    Refresh
                  </span>
                </Button>
              </div>
            </div>

            <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
              {metricCards.map((card) => (
                <div
                  key={card.label}
                  style={{
                    background: "white",
                    borderRadius: 20,
                    padding: 18,
                    border: "1px solid rgba(17,17,17,0.08)",
                  }}
                >
                  <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 36, height: 36, borderRadius: 12, background: "#fff1f7", color: COLORS.primaryDark }}>
                    {card.icon}
                  </div>
                  <div style={{ marginTop: 14, fontSize: 26, fontWeight: 700 }}>{card.value}</div>
                  <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 14 }}>{card.label}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <div style={{ padding: 20, display: "grid", gap: 14 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                Admin Menu
              </div>
              <div style={{ marginTop: 4, fontSize: 20, fontWeight: 800 }}>
                Pilih tab kerja admin
              </div>
              <p style={{ marginTop: 6, marginBottom: 0, color: COLORS.muted, lineHeight: 1.6 }}>
                Menu dipisah per tab supaya upload data, email settings, list Pinecone, detail batch, dan user management lebih mudah dicek.
              </p>
            </div>
            <div
              role="tablist"
              aria-label="Admin dashboard tabs"
              style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}
            >
            {adminTabs.map((tab) => {
              const active = adminTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setAdminTab(tab.id)}
                  style={{
                    textAlign: "left",
                    borderRadius: 20,
                    border: active ? `2px solid ${COLORS.primary}` : "1px solid rgba(17,17,17,0.08)",
                    background: active ? "linear-gradient(135deg, #fff1f7 0%, #ffffff 100%)" : "white",
                    color: COLORS.text,
                    padding: 16,
                    cursor: "pointer",
                    boxShadow: active ? "0 12px 30px rgba(232, 77, 150, 0.16)" : "0 6px 18px rgba(17,17,17,0.04)",
                  }}
                >
                  <div style={{ fontWeight: 800, fontSize: 15 }}>{tab.label}</div>
                  <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 13, lineHeight: 1.5 }}>{tab.helper}</div>
                </button>
              );
            })}
            </div>
          </div>
        </Card>

        {adminTab === "pinecone" && (
        <>
        <PineconeMetadataBrowser getToken={getStoredAuthToken} onAuthExpired={onAuthExpired} />
        <details><summary>Alat mirror lama (vector_records) — hanya data dari alur publikasi lama</summary>
        <Card>
          <div style={{ padding: 28, display: "grid", gap: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "start", flexWrap: "wrap" }}>
              <div>
                <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                  Pinecone Data List
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1.25 }}>Daftar mirror alur publikasi lama</div>
                <p style={{ marginTop: 8, marginBottom: 0, color: COLORS.muted, lineHeight: 1.7, maxWidth: 780 }}>
                  Daftar ini dibaca dari mirror MySQL <code>vector_records</code>. Saat admin pertama login, dashboard hanya mengambil {initialPineconeLimit} data awal agar ringan; gunakan filter atau Refresh Data untuk memuat halaman berikutnya.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <Button variant="outline" onClick={() => loadPineconeData(pineconeSearch, pineconeOffset, pineconeFilters, pineconeRecords.limit || initialPineconeLimit)} disabled={pineconeLoading}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <RefreshCw size={16} />
                    {pineconeLoading ? "Memuat..." : "Refresh Data"}
                  </span>
                </Button>
                <Button onClick={() => scanPineconeIndex({ resetCursor: true })} disabled={pineconeScanLoading}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <Search size={16} />
                    {pineconeScanLoading ? "Scanning..." : "Scan Pinecone"}
                  </span>
                </Button>
              </div>
            </div>

            {pineconeSummary?.summary_error || pineconeRecords?.records_error ? (
              <div style={{ background: "#fff8e8", color: "#9a6700", borderRadius: 14, padding: 12, fontSize: 13, lineHeight: 1.6 }}>
                Data Pinecone awal belum bisa dibaca: {pineconeSummary?.summary_error || pineconeRecords?.records_error}
              </div>
            ) : null}

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
              {[
                { label: "Total vector", value: pineconeSummary?.summary?.total_records ?? 0 },
                { label: "Batch", value: pineconeSummary?.summary?.batch_count ?? 0 },
                { label: "Dataset", value: pineconeSummary?.summary?.dataset_count ?? 0 },
                { label: "Indikator", value: pineconeSummary?.summary?.indicator_count ?? 0 },
                { label: "Wilayah", value: pineconeSummary?.summary?.area_count ?? 0 },
                { label: "Dengan URL", value: pineconeSummary?.summary?.with_download_url ?? 0 },
              ].map((item) => (
                <div key={item.label} style={{ borderRadius: 18, background: "#fbf8f5", border: "1px solid rgba(17,17,17,0.08)", padding: 16 }}>
                  <div style={{ color: COLORS.muted, fontSize: 13 }}>{item.label}</div>
                  <div style={{ marginTop: 8, fontSize: 24, fontWeight: 700 }}>{item.value}</div>
                </div>
              ))}
            </div>

            {pineconeScan ? (
              <div style={{ borderRadius: 22, background: "#fbf8f5", border: "1px solid rgba(17,17,17,0.08)", padding: 18, display: "grid", gap: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <div>
                    <div style={{ fontWeight: 800 }}>Hasil Scan Langsung Pinecone</div>
                    <div style={{ marginTop: 4, color: COLORS.muted, fontSize: 14 }}>
                      Index {pineconeScan.index_name || "-"} • Mode {pineconeScan.scan_mode || "-"} • ID discan {pineconeScan.ids_seen ?? 0} • Baru masuk MySQL {pineconeScan.mirrored_records ?? 0} • Sudah ada {pineconeScan.skipped_existing ?? 0}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                    <Pill style={{ background: pineconeScan.sample_error ? "#fff8e8" : "#eefbf3", color: pineconeScan.sample_error ? "#9a6700" : "#166534" }}>
                      {pineconeScan.sample_error ? "Stats OK, sample perlu cek" : "Scan OK"}
                    </Pill>
                    {pineconeScan.has_more ? (
                      <Button variant="outline" onClick={() => scanPineconeIndex()} disabled={pineconeScanLoading}>
                        Lanjut Scan
                      </Button>
                    ) : null}
                  </div>
                </div>

                {pineconeScan.sample_error ? (
                  <div style={{ color: "#9a6700", lineHeight: 1.6, fontSize: 14 }}>
                    Sample query tidak tersedia: {pineconeScan.sample_error}
                  </div>
                ) : null}

                {pineconeScan.mirror_error ? (
                  <div style={{ color: "#9a6700", lineHeight: 1.6, fontSize: 14 }}>
                    Scan terbaca, tetapi gagal masuk ke daftar MySQL: {pineconeScan.mirror_error}
                  </div>
                ) : null}

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                  {Object.entries(pineconeScan.namespaces || {}).map(([namespaceName, namespaceStats]) => (
                    <div key={namespaceName || "default"} style={{ borderRadius: 16, background: "white", border: "1px solid rgba(17,17,17,0.08)", padding: 14 }}>
                      <div style={{ color: COLORS.muted, fontSize: 13 }}>Namespace</div>
                      <div style={{ marginTop: 6, fontWeight: 800 }}>{namespaceName || "default"}</div>
                      <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 14 }}>
                        Vector: {namespaceStats?.vector_count ?? "-"}
                      </div>
                    </div>
                  ))}
                </div>

                {(pineconeScan.sample_matches || []).length > 0 ? (
                  <div style={{ display: "grid", gap: 8 }}>
                    <div style={{ fontWeight: 800 }}>Sample metadata dari index</div>
                    {(pineconeScan.sample_matches || []).slice(0, 5).map((match) => (
                      <div key={match.id || JSON.stringify(match).slice(0, 40)} style={{ borderRadius: 16, background: "white", border: "1px solid rgba(17,17,17,0.08)", padding: 14, display: "grid", gap: 6 }}>
                        <div style={{ fontWeight: 700, wordBreak: "break-word" }}>ID: {match.id || "-"}</div>
                        <div style={{ color: COLORS.muted, fontSize: 13 }}>Score: {match.score ?? "-"}</div>
                        <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", color: COLORS.muted, fontSize: 12 }}>
                          {JSON.stringify(match.metadata || {}, null, 2).slice(0, 900)}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            <form onSubmit={handlePineconeSearchSubmit} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <input
                value={pineconeSearch}
                onChange={(e) => setPineconeSearch(e.target.value)}
                placeholder="Cari batch, dataset, indikator, wilayah, source file..."
                style={{ ...inputStyle, flex: "1 1 320px" }}
              />
              <Button type="submit" disabled={pineconeLoading}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <Search size={16} />
                  Cari Data
                </span>
              </Button>
            </form>

            <div style={{ borderRadius: 22, background: "rgba(255,255,255,0.72)", border: "1px solid rgba(17,17,17,0.08)", padding: 16, display: "grid", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 800 }}>Filter detail data Pinecone</div>
                  <div style={{ color: COLORS.muted, fontSize: 13, marginTop: 4 }}>
                    Filter berdasarkan wilayah, tahun, tipe dokumen, file sumber, batch, dataset, dan indikator yang sudah tersimpan di MySQL.
                  </div>
                </div>
                <Button type="button" variant="outline" onClick={resetPineconeFilters} disabled={pineconeLoading}>
                  Reset Filter
                </Button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
                <select
                  value={pineconeFilters.province_code}
                  onFocus={() => loadRegions("provinces")}
                  onChange={(e) => handleFilterRegionSelect("province", e.target.value)}
                  style={inputStyle}
                >
                  <option value="">Pilih provinsi</option>
                  {(regionOptions.provinces || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <select
                  value={pineconeFilters.regency_code}
                  onChange={(e) => handleFilterRegionSelect("regency", e.target.value)}
                  style={inputStyle}
                  disabled={!pineconeFilters.province_code}
                >
                  <option value="">Pilih kab/kota</option>
                  {(regionOptions.regencies || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <select
                  value={pineconeFilters.district_code}
                  onChange={(e) => handleFilterRegionSelect("district", e.target.value)}
                  style={inputStyle}
                  disabled={!pineconeFilters.regency_code}
                >
                  <option value="">Pilih kecamatan</option>
                  {(regionOptions.districts || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <select
                  value={pineconeFilters.village_code}
                  onChange={(e) => handleFilterRegionSelect("village", e.target.value)}
                  style={inputStyle}
                  disabled={!pineconeFilters.district_code}
                >
                  <option value="">Pilih kelurahan/desa</option>
                  {(regionOptions.villages || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <input value={pineconeFilters.year_value} onChange={(e) => updatePineconeFilter("year_value", e.target.value.replace(/\D/g, ""))} placeholder="Tahun, contoh 2025" style={inputStyle} inputMode="numeric" />
                <select value={pineconeFilters.area_level} onChange={(e) => updatePineconeFilter("area_level", e.target.value)} style={inputStyle}>
                  <option value="">Semua level wilayah</option>
                  <option value="nasional">Nasional</option>
                  <option value="provinsi">Provinsi</option>
                  <option value="kabupaten_kota">Kab/Kota</option>
                  <option value="kecamatan">Kecamatan</option>
                  <option value="kelurahan">Kelurahan/Desa</option>
                </select>
                <select value={pineconeFilters.doc_type} onChange={(e) => updatePineconeFilter("doc_type", e.target.value)} style={inputStyle}>
                  <option value="">Semua tipe dokumen</option>
                  <option value="atomic">Atomic</option>
                  <option value="indicator">Indicator</option>
                  <option value="table">Table</option>
                  <option value="vector">Vector</option>
                </select>
                <input value={pineconeFilters.source_file} onChange={(e) => updatePineconeFilter("source_file", e.target.value)} placeholder="Nama file sumber" style={inputStyle} />
                <input value={pineconeFilters.source} onChange={(e) => updatePineconeFilter("source", e.target.value)} placeholder="Sumber, contoh BPS" style={inputStyle} />
                <input value={pineconeFilters.period} onChange={(e) => updatePineconeFilter("period", e.target.value)} placeholder="Periode, contoh Maret" style={inputStyle} />
                <input value={pineconeFilters.topic_primary} onChange={(e) => updatePineconeFilter("topic_primary", e.target.value)} placeholder="Topik utama" style={inputStyle} />
                <input value={pineconeFilters.topic_secondary} onChange={(e) => updatePineconeFilter("topic_secondary", e.target.value)} placeholder="Topik sekunder" style={inputStyle} />
                <input value={pineconeFilters.breakdown_value} onChange={(e) => updatePineconeFilter("breakdown_value", e.target.value)} placeholder="Breakdown, contoh Perkotaan" style={inputStyle} />
                <input value={pineconeFilters.subgroup_value} onChange={(e) => updatePineconeFilter("subgroup_value", e.target.value)} placeholder="Subgroup" style={inputStyle} />
                <input value={pineconeFilters.source_code_region} onChange={(e) => updatePineconeFilter("source_code_region", e.target.value)} placeholder="Kode sumber/region" style={inputStyle} />
                <input value={pineconeFilters.batch_id} onChange={(e) => updatePineconeFilter("batch_id", e.target.value)} placeholder="Batch ID" style={inputStyle} />
                <input value={pineconeFilters.dataset_id} onChange={(e) => updatePineconeFilter("dataset_id", e.target.value)} placeholder="Dataset ID" style={inputStyle} />
                <input value={pineconeFilters.series_label} onChange={(e) => updatePineconeFilter("series_label", e.target.value)} placeholder="Indikator / judul seri" style={inputStyle} />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button type="button" onClick={() => loadPineconeData(pineconeSearch, 0, pineconeFilters)} disabled={pineconeLoading}>
                  Terapkan Filter
                </Button>
              </div>
            </div>

            <div style={{ borderRadius: 22, background: "#fff7fb", border: "1px solid rgba(234,75,148,0.18)", padding: 16, display: "grid", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 800 }}>Edit cepat data terpilih</div>
                  <div style={{ color: COLORS.muted, fontSize: 13, marginTop: 4 }}>
                    Centang data, lalu isi field yang ingin diubah. Wilayah memakai dropdown berurutan: Provinsi → Kab/Kota → Kecamatan → Kelurahan/Desa.
                  </div>
                </div>
                <label style={{ display: "inline-flex", gap: 8, alignItems: "center", fontWeight: 700 }}>
                  <input
                    type="checkbox"
                    checked={(pineconeRecords.records || []).length > 0 && (pineconeRecords.records || []).every((record) => selectedPineconeIds.includes(record.pinecone_id))}
                    onChange={toggleAllVisiblePineconeRecords}
                  />
                  Check all halaman ini
                </label>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <select
                  value={bulkPineconeEdit.province_code}
                  onFocus={() => loadRegions("provinces")}
                  onChange={(e) => handleBulkRegionSelect("province", e.target.value)}
                  style={inputStyle}
                >
                  <option value="">Pilih provinsi</option>
                  {(regionOptions.provinces || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <select
                  value={bulkPineconeEdit.regency_code}
                  onChange={(e) => handleBulkRegionSelect("regency", e.target.value)}
                  style={inputStyle}
                  disabled={!bulkPineconeEdit.province_code}
                >
                  <option value="">Pilih kab/kota</option>
                  {(regionOptions.regencies || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <select
                  value={bulkPineconeEdit.district_code}
                  onChange={(e) => handleBulkRegionSelect("district", e.target.value)}
                  style={inputStyle}
                  disabled={!bulkPineconeEdit.regency_code}
                >
                  <option value="">Pilih kecamatan</option>
                  {(regionOptions.districts || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <select
                  value={bulkPineconeEdit.village_code}
                  onChange={(e) => handleBulkRegionSelect("village", e.target.value)}
                  style={inputStyle}
                  disabled={!bulkPineconeEdit.district_code}
                >
                  <option value="">Pilih kelurahan/desa</option>
                  {(regionOptions.villages || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <input
                  value={bulkPineconeEdit.source}
                  onChange={(e) => setBulkPineconeEdit((prev) => ({ ...prev, source: e.target.value }))}
                  placeholder="Set Source, contoh BPS"
                  style={inputStyle}
                />
                <input
                  value={bulkPineconeEdit.year_value}
                  onChange={(e) => setBulkPineconeEdit((prev) => ({ ...prev, year_value: e.target.value.replace(/\D/g, "") }))}
                  placeholder="Set Tahun, contoh 2025"
                  style={inputStyle}
                  inputMode="numeric"
                />
                <input
                  value={bulkPineconeEdit.series_label}
                  onChange={(e) => setBulkPineconeEdit((prev) => ({ ...prev, series_label: e.target.value }))}
                  placeholder="Set series_label"
                  style={inputStyle}
                />
                <input
                  value={bulkPineconeEdit.topic_primary}
                  onChange={(e) => setBulkPineconeEdit((prev) => ({ ...prev, topic_primary: e.target.value }))}
                  placeholder="Set topic_primary"
                  style={inputStyle}
                />
                <input
                  value={bulkPineconeEdit.subgroup_label}
                  onChange={(e) => setBulkPineconeEdit((prev) => ({ ...prev, subgroup_label: e.target.value }))}
                  placeholder="Set subgroup_label"
                  style={inputStyle}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ color: COLORS.muted, fontSize: 13 }}>{selectedPineconeIds.length} record dipilih</span>
                <Button type="button" onClick={saveBulkPineconeEdit} disabled={bulkPineconeSaving || selectedPineconeIds.length === 0}>
                  {bulkPineconeSaving ? "Menyimpan..." : "Simpan Edit Cepat"}
                </Button>
              </div>
            </div>

            <div style={{ borderRadius: 22, background: "white", border: "1px solid rgba(17,17,17,0.08)", overflow: "hidden" }}>
              <div style={{ padding: 16, borderBottom: "1px solid rgba(17,17,17,0.08)", display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <strong>{pineconeRecords.total ?? 0} record tersimpan</strong>
                <span style={{ color: COLORS.muted }}>Menampilkan {(pineconeRecords.records || []).length} record terbaru</span>
              </div>
              <div style={{ display: "grid", gap: 0, maxHeight: 520, overflowY: "auto" }}>
                {pineconeLoading ? (
                  <div style={{ padding: 18, color: COLORS.muted }}>Memuat daftar data...</div>
                ) : (pineconeRecords.records || []).length === 0 ? (
                  <div style={{ padding: 18, color: COLORS.muted }}>
                    Belum ada record publish di MySQL mirror. Publish batch ke Pinecone terlebih dahulu agar data muncul di sini.
                  </div>
                ) : (
                  (pineconeRecords.records || []).map((record) => (
                    <div key={record.pinecone_id} style={{ padding: 16, borderBottom: "1px solid rgba(17,17,17,0.06)", display: "grid", gap: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                        <div style={{ minWidth: 0, display: "flex", gap: 10, alignItems: "flex-start" }}>
                          <input
                            type="checkbox"
                            checked={selectedPineconeIds.includes(record.pinecone_id)}
                            onChange={() => togglePineconeRecordSelection(record.pinecone_id)}
                            aria-label={`Pilih ${record.series_label || record.pinecone_id}`}
                            style={{ marginTop: 5 }}
                          />
                          <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 700, lineHeight: 1.5, wordBreak: "break-word" }}>
                            {record.series_label || "Tanpa judul"}
                          </div>
                          <div style={{ marginTop: 4, color: COLORS.muted, fontSize: 14, lineHeight: 1.6 }}>
                            {record.area_name || "Tanpa wilayah"} • {record.value_text || "-"} {record.unit || ""} • {record.year_value || "tanpa tahun"} • {record.period || "-"}
                          </div>
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                          <Pill style={{ background: "#fff1f7", color: COLORS.primaryDark }}>
                            {record.doc_type || "vector"}
                          </Pill>
                          <Button variant="outline" onClick={() => startEditPineconeRecord(record)}>
                            Edit Wilayah
                          </Button>
                        </div>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8, color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                        <div><strong>Batch:</strong> {record.batch_id || "-"}</div>
                        <div><strong>Dataset:</strong> {record.dataset_id || "-"}</div>
                        <div><strong>Provinsi:</strong> {record.metadata?.scan_province || record.metadata?.provinsi || record.metadata?.province || "-"}</div>
                        <div><strong>Kab/Kota:</strong> {record.metadata?.scan_regency || record.metadata?.kabupaten_kota || record.metadata?.kabupaten || record.metadata?.kota || "-"}</div>
                        <div><strong>Kecamatan:</strong> {record.metadata?.scan_district || record.metadata?.kecamatan || record.metadata?.district || "-"}</div>
                        <div><strong>Kelurahan/Desa:</strong> {record.metadata?.scan_village || record.metadata?.kelurahan || record.metadata?.desa || record.metadata?.village || "-"}</div>
                        <div><strong>Level wilayah:</strong> {record.area_level || record.metadata?.scan_area_level || "-"}</div>
                        <div><strong>Kode wilayah:</strong> {record.area_code || record.metadata?.scan_area_code || "-"}</div>
                        <div><strong>Nama file:</strong> {record.source_file || record.metadata?.scan_file_name || "-"}</div>
                        <div><strong>Lokasi file:</strong> {record.source || record.download_url || record.metadata?.scan_file_location || "-"}</div>
                        <div><strong>Pinecone ID:</strong> {record.pinecone_id || "-"}</div>
                      </div>
                      {editingPineconeRecord?.pinecone_id === record.pinecone_id ? (
                        <div style={{ borderRadius: 16, background: "#fbf8f5", border: "1px solid rgba(17,17,17,0.08)", padding: 14, display: "grid", gap: 10 }}>
                          <div style={{ fontWeight: 800 }}>Edit Wilayah Indonesia</div>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                            <input list="wilayah-provinces" value={editingPineconeRecord.province} onChange={(e) => handleRegionAutocomplete("province", e.target.value)} placeholder="Ketik/pilih provinsi" style={inputStyle} />
                            <input list="wilayah-regencies" value={editingPineconeRecord.regency} onChange={(e) => handleRegionAutocomplete("regency", e.target.value)} placeholder="Ketik/pilih kab/kota" style={inputStyle} disabled={!editingPineconeRecord.province_code} />
                            <input list="wilayah-districts" value={editingPineconeRecord.district} onChange={(e) => handleRegionAutocomplete("district", e.target.value)} placeholder="Ketik/pilih kecamatan" style={inputStyle} disabled={!editingPineconeRecord.regency_code} />
                            <input list="wilayah-villages" value={editingPineconeRecord.village} onChange={(e) => handleRegionAutocomplete("village", e.target.value)} placeholder="Ketik/pilih kelurahan/desa" style={inputStyle} disabled={!editingPineconeRecord.district_code} />
                            <datalist id="wilayah-provinces">
                              {(regionOptions.provinces || []).map((item) => <option key={item.id} value={item.name} />)}
                            </datalist>
                            <datalist id="wilayah-regencies">
                              {(regionOptions.regencies || []).map((item) => <option key={item.id} value={item.name} />)}
                            </datalist>
                            <datalist id="wilayah-districts">
                              {(regionOptions.districts || []).map((item) => <option key={item.id} value={item.name} />)}
                            </datalist>
                            <datalist id="wilayah-villages">
                              {(regionOptions.villages || []).map((item) => <option key={item.id} value={item.name} />)}
                            </datalist>
                          </div>
                          <details style={{ color: COLORS.muted, fontSize: 13 }}>
                            <summary style={{ cursor: "pointer", fontWeight: 800 }}>Edit kode metadata wilayah</summary>
                            <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                              <input value={editingPineconeRecord.province_code} onChange={(e) => updateEditingRegionField("province_code", e.target.value)} placeholder="Kode provinsi" style={inputStyle} />
                              <input value={editingPineconeRecord.regency_code} onChange={(e) => updateEditingRegionField("regency_code", e.target.value)} placeholder="Kode kab/kota" style={inputStyle} />
                              <input value={editingPineconeRecord.district_code} onChange={(e) => updateEditingRegionField("district_code", e.target.value)} placeholder="Kode kecamatan" style={inputStyle} />
                              <input value={editingPineconeRecord.village_code} onChange={(e) => updateEditingRegionField("village_code", e.target.value)} placeholder="Kode kelurahan/desa" style={inputStyle} />
                            </div>
                          </details>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <Button onClick={savePineconeRecordRegion} disabled={regionLoading}>
                              {regionLoading ? "Menyimpan..." : "Simpan Wilayah"}
                            </Button>
                            <Button variant="outline" onClick={() => setEditingPineconeRecord(null)} disabled={regionLoading}>
                              Batal
                            </Button>
                          </div>
                        </div>
                      ) : null}

                      {record.metadata ? (
                        <details style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                          <summary style={{ cursor: "pointer", fontWeight: 700 }}>Metadata</summary>
                          <pre style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                            {JSON.stringify(record.metadata, null, 2).slice(0, 900)}
                          </pre>
                        </details>
                      ) : null}
                      {record.embedding_text ? (
                        <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                          <strong>Embedding text:</strong> {String(record.embedding_text).slice(0, 220)}{String(record.embedding_text).length > 220 ? "..." : ""}
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
              <div style={{ padding: 14, borderTop: "1px solid rgba(17,17,17,0.08)", display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ color: COLORS.muted, fontSize: 13 }}>
                  Halaman {Math.floor((pineconeRecords.offset || 0) / (pineconeRecords.limit || 50)) + 1} • Offset {pineconeRecords.offset || 0}
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <Button
                    variant="outline"
                    disabled={pineconeLoading || (pineconeRecords.offset || 0) <= 0}
                    onClick={() => loadPineconeData(pineconeSearch, Math.max(0, (pineconeRecords.offset || 0) - (pineconeRecords.limit || initialPineconeLimit)), pineconeFilters, pineconeRecords.limit || initialPineconeLimit)}
                  >
                    Sebelumnya
                  </Button>
                  <Button
                    variant="outline"
                    disabled={pineconeLoading || ((pineconeRecords.offset || 0) + (pineconeRecords.limit || 50)) >= (pineconeRecords.total || 0)}
                    onClick={() => loadPineconeData(pineconeSearch, (pineconeRecords.offset || 0) + (pineconeRecords.limit || initialPineconeLimit), pineconeFilters, pineconeRecords.limit || initialPineconeLimit)}
                  >
                    Berikutnya
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </Card>
        </details>
        </>
        )}

        {adminTab === "ingestion" && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.1fr) minmax(320px, 0.9fr)", gap: 24 }}>
          <Card>
            <div style={{ padding: 28 }}>
              <div style={{ marginBottom: 18, fontSize: 18, fontWeight: 700 }}>Upload Batch Baru</div>
              <div style={{ display: "grid", gap: 14 }}>
                <div>
                  <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted }}>Jenis sumber</div>
                  <select value={uploadSourceDomain} onChange={(e) => setUploadSourceDomain(e.target.value)} style={inputStyle}>
                    <option value="bps">Statistik / BPS</option>
                    <option value="environment">Lingkungan</option>
                    <option value="legal">Hukum / regulasi</option>
                  </select>
                </div>
                <div>
                  <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted }}>Default Source Link</div>
                  <input
                    value={defaultSourceUrl}
                    onChange={(e) => setDefaultSourceUrl(e.target.value)}
                    placeholder="Opsional, dipakai sebagai source_url default untuk semua file"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted }}>Stable Download URL</div>
                  <input
                    value={defaultDownloadUrl}
                    onChange={(e) => setDefaultDownloadUrl(e.target.value)}
                    placeholder="URL file resmi yang dapat diunduh worker"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted }}>Dataset Files</div>
                  <label
                    htmlFor="admin-batch-files"
                    style={{
                      display: "grid",
                      gap: 8,
                      borderRadius: 20,
                      border: "1px dashed rgba(17,17,17,0.18)",
                      background: "white",
                      padding: 18,
                      cursor: "pointer",
                    }}
                  >
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
                      <FolderUp size={18} />
                      Pilih file dataset atau dokumen
                    </span>
                    <span style={{ color: COLORS.muted, fontSize: 14, lineHeight: 1.7 }}>
                      Statistik menerima CSV/XLSX/ZIP. Lingkungan dan hukum juga menerima PDF, HTML, DOCX, dan TXT.
                    </span>
                  </label>
                  <input
                    id="admin-batch-files"
                    type="file"
                    multiple
                    accept={uploadSourceDomain === "bps" ? ".csv,.xlsx,.zip" : ".csv,.xlsx,.zip,.pdf,.html,.htm,.docx,.txt"}
                    onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))}
                    style={{ display: "none" }}
                  />
                </div>

                {selectedFiles.length > 0 ? (
                  <div
                    style={{
                      borderRadius: 18,
                      background: "#fff",
                      border: "1px solid rgba(17,17,17,0.08)",
                      padding: 16,
                    }}
                  >
                    <div style={{ marginBottom: 10, fontWeight: 700 }}>{selectedFiles.length} file dipilih</div>
                    <div style={{ display: "grid", gap: 8 }}>
                      {selectedFiles.slice(0, 8).map((file) => (
                        <div key={file.name + file.size} style={{ color: COLORS.muted, fontSize: 14 }}>
                          {file.name}
                        </div>
                      ))}
                      {selectedFiles.length > 8 ? (
                        <div style={{ color: COLORS.muted, fontSize: 14 }}>
                          + {selectedFiles.length - 8} file lainnya
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                <Button onClick={handlePreviewSubmit} disabled={previewLoading || selectedFiles.length === 0}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <Search size={16} />
                    {previewLoading ? "Membuat Preview..." : "Preview Batch"}
                  </span>
                </Button>
              </div>
            </div>
          </Card>

          <Card>
            <div style={{ padding: 28 }}>
              <div style={{ marginBottom: 18, fontSize: 18, fontWeight: 700 }}>Batch Terbaru</div>
              {loadingOverview ? (
                <p style={{ margin: 0, color: COLORS.muted }}>Memuat batch admin...</p>
              ) : batches.length === 0 ? (
                <p style={{ margin: 0, color: COLORS.muted }}>Belum ada batch ingestion.</p>
              ) : (
                <div style={{ display: "grid", gap: 10 }}>
                  {batches.map((batch) => {
                    const active = batch.id === activeBatch?.id;
                    return (
                      <button
                        key={batch.id}
                        onClick={() => handleOpenBatch(batch.id)}
                        style={{
                          textAlign: "left",
                          width: "100%",
                          borderRadius: 18,
                          border: active ? `1px solid ${COLORS.primary}` : "1px solid rgba(17,17,17,0.08)",
                          background: active ? "#fff1f7" : "white",
                          padding: 16,
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "start" }}>
                          <div>
                            <div style={{ fontWeight: 700, lineHeight: 1.5 }}>{batch.id}</div>
                            <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 14 }}>
                              {batch.file_count} file • {batch.atomic_record_count} atomic record
                            </div>
                          </div>
                          <Pill style={{ background: "#fff", color: COLORS.text, border: "1px solid rgba(17,17,17,0.08)" }}>
                            {batch.status}
                          </Pill>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}

              <div style={{ marginTop: 24, paddingTop: 18, borderTop: "1px solid rgba(17,17,17,0.08)" }}>
                <div style={{ marginBottom: 12, fontSize: 16, fontWeight: 800 }}>History upload & data yang perlu dibersihkan</div>
                {!(ingestionHistory.records || []).length ? (
                  <p style={{ margin: 0, color: COLORS.muted, lineHeight: 1.7 }}>
                    Belum ada history upload di MySQL. Jalankan preview batch agar file dan hasil quality gate tersimpan.
                  </p>
                ) : (
                  <div style={{ display: "grid", gap: 10 }}>
                    {(ingestionHistory.records || []).map((item) => (
                      <div key={item.file_id} style={{ borderRadius: 16, background: "white", border: "1px solid rgba(17,17,17,0.08)", padding: 14, display: "grid", gap: 6 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                          <strong style={{ wordBreak: "break-word" }}>{item.original_filename || item.dataset_title || item.file_id}</strong>
                          <Pill style={{ background: item.quality_status === "pass" ? "#ecfdf3" : item.quality_status === "fail" ? "#fff1f2" : "#fff8e6", color: item.quality_status === "pass" ? "#027a48" : item.quality_status === "fail" ? "#b42318" : "#92400e" }}>
                            {item.quality_status || item.parse_status || "-"}
                          </Pill>
                        </div>
                        <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                          {item.dataset_title || "Tanpa judul dataset"} • {item.atomic_record_count || 0} atomic • skor {item.quality_score ?? 0}
                        </div>
                        {item.quality_summary ? (
                          <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>{item.quality_summary}</div>
                        ) : null}
                        {item.issues?.critical_issues?.length || item.issues?.warnings?.length ? (
                          <div style={{ color: "#92400e", fontSize: 13, lineHeight: 1.6 }}>
                            Bersihkan: {[...(item.issues?.critical_issues || []), ...(item.issues?.warnings || [])].slice(0, 3).join(" • ")}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Card>
        </div>
        )}

        {adminTab === "activity" && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 0.95fr) minmax(360px, 1.05fr)", gap: 24 }}>
          <Card>
            <div style={{ padding: 28 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 18 }}>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 800 }}>History Login User</div>
                  <p style={{ margin: "6px 0 0", color: COLORS.muted, lineHeight: 1.6 }}>
                    Cek kapan user login, IP, user agent, dan apakah session sudah logout/revoke. Saat awal dibuka hanya {initialActivityLimit} user terbaru yang dimuat agar ringan.
                  </p>
                </div>
                <Pill style={{ background: "#fff1f7", color: COLORS.primaryDark }}>
                  {activityHistory.auth_total || 0} session
                </Pill>
              </div>

              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    setError("");
                    await loadActivityHistory(activityUserEmail);
                  } catch (err) {
                    setError(err.message || "Gagal memuat history user.");
                  }
                }}
                style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}
              >
                <select
                  value={activityUserEmail}
                  onChange={(e) => setActivityUserEmail(e.target.value)}
                  style={{ ...inputStyle, flex: "1 1 220px" }}
                >
                  <option value="">Semua user</option>
                  {users.map((user) => (
                    <option key={user.email} value={user.email}>{user.email}</option>
                  ))}
                </select>
                <input
                  value={activityUserEmail}
                  onChange={(e) => setActivityUserEmail(e.target.value)}
                  placeholder="Atau ketik email user"
                  style={{ ...inputStyle, flex: "1 1 260px" }}
                />
                <Button type="submit" disabled={activityLoading}>
                  {activityLoading ? "Memuat..." : "Tampilkan"}
                </Button>
              </form>

              {activityHistory.activity_error ? (
                <div style={{ background: "#fff8e8", color: "#9a6700", borderRadius: 14, padding: 12, marginBottom: 14, fontSize: 13, lineHeight: 1.6 }}>
                  History user belum bisa dibaca: {activityHistory.activity_error}. Data Pinecone dan fitur admin lain tetap dimuat.
                </div>
              ) : null}

              {!(activityHistory.auth_sessions || []).length ? (
                <p style={{ margin: 0, color: COLORS.muted }}>Belum ada history login di MySQL.</p>
              ) : (
                <div style={{ display: "grid", gap: 10, maxHeight: 540, overflowY: "auto", paddingRight: 4 }}>
                  {(activityHistory.auth_sessions || []).map((session, idx) => (
                    <div key={`${session.user_email}-${session.created_at}-${idx}`} style={{ borderRadius: 18, border: "1px solid rgba(17,17,17,0.08)", background: "white", padding: 14, display: "grid", gap: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                        <strong style={{ wordBreak: "break-word" }}>{session.user_email || "-"}</strong>
                        <Pill style={{ background: session.revoked_at ? "#f4f0ec" : "#eefbf3", color: session.revoked_at ? COLORS.muted : "#166534" }}>
                          {session.revoked_at ? "Logout" : "Aktif / belum revoked"}
                        </Pill>
                      </div>
                      <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                        Login: {formatAdminDate(session.created_at)} • Last seen: {formatAdminDate(session.last_seen_at)}
                      </div>
                      <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                        IP: {session.ip_address || "-"} • User agent: {session.user_agent || "-"}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <div style={{ padding: 28 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 18 }}>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 800 }}>History Session Chat</div>
                  <p style={{ margin: "6px 0 0", color: COLORS.muted, lineHeight: 1.6 }}>
                    Gunakan daftar ini untuk kroscek pertanyaan user, jawaban sistem, dan metadata hasil pencarian. Maksimal {activityHistory.chat_per_user_limit || 5} chat terbaru per user agar database tetap ringan.
                  </p>
                </div>
                <Pill style={{ background: "#eef7ff", color: "#075985" }}>
                  {activityHistory.chat_total || 0} chat
                </Pill>
              </div>

              {!(activityHistory.chat_messages || []).length ? (
                <p style={{ margin: 0, color: COLORS.muted }}>Belum ada history chat di MySQL.</p>
              ) : (
                <div style={{ display: "grid", gap: 12, maxHeight: 620, overflowY: "auto", paddingRight: 4 }}>
                  {(activityHistory.chat_messages || []).map((chat, idx) => (
                    <div key={`${chat.session_id}-${chat.created_at}-${idx}`} style={{ borderRadius: 18, border: "1px solid rgba(17,17,17,0.08)", background: "white", padding: 14, display: "grid", gap: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                        <strong style={{ wordBreak: "break-word" }}>{chat.user_email || "-"}</strong>
                        <span style={{ color: COLORS.muted, fontSize: 13 }}>{formatAdminDate(chat.created_at)}</span>
                      </div>
                      <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                        Session: {chat.session_id || "-"} • Latency: {chat.latency_ms ?? "-"} ms
                      </div>
                      <div style={{ display: "grid", gap: 6 }}>
                        <div style={{ fontWeight: 800 }}>Pertanyaan</div>
                        <div style={{ color: COLORS.text, lineHeight: 1.7 }}>{chat.question || "-"}</div>
                      </div>
                      <div style={{ display: "grid", gap: 6 }}>
                        <div style={{ fontWeight: 800 }}>Jawaban</div>
                        <div style={{ color: COLORS.muted, lineHeight: 1.7 }}>
                          {String(chat.answer || "-").slice(0, 500)}{String(chat.answer || "").length > 500 ? "..." : ""}
                        </div>
                      </div>
                      {chat.top_matches?.length ? (
                        <details>
                          <summary style={{ cursor: "pointer", fontWeight: 800 }}>Top matches / metadata pencarian</summary>
                          <pre style={{ margin: "10px 0 0", whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12, background: "#f8f6f3", borderRadius: 14, padding: 12, maxHeight: 220, overflow: "auto" }}>
                            {JSON.stringify(chat.top_matches, null, 2)}
                          </pre>
                        </details>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
        )}

        {adminTab === "users" && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 0.95fr) minmax(320px, 1.05fr)", gap: 24 }}>
          <Card>
            <div style={{ padding: 28 }}>
              <div style={{ marginBottom: 18, fontSize: 18, fontWeight: 700 }}>Tambah User Baru</div>
              <div style={{ display: "grid", gap: 14 }}>
                <input
                  placeholder="Nama user"
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                  style={inputStyle}
                />
                <input
                  placeholder="Media/Organisasi"
                  value={newUserOrganization}
                  onChange={(e) => setNewUserOrganization(e.target.value)}
                  style={inputStyle}
                />
                <input
                  placeholder="Email user baru"
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  style={inputStyle}
                />
                <input
                  placeholder="Nomor handphone"
                  value={newUserPhone}
                  onChange={(e) => setNewUserPhone(e.target.value)}
                  style={inputStyle}
                />
                <input
                  type="password"
                  placeholder="Password user baru"
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                  style={inputStyle}
                />
                <select
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value)}
                  style={inputStyle}
                >
                  <option value="trial">Trial 3 chat</option>
                  <option value="user">Akses tak terbatas</option>
                  <option value="admin">Admin</option>
                </select>
                <Button onClick={handleCreateUser} disabled={createUserLoading}>
                  {createUserLoading ? "Membuat user..." : "Buat user"}
                </Button>
              </div>
              <p style={{ marginTop: 14, marginBottom: 0, color: COLORS.muted, lineHeight: 1.7, fontSize: 14 }}>
                Admin bisa membuat akun trial 3 chat, akun akses tak terbatas, atau admin baru langsung dari dashboard ini.
              </p>
            </div>
          </Card>

          <Card>
            <div style={{ padding: 28 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 18 }}>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>Daftar User</div>
                  <div style={{ color: COLORS.muted, fontSize: 13, marginTop: 4 }}>
                    Menampilkan {usersPageStart}-{usersPageEnd} dari {usersTotal} user.
                  </div>
                </div>
                <Button onClick={() => loadUsers()} disabled={usersLoading}>
                  {usersLoading ? "Memuat..." : "Refresh"}
                </Button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 150px 150px", gap: 10, marginBottom: 14 }}>
                <input
                  placeholder="Cari nama, email, organisasi, atau nomor HP..."
                  value={usersSearch}
                  onChange={(e) => setUsersSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") loadUsers({ search: usersSearch, role: usersRoleFilter, status: usersStatusFilter, offset: 0 });
                  }}
                  style={inputStyle}
                />
                <select value={usersRoleFilter} onChange={(e) => setUsersRoleFilter(e.target.value)} style={inputStyle}>
                  <option value="">Semua role</option>
                  <option value="trial">Trial</option>
                  <option value="user">Tak terbatas</option>
                  <option value="admin">Admin</option>
                </select>
                <select value={usersStatusFilter} onChange={(e) => setUsersStatusFilter(e.target.value)} style={inputStyle}>
                  <option value="">Semua status</option>
                  <option value="active">Aktif</option>
                  <option value="pending_confirmation">Menunggu konfirmasi</option>
                  <option value="inactive">Nonaktif</option>
                </select>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <Button onClick={() => loadUsers({ search: usersSearch, role: usersRoleFilter, status: usersStatusFilter, offset: 0 })} disabled={usersLoading}>
                    Terapkan Filter
                  </Button>
                  <button
                    type="button"
                    onClick={() => {
                      setUsersSearch("");
                      setUsersRoleFilter("");
                      setUsersStatusFilter("");
                      loadUsers({ search: "", role: "", status: "", offset: 0 });
                    }}
                    style={{ ...secondaryButtonStyle, padding: "10px 16px" }}
                  >
                    Reset
                  </button>
                </div>
                <select
                  value={usersLimit}
                  onChange={(e) => loadUsers({ limit: Number(e.target.value), offset: 0 })}
                  style={{ ...inputStyle, width: 140, minHeight: 44 }}
                >
                  <option value={10}>10 / halaman</option>
                  <option value={25}>25 / halaman</option>
                  <option value={50}>50 / halaman</option>
                  <option value={100}>100 / halaman</option>
                </select>
              </div>

              {usersLoading || loadingOverview ? (
                <p style={{ margin: 0, color: COLORS.muted }}>Memuat user...</p>
              ) : users.length === 0 ? (
                <p style={{ margin: 0, color: COLORS.muted }}>Belum ada user sesuai filter.</p>
              ) : (
                <div style={{ display: "grid", gap: 10, maxHeight: 360, overflowY: "auto", paddingRight: 4 }}>
                  {users.map((user) => (
                    <div
                      key={user.email}
                      style={{
                        borderRadius: 18,
                        border: "1px solid rgba(17,17,17,0.08)",
                        background: "white",
                        padding: 14,
                        display: "grid",
                        gap: 12,
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 700, lineHeight: 1.5, wordBreak: "break-word" }}>{user.name || user.email}</div>
                        <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6, wordBreak: "break-word" }}>
                          {user.email} • {user.media_organization || "Tanpa organisasi"} • {user.phone || "Tanpa nomor HP"}
                        </div>
                        <div style={{ color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                          Status: {user.status || "-"} • Chat: {user.chat_limit ? `${user.chat_count || 0}/${user.chat_limit}` : "tak terbatas"}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                        <Pill style={{ background: user.role === "admin" ? "#fff1f7" : user.role === "trial" ? "#fff8e8" : "#eefbf3", color: user.role === "admin" ? COLORS.primaryDark : user.role === "trial" ? "#9a6700" : "#166534" }}>
                          {user.role === "trial" ? "trial 3 chat" : user.role === "user" ? "tak terbatas" : "admin"}
                        </Pill>
                        <select value={user.role} onChange={(e) => updateUserAccess(user.email, e.target.value)} style={{ ...inputStyle, padding: "10px 12px", minHeight: 0, width: 180 }}>
                          <option value="trial">Trial 3 chat</option>
                          <option value="user">Akses tak terbatas</option>
                          <option value="admin">Admin</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => resendUserConfirmation(user.email)}
                          disabled={confirmationLoadingEmail === user.email}
                          style={{
                            ...secondaryButtonStyle,
                            padding: "10px 12px",
                            opacity: confirmationLoadingEmail === user.email ? 0.6 : 1,
                          }}
                        >
                          {confirmationLoadingEmail === user.email ? "Mengirim..." : "Kirim email konfirmasi"}
                        </button>
                        <button
                          type="button"
                          onClick={() => updateUserStatus(user.email, user.status === "inactive" ? "active" : "inactive")}
                          disabled={userActionLoading === `${user.email}:status`}
                          style={{
                            ...secondaryButtonStyle,
                            padding: "10px 12px",
                            opacity: userActionLoading === `${user.email}:status` ? 0.6 : 1,
                          }}
                        >
                          {userActionLoading === `${user.email}:status`
                            ? "Menyimpan..."
                            : user.status === "inactive"
                              ? "Aktifkan"
                              : "Nonaktifkan"}
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteUser(user.email)}
                          disabled={userActionLoading === `${user.email}:delete`}
                          style={{
                            ...secondaryButtonStyle,
                            padding: "10px 12px",
                            color: "#b42318",
                            borderColor: "rgba(180,35,24,0.25)",
                            opacity: userActionLoading === `${user.email}:delete` ? 0.6 : 1,
                          }}
                        >
                          {userActionLoading === `${user.email}:delete` ? "Menghapus..." : "Delete"}
                        </button>
                      </div>
                      {confirmationStatusByEmail[user.email] ? (() => {
                        const status = confirmationStatusByEmail[user.email];
                        const tone = confirmationStatusTone(status);
                        return (
                          <div
                            style={{
                              borderRadius: 14,
                              border: `1px solid ${tone.border}`,
                              background: tone.background,
                              color: tone.color,
                              padding: "10px 12px",
                              fontSize: 13,
                              lineHeight: 1.6,
                              fontWeight: 700,
                            }}
                          >
                            <div>Status pengiriman konfirmasi:</div>
                            {status.email ? (
                              <div style={{ fontWeight: 600 }}>{confirmationChannelText("Email", status.email)}</div>
                            ) : null}
                            {status.whatsapp ? (
                              <div style={{ fontWeight: 600 }}>{confirmationChannelText("WhatsApp", status.whatsapp)}</div>
                            ) : null}
                          </div>
                        );
                      })() : null}
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 16 }}>
                <button
                  type="button"
                  onClick={() => loadUsers({ offset: Math.max(0, usersOffset - usersLimit) })}
                  disabled={!canPrevUsers || usersLoading}
                  style={{ ...secondaryButtonStyle, opacity: !canPrevUsers || usersLoading ? 0.55 : 1 }}
                >
                  Sebelumnya
                </button>
                <div style={{ color: COLORS.muted, fontSize: 13 }}>
                  Halaman {usersTotal === 0 ? 0 : Math.floor(usersOffset / usersLimit) + 1} dari {Math.max(1, Math.ceil(usersTotal / usersLimit))}
                </div>
                <button
                  type="button"
                  onClick={() => loadUsers({ offset: usersOffset + usersLimit })}
                  disabled={!canNextUsers || usersLoading}
                  style={{ ...secondaryButtonStyle, opacity: !canNextUsers || usersLoading ? 0.55 : 1 }}
                >
                  Berikutnya
                </button>
              </div>
            </div>
          </Card>
        </div>
        )}

        {adminTab === "settings" && (
          <Card>
            <div style={{ padding: 28, display: "grid", gap: 18 }}>
              <div>
                <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                  Settings Email
                </div>
                <div style={{ fontSize: 22, fontWeight: 800 }}>Gmail API & Refresh Token</div>
                <p style={{ marginTop: 8, marginBottom: 0, color: COLORS.muted, lineHeight: 1.7 }}>
                  Halaman ini untuk mengecek MySQL <code>app_settings</code>, status refresh token Gmail, dan membuka proses OAuth satu kali tanpa membuat token manual.
                </p>
              </div>

              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <Button onClick={loadGmailSetting} disabled={gmailSettingLoading}>
                  {gmailSettingLoading ? "Memuat..." : "Refresh Status Gmail API"}
                </Button>
                <Button variant="outline" onClick={startGmailOAuthConnect} disabled={gmailSettingLoading}>
                  Buat Auth URL Gmail
                </Button>
              </div>

              <div style={{ display: "grid", gap: 10, color: COLORS.muted, lineHeight: 1.7 }}>
                <div><strong style={{ color: COLORS.text }}>MySQL aktif:</strong> {gmailSetting?.mysql_operational_store ? "Ya" : "Belum / tidak terbaca"}</div>
                <div><strong style={{ color: COLORS.text }}>Tabel app_settings:</strong> {gmailSetting?.app_settings_available ? "Siap dipakai" : "Belum tersedia"}</div>
                {gmailSetting?.app_settings_error ? (
                  <div style={{ color: "#9f1d1d" }}><strong>Error app_settings:</strong> {gmailSetting.app_settings_error}</div>
                ) : null}
                <div><strong style={{ color: COLORS.text }}>Refresh token tersimpan di MySQL:</strong> {gmailSetting?.stored_refresh_token ? "Ada" : "Belum ada"}</div>
                <div><strong style={{ color: COLORS.text }}>Provider email:</strong> {gmailSetting?.email_delivery_provider || "-"}</div>
                <div><strong style={{ color: COLORS.text }}>Client ID:</strong> {gmailSetting?.gmail_client_id_configured ? "Terisi" : "Belum"}</div>
                <div><strong style={{ color: COLORS.text }}>Client Secret:</strong> {gmailSetting?.gmail_client_secret_configured ? "Terisi" : "Belum"}</div>
                <div><strong style={{ color: COLORS.text }}>GMAIL_API_FROM:</strong> {gmailSetting?.gmail_from_configured ? "Terisi" : "Belum"}</div>
                <div style={{ wordBreak: "break-word" }}>
                  <strong style={{ color: COLORS.text }}>Redirect URI Google Console:</strong> {gmailSetting?.redirect_uri || "-"}
                </div>
                <div><strong style={{ color: COLORS.text }}>Sumber Redirect URI:</strong> {gmailSetting?.redirect_uri_source || "-"}</div>
                {gmailSetting?.redirect_uri ? (
                  <div style={{ borderRadius: 16, background: "#fff8e8", color: "#7c4a03", padding: 14, lineHeight: 1.7 }}>
                    Jika muncul <strong>redirect_uri_mismatch</strong>, buka Google Cloud Console → OAuth Client → Authorized redirect URIs, lalu tambahkan URL ini persis sama: <code>{gmailSetting.redirect_uri}</code>
                  </div>
                ) : null}
              </div>

              <p style={{ margin: 0, color: COLORS.muted, lineHeight: 1.7 }}>
                Jika refresh token belum ada, klik <strong>Buat Auth URL Gmail</strong>, setujui scope Gmail Send, lalu kembali dan klik <strong>Refresh Status Gmail API</strong>. Untuk error redirect_uri_mismatch, pastikan Redirect URI di atas sudah didaftarkan di Google Cloud Console.
              </p>
            </div>
          </Card>
        )}

        {error ? (
          <div style={{ background: "#fff1f1", color: "#9f1d1d", borderRadius: 18, padding: 16 }}>
            {error}
          </div>
        ) : null}

        {success ? (
          <div style={{ background: "#eefbf3", color: "#166534", borderRadius: 18, padding: 16 }}>
            {success}
          </div>
        ) : null}

        {adminTab === "batch" && activeBatch && (
          <Card>
            <div style={{ padding: 28 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                <div>
                  <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                    Batch Detail
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 700 }}>{activeBatch.id}</div>
                <p style={{ marginTop: 8, marginBottom: 0, color: COLORS.muted, lineHeight: 1.7 }}>
                  Status {activeBatch.status}. Total {activeBatch.file_count} file dan {activeBatch.atomic_record_count} atomic record.
                </p>
                <p style={{ marginTop: 10, marginBottom: 0, color: COLORS.primaryDark, lineHeight: 1.7, fontWeight: 700 }}>
                  Inspector record otomatis terbuka di bawah untuk file yang siap diparse.
                </p>
              </div>
                <Button
                  onClick={() => handlePublish(activeBatch.id)}
                  disabled={!["preview_ready", "partial_failed"].includes(activeBatch.status) || publishLoading === activeBatch.id}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <Database size={16} />
                    {publishLoading === activeBatch.id ? "Publishing..." : "Publish to Pinecone"}
                  </span>
                </Button>
              </div>

              <div style={{ marginTop: 22, display: "grid", gap: 16 }}>
                {publishPreview ? (
                  <div
                    style={{
                      borderRadius: 20,
                      background: "#fbf8f5",
                      border: "1px solid rgba(17,17,17,0.08)",
                      padding: 18,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start", flexWrap: "wrap" }}>
                      <div>
                        <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                          Pinecone Publish Preview
                        </div>
                        <div style={{ fontWeight: 700, lineHeight: 1.6 }}>
                          {publishPreview.eligible_file_count} file siap publish • {publishPreview.eligible_record_count} record eligible
                        </div>
                        <div style={{ marginTop: 8, color: COLORS.muted, lineHeight: 1.7, fontSize: 14 }}>
                          Index: {publishPreview.publish_env?.index_name || "-"} • Embed model: {publishPreview.publish_env?.embed_model || "-"} • Dimensi: {publishPreview.publish_env?.embed_dimensions || "default"}
                        </div>
                      </div>
                      <Pill
                        style={{
                          background: publishPreview.publish_ready ? "#eefbf3" : "#fff8e8",
                          color: publishPreview.publish_ready ? "#166534" : "#9a6700",
                        }}
                      >
                        {publishPreview.publish_ready ? "Env siap publish" : "Env belum lengkap"}
                      </Pill>
                    </div>
                    {publishPreview.publish_env?.missing?.length ? (
                      <div style={{ marginTop: 12, color: "#9a6700", fontSize: 14, lineHeight: 1.7 }}>
                        Missing env: {publishPreview.publish_env.missing.join(" • ")}
                      </div>
                    ) : null}
                    {publishPreview.sample_prepared_records?.length ? (
                      <div style={{ marginTop: 14, color: COLORS.muted, fontSize: 14, lineHeight: 1.7 }}>
                        Sample payload final sudah tersedia di inspector record di bawah.
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {(activeBatch.files || []).map((file) => (
                  <div
                    key={file.id}
                    style={{
                      borderRadius: 20,
                      background: "white",
                      border: "1px solid rgba(17,17,17,0.08)",
                      padding: 18,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "start", flexWrap: "wrap" }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 700, lineHeight: 1.5 }}>{file.original_filename}</div>
                        <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 14 }}>
                          {file.dataset_title || "Dataset title belum terdeteksi"} • {file.parse_status}
                        </div>
                        <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 14 }}>
                          {file.data_row_count} row data • {file.atomic_record_count} atomic record • storage {file.storage_mode}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <Pill style={{ background: "#fff1f7", color: COLORS.primaryDark }}>
                          {file.provenance_status}
                        </Pill>
                        <Pill style={{ background: getQualityTone(file.quality_status).background, color: getQualityTone(file.quality_status).color }}>
                          {getQualityTone(file.quality_status).label} • {file.quality_score ?? 0}
                        </Pill>
                      </div>
                    </div>

                    <div style={{ marginTop: 14, display: "grid", gap: 10 }}>
                      {renderPipelinePills(file)}

                      <div style={{ borderRadius: 16, background: "#fbf8f5", border: "1px solid rgba(17,17,17,0.06)", padding: 14 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 6 }}>
                          Quality Gate
                        </div>
                        <div style={{ fontWeight: 700, lineHeight: 1.6 }}>
                          {file.quality_summary || "Belum ada ringkasan quality gate."}
                        </div>
                        {file.quality?.critical_issues?.length ? (
                          <div style={{ marginTop: 8, color: "#9f1d1d", fontSize: 14, lineHeight: 1.7 }}>
                            <strong>Critical:</strong> {file.quality.critical_issues.join(" • ")}
                          </div>
                        ) : null}
                        {file.quality?.warnings?.length ? (
                          <div style={{ marginTop: 8, color: "#9a6700", fontSize: 14, lineHeight: 1.7 }}>
                            <strong>Warning:</strong> {file.quality.warnings.join(" • ")}
                          </div>
                        ) : null}
                      </div>

                      {file.source_url ? (
                        <div style={{ fontSize: 14, lineHeight: 1.7 }}>
                          <strong>Source URL:</strong>{" "}
                          <a href={file.source_url} target="_blank" rel="noreferrer" style={{ color: COLORS.primaryDark, textDecoration: "none" }}>
                            {file.source_url}
                          </a>
                        </div>
                      ) : (
                        <div style={{ fontSize: 14, lineHeight: 1.7, color: COLORS.muted }}>
                          Source URL tidak diisi.
                        </div>
                      )}

                      {file.download_url ? (
                        <div style={{ fontSize: 14, lineHeight: 1.7 }}>
                          <strong>Download URL:</strong>{" "}
                          <a href={file.download_url} target="_blank" rel="noreferrer" style={{ color: COLORS.primaryDark, textDecoration: "none" }}>
                            {file.download_url}
                          </a>
                        </div>
                      ) : (
                        <div style={{ fontSize: 14, lineHeight: 1.7, color: COLORS.muted }}>
                          Download URL belum tersedia. File masih lokal atau Google Drive belum aktif.
                        </div>
                      )}

                      {file.gdrive_view_url ? (
                        <div style={{ fontSize: 14, lineHeight: 1.7 }}>
                          <strong>Drive View:</strong>{" "}
                          <a href={file.gdrive_view_url} target="_blank" rel="noreferrer" style={{ color: COLORS.primaryDark, textDecoration: "none" }}>
                            {file.gdrive_view_url}
                          </a>
                        </div>
                      ) : null}

                      {file.columns?.length ? (
                        <div>
                          <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                            Detected Columns
                          </div>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                            {file.columns.map((col) => (
                              <Pill key={`${file.id}-${col.column_index}`} style={{ background: "#f8f5f2", color: COLORS.text }}>
                                {col.series_label} {col.year ? `(${col.year})` : ""}
                              </Pill>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      {file.error_message ? (
                        <div style={{ background: "#fff1f1", color: "#9f1d1d", borderRadius: 16, padding: 14 }}>
                          {file.error_message}
                        </div>
                      ) : null}

                      {file.sample_records?.length ? (
                        <div>
                          <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                            Sample Atomic Records
                          </div>
                          <div style={{ display: "grid", gap: 10 }}>
                            {file.sample_records.slice(0, 3).map((record) => (
                              <div
                                key={record.id}
                                style={{
                                  borderRadius: 16,
                                  background: "#fbf8f5",
                                  border: "1px solid rgba(17,17,17,0.06)",
                                  padding: 14,
                                }}
                              >
                                <div style={{ fontWeight: 700, lineHeight: 1.5 }}>
                                  {record.series_label} • {record.area_name} • {record.year || "tanpa tahun"}
                                </div>
                                <div style={{ marginTop: 6, color: COLORS.muted, lineHeight: 1.7, fontSize: 14 }}>
                                  Nilai {record.value} {record.unit || ""}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      {file.normalization_status === "pending" ? (() => {
                        const reviewKey = `${activeBatch.id}:${file.id}`;
                        const draft = normalizationDrafts[reviewKey];
                        const form = normalizationForms[reviewKey] || {};
                        const machine = draft?.machine_result || {};
                        return (
                          <div style={{ borderRadius: 18, border: "1px solid #f0c36a", background: "#fffaf0", padding: 16, display: "grid", gap: 12 }}>
                            <div>
                              <div style={{ fontWeight: 800 }}>Review cepat normalisasi</div>
                              <div style={{ marginTop: 5, color: "#7c4a03", fontSize: 14, lineHeight: 1.6 }}>
                                Mesin menyimpan file ini sebagai draft. Buka hasil mesin, lengkapi field yang kosong, lalu satu kali simpan untuk menyetujui dan meneruskan ke MySQL + antrean Pinecone.
                              </div>
                            </div>
                            {!draft ? (
                              <Button variant="outline" onClick={() => openNormalizationReview(activeBatch.id, file.id)} disabled={normalizationLoading === reviewKey}>
                                {normalizationLoading === reviewKey ? "Memuat draft..." : "Buka review cepat"}
                              </Button>
                            ) : (
                              <div style={{ display: "grid", gap: 12 }}>
                                <div style={{ borderRadius: 14, background: "white", padding: 12, fontSize: 14, lineHeight: 1.7 }}>
                                  <strong>Yang berhasil dinormalisasi mesin:</strong><br />
                                  Parse {machine.parse_status || "-"} • quality {machine.quality_status || "-"} • {machine.atomic_record_count || 0} record.<br />
                                  {machine.quality_summary || machine.normalization_reason || "Tidak ada ringkasan."}
                                </div>
                                {!draft.can_approve ? (
                                  <div style={{ color: "#9f1d1d", fontWeight: 700 }}>{draft.blocked_reason}</div>
                                ) : (
                                  <>
                                    <input value={form.dataset_title || ""} onChange={(e) => updateNormalizationForm(reviewKey, "dataset_title", e.target.value)} placeholder="Judul dataset/dokumen" style={inputStyle} />
                                    <input value={form.source_url || ""} onChange={(e) => updateNormalizationForm(reviewKey, "source_url", e.target.value)} placeholder="Source URL resmi (wajib)" style={inputStyle} />
                                    <input value={form.download_url || ""} onChange={(e) => updateNormalizationForm(reviewKey, "download_url", e.target.value)} placeholder="Stable download URL (wajib)" style={inputStyle} />
                                    {draft.source_domain !== "bps" ? (
                                      <div>
                                        <div style={{ marginBottom: 6, fontSize: 13, fontWeight: 700 }}>Hasil ekstraksi domain — lengkapi bagian kosong</div>
                                        <div style={{ marginBottom: 8, color: COLORS.muted, fontSize: 13, lineHeight: 1.6 }}>
                                          Wajib: {(draft.domain_required_fields || []).join(" • ")}
                                        </div>
                                        <textarea value={form.domain_payload || ""} onChange={(e) => updateNormalizationForm(reviewKey, "domain_payload", e.target.value)} rows={12} style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace" }} />
                                      </div>
                                    ) : null}
                                    <label style={{ display: "flex", gap: 10, alignItems: "start", fontSize: 14, lineHeight: 1.6, cursor: "pointer" }}>
                                      <input type="checkbox" checked={!!form.approved} onChange={(e) => updateNormalizationForm(reviewKey, "approved", e.target.checked)} style={{ marginTop: 4 }} />
                                      <span>Saya menyetujui kondisi data saat ini. Simpan berarti data dianggap reviewed dan langsung diteruskan ke canonical MySQL serta outbox Pinecone.</span>
                                    </label>
                                    <Button onClick={() => approveNormalization(activeBatch.id, file.id)} disabled={!form.approved || normalizationLoading === reviewKey}>
                                      {normalizationLoading === reviewKey ? "Menyimpan..." : "Setujui & lanjutkan"}
                                    </Button>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })() : null}

                      {file.parse_status === "ready" ? (
                        <div style={{ display: "flex", justifyContent: "flex-end" }}>
                          <Button
                            variant="outline"
                            onClick={() => handleInspectFile(file)}
                            disabled={recordLoading === file.id}
                          >
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                              <Search size={16} />
                              {recordLoading === file.id ? "Membuka inspector..." : "Inspect records"}
                            </span>
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        )}

        {adminTab === "batch" && recordInspector && (
          <Card>
            <div style={{ padding: 28, display: "grid", gap: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "start", flexWrap: "wrap" }}>
                <div>
                  <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                    Record Inspector
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 700 }}>
                    {recordInspector.file?.original_filename}
                  </div>
                  <p style={{ marginTop: 8, marginBottom: 0, color: COLORS.muted, lineHeight: 1.7, maxWidth: 760 }}>
                    Ini tampilan hasil kerja mesin di lokal: record hasil parse, audit metadata, dan teks yang nanti dipakai untuk embedding sebelum masuk Pinecone.
                  </p>
                </div>
                <Pill style={{ background: "#fff1f7", color: COLORS.primaryDark }}>
                  {recordInspector.file?.parse_status}
                </Pill>
              </div>

              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <Pill style={{ background: getQualityTone(recordInspector.file?.quality_status).background, color: getQualityTone(recordInspector.file?.quality_status).color }}>
                  Quality {getQualityTone(recordInspector.file?.quality_status).label} • {recordInspector.file?.quality_score ?? 0}
                </Pill>
                {recordInspector.file?.quality_summary ? (
                  <div style={{ color: COLORS.muted, lineHeight: 1.7 }}>
                    {recordInspector.file.quality_summary}
                  </div>
                ) : null}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
                {[
                  { label: "Total record", value: recordInspector.record_audit_summary?.total ?? 0 },
                  { label: "Sehat", value: recordInspector.record_audit_summary?.healthy ?? 0 },
                  { label: "Perlu cek", value: recordInspector.record_audit_summary?.warning ?? 0 },
                  { label: "Bermasalah", value: recordInspector.record_audit_summary?.invalid ?? 0 },
                ].map((item) => (
                  <div
                    key={item.label}
                    style={{
                      borderRadius: 18,
                      background: "white",
                      border: "1px solid rgba(17,17,17,0.08)",
                      padding: 16,
                    }}
                  >
                    <div style={{ fontSize: 14, color: COLORS.muted }}>{item.label}</div>
                    <div style={{ marginTop: 8, fontSize: 26, fontWeight: 700 }}>{item.value}</div>
                  </div>
                ))}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 0.95fr) minmax(320px, 1.05fr)", gap: 20 }}>
                <div
                  style={{
                    borderRadius: 22,
                    background: "white",
                    border: "1px solid rgba(17,17,17,0.08)",
                    padding: 16,
                  }}
                >
                  <div style={{ marginBottom: 12, fontSize: 16, fontWeight: 700 }}>
                    Record hasil parse ({recordInspector.records?.length ?? 0} ditampilkan dari {recordInspector.records_total ?? 0})
                  </div>
                  <div style={{ display: "grid", gap: 10, maxHeight: 720, overflowY: "auto", paddingRight: 4 }}>
                    {(recordInspector.records || []).map((record) => {
                      const tone = getAuditTone(record.audit?.status);
                      const active = selectedRecord?.id === record.id;
                      return (
                        <button
                          key={record.id}
                          onClick={() => setSelectedRecordId(record.id)}
                          style={{
                            textAlign: "left",
                            width: "100%",
                            borderRadius: 18,
                            border: active ? `1px solid ${COLORS.primary}` : "1px solid rgba(17,17,17,0.08)",
                            background: active ? "#fff1f7" : "#fbf8f5",
                            padding: 14,
                            cursor: "pointer",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
                            <div style={{ minWidth: 0 }}>
                              <div style={{ fontWeight: 700, lineHeight: 1.5 }}>
                                {record.series_label} • {record.area_name}
                              </div>
                              <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 14, lineHeight: 1.6 }}>
                                {record.value} {record.unit || ""} • {record.year || "tanpa tahun"}
                              </div>
                            </div>
                            <Pill style={{ background: tone.background, color: tone.color }}>
                              {tone.label}
                            </Pill>
                          </div>
                          {record.audit?.issue_count ? (
                            <div style={{ marginTop: 8, fontSize: 13, color: tone.color }}>
                              {record.audit.issue_count} catatan audit
                            </div>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div
                  style={{
                    borderRadius: 22,
                    background: "white",
                    border: "1px solid rgba(17,17,17,0.08)",
                    padding: 18,
                  }}
                >
                  {selectedRecord ? (
                    <div style={{ display: "grid", gap: 16 }}>
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start", flexWrap: "wrap" }}>
                          <div>
                            <div style={{ fontSize: 20, fontWeight: 700, lineHeight: 1.4 }}>
                              {selectedRecord.title || `${selectedRecord.series_label} ${selectedRecord.area_name}`}
                            </div>
                            <div style={{ marginTop: 6, color: COLORS.muted, lineHeight: 1.7 }}>
                              {selectedRecord.series_label} • {selectedRecord.area_name} • {selectedRecord.year || "tanpa tahun"}
                            </div>
                          </div>
                          <Pill style={{ background: getAuditTone(selectedRecord.audit?.status).background, color: getAuditTone(selectedRecord.audit?.status).color }}>
                            {getAuditTone(selectedRecord.audit?.status).label}
                          </Pill>
                        </div>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
                        {[
                          { label: "Value", value: `${selectedRecord.value ?? "-"} ${selectedRecord.unit || ""}`.trim() },
                          { label: "Area code", value: selectedRecord.area_code || "-" },
                          { label: "Area level", value: selectedRecord.area_level || "-" },
                          { label: "Period", value: selectedRecord.period || "-" },
                        ].map((item) => (
                          <div
                            key={item.label}
                            style={{
                              borderRadius: 16,
                              background: "#fbf8f5",
                              border: "1px solid rgba(17,17,17,0.06)",
                              padding: 12,
                            }}
                          >
                            <div style={{ fontSize: 12, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.5 }}>
                              {item.label}
                            </div>
                            <div style={{ marginTop: 6, fontWeight: 700, lineHeight: 1.5 }}>
                              {item.value}
                            </div>
                          </div>
                        ))}
                      </div>

                      <div style={{ display: "grid", gap: 10 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                          Audit Record
                        </div>
                        {selectedRecord.audit?.missing_core?.length ? (
                          <div style={{ background: "#fff1f1", color: "#9f1d1d", borderRadius: 16, padding: 14, lineHeight: 1.7 }}>
                            <strong>Core issue:</strong> {selectedRecord.audit.missing_core.join(" • ")}
                          </div>
                        ) : (
                          <div style={{ background: "#eefbf3", color: "#166534", borderRadius: 16, padding: 14, lineHeight: 1.7 }}>
                            Field inti record sudah lengkap.
                          </div>
                        )}
                        {selectedRecord.audit?.warnings?.length ? (
                          <div style={{ background: "#fff8e8", color: "#9a6700", borderRadius: 16, padding: 14, lineHeight: 1.7 }}>
                            <strong>Peringatan:</strong> {selectedRecord.audit.warnings.join(" • ")}
                          </div>
                        ) : null}
                      </div>

                      <div style={{ display: "grid", gap: 10 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                          Embedding Text Preview
                        </div>
                        <div style={{ borderRadius: 16, background: "#fbf8f5", border: "1px solid rgba(17,17,17,0.06)", padding: 14, lineHeight: 1.8 }}>
                          {selectedRecord.embedding_text_preview}
                        </div>
                      </div>

                      {selectedRecordPineconePayload ? (
                        <div style={{ display: "grid", gap: 10 }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                            Pinecone Payload Preview
                          </div>
                          <div style={{ borderRadius: 16, background: "#fbf8f5", border: "1px solid rgba(17,17,17,0.06)", padding: 14, display: "grid", gap: 8, fontSize: 14, lineHeight: 1.7 }}>
                            <div><strong>ID:</strong> {selectedRecordPineconePayload.id || "-"}</div>
                            <div><strong>Doc type:</strong> {selectedRecordPineconePayload.doc_type || "-"}</div>
                            <div><strong>Text:</strong> {selectedRecordPineconePayload.text || "-"}</div>
                          </div>
                          <pre
                            style={{
                              margin: 0,
                              whiteSpace: "pre-wrap",
                              wordBreak: "break-word",
                              borderRadius: 16,
                              background: "#111111",
                              color: "#f5f2ef",
                              padding: 14,
                              fontSize: 12,
                              lineHeight: 1.7,
                              overflowX: "auto",
                            }}
                          >
                            {JSON.stringify(selectedRecordPineconePayload, null, 2)}
                          </pre>
                        </div>
                      ) : null}

                      <div style={{ display: "grid", gap: 10 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: COLORS.muted, textTransform: "uppercase", letterSpacing: 0.6 }}>
                          Metadata Penting
                        </div>
                        <div style={{ borderRadius: 16, background: "#fbf8f5", border: "1px solid rgba(17,17,17,0.06)", padding: 14, display: "grid", gap: 8, fontSize: 14, lineHeight: 1.7 }}>
                          <div><strong>Source file:</strong> {selectedRecord.source_file || "-"}</div>
                          <div><strong>Source URL:</strong> {selectedRecord.metadata?.source_url || "-"}</div>
                          <div><strong>Download URL:</strong> {selectedRecord.download_url || "-"}</div>
                          <div><strong>Provenance:</strong> {selectedRecord.metadata?.provenance_status || "-"}</div>
                          <div><strong>Batch ID:</strong> {selectedRecord.metadata?.ingest_batch_id || "-"}</div>
                          <div><strong>Raw area:</strong> {selectedRecord.metadata?.raw_area_label || "-"}</div>
                          <div><strong>Raw indicator:</strong> {selectedRecord.metadata?.raw_indicator_label || "-"}</div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: COLORS.muted, lineHeight: 1.8 }}>
                      Pilih salah satu record di sebelah kiri untuk melihat detail hasil parsingnya.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

export function ChatPage({ localMode = false, ready = true, navigation = null }) {
  const chatHistoryLimit = 200;
  const activeRequest = useRef(null);
  const transcript = useRef(null);
  const savedReadPosition = useRef(0);
  const previousView = useRef(navigation?.page);
  const [pendingConversation, setPendingConversation] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const [historyReady, setHistoryReady] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [selectedSource, setSelectedSource] = useState("bps");
  const [sourceOptions, setSourceOptions] = useState(publicSourceOptions);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 768);
  useEffect(() => {
    const resize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', resize);
    return () => { window.removeEventListener('resize', resize); activeRequest.current?.abort(); };
  }, []);

  useEffect(() => {
    if (ready || !activeRequest.current) return;
    activeRequest.current.abort();
    activeRequest.current = null;
    setLoading(false);
    setPendingConversation(null);
    setDraft(current => current || pendingConversation?.question || '');
    setError('');
  }, [ready]);

  useLayoutEffect(() => {
    if (navigation?.page === 'chat' && previousView.current === 'about') {
      transcript.current?.scrollTo({ top: savedReadPosition.current, behavior: 'instant' });
    }
    previousView.current = navigation?.page;
  }, [navigation?.page]);

  function navigate(page) {
    if (page === 'about' && navigation?.page !== 'about') savedReadPosition.current = transcript.current?.scrollTop || 0;
    setMobileHistoryOpen(false);
    navigation?.onNavigate(page);
  }

  function openSettings() { setMobileHistoryOpen(false); navigation?.onSettings(); }

  useEffect(() => {
    const controller = new AbortController();
    getPublicSearchSources({ signal: controller.signal })
      .then((response) => {
        const enabled = new Set(Array.isArray(response.sources) ? response.sources : []);
        setSourceOptions(publicSourceOptions.map((option) => ({
          ...option,
          enabled: enabled.has(option.value),
          preview: (response.preview_sources || []).includes(option.value),
        })));
        if (localMode && enabled.has(response.default_source)) setSelectedSource(response.default_source);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("cekdata_chat_history");
      const savedSelectedId = localStorage.getItem("cekdata_chat_selected_id");

      if (saved) {
        const parsed = JSON.parse(saved);

        if (Array.isArray(parsed)) {
          const trimmed = parsed.filter(item => item && typeof item.id === 'string'
            && typeof item.question === 'string' && item.result && typeof item.result === 'object').slice(-chatHistoryLimit);
          setConversations(trimmed.map(item => ({ ...item, result: upgradeContext(localMode ? upgradeGfwSources(item.result) : item.result) })));

          if (savedSelectedId && trimmed.some((item) => item.id === savedSelectedId)) {
            setSelectedId(savedSelectedId);
          } else if (trimmed.length > 0) {
            setSelectedId(trimmed[trimmed.length - 1].id);
          } else {
            setSelectedId(null);
          }
        } else {
          setConversations([]);
          setSelectedId(null);
        }
      } else {
        setConversations([]);
        setSelectedId(null);
      }
    } catch (e) {
      console.error("Gagal membaca histori chat", e);
      setConversations([]);
      setSelectedId(null);
    } finally {
      setHistoryReady(true);
    }
  }, []);

  useEffect(() => {
    if (!historyReady) return;

    try {
      const trimmed = conversations.slice(-chatHistoryLimit);
      localStorage.setItem("cekdata_chat_history", JSON.stringify(trimmed));

      if (selectedId && trimmed.some((item) => item.id === selectedId)) {
        localStorage.setItem("cekdata_chat_selected_id", selectedId);
      } else if (trimmed.length > 0) {
        localStorage.setItem("cekdata_chat_selected_id", trimmed[trimmed.length - 1].id);
      } else {
        localStorage.removeItem("cekdata_chat_selected_id");
      }
    } catch (e) {
      console.error("Gagal menyimpan histori chat", e);
    }
  }, [conversations, selectedId, historyReady]);

  const selectedConversation = pendingConversation || conversations.find((item) => item.id === selectedId) || null;

  // A new question/history selection starts at the top. Completing the same
  // request keeps its ID, so it never pulls a reader away from their position.
  useLayoutEffect(() => {
    savedReadPosition.current = 0;
    transcript.current?.scrollTo({ top: 0, behavior: 'instant' });
  }, [selectedConversation?.id]);

  function buildCopyText(result) {
    if (!result) return "";
    const canonical = canonicalCopyText(result);
    if (canonical !== null) return canonical;

    if (result.answer) return result.answer;
    if (result.parsed?.raw_answer) return result.parsed.raw_answer;

    const sections = [];
    if (result.parsed?.temuan_data) sections.push("Temuan data\n" + result.parsed.temuan_data);
    if (result.parsed?.kesimpulan) sections.push("Kesimpulan\n" + result.parsed.kesimpulan);
    if (result.parsed?.konteks_penting) sections.push("Konteks\n" + result.parsed.konteks_penting);
    if (result.parsed?.penilaian) sections.push("Penilaian\n" + result.parsed.penilaian);
    if (result.parsed?.alasan) sections.push("Alasan\n" + result.parsed.alasan);
    if (result.parsed?.peringatan_editorial) sections.push("Peringatan editorial\n" + result.parsed.peringatan_editorial);
    if (result.parsed?.followup_prompt) sections.push(result.parsed.followup_prompt);
    if (result.parsed?.sumber) sections.push("Sumber\n" + result.parsed.sumber);

    const unduh = result.parsed?.unduh_data;
    if (unduh) {
      if (Array.isArray(unduh)) {
        sections.push("Unduh data\n" + unduh.join("\n"));
      } else {
        sections.push("Unduh data\n" + unduh);
      }
    }

    return sections.join("\n\n").trim();
  }

  async function handleCopyAnswer(conversation) {
    try {
      const text = buildCopyText(conversation?.result);
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setCopiedId(conversation.id);
      window.setTimeout(() => {
        setCopiedId((prev) => (prev === conversation.id ? null : prev));
      }, 1500);
    } catch (err) {
      console.error("Gagal menyalin jawaban", err);
      setError('Jawaban belum berhasil disalin. Gunakan pilihan salin pada browser.');
    }
  }

  const historyItems = conversations.slice(-chatHistoryLimit).reverse();

  function buildContinuationQuestion(question, previousConversation) {
    return continuationQuestion(question,
      previousConversation?.result?.answer_origin === 'registered-statistics-v1'
        || previousConversation?.result?.clarification
        ? '' : previousConversation?.question || '');
  }

  async function handleAsk() {
    const question = draft.trim();
    if (question.length < 3 || !ready || activeRequest.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    const continuationParent = localMode ? null : selectedConversation;
    const submitted = {
      id: crypto.randomUUID(), question,
      continuation_of: continuationParent?.id || "",
      continuation_of_question: continuationParent?.question || "",
      source: selectedSource, result: null, feedback: null,
      created_at: new Date().toISOString(),
    };
    setPendingConversation(submitted);
    setDraft("");
    setMobileHistoryOpen(false);

    try {
      setLoading(true);
      setError("");

      const requestQuestion = buildContinuationQuestion(question, continuationParent);
      const authToken = localMode ? '' : getStoredAuthToken();
      const data = await askQuestion({
        question: requestQuestion,
        previousQuestion: continuationParent?.source === selectedSource
          ? (continuationParent?.result?.conversation_scope?.resolved_question || continuationParent?.question || '')
          : '',
        sources: sourcesForRequest(selectedSource, sourceOptions),
        token: authToken,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;

      const newItem = { ...submitted, result: upgradeContext(data) };

      setConversations((prev) => [...prev, newItem].slice(-chatHistoryLimit));
      setSelectedId(newItem.id);
      setPendingConversation(null);
      setMobileHistoryOpen(false);
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err.message || "Terjadi kesalahan");
        setDraft(question);
        if (err.status === 401) navigation?.onSessionExpired();
      }
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setLoading(false);
      }
    }
  }

  function handleNewChat() {
    activeRequest.current?.abort();
    activeRequest.current = null;
    setLoading(false);
    setSelectedId(null);
    setPendingConversation(null);
    setDraft("");
    setError("");
    setMobileHistoryOpen(false);
  }

  function setFeedback(id, value) {
    setConversations((prev) =>
      prev.map((item) => (item.id === id ? { ...item, feedback: value } : item))
    );
  }

  function HistoryList() {
    return (
      <>
        <Button onClick={handleNewChat} style={{ width: "100%", marginBottom: 16 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <MessageSquare size={16} />
            New chat
          </span>
        </Button>
        <p
          style={{
            margin: "0 0 14px",
            color: COLORS.muted,
            fontSize: 12,
            lineHeight: 1.6,
          }}
        >
          {localMode ? `Menyimpan ${chatHistoryLimit} riwayat terakhir di browser ini. Setiap pertanyaan diperiksa secara mandiri.` : <>Menyimpan {chatHistoryLimit} riwayat terakhir. Pilih salah satu riwayat lalu kirim pertanyaan
          lanjutan untuk meneruskan konteks chat tersebut.</>}
        </p>

        {localMode && historyItems.length > 0 && <Button variant="outline" disabled={loading}
          onClick={() => { handleNewChat(); setConversations([]); }}
          style={{ width: '100%', marginBottom: 16, fontSize: 12 }}>Hapus semua riwayat</Button>}

        <div style={{ display: "grid", gap: 8 }}>
          {historyItems.length === 0 ? (
            <div
              style={{
                color: COLORS.muted,
                fontSize: 14,
                lineHeight: 1.7,
                padding: "8px 4px",
              }}
            >
              Belum ada riwayat obrolan.
            </div>
          ) : (
            historyItems.map((item) => {
              const active = item.id === selectedId;
              return (
                <button
                  key={item.id}
                  disabled={loading}
                  onClick={() => {
                    setSelectedId(item.id);
                    setPendingConversation(null);
                    setError("");
                    setMobileHistoryOpen(false);
                  }}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    border: active ? `1px solid ${COLORS.primary}` : "1px solid transparent",
                    background: active ? "#fff1f7" : "transparent",
                    borderRadius: 14,
                    padding: 12,
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 700,
                      color: COLORS.text,
                      lineHeight: 1.5,
                      marginBottom: 4,
                    }}
                  >
                    {item.question.length > 72 ? item.question.slice(0, 72) + "..." : item.question}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </>
    );
  }

  const sidebarProps = navigation ? {
    navigation: { ...navigation, onNavigate: navigate, onSettings: openSettings,
      onSignOut: () => { setMobileHistoryOpen(false); navigation.onSignOut(); } },
    items: historyItems, selectedId: pendingConversation?.id || selectedId, loading,
    onSelect: item => {
      if (loading) return;
      setSelectedId(item.id); setPendingConversation(null); setError('');
      if (sourceOptions.some(option => option.value === item.source && option.enabled)) setSelectedSource(item.source);
      navigate('chat');
    },
    onClear: () => {
      if (loading) return;
      setConversations([]); setSelectedId(null); setPendingConversation(null); setError('');
    },
  } : null;

  return (
    <div className="chat-layout">
      <div className="chat-columns" style={{ gridTemplateColumns: isMobile ? "1fr" : "280px minmax(0,1fr)" }}>
        {!isMobile && navigation && <aside className="workspace-sidebar-host" aria-label="Navigasi"><WorkspaceSidebar {...sidebarProps} /></aside>}
        {!isMobile && !navigation ? (
          <aside className="chat-history" aria-label="Riwayat pertanyaan"
            style={{
              background: COLORS.panel,
              borderRight: "1px solid rgba(17,17,17,0.08)",
              padding: 16,
            }}
          >
            <HistoryList />
          </aside>
        ) : null}

        <main className="chat-main">
          {isMobile && <div className="chat-heading"
            style={{
              borderBottom: "1px solid rgba(17,17,17,0.08)",
              padding: "14px 18px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontSize: 14,
              fontWeight: 700,
            }}
          >
            {isMobile ? (
              <button
                onClick={() => setMobileHistoryOpen(true)}
                aria-label={navigation ? "Buka navigasi" : "Buka riwayat chat"}
                style={{
                  border: "none",
                  background: "transparent",
                  width: 32,
                  height: 32,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  padding: 0,
                  color: COLORS.text,
                  flexShrink: 0,
                }}
              >
                <Menu size={22} />
              </button>
            ) : null}

          </div>}

          <div className="chat-view" hidden={navigation?.page === 'about'}>
          <div ref={transcript} className="chat-transcript" role="region" aria-label="Pertanyaan dan jawaban" tabIndex={0}
            style={{ padding: isMobile ? 16 : 24 }}>
            <div style={{ maxWidth: 860, margin: "0 auto", display: "grid", gap: 18 }}>
              {!localMode && <><BPSArchiveSearch /><BPSStatisticsSearch /></>}
              {selectedConversation ? (
                <>
                  {selectedConversation.continuation_of_question ? (
                    <div style={{ display: "flex", justifyContent: "flex-end" }}>
                      <Pill style={{ background: "#f0f4ff", color: "#2980b9" }}>
                        Lanjutan dari:{" "}
                        {selectedConversation.continuation_of_question.length > 80
                          ? selectedConversation.continuation_of_question.slice(0, 80) + "..."
                          : selectedConversation.continuation_of_question}
                      </Pill>
                    </div>
                  ) : null}

                  <div className="chat-question" style={{ display: "flex", justifyContent: "flex-end" }}>
                    <div
                      style={{
                        maxWidth: "100%",
                        width: "fit-content",
                        background: COLORS.primary,
                        color: "white",
                        borderRadius: 24,
                        padding: "16px 18px",
                        lineHeight: 1.7,
                        textAlign: "left",
                      }}
                    >
                      {selectedConversation.question}
                    </div>
                  </div>

                  {selectedConversation.result && <div className="chat-answer" style={{ display: "flex", justifyContent: "flex-start" }}>
                    <div
                      style={{
                        maxWidth: "100%",
                        background: "white",
                        borderRadius: 24,
                        padding: 20,
                        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                        textAlign: "left",
                        position: "relative",
                      }}
                    >
                      <button
                        onClick={() => handleCopyAnswer(selectedConversation)}
                        title="Salin jawaban beserta sumber"
                        style={{
                          position: "absolute",
                          top: 14,
                          right: 14,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          border: "1px solid rgba(17,17,17,0.08)",
                          background: "#fff",
                          borderRadius: 999,
                          padding: "6px 10px",
                          cursor: "pointer",
                          color: COLORS.muted,
                          fontSize: 12,
                          fontWeight: 600,
                        }}
                      >
                        {copiedId === selectedConversation?.id ? <Check size={14} /> : <Copy size={14} />}
                        {copiedId === selectedConversation?.id ? "Tersalin" : "Salin"}
                      </button>
                      {canonicalAnswerView(selectedConversation.result) ? <CanonicalAnswer result={selectedConversation.result}
                        clarificationDisabled={loading} onClarify={(question, source) => { setDraft(question); setSelectedSource(source); }} /> : <>
                      {selectedConversation.result?.parsed?.penilaian ? (
                        <div style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 10 }}>
                          <Pill
                            style={{
                              background: verdictTone(selectedConversation.result.parsed.penilaian || "").bg,
                              color: verdictTone(selectedConversation.result.parsed.penilaian || "").color,
                            }}
                          >
                            {selectedConversation.result.parsed.penilaian}
                          </Pill>
                        </div>
                      ) : null}
                      {selectedConversation.result?.parsed?.claim && <Section title="Klaim">{selectedConversation.result.parsed.claim}</Section>}
                      {selectedConversation.result?.parsed?.penilaian ? (
                        <Section title={`Penilaian: ${selectedConversation.result.parsed.penilaian}`}>
                          {selectedConversation.result.parsed.alasan}
                        </Section>
                      ) : !selectedConversation.result?.parsed?.finding_groups && (selectedConversation.result?.parsed?.jawaban_utama || selectedConversation.result?.parsed?.kesimpulan) ? (
                        <div style={{ marginTop: 16, lineHeight: 1.8 }}>{renderReadableText(selectedConversation.result.parsed.jawaban_utama || selectedConversation.result.parsed.kesimpulan)}</div>
                      ) : null}
                      {selectedConversation.result?.parsed?.finding_groups ? (<>
                        {selectedConversation.result.parsed.finding_groups.map(group => <Section key={group.source} title={`Temuan Data ${group.source}`}><>
                          {renderReadableText(group.findings.map(point => `- ${point}`).join('\n'))}
                          {group.table && <FindingsTable table={group.table} />}
                        </></Section>)}
                        {selectedConversation.result.parsed.gfw_context && <Section title="Temuan Data Global Forest Watch"><>
                          <p>{selectedConversation.result.parsed.gfw_context.summary}</p>
                          <FindingsTable table={selectedConversation.result.parsed.gfw_context.table} />
                        </></Section>}
                        {selectedConversation.result.parsed.kesimpulan && <Section title="Kesimpulan">{selectedConversation.result.parsed.kesimpulan}</Section>}
                      </>) : selectedConversation.result?.parsed?.document_answer && selectedConversation.result?.parsed?.findings_table ? (<>
                        <Section title="Temuan Data">{selectedConversation.result.parsed.temuan_data}</Section>
                        <FindingsTable table={selectedConversation.result.parsed.findings_table} />
                      </>) : selectedConversation.result?.parsed?.findings_table ? (
                        <Section title="Temuan Data"><FindingsTable table={selectedConversation.result.parsed.findings_table} /></Section>
                      ) : selectedConversation.result?.parsed?.temuan_data ? (
                        <Section title="Temuan Data">{selectedConversation.result.parsed.temuan_data}</Section>
                      ) : null}

                      {!selectedConversation.result?.parsed?.temuan_data &&
                      !selectedConversation.result?.parsed?.konteks_penting &&
                      !selectedConversation.result?.parsed?.penilaian &&
                      !selectedConversation.result?.parsed?.alasan &&
                      !selectedConversation.result?.parsed?.peringatan_editorial &&
                      !selectedConversation.result?.parsed?.sumber &&
                      selectedConversation.result?.answer ? (
                        <p
                          style={{
                            margin: 0,
                            lineHeight: 1.8,
                            color: COLORS.text,
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {selectedConversation.result.answer}
                        </p>
                      ) : null}

                      {!selectedConversation.result?.parsed?.finding_groups && selectedConversation.result?.parsed?.konteks_penting ? (
                        <Section title="Konteks">
                          {selectedConversation.result.parsed.konteks_penting}
                        </Section>
                      ) : null}

                      {selectedConversation.result?.parsed?.peringatan_editorial ? (
                        <div
                          style={{
                            marginTop: 16,
                            borderRadius: 18,
                            padding: 16,
                            background: "#fff7fb",
                            border: "1px solid rgba(239,91,156,0.25)",
                          }}
                        >
                          <div
                            style={{
                              marginBottom: 8,
                              fontSize: 13,
                              fontWeight: 700,
                              color: COLORS.primaryDark,
                              textTransform: "uppercase",
                            }}
                          >
                            Peringatan editorial
                          </div>
                          <p style={{ margin: 0, lineHeight: 1.7 }}>
                            {selectedConversation.result.parsed.peringatan_editorial}
                          </p>
                        </div>
                      ) : null}

                      {selectedConversation.result?.parsed?.followup_prompt ? (
                        <div
                          style={{
                            marginTop: 16,
                            borderRadius: 20,
                            padding: 16,
                            background: "#f0f4ff",
                            border: "1px solid rgba(41,128,185,0.25)",
                          }}
                        >
                          <div
                            style={{
                              marginBottom: 8,
                              fontSize: 13,
                              fontWeight: 700,
                              color: "#2980b9",
                              textTransform: "uppercase",
                            }}
                          >
                            Bantu kami membantu kamu
                          </div>
                          <p style={{ margin: 0, lineHeight: 1.7 }}>
                            {selectedConversation.result.parsed.followup_prompt}
                          </p>
                        </div>
                      ) : null}

                      {selectedConversation.result?.parsed?.document_answer ? (
                        <>
                          {!selectedConversation.result.parsed.finding_groups && selectedConversation.result.parsed.gfw_context && <Section title="Data Global Forest Watch"><>
                            <p>{selectedConversation.result.parsed.gfw_context.summary}</p>
                            <FindingsTable table={selectedConversation.result.parsed.gfw_context.table} />
                            <p>{selectedConversation.result.parsed.gfw_context.context}</p>
                          </></Section>}
                          <DocumentSourceFooter result={selectedConversation.result} />
                          {selectedConversation.result.parsed.gfw_context && <GfwSourceFooter result={selectedConversation.result.parsed.gfw_context} />}
                        </>
                      ) : hasMapbiomasSources(selectedConversation.result) ? (
                        <MapbiomasSourceFooter result={selectedConversation.result} />
                      ) : hasGfwSources(selectedConversation.result) ? (
                        <GfwSourceFooter result={selectedConversation.result} />
                      ) : <>
                        {selectedConversation.result?.parsed?.sumber ? (
                          <Section title="Sumber"><SourceLinks title={selectedConversation.result.parsed.sumber}
                            items={selectedConversation.result.parsed.source_items}
                            value={selectedConversation.result.parsed.link_sumber} /></Section>
                        ) : <SourceLinks value={selectedConversation.result?.parsed?.link_sumber} />}
                        {selectedConversation.result?.parsed?.unduh_data ? (
                          <DownloadLinks value={selectedConversation.result.parsed.unduh_data} />
                        ) : null}
                      </>}

                      <VerifiedSources claims={selectedConversation.result?.claims} />
                      </>}

                      <div
                        style={{
                          marginTop: 18,
                          paddingTop: 16,
                          borderTop: "1px solid rgba(17,17,17,0.08)",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: 10,
                            fontSize: 13,
                            fontWeight: 700,
                            color: COLORS.muted,
                            textTransform: "uppercase",
                            letterSpacing: 0.6,
                          }}
                        >
                          Feedback (tersimpan di perangkat ini)
                        </div>
                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                          <button
                            onClick={() => setFeedback(selectedConversation.id, "membantu")}
                            style={feedbackChipStyle(selectedConversation.feedback === "membantu")}
                          >
                            <ThumbsUp size={16} />
                            Membantu
                          </button>
                          <button
                            onClick={() => setFeedback(selectedConversation.id, "kurang tepat")}
                            style={feedbackChipStyle(selectedConversation.feedback === "kurang tepat")}
                          >
                            <CircleHelp size={16} />
                            Kurang tepat
                          </button>
                          <button
                            onClick={() => setFeedback(selectedConversation.id, "salah")}
                            style={feedbackChipStyle(selectedConversation.feedback === "salah")}
                          >
                            <ThumbsDown size={16} />
                            Salah
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>}
                </>
              ) : (
                <div
                  style={{
                    color: COLORS.muted,
                    textAlign: "center",
                    lineHeight: 1.8,
                    padding: "48px 16px",
                  }}
                >
                  {ready ? 'Tulis pertanyaan atau klaim untuk mulai memeriksa data.' : 'Buka Pengaturan API key untuk mulai menggunakan Cek Data AI.'}
                </div>
              )}

              {!ready && navigation && <button type="button" className="workspace-button" onClick={openSettings}>Buka Pengaturan API key</button>}
              {loading && <div className="chat-pending" role="status" aria-live="polite">
                <span className="chat-pending-dots" aria-hidden="true"><i /><i /><i /></span>
                <span>Sedang memeriksa data…</span>
              </div>}
              {error ? (
                <div
                  role="alert"
                  style={{
                    background: "#fff1f1",
                    color: "#9f1d1d",
                    borderRadius: 16,
                    padding: 14,
                    textAlign: "left",
                  }}
                >
                  {error}
                </div>
              ) : null}
            </div>
          </div>

          <div className="chat-composer"
            style={{
              borderTop: "1px solid rgba(17,17,17,0.08)",
              paddingTop: isMobile ? 10 : 14,
              paddingBottom: "max(10px, env(safe-area-inset-bottom))",
              paddingLeft: isMobile ? 12 : 16,
              paddingRight: isMobile ? 12 : 16,
              background: COLORS.bg,
            }}
          >
            <div
              style={{
                maxWidth: 860,
                margin: "0 auto",
              }}
            >
              {!localMode && selectedConversation ? (
                <div
                  style={{
                    marginBottom: 10,
                    color: COLORS.muted,
                    fontSize: 12,
                    lineHeight: 1.5,
                  }}
                >
                  <>Melanjutkan dari chat terpilih. Klik <strong>New chat</strong> bila ingin memulai konteks baru.</>
                </div>
              ) : null}

              <div style={{ position: "relative" }}>
                <textarea
                  aria-label="Pertanyaan atau klaim"
                  maxLength={1600}
                  disabled={loading || !ready}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      handleAsk();
                    }
                  }}
                  placeholder="Tulis pertanyaan atau klaim yang ingin diperiksa..."
                  style={{
                    fontFamily: 'inherit',
                    width: "100%",
                    minHeight: 82,
                    maxHeight: 180,
                    borderRadius: 22,
                    border: "1px solid rgba(17,17,17,0.08)",
                    background: "white",
                    padding: "14px 16px 48px",
                    fontSize: 16,
                    lineHeight: 1.6,
                    resize: "vertical",
                    boxSizing: "border-box",
                    color: COLORS.text,
                    boxShadow: "0 8px 24px rgba(17,17,17,0.06)",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: 10,
                    right: 10,
                    bottom: 9,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 10,
                    pointerEvents: "none",
                  }}
                >
                  <SourcePicker value={selectedSource} options={sourceOptions} disabled={loading}
                    onChange={value => { setSelectedSource(value); setSelectedId(null); setPendingConversation(null); setError(''); }} />
                  <Button onClick={handleAsk} disabled={!ready || loading || draft.trim().length < 3} style={{ height: 36, minHeight: 36, padding: "8px 14px", pointerEvents: "auto" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <Send size={15} />
                      {loading ? "Memeriksa..." : "Kirim"}
                    </span>
                  </Button>
                </div>
              </div>

              {sourceOptions.some(option => option.value === selectedSource && option.preview) &&
                <p role="status" style={{ fontSize: 12, textAlign: 'center', color: COLORS.muted }}>
                  Uji coba Environment: cakupan dan akurasi pencarian masih dievaluasi. Periksa sumber pada setiap hasil.
                </p>}
              <p
                style={{
                  marginTop: 10,
                  marginBottom: 0,
                  textAlign: "center",
                  fontSize: 11,
                  lineHeight: 1.5,
                  color: COLORS.muted,
                }}
              >
                Periksa dulu sumber sebelum menggunakan hasil.
              </p>
            </div>
          </div>
          </div>
          {navigation?.page === 'about' && <section className="workspace-about-page" aria-label="About Cek Data AI">
            <button className="workspace-button workspace-back" onClick={() => navigate('chat')}><ArrowLeft size={17} />Back to chat</button>
            <AboutPage />
          </section>}
        </main>
      </div>

      {navigation && <WorkspaceDialog open={isMobile && mobileHistoryOpen} onClose={() => setMobileHistoryOpen(false)} title="Navigasi" className="workspace-drawer">
        <WorkspaceSidebar {...sidebarProps} />
      </WorkspaceDialog>}
      {!navigation && isMobile && mobileHistoryOpen ? (
        <>
          <div
            onClick={() => setMobileHistoryOpen(false)}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.25)",
              zIndex: 40,
            }}
          />
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              bottom: 0,
              width: "80%",
              maxWidth: 320,
              background: COLORS.panel,
              borderRight: "1px solid rgba(17,17,17,0.08)",
              padding: 16,
              zIndex: 50,
              overflowY: "auto",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 700 }}>Riwayat</div>
              <button
                onClick={() => setMobileHistoryOpen(false)}
                style={{
                  border: "none",
                  background: "transparent",
                  width: 32,
                  height: 32,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  padding: 0,
                  color: COLORS.text,
                }}
              >
                <X size={20} />
              </button>
            </div>
            <HistoryList />
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function App() {
  const adminLoginPath = "/admin-login";
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    try {
      return localStorage.getItem("cekdata_logged_in") === "true";
    } catch (e) {
      console.error("Gagal membaca status login", e);
      return false;
    }
  });

  const [userRole, setUserRole] = useState(() => getStoredRole());
  const isAdmin = userRole === "admin";

  const [page, setPage] = useState(() => {
    try {
      if (window.location.pathname.replace(/\/$/, "") === adminLoginPath) {
        return "admin-signin";
      }

      const savedLogin = localStorage.getItem("cekdata_logged_in") === "true";
      const savedPage = localStorage.getItem("cekdata_page");
      const savedRole = localStorage.getItem("cekdata_role") || "";

      if (savedLogin) {
        if (savedPage && ["home", "about", "signin", "admin-signin", "chat", "admin"].includes(savedPage)) {
          if (savedPage === "admin" && savedRole !== "admin") {
            return "chat";
          }
          return savedPage;
        }
        return savedRole === "admin" ? "admin" : "chat";
      }

      if (savedPage && ["home", "about", "signin", "admin-signin"].includes(savedPage)) {
        return savedPage;
      }

      return "home";
    } catch (e) {
      console.error("Gagal membaca status halaman", e);
      return "home";
    }
  });

  useEffect(() => {
    try {
      if ((page === "chat" || page === "admin") && !isLoggedIn) {
        localStorage.setItem("cekdata_page", "signin");
      } else if (page === "admin" && !isAdmin) {
        localStorage.setItem("cekdata_page", "chat");
      } else {
        localStorage.setItem("cekdata_page", page);
      }
    } catch (e) {
      console.error("Gagal menyimpan status halaman", e);
    }
  }, [page, isLoggedIn, isAdmin]);

  useEffect(() => {
    const targetPath = page === "admin-signin" ? adminLoginPath : "/";
    if (window.location.pathname !== targetPath) {
      window.history.replaceState({}, "", targetPath);
    }
  }, [page]);

  useEffect(() => {
    try {
      localStorage.setItem("cekdata_logged_in", isLoggedIn ? "true" : "false");
    } catch (e) {
      console.error("Gagal menyimpan status login", e);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    try {
      if (userRole) {
        localStorage.setItem("cekdata_role", userRole);
      } else {
        localStorage.removeItem("cekdata_role");
      }
    } catch (e) {
      console.error("Gagal menyimpan role user", e);
    }
  }, [userRole]);

  function handleSignOut() {
    setIsLoggedIn(false);
    setUserRole("");
    localStorage.removeItem("cekdata_logged_in");
    localStorage.removeItem("cekdata_auth_token");
    localStorage.removeItem("cekdata_role");
    localStorage.setItem("cekdata_page", "home");
    setPage("home");
  }

  function handleAuthExpired() {
    setIsLoggedIn(false);
    setUserRole("");
    localStorage.removeItem("cekdata_logged_in");
    localStorage.removeItem("cekdata_auth_token");
    localStorage.removeItem("cekdata_role");
    localStorage.setItem("cekdata_page", "admin-signin");
    setPage("admin-signin");
  }

  return (
    <div className={page === "chat" && isLoggedIn ? "chat-app-shell" : undefined}
      style={{
        minHeight: "100vh",
        background: COLORS.bg,
        color: COLORS.text,
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Header page={page} setPage={setPage} isLoggedIn={isLoggedIn} isAdmin={isAdmin} handleSignOut={handleSignOut} />

      <div className={page === "chat" && isLoggedIn ? "chat-app-content" : undefined} style={{ flex: 1 }}>
        {page === "home" ? <HomePage setPage={setPage} /> : null}
        {page === "about" ? <AboutPage /> : null}
        {page === "signin" ? <UserLoginPage setPage={setPage} setIsLoggedIn={setIsLoggedIn} setUserRole={setUserRole} /> : null}
        {page === "admin-signin" ? <AdminLoginPage setPage={setPage} setIsLoggedIn={setIsLoggedIn} setUserRole={setUserRole} /> : null}
        {page === "chat" ? (
          isLoggedIn ? (
            <ChatPage />
          ) : (
            <UserLoginPage setPage={setPage} setIsLoggedIn={setIsLoggedIn} setUserRole={setUserRole} />
          )
        ) : null}
        {page === "admin" ? (
          isLoggedIn ? (
            <AdminPage isAdmin={isAdmin} onAuthExpired={handleAuthExpired} />
          ) : (
            <AdminLoginPage setPage={setPage} setIsLoggedIn={setIsLoggedIn} setUserRole={setUserRole} />
          )
        ) : null}
      </div>

      {page !== "chat" && page !== "admin" ? (
        <HomeFooter />
      ) : null}
    </div>
  );
}
