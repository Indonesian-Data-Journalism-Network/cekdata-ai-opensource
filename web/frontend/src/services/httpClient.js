import { API_BASE } from "../config/api.js";

export class ApiError extends Error {
  constructor(message, { status = 0, payload = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function requestJson(
  path,
  { method = "GET", body, token = "", signal, headers = {} } = {},
  fetchImpl = fetch,
) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const requestHeaders = { Accept: "application/json", ...headers };
  if (body !== undefined && !(body instanceof FormData)) {
    requestHeaders["Content-Type"] = requestHeaders["Content-Type"] || "application/json";
  }
  if (token) requestHeaders.Authorization = `Bearer ${token}`;
  const response = await fetchImpl(`${API_BASE}${normalizedPath}`, {
    method,
    headers: requestHeaders,
    body:
      body === undefined || body instanceof FormData || typeof body === "string"
        ? body
        : JSON.stringify(body),
    signal,
  });
  const contentType = response.headers?.get?.("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" ? payload.detail || payload.error || payload.message : "";
    throw new ApiError(detail || `HTTP ${response.status}`, { status: response.status, payload });
  }
  return payload;
}
