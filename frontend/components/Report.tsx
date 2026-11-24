'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { aed, pct, num, monthsText, LABEL, safeUrl, host } from '@/lib/fmt';
import { makeExplain } from '@/lib/explain';
import { Badge, LabelBadge, Stat, HBar, MathProvider, MathButton, scoreTone, scoreWord, Source } from './ui';
import { FanChart, CurveChart, Tornado } from './charts';

const TABS = [['decision', 'Decision'], ['funnel', 'Funnel'], ['lab', 'What-if lab'], ['experiments', 'Experiments'], ['audit', 'Audit'], ['sources', 'Assumptions & sources']];
const AGENT_NAMES: Record<string, string> = { orch: 'Orchestrator', market: 'Market agent', customer: 'Customer agent', competition: 'Competition agent', finance: 'Finance agent', regulation: 'Regulation agent', usability: 'Ease-of-use agent', critic: 'Critic', offline: 'Offline mode', funnel: 'Decision funnel' };

export default function Report({ id }: { id: string }) {
  const [d, setD] = useState<any>(null); const [err, setErr] = useState(''); const [tab, setTab] = useState('decision');
  useEffect(() => {
    let stop = false, timer: any;
    const poll = async () => {
      try { const x = await api.get(id); if (stop) return; setD(x); if (x.status === 'running') timer = setTimeout(poll, 1500); }
      catch (e: any) { setErr(e.message); }
    };
    poll(); const h = location.hash.slice(1); if (TABS.some(t => t[0] === h)) setTab(h);
    return () => { stop = true; clearTimeout(timer); };
  }, [id]);
  const go = (t: string) => { setTab(t); history.replaceState(null, '', `#${t}`); scrollTo(0, 0); };
  const explain = useMemo(() => (d?.result ? makeExplain(d.result) : () => null), [d]);
  return (
    <MathProvider explain={explain}>
      <header className="topbar"><div className="container"><a className="brand" href="/"><i />ValidateUAE</a>
        {d?.status === 'done' && <nav className="tabs" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => go(k)}>{l}</button>)}</nav>}
      </div></header>
      <main className="container page">
        {err && <p className="error">{err}</p>}
        {!d && !err && <p className="muted">Loading…</p>}
        {d?.status === 'running' && <Progress d={d} />}
        {d?.status === 'error' && <div className="card"><h2>Something went wrong</h2><p>{d.error}</p><a className="btn" href="/">Start again</a></div>}
        {d?.status === 'done' && (
          <>
            {tab === 'decision' && <Decision d={d} go={go} />}
            {tab === 'funnel' && <Funnel d={d} go={go} />}
            {tab === 'lab' && <Lab d={d} setD={setD} />}
            {tab === 'experiments' && <Experiments d={d} setD={setD} />}
            {tab === 'audit' && <Audit d={d} />}
            {tab === 'sources' && <Sources d={d} setD={setD} />}
          </>
        )}
      </main>
    </MathProvider>
  );
}

function Progress({ d }: { d: any }) {
  const order = ['orch', 'market', 'customer', 'competition', 'finance', 'regulation', 'usability', 'critic', 'offline', 'funnel'];
  const p = [...(d.progress || [])].sort((a, b) => order.indexOf(a.stage) - order.indexOf(b.stage));
  return (
    <div className="card" style={{ maxWidth: 760, margin: '0 auto' }}>
      <h1>Working on your idea</h1><p className="muted">AI agents research in parallel, then the funnel runs. This page updates by itself.</p>
      <ol className="steps">{p.length ? p.map((s, i) => <li key={s.stage}><span className={`dot ${s.status}`}>{s.status === 'done' ? '✓' : s.status === 'fallback' ? '!' : i + 1}</span><div><b>{AGENT_NAMES[s.stage] || s.stage}</b><div className="small muted">{s.status === 'working' ? 'Working…' : s.text}</div></div></li>) : <li><span className="dot working">…</span><div>Starting…</div></li>}</ol>
    </div>
  );
}

function Decision({ d, go }: { d: any; go: (t: string) => void }) {
  const r = d.result, f = r.stages.forecast, dec = r.decision, L = r.limits, ag = d.agents || {};
  const brief = ag.orch?.neutral_brief || r.intake.idea;
  const seg = r.stages.segment.segments[0]; const mix = r.stages.optimise.channel_mix;
  const risks = [...(ag.critic?.pre_mortem || []), ...r.stages.anomaly.flags.filter((x: any) => x.optimistic).map((x: any) => `${x.name} looks optimistic: better than ${pct(x.percentile > .5 ? x.percentile : 1 - x.percentile)} of comparable plans.`)];
  const checks = [['market', 'Market', 'Is there enough demand within reach?'], ['customers', 'Customers', 'Do they feel the pain and value the offer?'], ['competition', 'Competition', 'How hard is the market?'], ['money', 'Money', 'Does it pay back within your limits?'], ['usability', 'Ease of use', 'Is it easy to get value?'], ['evidence', 'Evidence', 'How much is measured, not guessed?']];
  return (
    <div className="stack">
      <div className={`decision ${dec.code}`}>
        <div className="kicker">{r.intake.emirate} · {r.intake.setup} · decision for: {brief}</div>
        <h1>{dec.label}</h1>
        <ul>{dec.reasons.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
        <div style={{ marginTop: 10 }}><MathButton k="decision" text="How this decision is made" /></div>
      </div>
      <div className="grid g4">
        <Stat label={`Chance of paying back in ${f.horizon} months`} value={pct(f.p_payback)} sub={`You need at least ${pct(L.min_payback)}`} math="p_payback" />
        <Stat label="Chance of needing more than your budget" value={pct(f.p_ruin)} sub={`Your limit: ${pct(L.max_ruin)} · budget ${aed(L.budget)}`} math="p_ruin" />
        <Stat label="Expected value (NPV)" value={aed(f.npv_mean)} sub={`Bad case ${aed(f.npv_p10)} · good case ${aed(f.npv_p90)}`} math="npv" />
        <Stat label="Evidence strength" value={pct(r.evidence.strength)} sub="Share of the inputs backed by sources or measurements" math="evidence" />
      </div>
      {dec.code === 'pivot' || (dec.code === 'test' && dec.best) ? (
        <div className="card"><h2>The launch plan that works best</h2>
          <p><b>{dec.best.name}.</b> Payback chance {pct(f.p_payback)} → <b>{pct(dec.best.p_payback)}</b>; chance of exceeding budget {pct(f.p_ruin)} → <b>{pct(dec.best.p_ruin)}</b>; expected value {aed(f.npv_mean)} → <b>{aed(dec.best.npv_mean)}</b>.</p>
          <p className="small muted">{dec.feasible} of 12 tested launch plans meet your limits. <button className="link" onClick={() => go('funnel')}>See all plans</button></p>
        </div>) : null}
      <div className="grid g2">
        <div className="card"><h2>Launch plan</h2>
          <table><tbody>
            <tr><td>Start with</td><td><b>{seg?.name}</b> <span className="small muted">({pct(seg?.value_share)} of expected revenue)</span></td></tr>
            <tr><td>Spend per customer</td><td>{aed(r.unit.arpu)} a month</td></tr>
            <tr><td>Customers needed to cover fixed costs</td><td>{num(r.unit.bep_customers)}</td></tr>
            <tr><td>Typical payback</td><td>{monthsText(f.payback_median)}</td></tr>
            <tr><td>Cash to have ready (90% of futures)</td><td>{aed(f.cash_need_p90)}</td></tr>
            <tr><td>Best marketing channels</td><td>{mix.allocation.filter((a: any) => a.customers > .5).slice(0, 3).map((a: any) => a.channel).join(', ')}</td></tr>
          </tbody></table>
        </div>
        <div className="card"><h2>Stop rules (kill criteria)</h2>
          <ul style={{ margin: 0, paddingLeft: 20 }}>{r.kill_criteria.map((x: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{x}</li>)}</ul>
          <MathButton k="kill" />
        </div>
      </div>
      <div className="card"><h2>Do these next</h2><p className="small muted">The inputs that explain most of the uncertainty in profit, and the cheapest test that settles each one.</p>
        <div className="grid g3">{r.next_steps.map((s: any, i: number) => <div key={i} className="stat"><div className="l">{s.stage}</div><div style={{ fontWeight: 700, margin: '4px 0' }}>{s.experiment}</div><div className="small muted">{s.why}</div></div>)}</div>
        <div className="row" style={{ marginTop: 12 }}><button onClick={() => go('experiments')}>Enter results</button><MathButton k="leak" text="How these were chosen" /></div>
      </div>
      <div><h2>Six checks in plain words</h2>
        <div className="grid g3">{checks.map(([k, n, q]) => { const s = r.scores[k]; return (
          <div key={k} className="card"><div className="row between"><h3 style={{ margin: 0 }}>{n}</h3><Badge tone={scoreTone(s)}>{scoreWord(s)}</Badge></div>
            <div className="small muted">{q}</div><div style={{ fontSize: 30, fontWeight: 750, margin: '6px 0' }}>{s == null ? '–' : Math.round(s)}<span className="small muted"> / 100</span></div>
            <div className="small">{checkLine(k, r, ag)}</div></div>); })}</div>
      </div>
      <div className="card"><div className="row between"><h2 style={{ margin: 0 }}>How simulated customers reacted</h2><MathButton k="forecast" /></div>
        <p className="small muted">{num(f.abm.agents)} simulated UAE buyers, each with friends, replayed {num(f.runs)} times. {pct(f.abm.wom_share)} of customers came through friends; a competitor hit back in {pct(f.abm.runs_with_competitor_reaction)} of runs; {pct(f.abm.unhappy_left_share)} of the customers who left were unhappy.</p>
        <ul style={{ margin: 0, paddingLeft: 18 }}>{f.abm.journeys.slice(0, 4).map((j: any, i: number) => <li key={i} className="small" style={{ marginBottom: 6 }}><Badge tone={j.kind === 'stayed' ? 'good' : j.kind === 'said no' ? 'neutral' : 'bad'}>{j.kind}</Badge> <b>{j.who}</b>: {j.story}</li>)}</ul>
      </div>
      <div className="grid g2">
        <div className="card"><h2>Biggest risks</h2>{risks.length ? <ol style={{ margin: 0, paddingLeft: 20 }}>{risks.slice(0, 6).map((x, i) => <li key={i} style={{ marginBottom: 6 }}>{x}</li>)}</ol> : <p className="muted">Run with AI agents for a critic's pre-mortem.</p>}
          {ag.critic?.pivot_ideas?.length ? <><h3 style={{ marginTop: 14 }}>Pivot ideas from the critic</h3><ul style={{ margin: 0, paddingLeft: 20 }}>{ag.critic.pivot_ideas.map((p: any, i: number) => <li key={i}><b>{p.name}</b>: {p.why}</li>)}</ul></> : null}</div>
        <div className="card"><h2>What happened where</h2><ol className="steps">{(d.progress || []).map((s: any, i: number) => <li key={i}><span className={`dot ${s.status}`}>{s.status === 'done' ? '✓' : s.status === 'fallback' ? '!' : i + 1}</span><div><b>{AGENT_NAMES[s.stage] || s.stage}</b><div className="small muted">{s.text}</div></div></li>)}</ol></div>
      </div>
      {r.warnings?.length ? <div className="callout warn"><b>Notes</b><ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>{r.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}</ul></div> : null}
    </div>
  );
}

function checkLine(k: string, r: any, ag: any) {
  const S = r.stages;
  if (k === 'market') return `${num(S.classify.potential_used)} potential customers within reach, against ${num(r.unit.bep_customers)} needed to cover fixed costs.`;
  if (k === 'customers') return `${pct(S.classify.mean_adoption, 1)} of category buyers would buy once aware. Buyers' pain averages ${pct(S.classify.pain_adopters)}; they'd pay ${S.classify.value_ratio.toFixed(2)}× your price.`;
  if (k === 'competition') return `Competitive pressure ${r.competition.force_avg.toFixed(1)} out of 5; differentiation ${Math.round(r.competition.differentiation)} out of 100${ag.competition ? '' : ' (category prior)'}.`;
  if (k === 'money') return `${pct(S.forecast.p_payback)} payback chance; ${pct(S.forecast.p_ruin)} chance of needing more than your budget.`;
  if (k === 'usability') return ag.usability ? `${ag.usability.steps_to_first_value} steps to first value; ${ag.usability.issues.length} issues found.` : 'Not assessed without AI agents. Test the journey with 5 real users.';
  return `${Object.values(r.evidence.labels).filter((v: any) => ['measured', 'web', 'benchmarked'].includes(v)).length} of ${Object.keys(r.evidence.labels).length} key inputs have a source or measurement.`;
}

function StageCard({ n, q, family, algo, check, passes, children, math }: any) {
  return (
    <div className="card stage">
      <div className="row" style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}><span className="n">{n}</span><div style={{ flex: 1 }}>
        <div className="row between"><h2 style={{ margin: 0 }}>{q}</h2>{math && <MathButton k={math} />}</div>
        <div className="meta"><div><b>Algorithm family</b>{family}</div><div><b>Method used</b>{algo}</div><div><b>Data check</b><Badge tone={check[0]}>{check[1]}</Badge> <span className="small">{check[2]}</span></div><div><b>Passes on</b>{passes}</div></div>
        {children}
      </div></div>
    </div>
  );
}

function Funnel({ d, go }: { d: any; go: (t: string) => void }) {
  const r = d.result, S = r.stages, ag = d.agents || {}, ev = S.experiments.evidence, f = S.forecast;
  const maxSeg = Math.max(...S.segment.segments.map((s: any) => s.value_share));
  const calibrated = S.classify.calibrated;
  const conv = ev.conversion;
  return (
    <div className="stack">
      <div><h1>The decision funnel</h1><p className="lead">Your 7-step recipe, applied to this idea. Each stage answers one question with the simplest algorithm that fits, checks whether the data supports it, and passes probabilities and amounts (not yes/no labels) to the next stage.</p></div>
      <div className="card"><h2>Step 1: the decision</h2><div className="meta">
        <div><b>Decision</b>Launch, launch with changes, test first, or stop</div><div><b>Success metric</b>Chance of paying back within {f.horizon} months, and expected value</div>
        <div><b>Limits</b>Cash need ≤ {aed(r.limits.budget)} in at least {pct(1 - r.limits.max_ruin)} of futures; payback chance ≥ {pct(r.limits.min_payback)}</div><div><b>Hard rules</b>Licence blockers and capacity below break-even override the model</div></div></div>

      <StageCard n={1} q="What does the market look like?" family="Descriptive statistics" algo="Blinded synthetic UAE population (20,000 people)" check={['info', 'Synthetic', 'Built from category priors, never from your idea.']} passes="Category buyers, spend, pain" math="describe">
        <div className="grid g4"><Stat label="Category buyers in focus" value={num(S.describe.category_buyers)} /><Stat label="Median spend today" value={aed(S.describe.spend_median)} sub={`${aed(S.describe.spend_p25)} to ${aed(S.describe.spend_p75)}`} /><Stat label="High pain with today's options" value={pct(S.describe.pain_high_share)} /><Stat label="Category spend per year" value={aed(S.describe.tam_aed)} /></div>
        <p className="small muted" style={{ marginTop: 10 }}>{S.describe.note}</p>
      </StageCard>

      <StageCard n={2} q="Who is similar?" family="Clustering" algo={`Gaussian mixture, ${S.segment.k} groups chosen by BIC`} check={['good', 'Pass', 'Clustering needs no labels.']} passes="Segment as a feature; beachhead segment" math="segment">
        <div className="scroll"><table><thead><tr><th>Segment</th><th className="num">Share</th><th className="num">P(buy)</th><th className="num">Spend</th><th className="num">Customers</th><th>Share of value</th></tr></thead><tbody>
          {S.segment.segments.map((s: any, i: number) => <tr key={s.id}><td>{s.name} {i === 0 && <Badge tone="good">Beachhead</Badge>}<div className="tiny muted">Pain {pct(s.pain)} · online {pct(s.digital)} · mostly {s.top_emirate}</div></td><td className="num">{pct(s.share)}</td><td className="num">{pct(s.adoption, 1)}</td><td className="num">{aed(s.arpu)}</td><td className="num">{num(s.expected_customers)}</td><td style={{ minWidth: 120 }}><div className="bar"><i style={{ width: `${s.value_share / maxSeg * 100}%` }} /></div><span className="tiny">{pct(s.value_share)}</span></td></tr>)}
        </tbody></table></div>
      </StageCard>

      <StageCard n={3} q="Is anything unusual in the plan?" family="Anomaly detection" algo="Isolation Forest vs 3,000 comparable plans" check={['good', 'Pass', 'Reference plans from category ranges.']} passes="Optimism flags (lower evidence strength)" math="anomaly">
        <p>{S.anomaly.outlier ? <Badge tone="bad">Unusual plan</Badge> : <Badge tone="good">Looks like a normal plan</Badge>} <span className="small">Your plan looks more typical than {pct(1 - S.anomaly.more_normal_share)} of {num(S.anomaly.reference_size)} comparable plans. {S.anomaly.optimistic_count} assumption(s) flagged as optimistic.</span></p>
        <div className="scroll"><table><thead><tr><th>Assumption</th><th className="num">Yours</th><th className="num">Typical</th><th>Percentile among comparable plans</th></tr></thead><tbody>
          {S.anomaly.per_assumption.map((a: any) => <tr key={a.key}><td>{a.name} {a.optimistic ? <Badge tone="bad">Optimistic</Badge> : a.unusual ? <Badge tone="warn">Unusual</Badge> : null}</td><td className="num">{num(a.value, a.value < 100 ? 1 : 0)}</td><td className="num">{num(a.typical, a.typical < 100 ? 1 : 0)}</td><td style={{ minWidth: 160 }}><div className="bar" style={{ position: 'relative' }}><i style={{ width: `${a.percentile * 100}%`, background: a.unusual ? '#c43b3b' : '#2348d6' }} /></div><span className="tiny">{pct(a.percentile)}</span></td></tr>)}
        </tbody></table></div>
      </StageCard>

      <StageCard n={4} q="Will they buy?" family="Classification" algo="Logistic choice model per simulated buyer" check={calibrated ? (conv && conv.k < 30 ? ['warn', 'Few positives', `Calibrated with ${conv.k} sign-ups; under 30 is weak.`] : ['good', 'Calibrated', 'Fitted to your measured results.']) : ['warn', 'Rule', 'No outcomes yet: coefficients are starting assumptions until a landing-page test.']} passes="Probability of buying → market potential" math="classify">
        <div className="grid g4"><Stat label="Average P(buy) once aware" value={pct(S.classify.mean_adoption, 1)} /><Stat label="Buyers if everyone knew" value={num(S.classify.potential.adopters_if_aware)} /><Stat label="Reach of one business" value={pct(S.classify.potential.catchment)} sub="Catchment at launch" /><Stat label="Market potential used" value={num(S.classify.potential_used)} sub={S.classify.haircut < 1 ? `After the critic's ${pct(1 - S.classify.haircut)} cut` : 'customers'} /></div>
      </StageCard>

      <StageCard n={5} q="How much will they spend?" family="Regression (hurdle: whether, then how much)" algo="Weighted linear regression on log spend" check={ev.acceptance ? ['good', 'Pass', 'Pricing test data present.'] : ['warn', 'Rule', 'Spend follows today\'s category spend until a pricing test.']} passes="Spend per customer" math="regress">
        <div className="grid g2"><div><Stat label="Expected spend per customer per month" value={aed(S.regress.expected_arpu)} sub={`Planned price ${aed(S.regress.planned_price)} · R² ${S.regress.r2.toFixed(2)}`} /></div>
          <div>{S.regress.drivers.slice(0, 4).map((x: any) => <HBar key={x.feature} name={x.feature.replace('_', ' ')} frac={Math.abs(x.effect) / Math.max(...S.regress.drivers.map((y: any) => Math.abs(y.effect)), 1e-9)} value={(x.effect >= 0 ? '+' : '') + x.effect.toFixed(3)} />)}</div></div>
      </StageCard>

      <StageCard n={6} q="How long do customers stay, and when do you pay back?" family="Survival analysis" algo="Exponential lifetimes; Kaplan-Meier on payback" check={ev.churn ? ['good', 'Measured', 'Churn from your pilot.'] : ['warn', 'Rule', 'Churn is an estimate until a pilot measures it.']} passes="Lifetime value; payback timing" math="survival">
        <div className="grid g2"><div><h3>Chance of having paid back, by month</h3><CurveChart data={S.survival.payback_curve.map((p: number, i: number) => ({ m: i + 1, p }))} x="m" y="p" refLine={r.limits.min_payback} xFmt={(v: any) => `M${v}`} /></div>
          <div><h3>How long customers stay</h3><table><thead><tr><th>Segment</th><th className="num">Median months</th><th className="num">Monthly churn</th></tr></thead><tbody>{S.survival.customers.map((c: any, i: number) => <tr key={i}><td>{c.segment}</td><td className="num">{num(c.median_months, 1)}</td><td className="num">{pct(c.monthly_hazard, 1)}</td></tr>)}</tbody></table></div></div>
      </StageCard>

      <StageCard n={7} q="How many customers in future?" family="Simulation (agent-based model)" algo={`${num(f.abm.agents)} customer agents on a friend network, replayed ${num(f.runs)} times`} check={['good', 'Pass', 'Agents come from the blinded market; every input is a range known today.']} passes="Cash, NPV, payback, cash need per run" math="forecast">
        <p className="small">Each agent is one simulated UAE buyer (standing for about {num(f.abm.people_per_agent)} real people) with their own willingness to pay, pain, channel and {f.abm.friends_per_agent} friends. Every month they may see your marketing or hear from friends, decide to buy, have a good or bad experience, recommend you or warn friends, and leave. A competitor answers when you take share; shocks, boom and downturn months, summer and Ramadan hit along the way.</p>
        <div className="grid g4" style={{ margin: '12px 0' }}>
          <Stat label="Customers won through friends" value={pct(f.abm.wom_share)} sub="the rest came from marketing" />
          <Stat label="Runs where a competitor hit back" value={pct(f.abm.runs_with_competitor_reaction)} sub="4-month promotion each time" />
          <Stat label="Leavers who left unhappy" value={pct(f.abm.unhappy_left_share)} sub="and warned their friends" />
          <Stat label="Buyers turned away (full)" value={num(f.abm.turned_away)} sub="capacity limit, typical run" />
        </div>
        <div className="grid g2"><div><h3>Customer funnel after {f.horizon} months (typical run)</h3><MarketFunnel b={f.bands} /><h3 style={{ marginTop: 16 }}>Active customers over time</h3><FanChart band={f.bands.customers} height={200} /></div>
          <div><h3>Cash over time (AED)</h3><FanChart band={f.bands.cash} money /></div></div>
        <h3 style={{ marginTop: 14 }}>Customer stories from one run</h3>
        <ul style={{ margin: 0, paddingLeft: 18 }}>{f.abm.journeys.map((j: any, i: number) => <li key={i} className="small" style={{ marginBottom: 6 }}><Badge tone={j.kind === 'stayed' ? 'good' : j.kind === 'said no' ? 'neutral' : 'bad'}>{j.kind}</Badge> <b>{j.who}</b>: {j.story}</li>)}</ul>
        <p className="small muted" style={{ marginTop: 8 }}>Shocks hit about {f.shocks_per_run.toFixed(1)} times per run: {Object.entries(f.shock_count).map(([k, v]) => `${v} ${k}`).join(', ')} across all runs.</p>
      </StageCard>

      <StageCard n={8} q="What are customers talking about?" family="Text analysis (NLP)" algo="TF-IDF + k-means topics, matched to your idea" check={S.text.status === 'ran' ? ['good', 'Pass', `${S.text.n_docs} pieces of text.`] : ['neutral', 'Skipped', S.text.reason]} passes="Does real talk match the problem you claim?" math="text">
        {S.text.status === 'ran' ? <>
          <p>{S.text.evidence_supports_problem ? <Badge tone="good">Customer talk matches your problem</Badge> : <Badge tone="warn">Weak match with your problem</Badge>}</p>
          <div className="scroll"><table><thead><tr><th>Topic (top words)</th><th className="num">Share</th><th className="num">Negative</th><th className="num">Match</th><th>Example</th></tr></thead><tbody>{S.text.topics.map((t: any, i: number) => <tr key={i}><td>{t.terms.slice(0, 4).join(', ')}</td><td className="num">{pct(t.share)}</td><td className="num">{pct(t.negative_share)}</td><td className="num">{t.idea_match.toFixed(2)}</td><td className="small">“{t.example}”</td></tr>)}</tbody></table></div>
        </> : <p className="small">Paste reviews or interview notes when you start an analysis, or run with AI agents, which collect customer quotes from the web.</p>}
      </StageCard>

      <StageCard n={9} q="Does our action change it?" family="A/B test, uplift" algo="Bayesian Beta-binomial tests, power analysis" check={d.experiments.length ? ['good', 'Pass', `${d.experiments.length} experiment(s) entered.`] : ['neutral', 'Waiting', 'No experiments yet.']} passes="Calibration for stages 4, 5 and 6" math="experiments">
        <div className="grid g3"><Stat label="Predicted sign-up rate" value={pct(S.experiments.predicted_conversion, 1)} sub="Stage 4, before any test" /><Stat label="Visitors needed per version" value={num(S.experiments.sample_size_landing)} sub="to detect a 50% lift" /><Stat label="A/B tests run" value={ev.ab.length} /></div>
        {ev.ab.map((a: any, i: number) => <p key={i} className="small">{a.name}: {pct(a.p_b_better)} chance that {a.label_b} beats {a.label_a} (lift {pct(a.lift_mean)}).</p>)}
        <button style={{ marginTop: 10 }} onClick={() => go('experiments')}>Run and enter experiments</button>
      </StageCard>

      <StageCard n={10} q="What is the best allocation?" family="Optimisation" algo="Linear programme for channels; 12 launch plans under your limits" check={['good', 'Pass', 'Uses the same simulated futures for a fair comparison.']} passes="One recommended plan" math="optimise">
        <h3>Monthly marketing budget {aed(S.optimise.channel_mix.budget)}: best split</h3>
        <div className="scroll"><table><thead><tr><th>Channel</th><th className="num">Spend</th><th className="num">Customers</th><th className="num">Cost each</th></tr></thead><tbody>{S.optimise.channel_mix.allocation.map((a: any) => <tr key={a.channel}><td>{a.channel}</td><td className="num">{aed(a.spend)}</td><td className="num">{num(a.customers)}</td><td className="num">{a.cac ? aed(a.cac) : '–'}</td></tr>)}</tbody></table></div>
        <p className="small muted">Blended cost to win a customer {aed(S.optimise.channel_mix.blended_cac)}, against {aed(S.optimise.channel_mix.base_cac)} on a single channel.</p>
        <h3 style={{ marginTop: 14 }}>Launch plans tested</h3>
        <div className="scroll"><table><thead><tr><th>Plan</th><th className="num">Payback chance</th><th className="num">Exceeds budget</th><th className="num">Expected NPV</th><th>Meets limits</th></tr></thead><tbody>
          {S.optimise.options.map((o: any) => { const ok = o.p_payback >= r.limits.min_payback && o.p_ruin <= r.limits.max_ruin && o.npv_mean > 0; return <tr key={o.name}><td>{o.name}{o.name === r.decision.best.name && <> <Badge tone="info">Best</Badge></>}</td><td className="num">{pct(o.p_payback)}</td><td className="num">{pct(o.p_ruin)}</td><td className="num">{aed(o.npv_mean)}</td><td>{ok ? <Badge tone="good">Yes</Badge> : <Badge tone="neutral">No</Badge>}</td></tr>; })}
        </tbody></table></div>
      </StageCard>

      <div className="card"><div className="row between"><h2 style={{ margin: 0 }}>Step 6: where the funnel leaks</h2><MathButton k="leak" /></div>
        <p className="small muted">Share of the uncertainty in profit explained by each input. Upgrade the evidence for the top one first, then re-measure.</p>
        <Tornado rows={r.leak.rows} />
      </div>
      <div className="card"><h2>Step 7: prove and protect</h2><p>Run the experiments, keep the stop rules, and check the <button className="link" onClick={() => go('audit')}>audit</button>: it re-runs the analysis without your claims, against an average business, and under heavy shocks, and confirms the simulated market never saw your idea.</p></div>
    </div>
  );
}

const SLIDERS = [['price', 'Spend per customer per month', .4, 2.5], ['cac', 'Cost to win one customer', .3, 3], ['fixed', 'Fixed costs per month', .4, 2.5], ['setup', 'Setup cost', .3, 2.5], ['churn', 'Monthly churn (%)', .3, 3]] as const;
function Lab({ d, setD }: { d: any; setD: (x: any) => void }) {
  const r = d.result, A = r.assumptions;
  const init = () => ({ vals: Object.fromEntries(SLIDERS.map(([k]) => [k, A[k].likely])), sat: r.unit.satisfaction, shocks: r.settings.shocks, cycles: r.settings.cycles, seasonality: r.settings.seasonality, runs: Math.min(r.settings.runs, 1500), seed: r.settings.seed });
  const [w, setW] = useState<any>(init); const [out, setOut] = useState<any>(null); const [busy, setBusy] = useState(false); const [msg, setMsg] = useState('');
  const t = useRef<any>(null);
  const payload = () => ({ overrides: Object.fromEntries(SLIDERS.map(([k]) => { const f = w.vals[k] / A[k].likely; return [k, { min: A[k].min * f, likely: w.vals[k], max: A[k].max * f, label: 'founder', source: 'Set in the What-if lab' }]; }).filter(([k]: any) => Math.abs(w.vals[k] - A[k].likely) > 1e-9)),
    settings: { shocks: w.shocks, cycles: w.cycles, seasonality: w.seasonality, runs: w.runs, seed: w.seed, satisfaction: Math.abs(w.sat - r.unit.satisfaction) > 1e-6 ? w.sat : null } });
  useEffect(() => { clearTimeout(t.current); t.current = setTimeout(async () => { setBusy(true); try { const p = payload(); setOut(await api.whatif(d.id, p.overrides, p.settings)); } catch (e: any) { setMsg(e.message); } setBusy(false); }, 350); return () => clearTimeout(t.current); }, [w]);
  const f = out?.forecast || r.stages.forecast;
  const fmt = (k: string, v: number) => k === 'churn' ? v.toFixed(1) + '%' : aed(v);
  return (
    <div className="stack">
      <div><h1>What-if lab</h1><p className="lead">Move a slider and the agent-based market reruns on the server: every simulated customer decides again. The band runs from a bad case (10th percentile) to a good case (90th).</p></div>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', alignItems: 'start' }}>
        <div className="card">
          {SLIDERS.map(([k, l, lo, hi]) => <div className="field" key={k}><div className="row between"><label htmlFor={`s-${k}`} style={{ margin: 0 }}>{l}</label><b>{fmt(k, w.vals[k])}</b></div><input id={`s-${k}`} type="range" min={A[k].likely * lo} max={A[k].likely * hi} step={A[k].likely / 100} value={w.vals[k]} onChange={e => setW({ ...w, vals: { ...w.vals, [k]: +e.target.value } })} /></div>)}
          <div className="field"><div className="row between"><label htmlFor="s-sat" style={{ margin: 0 }}>Customer satisfaction</label><b>{pct(w.sat)}</b></div><input id="s-sat" type="range" min={.05} max={.97} step={.01} value={w.sat} onChange={e => setW({ ...w, sat: +e.target.value })} /></div>
          <div className="field"><div className="row between"><label htmlFor="s-sh" style={{ margin: 0 }}>Random shocks</label><b>{['None', 'Low', 'Medium', 'High'][w.shocks]}</b></div><input id="s-sh" type="range" min={0} max={3} step={1} value={w.shocks} onChange={e => setW({ ...w, shocks: +e.target.value })} /></div>
          <label className="row" style={{ fontWeight: 500 }}><input type="checkbox" checked={w.cycles} onChange={e => setW({ ...w, cycles: e.target.checked })} /> Economic cycles (boom and downturn)</label>
          <label className="row" style={{ fontWeight: 500 }}><input type="checkbox" checked={w.seasonality} onChange={e => setW({ ...w, seasonality: e.target.checked })} /> UAE seasons (summer, Ramadan)</label>
          <div className="row" style={{ marginTop: 14 }}><button onClick={() => setW({ ...w, seed: w.seed + 1 })}>Replay with new random events</button><button onClick={() => setW(init())}>Reset sliders</button></div>
          <button className="primary" style={{ width: '100%', marginTop: 10 }} onClick={async () => { setBusy(true); try { const p = payload(); setD(await api.apply(d.id, p.overrides, p.settings)); setMsg('Saved: the whole report has been recalculated with these settings.'); } catch (e: any) { setMsg(e.message); } setBusy(false); }}>Use these settings in the report</button>
          {msg && <p className="small" role="status" style={{ marginTop: 8 }}>{msg}</p>}
        </div>
        <div className="stack" style={{ gridColumn: 'span 2', opacity: busy ? .6 : 1 }}>
          <div className="grid g4"><Stat label="Payback chance" value={pct(f.p_payback)} sub={`Need ${pct(r.limits.min_payback)}`} /><Stat label="Exceeds budget" value={pct(f.p_ruin)} sub={`Limit ${pct(r.limits.max_ruin)}`} /><Stat label="Expected NPV" value={aed(f.npv_mean)} /><Stat label="Typical payback" value={f.payback_median ? `Month ${Math.round(f.payback_median)}` : 'Beyond horizon'} /></div>
          <div className="card"><h3>Cash over time (AED)</h3><div className="legend" style={{ marginBottom: 6 }}><span><i style={{ background: '#2348d6' }} />Typical future</span><span><i style={{ background: '#2348d624' }} />Bad to good case</span><span><i style={{ background: '#a86a00' }} />Zero: paid back</span></div><FanChart band={f.bands.cash} money /></div>
          <div className="card"><h3>Active customers</h3><FanChart band={f.bands.customers} height={220} /></div>
        </div>
      </div>
    </div>
  );
}

function Experiments({ d, setD }: { d: any; setD: (x: any) => void }) {
  const r = d.result, ev = r.stages.experiments.evidence;
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('');
  const submit = async (e: any, kind: string, build: (g: (n: string) => number) => any) => {
    e.preventDefault(); setErr(''); setMsg('');
    const fd = new FormData(e.target); const g = (n: string) => { const v = fd.get(n); return v === '' || v == null ? NaN : Number(v); };
    const body = build(g); if (Object.values(body).some(v => typeof v === 'number' && !isFinite(v as number))) return setErr('Fill in every number.');
    try { const before = r.stages.forecast.p_payback; const x = await api.addExperiment(d.id, { kind, ...body }); setD(x); e.target.reset(); setMsg(`Added. Payback chance ${pct(before)} → ${pct(x.result.stages.forecast.p_payback)}.`); } catch (x: any) { setErr(x.message); }
  };
  const F = ({ n, l, def }: any) => <div className="field"><label htmlFor={n}>{l}</label><input id={n} name={n} type="number" min={0} step="any" defaultValue={def} /></div>;
  const desc = (e: any) => e.kind === 'landing' ? `Landing page: ${e.signups} sign-ups from ${e.visitors} visitors, AED ${e.spend}` : e.kind === 'pricing' ? `Pricing: ${e.points.map((p: any) => `${p.k}/${p.n} at AED ${p.price}`).join('; ')}` : e.kind === 'interviews' ? `Interviews: ${e.k} of ${e.n} with strong pain` : e.kind === 'pilot' ? `Pilot: ${e.lost} lost from ${e.customers} customers over ${e.months} months` : `A/B ${e.name || ''}: ${e.kA}/${e.nA} vs ${e.kB}/${e.nB}`;
  return (
    <div className="stack">
      <div><h1>Experiments: replace guesses with evidence</h1><p className="lead">Run a cheap real test, enter what happened, and the funnel recalibrates with Bayesian updating. Measured numbers always outweigh AI estimates, priors and simulated data.</p></div>
      {err && <p className="error" role="alert">{err}</p>}{msg && <p className="callout" role="status">{msg}</p>}
      <div className="grid g3" style={{ alignItems: 'start' }}>
        <form className="card" onSubmit={e => submit(e, 'landing', g => ({ visitors: g('visitors'), signups: g('signups'), spend: g('spend'), pay_rate: g('pay_rate') }))}><h2>Landing-page test</h2><p className="small muted">Calibrates who buys (stage 4) and measures the cost to win a customer. Aim for {num(r.stages.experiments.sample_size_landing)} visitors.</p><F n="visitors" l="Visitors" /><F n="signups" l="Sign-ups" /><F n="spend" l="Ad spend (AED)" /><F n="pay_rate" l="Sign-ups expected to pay (%)" def={30} /><button className="primary">Add result</button></form>
        <form className="card" onSubmit={e => submit(e, 'pricing', g => ({ points: [[g('p1'), g('n1'), g('k1')], [g('p2'), g('n2'), g('k2')]].filter(x => isFinite(x[0]) && isFinite(x[1]) && isFinite(x[2])).map(([price, n, k]) => ({ price, n, k })) }))}><h2>Pricing test</h2><p className="small muted">Ask people at one or two prices. Two prices let the model fit price sensitivity (stage 5).</p><div className="grid g3" style={{ gap: '0 8px' }}><F n="p1" l="Price A (AED)" def={Math.round(r.assumptions.price.likely)} /><F n="n1" l="Asked" /><F n="k1" l="Accepted" /><F n="p2" l="Price B (AED)" /><F n="n2" l="Asked" /><F n="k2" l="Accepted" /></div><button className="primary">Add result</button></form>
        <form className="card" onSubmit={e => submit(e, 'interviews', g => ({ n: g('n'), k: g('k') }))}><h2>Customer interviews</h2><p className="small muted">How many describe the problem as a strong, frequent pain? Updates stage 4.</p><F n="n" l="People interviewed" /><F n="k" l="Described strong pain" /><button className="primary">Add result</button></form>
        <form className="card" onSubmit={e => submit(e, 'pilot', g => ({ customers: g('customers'), months: g('months'), lost: g('lost') }))}><h2>Pilot</h2><p className="small muted">Serve real paying customers for a few months. Measures churn (stage 6).</p><F n="customers" l="Paying customers" /><F n="months" l="Months" /><F n="lost" l="Customers who left" /><button className="primary">Add result</button></form>
        <form className="card" onSubmit={e => submit(e, 'ab', g => ({ name: 'A/B test', nA: g('nA'), kA: g('kA'), nB: g('nB'), kB: g('kB') }))}><h2>A/B test</h2><p className="small muted">Compare two versions (offer, page, price). Reports the chance B beats A.</p><div className="grid g2" style={{ gap: '0 8px' }}><F n="nA" l="A: visitors" /><F n="kA" l="A: conversions" /><F n="nB" l="B: visitors" /><F n="kB" l="B: conversions" /></div><button className="primary">Add result</button></form>
      </div>
      <div className="card"><h2>Results so far</h2>
        {d.experiments.length ? <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>{d.experiments.map((e: any, i: number) => <li key={i} className="row between" style={{ borderBottom: '1px solid var(--line)', padding: '8px 0' }}><span><Badge tone="good">Measured</Badge> {desc(e)}</span><button onClick={async () => setD(await api.removeExperiment(d.id, i))}>Remove</button></li>)}</ul> : <p className="muted">No results yet: every number is still an estimate.</p>}
        {ev.conversion && <p className="small" style={{ marginTop: 10 }}>Conversion belief Beta({ev.conversion.a}, {ev.conversion.b}): mean {pct(ev.conversion.mean, 2)}. Cost to win a customer now {aed(r.assumptions.cac.min)} to {aed(r.assumptions.cac.max)}.</p>}
        {ev.pain && <p className="small">Strong pain in {pct(ev.pain.mean)} of interviews, against {pct(ev.pain.prior)} in the simulated market.</p>}
        {ev.elasticity && <p className="small">Fitted price sensitivity: {ev.elasticity.toFixed(2)}.</p>}
        {ev.ab.map((a: any, i: number) => <p key={i} className="small">A/B: {pct(a.p_b_better)} chance B beats A; lift {pct(a.lift_mean)} (90% interval {pct(a.lift_ci[0])} to {pct(a.lift_ci[1])}).</p>)}
      </div>
    </div>
  );
}

function Audit({ d }: { d: any }) {
  const r = d.result, a = r.audit, f = r.stages.forecast;
  const [cal, setCal] = useState<any>(null); const [saved, setSaved] = useState('');
  useEffect(() => { api.calibration().then(setCal).catch(() => {}); }, []);
  return (
    <div className="stack">
      <div><h1>Audit: can you trust this?</h1><p className="lead">Checks that the answer is not built to please. The tool re-runs itself under hostile conditions and shows what changes.</p></div>
      <div className="grid g2">
        <div className="card"><h2>1. The simulated market never saw your idea</h2><p>{a.synthetic.note}</p><p className="small">Fingerprint <code>{a.synthetic.fingerprint}</code>: identical for any idea of this type and seed. {a.synthetic.check.passed ? <Badge tone="good">Population check passed</Badge> : <Badge tone="bad">Population check failed</Badge>} largest gap {pct(a.synthetic.check.max_gap, 1)}.</p>
          <details><summary>Population shares</summary><table><thead><tr><th>Group</th><th className="num">Target</th><th className="num">Simulated</th></tr></thead><tbody>{a.synthetic.check.rows.map((x: any, i: number) => <tr key={i}><td>{x.group}: {x.category}</td><td className="num">{pct(x.target)}</td><td className="num">{pct(x.actual, 1)}</td></tr>)}</tbody></table></details></div>
        <div className="card"><h2>2. Compared with an average business</h2>{a.base_rate ? <><p>An average {r.intake.business_type} plan in {r.intake.emirate}, built from category priors only, has a <b>{pct(a.base_rate.p_payback)}</b> payback chance. Yours: <b>{pct(f.p_payback)}</b>.</p><p className="small muted">If your plan only beats the average because of unverified claims, check point 3.</p></> : <p className="muted">Your analysis already uses category priors only, so it is the average business.</p>}</div>
        <div className="card"><h2>3. How much rests on claims?</h2>{a.claims_dependence ? <p>Remove every AI and founder number and the payback chance becomes <b>{pct(a.claims_dependence.p_payback_without_claims)}</b> ({a.claims_dependence.change >= 0 ? '+' : ''}{pct(a.claims_dependence.change)} from claims). {Math.abs(a.claims_dependence.change) > .2 ? 'A large share of the result depends on claims that are not yet measured.' : 'The result does not depend heavily on unverified claims.'}</p> : <p className="muted">No claims were added: nothing to remove.</p>}</div>
        <div className="card"><h2>4. Under heavy shocks</h2><p>With the shock level at “High”, the payback chance is <b>{pct(a.stress.p_payback)}</b> (now {pct(f.p_payback)}) and the chance of exceeding the budget is <b>{pct(a.stress.p_ruin)}</b>.</p></div>
        <div className="card"><h2>5. Concentration and optimism</h2><p>{pct(a.concentration.top_share)} of expected revenue comes from one segment ({a.concentration.top_segment}). {a.optimism_flags} assumption(s) flagged as optimistic by the Isolation Forest. {a.neutral_brief ? 'Agents worked from a neutral rewrite of your idea, so enthusiastic wording could not sway them.' : ''}</p></div>
        <div className="card"><h2>6. Monitoring: was it right?</h2><p className="small">Months later, record what happened. Across many ideas this measures calibration with the Brier score.</p>
          <div className="row"><button onClick={async () => { await api.outcome(d.id, { paid_back: true }); setSaved('Recorded: paid back.'); api.calibration().then(setCal); }}>It paid back</button><button onClick={async () => { await api.outcome(d.id, { paid_back: false }); setSaved('Recorded: did not pay back.'); api.calibration().then(setCal); }}>It did not</button></div>
          {saved && <p className="small" role="status">{saved}</p>}{cal && <p className="small muted">{cal.n ? `Brier score ${cal.brier.toFixed(3)} over ${cal.n} ideas (guessing the average scores ${cal.base_brier.toFixed(3)}).` : cal.note}</p>}</div>
      </div>
    </div>
  );
}

const EDIT_KEYS = ['price', 'var_pct', 'fixed', 'setup', 'cac', 'churn', 'capacity', 'p', 'q'];
function Sources({ d, setD }: { d: any; setD: (x: any) => void }) {
  const r = d.result, A = r.assumptions, ag = d.agents || {};
  const [edit, setEdit] = useState<any>(() => Object.fromEntries(EDIT_KEYS.map(k => [k, { min: A[k].min, likely: A[k].likely, max: A[k].max, label: ['founder', 'benchmarked', 'measured'].includes(A[k].label) ? A[k].label : 'founder', source: A[k].source, dirty: false }])));
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('');
  const up = (k: string, f: string, v: any) => setEdit({ ...edit, [k]: { ...edit[k], [f]: v, dirty: true } });
  const save = async () => {
    setErr('');
    const ov: any = {};
    for (const k of EDIT_KEYS) { const e = edit[k]; if (!e.dirty) continue; const v = [+e.min, +e.likely, +e.max]; if (v.some(x => !isFinite(x) || x < 0) || !(v[0] <= v[1] && v[1] <= v[2])) return setErr(`${A[k].name}: low ≤ likely ≤ high, all zero or more.`); ov[k] = { min: v[0], likely: v[1], max: v[2], label: e.label, source: e.source }; }
    if (!Object.keys(ov).length) return setErr('Change a value first.');
    try { const x = await api.apply(d.id, ov, {}); setD(x); setMsg('Recalculated with your edits.'); } catch (e: any) { setErr(e.message); }
  };
  const srcCount: number = Object.values(d.sources || {}).reduce((s: number, v: any) => s + v.length, 0) as number;
  return (
    <div className="stack">
      <div><h1>Assumptions and sources</h1><p className="lead">Every input, where it came from, and the raw research. If you have a real quote or an official figure, enter it as “Benchmarked” with its source.</p></div>
      <div className="card"><h2>Every assumption</h2>
        <div className="scroll"><table><thead><tr><th>Assumption</th><th>Now</th><th className="num">Low</th><th className="num">Likely</th><th className="num">High</th><th>New label</th><th>Source</th></tr></thead><tbody>
          {EDIT_KEYS.map(k => <tr key={k}><td><b>{A[k].name}</b><div className="tiny muted">{A[k].source}</div><Source url={A[k].url} /></td><td><LabelBadge label={A[k].label} /></td>
            {['min', 'likely', 'max'].map(f => <td key={f}><input type="number" step="any" value={edit[k][f]} onChange={e => up(k, f, e.target.value)} style={{ minWidth: 100 }} aria-label={`${A[k].name} ${f}`} /></td>)}
            <td><select value={edit[k].label} onChange={e => up(k, 'label', e.target.value)} style={{ minWidth: 150 }}>{['founder', 'benchmarked', 'measured'].map(l => <option key={l} value={l}>{LABEL[l]}</option>)}</select></td>
            <td><input value={edit[k].source} onChange={e => up(k, 'source', e.target.value)} style={{ minWidth: 180 }} aria-label={`${A[k].name} source`} /></td></tr>)}
        </tbody></table></div>
        {err && <p className="error">{err}</p>}{msg && <p className="small" role="status">{msg}</p>}
        <div className="row" style={{ marginTop: 10 }}><button className="primary" onClick={save}>Recalculate</button><button onClick={async () => { setD(await api.reset(d.id)); setMsg('All edits undone.'); }}>Undo all edits</button></div>
      </div>
      {!Object.keys(ag).length && <div className="callout warn">This analysis ran without AI agents, so every input is a category prior. Add an Anthropic API key on the server to get web research with sources.</div>}
      {ag.regulation && <div className="card"><h2>Licence and approvals</h2><p><b>{ag.regulation.licence_type || 'Licence type not identified'}</b>{ag.regulation.authority && <> from {ag.regulation.authority}</>}. <Source url={ag.regulation.url} /></p>
        {ag.regulation.hard_blockers?.length ? <p className="error">Blockers: {ag.regulation.hard_blockers.join('; ')}</p> : null}
        <ul>{ag.regulation.approvals.map((x: any, i: number) => <li key={i}>{x.name}{x.note && `: ${x.note}`} <Source url={x.url} /></li>)}</ul>
        <p className="small muted">{ag.regulation.cost_aed?.min != null && `Cost about ${aed(ag.regulation.cost_aed.min)} to ${aed(ag.regulation.cost_aed.max)}. `}{ag.regulation.timeline_weeks?.min != null && `Timeline ${ag.regulation.timeline_weeks.min} to ${ag.regulation.timeline_weeks.max} weeks. `}{ag.regulation.notes}</p></div>}
      <div className="grid g2">
        {ag.competition && <div className="card"><h2>Competitors found</h2><table><tbody>{ag.competition.competitors.map((c: any, i: number) => <tr key={i}><td><b>{c.name}</b> <Badge tone="neutral">{c.type}</Badge><div className="small">{c.note}{c.price_point && ` · ${c.price_point}`}</div><Source url={c.url} /></td></tr>)}</tbody></table></div>}
        {ag.customer && <div className="card"><h2>What customers say</h2><ul style={{ paddingLeft: 18 }}>{ag.customer.evidence.slice(0, 10).map((e: any, i: number) => <li key={i} className="small" style={{ marginBottom: 6 }}>“{e.quote}” <Source url={e.url} /></li>)}</ul></div>}
        {ag.market && <div className="card"><h2>Market research</h2><p className="small">{ag.market.tam_reasoning}</p><ul>{ag.market.trends.map((t: any, i: number) => <li key={i} className="small">{t.text} <Source url={t.url} /></li>)}</ul></div>}
        {ag.finance && <div className="card"><h2>Cost research</h2><table><tbody>{ag.finance.cost_breakdown.map((c: any, i: number) => <tr key={i}><td>{c.item} <Source url={c.url} /></td><td className="num">{aed(c.monthly_aed)}</td></tr>)}</tbody></table><p className="small muted">{ag.finance.reasoning}</p></div>}
        {ag.usability && <div className="card"><h2>Customer journey</h2><ol>{ag.usability.flow_steps.map((s: any, i: number) => <li key={i}><b>{s.step}</b> <span className="small muted">{s.note}</span></li>)}</ol>{ag.usability.issues.map((x: any, i: number) => <p key={i} className="small"><Badge tone={x.severity >= 3 ? 'bad' : x.severity === 2 ? 'warn' : 'neutral'}>{['', 'Minor', 'Major', 'Critical'][x.severity]}</Badge> {x.issue} ({x.heuristic})</p>)}</div>}
      </div>
      {srcCount > 0 && <details><summary>All {srcCount} web sources the agents found</summary>{Object.entries(d.sources).map(([k, v]: any) => v.length ? <div key={k}><h3 style={{ marginTop: 12 }}>{AGENT_NAMES[k]}</h3><ul>{v.map((s: any, i: number) => { const u = safeUrl(s.url); return u ? <li key={i} className="small"><a href={u} target="_blank" rel="noopener noreferrer">{s.title || host(u)}</a></li> : null; })}</ul></div> : null)}</details>}
      {Object.keys(d.agent_errors || {}).length > 0 && <div className="callout warn">Some agents could not finish and used category priors: {Object.keys(d.agent_errors).map(k => AGENT_NAMES[k]).join(', ')}.</div>}
    </div>
  );
}

function MarketFunnel({ b }: { b: any }) {
  const last = (k: string) => b[k].p50[b[k].p50.length - 1];
  const still = last('customers'), left = last('left'), no = last('said_no'), un = last('unaware');
  const steps = [['People within reach', un + no + still + left], ['Heard about you', no + still + left], ['Bought at least once', still + left], ['Still customers', still]];
  return (
    <div role="img" aria-label="Customer funnel">
      {steps.map(([n, v]: any, i) => { const prev = i ? (steps[i - 1][1] as number) : v; return (
        <div key={n} style={{ margin: '6px 0' }}>
          <div className="row between small"><b>{n}</b><span className="num">{num(v)}{i > 0 && <span className="muted"> · {pct(v / Math.max(prev, 1), v / Math.max(prev, 1) < .1 ? 1 : 0)} of previous step</span>}</span></div>
          <div className="bar" style={{ height: 14 }}><i style={{ width: `${Math.max(1.5, Math.sqrt(v / Math.max(steps[0][1] as number, 1)) * 100)}%`, background: ['#9fb3f0', '#6f8ee6', '#3f66dd', '#2348d6'][i] }} /></div>
        </div>); })}
      <p className="tiny muted">Bar lengths use a square-root scale so small steps stay visible.</p>
    </div>
  );
}
