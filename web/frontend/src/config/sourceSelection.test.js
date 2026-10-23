import test from "node:test";
import assert from "node:assert/strict";

import { publicSourceOptions, sourcesForRequest } from "./sourceSelection.js";

test("only explicit primary sources are offered", () => {
  assert.deepEqual(publicSourceOptions.map(option => option.value).sort(), ['bps', 'environment', 'legal']);
  assert.throws(() => sourcesForRequest("auto"));
});

test("available BPS selection is sent to the API", () => {
  assert.deepEqual(sourcesForRequest("bps"), ["bps"]);
});

test("sources that are not public cannot be sent by the client", () => {
  assert.throws(() => sourcesForRequest("environment"));
  assert.throws(() => sourcesForRequest("legal"));
  assert.equal(publicSourceOptions.find((item) => item.value === "environment").enabled, false);
});

test("backend-approved runtime options can enable a gated source", () => {
  const runtimeOptions = publicSourceOptions.map((item) => ({
    ...item,
    enabled: item.value === "auto" || item.value === "environment",
  }));
  assert.deepEqual(sourcesForRequest("environment", runtimeOptions), ["environment"]);
  assert.throws(() => sourcesForRequest("bps", runtimeOptions));
});
