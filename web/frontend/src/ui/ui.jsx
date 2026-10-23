export const COLORS = {
  bg: "#efebe7",
  panel: "#f7f3ef",
  panelSoft: "#fbf8f5",
  primary: "#ef5b9c",
  primaryDark: "#db4e8c",
  text: "#111111",
  border: "#1d1d1d",
  muted: "#6f6a67",
};

export function Button({ children, onClick, variant = "solid", style = {}, disabled = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        border: variant === "outline" ? "1px solid rgba(17,17,17,0.12)" : "none",
        background: disabled ? "#d7d2ce" : variant === "outline" ? "white" : COLORS.primary,
        color: variant === "outline" ? COLORS.text : "white",
        borderRadius: 16,
        padding: "12px 18px",
        fontSize: 15,
        fontWeight: 700,
        cursor: disabled ? "not-allowed" : "pointer",
        ...style,
      }}
    >
      {children}
    </button>
  );
}

export function Card({ children, style = {} }) {
  return (
    <div
      style={{
        background: COLORS.panel,
        borderRadius: 28,
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function Pill({ children, style = {} }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: 9999,
        padding: "6px 12px",
        fontSize: 13,
        fontWeight: 700,
        ...style,
      }}
    >
      {children}
    </span>
  );
}

export const pStyle = {
  marginTop: 0,
  marginBottom: 16,
  color: COLORS.text,
  lineHeight: 1.8,
};

export const inputStyle = {
  width: "100%",
  border: "none",
  borderRadius: 16,
  background: "white",
  padding: "14px 16px",
  fontSize: 15,
  boxSizing: "border-box",
  color: COLORS.text,
};
