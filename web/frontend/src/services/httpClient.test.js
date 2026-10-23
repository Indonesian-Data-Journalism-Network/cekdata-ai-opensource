import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, requestJson } from "./httpClient.js";

function response({ ok = true, status = 200, payload = {}, contentType = "application/json" }) {
  return {
    ok,
    status,
    headers: { get: () => contentType },
    json: async () => payload,
    text: async () => String(payload),
  };
}

test("requestJson centralizes auth and JSON serialization", async () => {
  let captured;
  const payload = await requestJson(
    "/ask",
    { method: "POST", body: { question: "data" }, token: "secret" },
    async (url, options) => {
      captured = { url, options };
      return response({ payload: { answer: "ok" } });
    },
  );

  assert.equal(payload.answer, "ok");
  assert.equal(captured.options.headers.Authorization, "Bearer secret");
  assert.equal(captured.options.body, JSON.stringify({ question: "data" }));
  assert.match(captured.url, /\/ask$/);
});

test("requestJson returns a typed API error without losing status", async () => {
  await assert.rejects(
    requestJson(
      "/ask",
      {},
      async () => response({ ok: false, status: 422, payload: { detail: "invalid" } }),
    ),
    (error) => error instanceof ApiError && error.status === 422 && error.message === "invalid",
  );
});
