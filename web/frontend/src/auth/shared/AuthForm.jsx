import { useState } from "react";
import { motion } from "framer-motion";

import { API_BASE } from "../../config/api";
import { Button, Card, COLORS, inputStyle } from "../../ui/ui";

export default function AuthForm({
  allowSignup = false,
  allowForgotPassword = false,
  expectedRole = null,
  setPage,
  setIsLoggedIn,
  setUserRole,
  subtitle = "Masuk ke akun yang sudah terdaftar untuk memakai Cek Data AI.",
  signupSubtitle = "Buat akun user baru untuk langsung masuk dan mencoba chat.",
  title = "Sign In",
  demoCredentials = null,
}) {
  const [mode, setMode] = useState("signin");
  const [name, setName] = useState("");
  const [mediaOrganization, setMediaOrganization] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  function applyDemoCredentials() {
    if (!demoCredentials) return;
    setMode("signin");
    setEmail(demoCredentials.email);
    setName("");
    setMediaOrganization("");
    setPhone("");
    setPassword(demoCredentials.password);
    setConfirmPassword("");
    setError("");
  }

  async function handleAuth() {
    if (!email.trim() || !password.trim()) {
      setError("Masukkan email dan password.");
      return;
    }
    if (mode === "signup") {
      if (password.trim().length < 8) {
        setError("Password minimal 8 karakter.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Konfirmasi password belum sama.");
        return;
      }
      if (!name.trim() || !mediaOrganization.trim() || !phone.trim()) {
        setError("Nama, Media/Organisasi, dan Nomor handphone wajib diisi.");
        return;
      }
    }
    try {
      setLoading(true);
      setError("");
      setNotice("");
      const endpoint = mode === "signup" ? "/signup" : "/login";
      const res = await fetch(API_BASE + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          media_organization: mediaOrganization.trim(),
          email: email.trim(),
          phone: phone.trim(),
          password,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || (mode === "signup" ? "Pendaftaran gagal." : "Email atau password salah."));
        return;
      }
      if (mode === "signup" && data.status === "pending_confirmation") {
        setNotice(`${data.message || "Pendaftaran diterima. Silakan cek email/WhatsApp untuk konfirmasi."}${data.confirmation_link ? ` Link demo: ${data.confirmation_link}` : ""}`);
        setMode("signin");
        setPassword("");
        setConfirmPassword("");
        return;
      }
      const role = data.role || "user";
      if (expectedRole && role !== expectedRole) {
        setError(expectedRole === "admin" ? "Akun ini bukan akun admin." : "Akun ini bukan akun user.");
        return;
      }
      try { localStorage.setItem("cekdata_auth_token", data.token || ""); } catch {}
      try { localStorage.setItem("cekdata_role", role); } catch {}
      setIsLoggedIn(true);
      setUserRole(role);
      localStorage.setItem("cekdata_logged_in", "true");
      setPage(role === "admin" ? "admin" : "chat");
    } catch (e) {
      setError("Gagal menghubungi server. Pastikan backend berjalan.");
    } finally {
      setLoading(false);
    }
  }

  async function handleForgotPassword() {
    if (!email.trim()) {
      setError("Masukkan email user yang terdaftar.");
      return;
    }
    try {
      setLoading(true);
      setError("");
      setNotice("");
      const res = await fetch(API_BASE + "/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || "Gagal mengirim link reset password.");
        return;
      }
      const emailDelivery = data?.delivery?.email || {};
      if (emailDelivery.status && emailDelivery.status !== "sent") {
        setError(
          `Email reset belum terkirim (${emailDelivery.error || emailDelivery.reason || emailDelivery.status}).`
        );
        return;
      }
      setNotice(data?.message || "Link reset password sudah dikirim ke email terdaftar.");
      setMode("signin");
      setPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError("Gagal menghubungi server. Pastikan backend berjalan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        maxWidth: 1280,
        margin: "0 auto",
        padding: "40px 24px",
        minHeight: "calc(100vh - 120px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{ width: "100%", maxWidth: 460 }}
      >
        <Card>
          <div style={{ padding: 32, textAlign: "left" }}>
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ marginTop: 8, fontSize: 28, fontWeight: 700 }}>
                {mode === "signup" ? "Sign Up" : mode === "forgot" ? "Lupa Password" : title}
              </div>
              <p style={{ marginTop: 8, color: COLORS.muted, lineHeight: 1.7 }}>
                {mode === "signup"
                  ? signupSubtitle
                  : mode === "forgot"
                    ? "Masukkan email user terdaftar. Sistem akan mengirim link reset password ke email tersebut."
                    : subtitle}
              </p>
            </div>

            {allowSignup ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
                <Button
                  variant={mode === "signin" ? "solid" : "outline"}
                  onClick={() => {
                    setMode("signin");
                    setError("");
                    setNotice("");
                  }}
                  style={{ width: "100%" }}
                >
                  Sign In
                </Button>
                <Button
                  variant={mode === "signup" ? "solid" : "outline"}
                  onClick={() => {
                    setMode("signup");
                    setError("");
                    setNotice("");
                  }}
                  style={{ width: "100%" }}
                >
                  Sign Up
                </Button>
              </div>
            ) : null}

            {demoCredentials && mode === "signin" ? (
              <div
                style={{
                  border: "1px dashed rgba(17,17,17,0.18)",
                  borderRadius: 18,
                  padding: 14,
                  marginBottom: 14,
                  background: "#fffafc",
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 800, color: COLORS.primaryDark, marginBottom: 6 }}>
                  Akun demo
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.6, color: COLORS.muted, marginBottom: 10 }}>
                  Email: <strong>{demoCredentials.email}</strong><br />
                  Password: <strong>{demoCredentials.password}</strong>
                </div>
                <Button variant="outline" onClick={applyDemoCredentials} style={{ width: "100%" }}>
                  Isi akun demo
                </Button>
              </div>
            ) : null}

            <div style={{ display: "grid", gap: 14 }}>
              {mode === "signup" ? (
                <>
                  <input
                    placeholder="Nama"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    style={inputStyle}
                  />
                  <input
                    placeholder="Media/Organisasi"
                    value={mediaOrganization}
                    onChange={(e) => setMediaOrganization(e.target.value)}
                    style={inputStyle}
                  />
                </>
              ) : null}
              <input
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={inputStyle}
              />
              {mode === "signup" ? (
                <input
                  placeholder="Nomor handphone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  style={inputStyle}
                />
              ) : null}
              {mode !== "forgot" ? (
                <input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={inputStyle}
                />
              ) : null}
              {mode === "signup" ? (
                <input
                  type="password"
                  placeholder="Konfirmasi password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  style={inputStyle}
                />
              ) : null}
              <Button
                onClick={mode === "forgot" ? handleForgotPassword : handleAuth}
                style={{ width: "100%" }}
              >
                {loading
                  ? (mode === "signup" ? "Membuat akun..." : mode === "forgot" ? "Mengirim link..." : "Masuk...")
                  : (mode === "signup" ? "Buat akun" : mode === "forgot" ? "Kirim Link Reset" : "Masuk")}
              </Button>
              {allowForgotPassword && mode === "signin" ? (
                <button
                  type="button"
                  onClick={() => {
                    setMode("forgot");
                    setError("");
                    setNotice("");
                    setPassword("");
                    setConfirmPassword("");
                  }}
                  style={{
                    border: 0,
                    background: "transparent",
                    color: COLORS.primaryDark,
                    fontWeight: 800,
                    cursor: "pointer",
                    textAlign: "center",
                  }}
                >
                  Lupa password?
                </button>
              ) : null}
              {mode === "forgot" ? (
                <Button
                  variant="outline"
                  onClick={() => {
                    setMode("signin");
                    setError("");
                    setNotice("");
                  }}
                  style={{ width: "100%" }}
                >
                  Kembali ke Sign In
                </Button>
              ) : null}
            </div>

            {error ? (
              <p
                style={{
                  marginTop: 14,
                  marginBottom: 0,
                  color: "#b42318",
                  lineHeight: 1.6,
                  textAlign: "center",
                  fontSize: 14,
                }}
              >
                {error}
              </p>
            ) : null}

            {notice ? (
              <p
                style={{
                  marginTop: 14,
                  marginBottom: 0,
                  color: "#166534",
                  lineHeight: 1.6,
                  textAlign: "center",
                  fontSize: 14,
                }}
              >
                {notice}
              </p>
            ) : null}

            {allowSignup ? (
              <p
                style={{
                  marginTop: 16,
                  marginBottom: 0,
                  color: COLORS.muted,
                  lineHeight: 1.7,
                  textAlign: "center",
                }}
              >
                {mode === "signup"
                  ? "Setelah form dikirim, kamu akan menerima link konfirmasi via email dan WhatsApp. Akun trial aktif setelah link diklik dan dibatasi 3 chat."
                  : mode === "forgot"
                    ? "Link reset hanya dikirim jika email sudah terdaftar sebagai user."
                    : "Belum punya akun? Pindah ke Sign Up."}
              </p>
            ) : null}
          </div>
        </Card>
      </motion.div>
    </div>
  );
}
