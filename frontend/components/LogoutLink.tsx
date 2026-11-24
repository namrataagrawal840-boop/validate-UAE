'use client';
import { useEffect, useState } from 'react';
import { auth } from '@/lib/api';

/** Shows who is signed in and a log-out link; sends visitors without a token to the login page. */
export function LogoutLink() {
  const [user, setUser] = useState<string | null>(null);
  useEffect(() => {
    if (!auth.token()) { window.location.href = '/login'; return; }
    setUser(auth.user());
  }, []);
  if (!user) return null;
  return <span style={{ marginLeft: 'auto', fontSize: 14, color: 'var(--muted)' }}>{user} · <a href="#" onClick={(e) => { e.preventDefault(); auth.logout(); }}>Log out</a></span>;
}
