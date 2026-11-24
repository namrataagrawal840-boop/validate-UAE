'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

const EXAMPLES = [
  { idea: 'A cloud kitchen in Business Bay delivering healthy, high-protein lunches to office workers, ordered through our own app and the delivery platforms.', business_type: 'kitchen', emirate: 'Dubai', setup: 'Mainland', target_customer: 'Office workers aged 25-45 in Business Bay and DIFC', budget_aed: 600000 },
  { idea: 'An online platform that matches children aged 6 to 14 with qualified Arabic tutors for live lessons, with weekly progress reports for parents.', business_type: 'education', emirate: 'All UAE', setup: 'Free zone', target_customer: 'Parents who want their children to improve their Arabic', budget_aed: 300000 },
  { idea: 'A women-only boutique fitness studio in Sharjah with small group classes, childcare during sessions and flexible class packs.', business_type: 'fitness', emirate: 'Sharjah', setup: 'Mainland', target_customer: 'Women aged 25-50 living in Sharjah', budget_aed: 900000 },
];
const blank = { idea: '', business_type: 'kitchen', emirate: 'Dubai', setup: 'Mainland', target_customer: '', budget_aed: 500000, min_payback_probability: 0.6, max_ruin_probability: 0.2, horizon_months: 36, price: '', fixed: '', setup_budget: '', evidence_text: '', use_ai: true };

export default function Home() {
  const [f, setF] = useState<any>(blank);
  const [meta, setMeta] = useState<any>(null);
  const [past, setPast] = useState<any[]>([]);
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { api.meta().then(setMeta).catch(() => setErr('Cannot reach the server. Is the backend running?')); api.list().then(setPast).catch(() => {}); }, []);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  async function submit(e: any) {
    e.preventDefault(); setErr('');
    if (f.idea.trim().length < 20) return setErr('Describe the idea in at least one full sentence (20 characters or more).');
    if (!(+f.budget_aed > 0)) return setErr('Enter the cash you can put in, in AED.');
    const body: any = { ...f, budget_aed: +f.budget_aed, min_payback_probability: +f.min_payback_probability, max_ruin_probability: +f.max_ruin_probability, horizon_months: +f.horizon_months };
    for (const k of ['price', 'fixed', 'setup_budget']) body[k] = +f[k] > 0 ? +f[k] : null;
    setBusy(true);
    try { const { id } = await api.create(body); location.href = `/report?id=${id}`; } catch (x: any) { setErr(x.message); setBusy(false); }
  }
  return (
    <>
      <header className="topbar"><div className="container"><a className="brand" href="/"><i />ValidateUAE</a></div></header>
      <main className="container page">
        <div className="grid g2" style={{ alignItems: 'start', gap: 32 }}>
          <div className="stack">
            <h1>Test a business idea against the UAE market before you spend on it</h1>
            <p className="lead">Start with the decision: should you launch, launch with changes, test first, or stop? AI agents research your idea on the web with sources. Ten algorithm stages turn the research into one answer. Then an agent-based simulation replays the market customer by customer, with word of mouth, a reacting competitor and random shocks, and checks the result against your cash and your appetite for risk.</p>
            <div className="card pastel"><h3>How it decides</h3>
              <ol className="small" style={{ margin: 0, paddingLeft: 20 }}>
                <li>Describe the market and group buyers (statistics, Gaussian mixture)</li>
                <li>Flag unrealistic assumptions (Isolation Forest)</li>
                <li>Predict who buys and how much they spend (choice model, regression)</li>
                <li>Model how long customers stay and when you pay back (survival analysis)</li>
                <li>Simulate thousands of individual UAE customers with friend networks, a reacting competitor, shocks and UAE seasons (agent-based simulation)</li>
                <li>Read customer complaints (TF-IDF topics)</li>
                <li>Plan the tests that settle it (Bayesian A/B)</li>
                <li>Allocate the budget and pick the best launch plan (linear programming, optimisation)</li>
              </ol>
            </div>
            <div><h3>Try an example</h3><div className="grid" style={{ gap: 8 }}>{EXAMPLES.map((x, i) => <button key={i} type="button" style={{ textAlign: 'left', padding: '10px 14px', fontWeight: 500, minHeight: 0 }} onClick={() => setF({ ...blank, ...x })}>{x.idea}</button>)}</div></div>
            {past.length > 0 && <div><h3>Recent analyses</h3><ul className="small" style={{ paddingLeft: 18 }}>{past.slice(0, 6).map(p => <li key={p.id}><a href={`/report?id=${p.id}`}>{p.idea}</a> <span className="faint">({p.status})</span></li>)}</ul></div>}
          </div>
          <form className="card" onSubmit={submit} noValidate>
            <h2>1. The idea</h2>
            <div className="field"><label htmlFor="idea">Describe it in plain words</label><textarea id="idea" value={f.idea} onChange={set('idea')} placeholder="A home-cleaning subscription for villas in Arabian Ranches, booked through WhatsApp" /></div>
            <div className="grid g2" style={{ gap: '0 12px' }}>
              <div className="field"><label htmlFor="bt">Business type</label><select id="bt" value={f.business_type} onChange={set('business_type')}>{meta ? Object.entries(meta.types).map(([k, v]: any) => <option key={k} value={k}>{v}</option>) : <option>{f.business_type}</option>}</select></div>
              <div className="field"><label htmlFor="em">Where</label><select id="em" value={f.emirate} onChange={set('emirate')}>{(meta?.emirates || ['Dubai']).map((e: string) => <option key={e}>{e}</option>)}</select></div>
              <div className="field"><label htmlFor="su">Setup</label><select id="su" value={f.setup} onChange={set('setup')}>{['Mainland', 'Free zone', 'Online only', 'Home-based'].map(s => <option key={s}>{s}</option>)}</select></div>
              <div className="field"><label htmlFor="tc">Target customer</label><input id="tc" value={f.target_customer} onChange={set('target_customer')} placeholder="Families in Dubai Marina" /></div>
            </div>
            <h2 style={{ marginTop: 8 }}>2. Your decision limits</h2>
            <p className="small muted">These are the rules the answer must never break.</p>
            <div className="grid g2" style={{ gap: '0 12px' }}>
              <div className="field"><label htmlFor="bud">Cash you can put in (AED)</label><input id="bud" type="number" min={1} value={f.budget_aed} onChange={set('budget_aed')} /><div className="hint">Including setup. Needing more than this counts as running out.</div></div>
              <div className="field"><label htmlFor="hz">Time to pay back</label><select id="hz" value={f.horizon_months} onChange={set('horizon_months')}>{[24, 36, 48, 60].map(m => <option key={m} value={m}>{m} months</option>)}</select></div>
              <div className="field"><label htmlFor="mp">Minimum chance of paying back</label><select id="mp" value={f.min_payback_probability} onChange={set('min_payback_probability')}>{[.5, .6, .7, .8].map(v => <option key={v} value={v}>{v * 100}%</option>)}</select></div>
              <div className="field"><label htmlFor="mr">Most risk of running out you accept</label><select id="mr" value={f.max_ruin_probability} onChange={set('max_ruin_probability')}>{[.05, .1, .2, .3].map(v => <option key={v} value={v}>{v * 100}%</option>)}</select></div>
            </div>
            <details style={{ marginBottom: 14 }}><summary>3. Numbers and evidence you already have (optional)</summary>
              <p className="hint">Leave blank to let the agents estimate. Your numbers are labelled “Founder input”.</p>
              <div className="grid g3" style={{ gap: '0 12px' }}>
                <div className="field"><label htmlFor="pr">Spend per customer per month (AED)</label><input id="pr" type="number" min={0} value={f.price} onChange={set('price')} /></div>
                <div className="field"><label htmlFor="fx">Fixed costs per month (AED)</label><input id="fx" type="number" min={0} value={f.fixed} onChange={set('fixed')} /></div>
                <div className="field"><label htmlFor="sb">Setup cost (AED)</label><input id="sb" type="number" min={0} value={f.setup_budget} onChange={set('setup_budget')} /></div>
              </div>
              <div className="field"><label htmlFor="ev">Customer reviews, complaints or interview notes</label><textarea id="ev" value={f.evidence_text} onChange={set('evidence_text')} placeholder="Paste one per line. Used by the text-analysis stage." /></div>
            </details>
            <label className="row" style={{ fontWeight: 500 }}><input type="checkbox" checked={f.use_ai} onChange={set('use_ai')} disabled={meta && !meta.ai_enabled} style={{ width: 18 }} />Use AI agents with web research {meta && !meta.ai_enabled && <span className="faint small">(no API key on the server)</span>}</label>
            {err && <p className="error" role="alert">{err}</p>}
            <button className="primary" type="submit" disabled={busy} style={{ width: '100%', marginTop: 14 }}>{busy ? 'Starting…' : 'Run the validation'}</button>
            <p className="hint">About 1 to 3 minutes with AI research, a few seconds without.</p>
          </form>
        </div>
      </main>
    </>
  );
}
