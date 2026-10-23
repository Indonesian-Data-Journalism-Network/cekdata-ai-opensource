import assert from "node:assert/strict";
import test from "node:test";

import { resolveApiBase } from "./resolveApiBase.js";

const defaults = {
  defaultApiBase: "https://staging.example.test",
};

test("explicit staging URL overrides the default", () => {
  const result = resolveApiBase({
    ...defaults,
    envApiBase: "https://staging.example.test",
  });

  assert.equal(result, "https://staging.example.test");
});

test("configured URL is normalized without trailing slashes", () => {
  const result = resolveApiBase({
    ...defaults,
    envApiBase: " https://staging.example.test/// ",
  });

  assert.equal(result, "https://staging.example.test");
});

test("Railway staging is used when no explicit URL exists", () => {
  const result = resolveApiBase({...defaults, envApiBase: ""});

  assert.equal(result, "https://staging.example.test");
});

test("default URL is normalized", () => {
  const result = resolveApiBase({envApiBase: "", defaultApiBase: "https://default.test///"});

  assert.equal(result, "https://default.test");
});
