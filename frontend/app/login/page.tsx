'use client';
import { useState } from 'react';
import { api, auth } from '@/lib/api';

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [u, setU] = useState(''); const [p, setP] = useState(''); const [p2, setP2] = useState('');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr('');
    if (mode === 'register' && p !== p2) { setErr('The two passwords do not match.'); return; }
    setBusy(true);
    try {
      const r = mode === 'login' ? await api.login(u, p) : await api.register(u, p);
      auth.set(r.token, r.username); window.location.href = '/';
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <main className="container" style={{ maxWidth: 440, paddingTop: 64 }}>
      <a className="brand" href="/"><i />ValidateUAE</a>
      <div className="card" style={{ marginTop: 20 }}>
        <h2>{mode === 'login' ? 'Log in' : 'Create an account'}</h2>
        <p className="muted">Your projects are private to your account.</p>
        <form onSubmit={submit} style={{ display: 'grid', gap: 12 }}>
          <label>Username<input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" required minLength={3} /></label>
          <label>Password<input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 8 : 1} /></label>
          {mode === 'register' && <label>Repeat the password<input type="password" value={p2} onChange={(e) => setP2(e.target.value)} required /></label>}
          {err && <div className="callout" role="alert">{err}</div>}
          <button className="btn" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}</button>
        </form>
        <p className="muted" style={{ marginTop: 12 }}>
          {mode === 'login' ? <>No account? <a href="#" onClick={(e) => { e.preventDefault(); setMode('register'); }}>Create one</a></> :
            <>Have an account? <a href="#" onClick={(e) => { e.preventDefault(); setMode('login'); }}>Log in</a></>}
        </p>
      </div>
    </main>
  );
}
