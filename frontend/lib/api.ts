export const API = process.env.NEXT_PUBLIC_API_BASE || '';
async function req(path: string, init?: RequestInit) {
  const r = await fetch(API + path, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = body?.detail;
    throw new Error(Array.isArray(d) ? d.map((x: any) => x.msg).join('; ') : d || `Request failed (${r.status})`);
  }
  return body;
}
export const api = {
  meta: () => req('/api/meta'),
  list: () => req('/api/analyses'),
  create: (intake: any) => req('/api/analyses', { method: 'POST', body: JSON.stringify(intake) }),
  get: (id: string) => req(`/api/analyses/${id}`),
  addExperiment: (id: string, e: any) => req(`/api/analyses/${id}/experiments`, { method: 'POST', body: JSON.stringify(e) }),
  removeExperiment: (id: string, i: number) => req(`/api/analyses/${id}/experiments/${i}`, { method: 'DELETE' }),
  whatif: (id: string, overrides: any, settings: any) => req(`/api/analyses/${id}/whatif`, { method: 'POST', body: JSON.stringify({ overrides, settings }) }),
  apply: (id: string, overrides: any, settings: any) => req(`/api/analyses/${id}/apply`, { method: 'POST', body: JSON.stringify({ overrides, settings }) }),
  reset: (id: string) => req(`/api/analyses/${id}/reset`, { method: 'POST' }),
  outcome: (id: string, o: any) => req(`/api/analyses/${id}/outcome`, { method: 'POST', body: JSON.stringify(o) }),
  calibration: () => req('/api/calibration'),
};
