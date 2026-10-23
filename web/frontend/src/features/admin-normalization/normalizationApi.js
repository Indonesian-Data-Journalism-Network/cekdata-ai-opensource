import { requestJson } from "../../services/httpClient.js";

export function previewBatch({ formData, token, signal }) {
  return requestJson("/admin/batches/preview", {
    method: "POST",
    body: formData,
    token,
    signal,
  });
}

export function listNormalizationReviews({ token, limit = 100, signal }) {
  const boundedLimit = Math.max(1, Math.min(Number(limit) || 100, 500));
  return requestJson(`/admin/normalization/reviews?limit=${boundedLimit}`, { token, signal });
}
