'use client';
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Report from '@/components/Report';

function Inner() {
  const id = useSearchParams().get('id');
  if (!id) return <main className="container page"><p>No analysis selected. <a href="/">Start one</a>.</p></main>;
  return <Report id={id} />;
}
export default function Page() { return <Suspense fallback={<main className="container page"><p className="muted">Loading…</p></main>}><Inner /></Suspense>; }
