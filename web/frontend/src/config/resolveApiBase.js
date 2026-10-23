export function resolveApiBase({ envApiBase, defaultApiBase }) {
  const configuredBase = String(envApiBase || "").trim().replace(/\/+$/, "");
  if (configuredBase) return configuredBase;

  return String(defaultApiBase || "").trim().replace(/\/+$/, "");
}
