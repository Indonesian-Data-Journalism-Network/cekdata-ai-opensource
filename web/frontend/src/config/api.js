// Browser requests remain same-origin in both local and public deployments.
export const API_BASE = "/api";
export const DEMO_LOGIN_ENABLED = false;
export const PUBLIC_MODE = import.meta.env?.VITE_PUBLIC_MODE === "true";
