export const publicSourceOptions = Object.freeze([
  {
    value: "bps",
    label: "General",
    enabled: true,
  },
  {
    value: "environment",
    label: "Environment",
    enabled: false,
  },
  {
    value: "legal",
    label: "Legal",
    enabled: false,
  },
]);

export function sourcesForRequest(selectedSource, options = publicSourceOptions) {
  const option = options.find((item) => item.value === selectedSource);
  if (!option || !option.enabled) throw new Error('Sumber utama belum tersedia. Pilih sumber yang tersedia.');
  return [option.value];
}
