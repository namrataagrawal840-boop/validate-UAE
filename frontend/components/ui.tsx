'use client';
import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { LABEL, labelTone, safeUrl, host } from '@/lib/fmt';

export const Badge = ({ tone = 'neutral', children }: { tone?: string; children: ReactNode }) => <span className={`badge t-${tone}`}>{children}</span>;
export const LabelBadge = ({ label }: { label: string }) => <Badge tone={labelTone(label)}>{LABEL[label] || label}</Badge>;
export const Stat = ({ label, value, sub, math }: { label: string; value: ReactNode; sub?: ReactNode; math?: string }) => (
  <div className="stat"><div className="l">{label}</div><div className="v">{value}</div>{sub && <div className="tiny muted">{sub}</div>}{math && <MathButton k={math} />}</div>
);
export const HBar = ({ name, frac, value, color }: { name: ReactNode; frac: number; value: ReactNode; color?: string }) => (
  <div className="hbar"><div>{name}</div><div className="bar"><i style={{ width: `${Math.max(1.5, Math.min(100, frac * 100))}%`, background: color }} /></div><div className="num">{value}</div></div>
);
export const scoreTone = (s: number | null) => (s == null ? 'neutral' : s >= 65 ? 'good' : s >= 45 ? 'warn' : 'bad');
export const scoreWord = (s: number | null) => (s == null ? 'Not assessed' : s >= 65 ? 'Strong' : s >= 45 ? 'Uncertain' : 'Weak');
export const Source = ({ url }: { url?: string }) => { const u = safeUrl(url); return u ? <a href={u} target="_blank" rel="noopener noreferrer" className="tiny">{host(u)} ↗</a> : null; };

type MathInfo = { title: string; plain: string; formula?: string; inputs?: [string, string, string?][] };
const MathCtx = createContext<{ open: (k: string) => void }>({ open: () => {} });
export const useMath = () => useContext(MathCtx);
export function MathProvider({ explain, children }: { explain: (k: string) => MathInfo | null; children: ReactNode }) {
  const [key, setKey] = useState<string | null>(null);
  useEffect(() => { const f = (e: KeyboardEvent) => e.key === 'Escape' && setKey(null); addEventListener('keydown', f); return () => removeEventListener('keydown', f); }, []);
  const m = key ? explain(key) : null;
  return (
    <MathCtx.Provider value={{ open: setKey }}>
      {children}
      {m && (
        <div className="drawer" onClick={() => setKey(null)} role="dialog" aria-modal="true" aria-label={m.title}>
          <div className="sheet" onClick={e => e.stopPropagation()}>
            <div className="row between"><h2 style={{ margin: 0 }}>{m.title}</h2><button onClick={() => setKey(null)} autoFocus>Close</button></div>
            <h3 style={{ marginTop: 18 }}>In plain words</h3><p>{m.plain}</p>
            {m.formula && <><h3>The math</h3><div className="formula">{m.formula}</div></>}
            {m.inputs?.length ? <><h3 style={{ marginTop: 18 }}>Inputs</h3><table><tbody>{m.inputs.map(([a, b, c], i) => <tr key={i}><td>{a}</td><td className="num">{b}</td><td>{c ? <LabelBadge label={c} /> : null}</td></tr>)}</tbody></table></> : null}
          </div>
        </div>
      )}
    </MathCtx.Provider>
  );
}
export const MathButton = ({ k, text = 'Show the math' }: { k: string; text?: string }) => { const { open } = useMath(); return <button className="link small" onClick={() => open(k)}>{text}</button>; };
