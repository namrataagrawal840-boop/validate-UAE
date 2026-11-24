export const aed = (v: number | null | undefined) => {
  if (v == null || !isFinite(v)) return '–';
  const a = Math.abs(v);
  const s = a >= 1e9 ? (a / 1e9).toFixed(1) + 'B' : a >= 1e6 ? (a / 1e6).toFixed(a >= 1e7 ? 1 : 2) + 'M' : a >= 1e4 ? Math.round(a / 1e3) + 'k' : Math.round(a).toLocaleString('en');
  return (v < 0 ? '−' : '') + 'AED ' + s;
};
export const pct = (v: number | null | undefined, d = 0) => (v == null || !isFinite(v) ? '–' : (v * 100).toFixed(d) + '%');
export const num = (v: number | null | undefined, d = 0) => (v == null || !isFinite(v) ? '–' : v.toLocaleString('en', { maximumFractionDigits: d, minimumFractionDigits: d }));
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const monthLabel = (i: number) => `${MON[i % 12]} ${String(2027 + Math.floor(i / 12)).slice(2)}`;
export const monthsText = (m: number | null | undefined) => (m == null ? 'Not within the horizon' : `Month ${Math.round(m)} (${MON[(Math.round(m) - 1) % 12]} ${2027 + Math.floor((Math.round(m) - 1) / 12)})`);
export const safeUrl = (u?: string) => (u && /^https?:\/\//.test(u) ? u : undefined);
export const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return u; } };
export const LABEL: Record<string, string> = { measured: 'Measured', benchmarked: 'Benchmarked (your source)', web: 'Benchmarked (web source)', founder: 'Founder input', ai: 'AI estimate', critic: 'AI estimate, cut by critic', derived: 'Derived by the model', prior: 'Category prior' };
export const labelTone = (l: string) => (l === 'measured' ? 'good' : l === 'web' || l === 'benchmarked' ? 'info' : l === 'founder' ? 'neutral' : 'warn');
