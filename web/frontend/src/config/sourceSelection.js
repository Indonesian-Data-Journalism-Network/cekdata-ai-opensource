export const publicSourceOptions = Object.freeze([
  {
    value: "bps",
    label: "BPS",
    description: "Statistik resmi Badan Pusat Statistik.",
    enabled: true,
  },
  {
    value: "environment",
    label: "Environment",
    description: "Data iklim, hutan, dan lingkungan dari sumber yang tersedia.",
    enabled: false,
  },
  {
    value: "legal",
    label: "Legal",
    description: "Peraturan dan dokumen hukum. Akses sedang disiapkan.",
    enabled: false,
  },
]);

export function sourcesForRequest(selectedSource, options = publicSourceOptions) {
  const option = options.find((item) => item.value === selectedSource);
  if (!option || !option.enabled) throw new Error('Sumber utama belum tersedia. Pilih sumber yang tersedia.');
  return [option.value];
}
