export const API = process.env.NEXT_PUBLIC_API_BASE || '';
const KEY = 'vu_token';
export const auth = {
  token: () => (typeof window === 'undefined' ? null : window.localStorage.getItem(KEY)),
  set: (t: string, user: string) => { window.localStorage.setItem(KEY, t); window.localStorage.setItem('vu_user', user); },
  user: () => (typeof window === 'undefined' ? null : window.localStorage.getItem('vu_user')),
  logout: () => { window.localStorage.removeItem(KEY); window.localStorage.removeItem('vu_user'); window.location.href = '/login'; },
};
async function req(path: string, init?: RequestInit) {
  const t = auth.token();
  const r = await fetch(API + path, { ...init, headers: { 'Content-Type': 'application/json', ...(t ? { Authorization: `Bearer ${t}` } : {}), ...(init?.headers || {}) } });
  const body = await r.json().catch(() => ({}));
  if (r.status === 401 && !path.startsWith('/api/auth/')) { auth.logout(); throw new Error('Please log in.'); }
  if (!r.ok) {
    const d = body?.detail;
    throw new Error(Array.isArray(d) ? d.map((x: any) => x.msg).join('; ') : d || `Request failed (${r.status})`);
  }
  return body;
}
export const api = {
  login: (username: string, password: string) => req('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  register: (username: string, password: string) => req('/api/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
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
  applyVariant: (id: string, variant_id: string) => req(`/api/analyses/${id}/variants`, { method: 'POST', body: JSON.stringify({ variant_id }) }),
  removeVariant: (id: string, vid: string) => req(`/api/analyses/${id}/variants/${encodeURIComponent(vid)}`, { method: 'DELETE' }),
  susQuestions: () => req('/api/sus-questions'),
};
