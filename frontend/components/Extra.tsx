'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { aed, pct, num, monthLabel } from '@/lib/fmt';
import { Badge, Stat, HBar, MathButton, scoreTone, Source } from './ui';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, CartesianGrid, LineChart, Line, Cell } from 'recharts';

/* ---------- Decision page additions ---------- */
export function ValidationCard({ r }: { r: any }) {
  const v = r.validation;
  return (
    <div className="card pastel">
      <div className="row between"><h2 style={{ margin: 0 }}>Validation score</h2><MathButton k="validation" /></div>
      <div className="row" style={{ alignItems: 'flex-end', gap: 18, margin: '8px 0 14px' }}>
        <div style={{ fontSize: 56, fontWeight: 800, lineHeight: 1 }}>{Math.round(v.score)}</div>
        <div><Badge tone={v.score >= 70 ? 'good' : v.score >= 50 ? 'warn' : 'bad'}>{v.verdict}</Badge><div className="small muted" style={{ marginTop: 4 }}>Likely range {Math.round(v.low)} to {Math.round(v.high)} out of 100</div></div>
      </div>
      <div style={{ position: 'relative', height: 18, borderRadius: 9, background: 'linear-gradient(90deg,#f6c1c1,#f8e2a8 45%,#b4e6d6 70%,#c3cbf7)' }} role="img" aria-label={`Score ${Math.round(v.score)}, range ${Math.round(v.low)} to ${Math.round(v.high)}`}>
        <div style={{ position: 'absolute', top: -4, bottom: -4, left: `${v.low}%`, width: `${v.high - v.low}%`, border: '2px solid #2b3047', borderRadius: 11, background: 'rgba(255,255,255,.35)' }} />
        <div style={{ position: 'absolute', top: -8, height: 34, width: 4, borderRadius: 2, background: '#2b3047', left: `calc(${v.score}% - 2px)` }} />
      </div>
      <div className="row between tiny muted" style={{ marginTop: 6 }}><span>0 weak</span><span>50</span><span>100 strong</span></div>
      <p className="small muted" style={{ marginTop: 10 }}>A weighted average of the checks (money and customers count most). The range is wider when evidence is thin, when the critic flags weak claims, and when payback is close to a coin toss. The decision above uses your limits; this score summarises overall strength.</p>
    </div>
  );
}

export function IdeaCard({ r }: { r: any }) {
  const i = r.idea, c = i.canvas || {};
  const cells = [['Problem', c.problem], ['Customer segments', c.customer_segments], ['Unique value', c.unique_value], ['Solution', c.solution], ['Channels', c.channels], ['Revenue', c.revenue_streams], ['Costs', c.cost_structure], ['Key metrics', c.key_metrics], ['Unfair advantage', c.unfair_advantage]];
  return (
    <div className="card">
      <h2>The idea at a glance</h2>
      <p><b>Neutral brief:</b> {i.brief}</p>
      <h3 style={{ marginTop: 12 }}>Lean Canvas {i.canvas_source === 'template' && <Badge tone="warn">template: run with AI to fill</Badge>}</h3>
      <div className="meta">{cells.map(([k, v]) => <div key={k}><b>{k}</b>{v || '–'}</div>)}</div>
      <div className="grid g2">
        <div><h3>Key assumptions to test</h3><ol style={{ margin: 0, paddingLeft: 20 }}>{i.assumptions.map((a: string, j: number) => <li key={j} className="small">{a}</li>)}</ol></div>
        {i.rubric?.length ? <div><h3>AI judge rubric</h3>{i.rubric.map((x: any, j: number) => <HBar key={j} name={<span title={x.reason}>{x.criterion}</span>} frac={x.score / 5} value={`${x.score}/5`} color={x.score >= 4 ? '#3f9c7a' : x.score >= 3 ? '#f0c27a' : '#d4777c'} />)}<p className="tiny muted">Hover a criterion for the reason. A fixed rubric reduces flattery.</p></div> : <div><h3>AI judge rubric</h3><p className="small muted">Run with AI agents to score problem severity, solution fit, differentiation, UAE feasibility and timing.</p></div>}
      </div>
      {i.applied?.length ? <p className="callout" style={{ marginTop: 12 }}>Changes applied to this plan: {i.applied.map((a: any) => a.name).join('; ')}.</p> : null}
    </div>
  );
}

export function summaryText(d: any) {
  const r = d.result, f = r.stages.forecast;
  return [`ValidateUAE report`, r.idea.brief, `${r.intake.emirate} · ${r.intake.setup}`, '', `Decision: ${r.decision.label}`, ...r.decision.reasons.map((x: string) => `- ${x}`), '',
    `Validation score ${Math.round(r.validation.score)}/100 (range ${Math.round(r.validation.low)}–${Math.round(r.validation.high)}): ${r.validation.verdict}`,
    `Payback chance within ${f.horizon} months: ${pct(f.p_payback)}; chance of exceeding budget: ${pct(f.p_ruin)}; expected NPV ${aed(f.npv_mean)}`,
    `Evidence strength: ${pct(r.evidence.strength)}`, '', 'Stop rules:', ...r.kill_criteria.map((x: string) => `- ${x}`), '', 'Next tests:', ...r.next_steps.map((s: any) => `- ${s.experiment} (${s.why})`),
    '', 'Decision support only, not financial advice.'].join('\n');
}

/* ---------- Market sizing (funnel stage 1) ---------- */
export function MarketSizing({ r }: { r: any }) {
  const s = r.market_sizing; const max = Math.max(s.tam_synthetic, s.tam_ai || 0, 1);
  return (
    <div style={{ marginTop: 14 }}>
      <div className="row between"><h3 style={{ margin: 0 }}>TAM, SAM and SOM: top-down vs bottom-up</h3><MathButton k="sizing" /></div>
      <HBar name="TAM: category spend (simulated market)" frac={s.tam_synthetic / max} value={aed(s.tam_synthetic) + '/yr'} color="#c9cff7" />
      {s.tam_ai ? <HBar name="TAM: AI research (top-down)" frac={s.tam_ai / max} value={aed(s.tam_ai) + '/yr'} color="#c9cff7" /> : null}
      <HBar name="SAM: spend within your reach" frac={s.sam / max} value={aed(s.sam) + '/yr'} color="#aab3f2" />
      {s.som_top_down ? <HBar name="SOM: AI research (top-down)" frac={s.som_top_down / max} value={aed(s.som_top_down) + '/yr'} /> : null}
      <HBar name="SOM: agent simulation (bottom-up)" frac={s.som_bottom_up / max} value={aed(s.som_bottom_up) + '/yr'} />
      <p className="small" style={{ marginTop: 6 }}>{s.flag ? <Badge tone="bad">Disagree by {s.disagreement.toFixed(1)}×</Badge> : s.disagreement ? <Badge tone="good">Agree within {s.disagreement.toFixed(1)}×</Badge> : null} {s.note}</p>
    </div>
  );
}

/* ---------- Customer value tab ---------- */
export function CustomerValue({ d }: { d: any }) {
  const r = d.result, v = r.value, u = v.usability, h = v.wtp_hist;
  const data = h.counts.map((c: number, i: number) => ({ x: Math.round((h.edges[i] + h.edges[i + 1]) / 2), c, above: h.edges[i] >= h.price }));
  const canvas = v.canvas || {}; const has = Object.values(canvas).some((x: any) => x?.length);
  const kanoTone: any = { 'must-have': 'bad', performance: 'info', delighter: 'good', indifferent: 'neutral' };
  return (
    <div className="stack">
      <div><h1>Customer value: is it worth paying for, and easy to use?</h1><p className="lead">Who the customer is, what job they are trying to get done, how your offer relieves their pains, what they would pay, and how easy it is to get value.</p></div>
      <div className="grid g4">
        <Stat label="Value gap score" value={`${Math.round(v.value_gap_score)}/100`} sub={`Likely buyers would pay ${v.value_ratio.toFixed(2)}× your price`} math="value" />
        <Stat label="Pain among likely buyers" value={pct(v.pain_adopters)} sub="How unhappy they are with today's options" />
        <Stat label="Simulated buyers who accept your price" value={pct(h.share_above_price)} sub={`at ${aed(h.price)} a month`} />
        <Stat label="Ease-of-use score" value={u.score == null ? '–' : `${Math.round(u.score)}/100`} sub={u.measured ? `Measured: SUS ${u.measured.sus ?? '–'}` : u.score == null ? 'Not assessed yet' : 'AI review; test with 5 users'} />
      </div>
      <div className="grid g2">
        <div className="card"><h2>Willingness to pay vs your price</h2><p className="small muted">Simulated buyers in your area from the blinded market. Bars at or above your price are dark.</p>
          <div style={{ width: '100%', height: 240 }}><ResponsiveContainer><BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}><CartesianGrid stroke="#e9ecf3" vertical={false} /><XAxis dataKey="x" tick={{ fontSize: 12, fill: '#586079' }} tickFormatter={(x: any) => `${x}`} /><YAxis hide /><Tooltip formatter={(c: any) => [num(c), 'Simulated buyers']} labelFormatter={(x: any) => `About AED ${x} a month`} /><Bar dataKey="c" isAnimationActive={false}>{data.map((x: any, i: number) => <Cell key={i} fill={x.above ? '#7682e6' : '#e2e6fb'} />)}</Bar><ReferenceLine x={data.find((x: any) => x.above)?.x} stroke="#d9a35a" strokeDasharray="4 4" /></BarChart></ResponsiveContainer></div>
          <p className="tiny muted">AED per month. Run the Van Westendorp survey on the Experiments tab to replace this with real answers.</p></div>
        <div className="card"><h2>Jobs to be done</h2>{v.jtbd.length ? <ul style={{ paddingLeft: 18 }}>{v.jtbd.map((j: any, i: number) => <li key={i}><Badge tone="neutral">{j.type}</Badge> {j.job}</li>)}</ul> : <p className="muted small">Run with AI agents to describe the customer's functional, emotional and social jobs.</p>}
          <h3>Pains found</h3>{v.pains.length ? v.pains.map((p: any, i: number) => <HBar key={i} name={<>{p.pain} <Source url={p.url} /></>} frac={p.intensity / 100} value={Math.round(p.intensity)} color={p.intensity >= 65 ? '#d4777c' : '#f0c27a'} />) : <p className="muted small">Not researched yet.</p>}</div>
      </div>
      <div className="card"><h2>Value Proposition Canvas</h2>{has ? (
        <div className="grid g2">
          <div className="stat"><h3>Customer profile</h3>{[['Jobs', canvas.jobs], ['Pains', canvas.pains], ['Gains', canvas.gains]].map(([k, xs]: any) => <div key={k}><b className="small">{k}</b><ul className="small" style={{ margin: '2px 0 8px', paddingLeft: 18 }}>{(xs || []).map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></div>)}</div>
          <div className="stat"><h3>Value map (your offer)</h3>{[['Products and services', canvas.products], ['Pain relievers', canvas.pain_relievers], ['Gain creators', canvas.gain_creators]].map(([k, xs]: any) => <div key={k}><b className="small">{k}</b><ul className="small" style={{ margin: '2px 0 8px', paddingLeft: 18 }}>{(xs || []).map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></div>)}</div>
        </div>) : <p className="muted">Run with AI agents to fill the canvas from real customer research.</p>}
        <p className="small muted">Fit means each important pain on the left has a pain reliever on the right.</p></div>
      <div className="grid g2">
        <div className="card"><h2>Kano features</h2>{v.kano.length ? <table><tbody>{v.kano.map((k: any, i: number) => <tr key={i}><td>{k.feature}</td><td><Badge tone={kanoTone[k.category]}>{k.category}</Badge></td></tr>)}</tbody></table> : <p className="muted small">Run with AI agents to classify features.</p>}
          <p className="small muted">Build must-haves first, then performance features. Delighters only matter once the basics work.</p></div>
        <div className="card"><h2>Ease of use</h2>
          {u.measured ? <p><Badge tone="good">Measured</Badge> {u.measured.users} users completed {pct(u.measured.success)} of tasks{u.measured.sus != null && <>; SUS {u.measured.sus.toFixed(1)} ({u.measured.sus_grade})</>}.</p> : null}
          {u.journey?.length ? <><h3>Customer journey ({u.steps} steps to first value)</h3><ol className="small" style={{ paddingLeft: 20 }}>{u.journey.map((s: any, i: number) => <li key={i}><b>{s.step}</b> {s.note && <span className="muted">· {s.note}</span>}</li>)}</ol></> : <p className="small muted">Run with AI agents for a journey review, or enter a usability test on the Experiments tab.</p>}
          {u.issues?.map((x: any, i: number) => <p key={i} className="small"><Badge tone={x.severity >= 3 ? 'bad' : x.severity === 2 ? 'warn' : 'neutral'}>{['', 'Minor', 'Major', 'Critical'][x.severity]}</Badge> {x.issue} <span className="muted">({x.heuristic})</span></p>)}
        </div>
      </div>
      {v.alternatives.length ? <div className="card"><h2>What customers use today</h2><table><tbody>{v.alternatives.map((a: any, i: number) => <tr key={i}><td>{a.name} <Source url={a.url} /></td><td className="num">{aed(a.monthly_cost_aed)} / month</td></tr>)}</tbody></table></div> : null}
    </div>
  );
}

/* ---------- Improve tab ---------- */
export function Improve({ d, setD }: { d: any; setD: (x: any) => void }) {
  const r = d.result, im = r.improve; const [busy, setBusy] = useState(''); const [err, setErr] = useState('');
  const act = async (fn: () => Promise<any>, id: string) => { setBusy(id); setErr(''); try { setD(await fn()); } catch (e: any) { setErr(e.message); } setBusy(''); };
  return (
    <div className="stack">
      <div><h1>Improve my idea</h1><p className="lead">Concrete changes to the idea, each replayed in the agent-based market with the same random events as your current plan, so the comparison is fair. The best changes are then crossed in pairs, like one generation of a genetic algorithm; a combination is kept only if it beats both parents.</p></div>
      {err && <p className="error">{err}</p>}
      {r.idea.applied?.length ? <div className="card"><h2>Applied to your plan</h2><div className="row">{r.idea.applied.map((a: any) => <button key={a.id} disabled={!!busy} onClick={() => act(() => api.removeVariant(d.id, a.id), a.id)}>{busy === a.id ? 'Removing…' : `${a.name}: remove`}</button>)}</div></div> : null}
      <div className="card">
        <div className="row between"><h2 style={{ margin: 0 }}>Tested changes, ranked</h2><MathButton k="improve" /></div>
        <p className="small muted">Current plan: {pct(im.base.p_payback)} payback chance, expected value {aed(im.base.npv_mean)} (each tested with the same set of replays).</p>
        <div className="scroll"><table><thead><tr><th>Change</th><th>What it does</th><th className="num">Payback chance</th><th className="num">Expected value</th><th></th></tr></thead><tbody>
          {im.variants.map((v: any) => <tr key={v.id}><td><b>{v.name}</b> {v.ai && <Badge tone="info">AI pivot</Badge>} {v.combo && <Badge tone="good">Recombined</Badge>}<div className="tiny muted">{Object.entries(v.changes).map(([k, x]: any) => `${k} ${x > 0 ? '+' : ''}${Math.round(x)}${['var_pct', 'satisfaction'].includes(k) ? ' pts' : '%'}`).join(', ')}</div></td>
            <td className="small">{v.what}</td><td className="num">{pct(v.p_payback)} <span className="small" style={{ color: v.d_payback > 0 ? '#3f9c7a' : v.d_payback < 0 ? '#d4777c' : undefined }}>({v.d_payback >= 0 ? '+' : '−'}{Math.abs(Math.round(v.d_payback * 100))})</span></td>
            <td className="num">{aed(v.npv_mean)}</td><td><button disabled={!!busy} onClick={() => act(() => api.applyVariant(d.id, v.id), v.id)}>{busy === v.id ? 'Applying…' : 'Apply'}</button></td></tr>)}
        </tbody></table></div>
        <p className="small muted">Applying a change re-runs the whole funnel with it. Remove it any time.</p>
      </div>
      <div className="grid g2">
        <div className="card"><h2>What moves the result most</h2><p className="small muted">Improve evidence for these first; they explain most of the uncertainty in profit.</p>{r.leak.rows.slice(0, 6).map((x: any) => <HBar key={x.key} name={x.name} frac={x.variance_share / r.leak.rows[0].variance_share} value={pct(x.variance_share)} />)}</div>
        <div className="card"><h2>Pivot ideas from the critic</h2>{(d.agents?.critic?.pivot_ideas || []).length ? <ul style={{ paddingLeft: 18 }}>{d.agents.critic.pivot_ideas.map((p: any, i: number) => <li key={i} style={{ marginBottom: 6 }}><b>{p.name}</b>: {p.why}</li>)}</ul> : <p className="muted small">Run with AI agents for pivots tailored to this idea. Built-in changes are tested meanwhile.</p>}</div>
      </div>
    </div>
  );
}

/* ---------- Experiment kit and extra experiment results ---------- */
export function Kit({ r }: { r: any }) {
  const k = r.kit; const [copied, setCopied] = useState('');
  const copy = (t: string, w: string) => navigator.clipboard?.writeText(t).then(() => setCopied(w), () => setCopied(''));
  const landing = `${k.landing.headline}\n${k.landing.subheadline}\n\n${k.landing.bullets.map((b: string) => '• ' + b).join('\n')}\n\n[${k.landing.cta}]`;
  return (
    <div className="card"><div className="row between"><h2 style={{ margin: 0 }}>Experiment kit</h2>{k.source === 'template' ? <Badge tone="warn">Template</Badge> : <Badge tone="info">Written by AI</Badge>}</div>
      <p className="small muted">Everything you need to run the tests below.</p>
      <ol className="small">{k.plan.map((p: string, i: number) => <li key={i}>{p}</li>)}</ol>
      <div className="grid g2">
        <div className="stat"><div className="row between"><b>Landing page</b><button className="link small" onClick={() => copy(landing, 'landing')}>{copied === 'landing' ? 'Copied' : 'Copy'}</button></div>
          <div style={{ fontSize: 20, fontWeight: 750, marginTop: 6 }}>{k.landing.headline}</div><p className="small">{k.landing.subheadline}</p><ul className="small" style={{ paddingLeft: 18 }}>{k.landing.bullets.map((b: string, i: number) => <li key={i}>{b}</li>)}</ul><span className="btn primary" style={{ pointerEvents: 'none' }}>{k.landing.cta}</span></div>
        <div className="stat"><b>Ads for an A/B test</b>{k.ads.map((a: any, i: number) => <div key={i} style={{ marginTop: 8 }}><div className="row between"><Badge tone="neutral">{a.label}</Badge><button className="link small" onClick={() => copy(a.text, a.label)}>{copied === a.label ? 'Copied' : 'Copy'}</button></div><p className="small" style={{ margin: '4px 0 0' }}>{a.text}</p></div>)}</div>
        <div className="stat"><div className="row between"><b>Interview script</b><button className="link small" onClick={() => copy(k.interview.join('\n'), 'int')}>{copied === 'int' ? 'Copied' : 'Copy'}</button></div><ol className="small" style={{ paddingLeft: 20 }}>{k.interview.map((q: string, i: number) => <li key={i}>{q}</li>)}</ol></div>
        <div className="stat"><div className="row between"><b>Survey (first 4 = Van Westendorp)</b><button className="link small" onClick={() => copy(k.survey.join('\n'), 'sv')}>{copied === 'sv' ? 'Copied' : 'Copy'}</button></div><ol className="small" style={{ paddingLeft: 20 }}>{k.survey.map((q: string, i: number) => <li key={i}>{q}</li>)}</ol></div>
      </div>
    </div>
  );
}

export function ExtraResults({ r }: { r: any }) {
  const e = r.stages.experiments.evidence;
  if (!e.vw && !e.sales && !e.nps && !e.usability) return null;
  return (
    <div className="grid g2">
      {e.vw && <div className="card"><div className="row between"><h2 style={{ margin: 0 }}>Van Westendorp price range</h2><MathButton k="vw" /></div>
        <div className="grid g4" style={{ margin: '10px 0' }}><Stat label="Lowest acceptable" value={aed(e.vw.pmc)} /><Stat label="Optimal price" value={aed(e.vw.opp)} /><Stat label="Indifference price" value={aed(e.vw.ipp)} /><Stat label="Highest acceptable" value={aed(e.vw.pme)} /></div>
        <p className="small">{e.vw.accept_k} of {e.vw.accept_n} respondents find your price of {aed(r.assumptions.price.likely)} acceptable.</p>
        <div style={{ width: '100%', height: 220 }}><ResponsiveContainer><LineChart data={e.vw.curves.price.map((p: number, i: number) => ({ p, tc: e.vw.curves.too_cheap[i], c: e.vw.curves.cheap[i], x: e.vw.curves.expensive[i], te: e.vw.curves.too_expensive[i] }))}><CartesianGrid stroke="#e9ecf3" vertical={false} /><XAxis dataKey="p" tick={{ fontSize: 12 }} /><YAxis tickFormatter={(v: any) => pct(v)} tick={{ fontSize: 12 }} width={44} /><Tooltip formatter={(v: any) => pct(v)} labelFormatter={(p: any) => `AED ${p}`} />
          <Line dataKey="tc" name="Too cheap" stroke="#c9cff7" dot={false} isAnimationActive={false} /><Line dataKey="c" name="Cheap" stroke="#7682e6" dot={false} isAnimationActive={false} /><Line dataKey="x" name="Expensive" stroke="#f0c27a" dot={false} isAnimationActive={false} /><Line dataKey="te" name="Too expensive" stroke="#d4777c" dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div></div>}
      {e.sales && <div className="card"><h2>Sales forecast from your real data</h2><p className="small muted">Holt's exponential smoothing (level and trend), with an 80% range that widens over time.</p>
        <div style={{ width: '100%', height: 240 }}><ResponsiveContainer><LineChart data={[...e.sales.history.map((v: number, i: number) => ({ t: `M${i + 1}`, actual: v })), ...e.sales.forecast.map((v: number, i: number) => ({ t: `M${e.sales.history.length + i + 1}`, f: v, lo: e.sales.low[i], hi: e.sales.high[i] }))]}><CartesianGrid stroke="#e9ecf3" vertical={false} /><XAxis dataKey="t" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} width={56} tickFormatter={(v: any) => num(v)} /><Tooltip formatter={(v: any) => aed(v)} />
          <Line dataKey="actual" name="Actual" stroke="#2b3047" strokeWidth={2.5} isAnimationActive={false} /><Line dataKey="f" name="Forecast" stroke="#7682e6" strokeWidth={2.5} strokeDasharray="5 4" dot={false} isAnimationActive={false} /><Line dataKey="lo" name="Low" stroke="#c9cff7" dot={false} isAnimationActive={false} /><Line dataKey="hi" name="High" stroke="#c9cff7" dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>
        <p className="small">Trend: {e.sales.trend_per_month >= 0 ? '+' : ''}{aed(e.sales.trend_per_month)} a month.</p></div>}
      {(e.nps || e.usability) && <div className="card"><h2>Satisfaction and usability</h2>
        {e.nps && <p>NPS <b>{Math.round(e.nps.nps)}</b> from {e.nps.n} pilot customers; it now sets satisfaction in the simulation to <b>{pct(e.nps.satisfaction)}</b>.</p>}
        {e.usability && <p>Usability test: {e.usability.users} users, {pct(e.usability.success)} task success{e.usability.sus != null && <>, SUS <b>{e.usability.sus.toFixed(1)}</b> ({e.usability.sus_grade})</>}. Ease-of-use score now <b>{Math.round(e.usability.score)}</b> (measured).</p>}</div>}
    </div>
  );
}

export function SusHelper() {
  const [qs, setQs] = useState<string[]>([]); const [ans, setAns] = useState<number[]>(Array(10).fill(3)); const [list, setList] = useState<number[]>([]);
  useEffect(() => { api.susQuestions().then(setQs).catch(() => {}); }, []);
  const score = ans.reduce((s, a, i) => s + (i % 2 === 0 ? a - 1 : 5 - a), 0) * 2.5;
  return (
    <details><summary>SUS calculator: score one tester's 10 answers</summary>
      {qs.map((q, i) => <div key={i} className="row between small" style={{ borderBottom: '1px solid var(--line)', padding: '4px 0' }}><span style={{ flex: 1 }}>{i + 1}. {q}</span><select value={ans[i]} onChange={e => { const a = [...ans]; a[i] = +e.target.value; setAns(a); }} style={{ width: 160 }} aria-label={`Answer ${i + 1}`}>{[1, 2, 3, 4, 5].map(v => <option key={v} value={v}>{v} {v === 1 ? '(disagree)' : v === 5 ? '(agree)' : ''}</option>)}</select></div>)}
      <div className="row" style={{ marginTop: 8 }}><b>SUS score: {score.toFixed(1)}</b><button type="button" onClick={() => setList([...list, score])}>Add to list</button></div>
      {list.length > 0 && <p className="small">Scores so far: <code>{list.join(', ')}</code>. Paste them into the usability form.</p>}
    </details>
  );
}
