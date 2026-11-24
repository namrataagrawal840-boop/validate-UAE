"""Validation lab: hypotheses -> plans and materials -> recorded results -> expected vs actual.

Confidence and the forecast change only when a result is recorded (it becomes an experiment the engine
calibrates on and a ledger record). Suggestions, plans and materials never change any number.
"""
import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from app import evidence as EV
from app import lab as LB
from app import store
from app.funnel.validation import SUS_QUESTIONS
from ui import report
from ui import glossary as G
from ui.common import ss, esc, pct, aed, kpi, chart, section, soft, PLOT, LINE, refresh, add_experiment, remove_experiment, user_id

STATUS_TONE = {"planned": ("Planned", ""), "needs more data": ("Needs more data", "warn"), "inconclusive": ("Inconclusive", "info"),
               "validated": ("Validated", "good"), "invalidated": ("Disproved", "bad")}
KINDS_FOR = {"signup_rate": ["landing"], "price_acceptance": ["pricing", "vanwestendorp"], "pain_share": ["interviews"], "monthly_churn": ["pilot"],
             "task_success": ["usability"], "ab_b_better": ["ab"], "sales_growth": ["sales"]}
KIND_LABEL = {"landing": "Landing page", "pricing": "Pricing", "vanwestendorp": "Van Westendorp", "interviews": "Interviews", "pilot": "Pilot + NPS",
              "usability": "Usability (SUS)", "ab": "A/B test", "sales": "Real sales"}


def fmt(unit, v):
    return "–" if v is None else f"{v:.1%}" if unit in ("rate", "prob", "growth") else f"{v:g}"


def common_fields(prefix):
    c = st.columns([1, 1, 2])
    when = c[0].date_input("Date collected", dt.date.today(), max_value=dt.date.today(), key=f"{prefix}d")
    geo = c[1].selectbox("Where", list(EV.GEOGRAPHY), format_func=lambda g: EV.GEOGRAPHY[g][0], key=f"{prefix}g")
    url = c[2].text_input("Link to raw data (optional)", key=f"{prefix}u", placeholder="Google Sheet, form results, analytics…")
    lim = st.text_input("Limitations (optional)", key=f"{prefix}l", placeholder="e.g. recruited through one parents' WhatsApp group")
    return dict(date=when.isoformat(), geography=geo, source_url=url.strip()[:1000] if url.strip().startswith("http") else "", limitations=lim[:500] or None)


def result_form(kind, r, prefix, hid):
    def add(e, label):
        if extra["limitations"] is None: extra.pop("limitations")
        add_experiment({**e, **extra}, f"Recorded: {label}. Added to the evidence ledger; confidence and the forecast were recalculated.", hypothesis_id=hid)
    key = f"{prefix}{kind}"
    with st.form(key, clear_on_submit=False):
        if kind == "landing":
            c = st.columns(4); vi = c[0].number_input("Visitors", 0, key=key + "a"); si = c[1].number_input("Sign-ups", 0, key=key + "b")
            sp = c[2].number_input("Ad spend (AED)", 0.0, key=key + "c"); pr = c[3].number_input("Sign-ups expected to pay (%)", 1, 100, 30, key=key + "e")
        elif kind == "pricing":
            c = st.columns(3); p1 = c[0].number_input("Price A (AED)", 0.0, value=float(round(r["assumptions"]["price"]["likely"])), key=key + "a")
            n1 = c[1].number_input("Asked at A", 0, key=key + "b"); k1 = c[2].number_input("Accepted A", 0, key=key + "c")
            p2 = c[0].number_input("Price B (AED, optional)", 0.0, key=key + "e"); n2 = c[1].number_input("Asked at B", 0, key=key + "f"); k2 = c[2].number_input("Accepted B", 0, key=key + "h")
        elif kind == "vanwestendorp":
            txt = st.text_area("One respondent per line: too cheap, cheap, expensive, too expensive (AED a month). At least 5 lines.", placeholder="60, 100, 160, 220\n80, 120, 180, 250", key=key + "a")
        elif kind == "interviews":
            c = st.columns(2); n = c[0].number_input("People interviewed", 0, key=key + "a"); kk = c[1].number_input("Described a serious problem", 0, key=key + "b")
        elif kind == "pilot":
            c = st.columns(3); cu = c[0].number_input("Paying customers", 0, key=key + "a"); mo = c[1].number_input("Months", 0.0, key=key + "b"); lo = c[2].number_input("Customers who left", 0, key=key + "c")
            pm = c[0].number_input("Promoters (9-10)", 0, key=key + "e"); pa = c[1].number_input("Passives (7-8)", 0, key=key + "f"); de = c[2].number_input("Detractors (0-6)", 0, key=key + "h")
        elif kind == "usability":
            c = st.columns(3); us = c[0].number_input("Users tested", 1, value=5, key=key + "a"); td = c[1].number_input("Tasks completed", 0, key=key + "b"); tt = c[2].number_input("Tasks attempted", 0, key=key + "c")
            sus = st.text_input("SUS scores, 0-100, comma-separated", placeholder="72.5, 80, 65", key=key + "e")
        elif kind == "ab":
            c = st.columns(4); na = c[0].number_input("A: visitors", 0, key=key + "a"); ka = c[1].number_input("A: conversions", 0, key=key + "b")
            nb = c[2].number_input("B: visitors", 0, key=key + "c"); kb = c[3].number_input("B: conversions", 0, key=key + "e")
        elif kind == "sales":
            txt = st.text_input("Monthly revenue in AED, oldest first (at least 4 months)", placeholder="12000, 15000, 17500, 21000", key=key + "a")
        extra = common_fields(key)
        go_ = st.form_submit_button("Record result", type="primary")
    if not go_: return
    try:
        if kind == "landing":
            assert vi > 0 and sp > 0 and si <= vi, "Visitors and spend must be above zero, and sign-ups cannot exceed visitors."
            add(dict(kind="landing", visitors=int(vi), signups=int(si), spend=float(sp), pay_rate=float(pr)), "landing-page test")
        elif kind == "pricing":
            pts = [dict(price=p, n=int(n_), k=int(k_)) for p, n_, k_ in ((p1, n1, k1), (p2, n2, k2)) if p > 0 and n_ > 0]
            assert pts and all(x["k"] <= x["n"] for x in pts), "Enter at least one price with people asked; accepted cannot exceed asked."
            add(dict(kind="pricing", points=pts), "pricing test")
        elif kind == "vanwestendorp":
            try:
                rows = [[float(x) for x in line.replace(";", ",").split(",")] for line in txt.strip().splitlines() if line.strip()]
            except ValueError:
                rows = []
            assert len(rows) >= 5 and all(len(x) == 4 and 0 < x[0] <= x[1] <= x[2] <= x[3] for x in rows), "Each line needs four prices in order (too cheap ≤ cheap ≤ expensive ≤ too expensive), at least 5 lines."
            add(dict(kind="vanwestendorp", rows=rows), "Van Westendorp survey")
        elif kind == "interviews":
            assert n > 0 and kk <= n, "Interview at least one person; serious-problem answers cannot exceed the number interviewed."
            add(dict(kind="interviews", n=int(n), k=int(kk)), "interviews")
        elif kind == "pilot":
            assert cu > 0 and mo > 0 and lo <= cu, "Enter customers and months above zero; leavers cannot exceed customers."
            e = dict(kind="pilot", customers=int(cu), months=float(mo), lost=int(lo))
            if pm + pa + de > 0: e.update(promoters=int(pm), passives=int(pa), detractors=int(de))
            add(e, "pilot")
        elif kind == "usability":
            try:
                sv = [float(x) for x in sus.replace(";", ",").split(",") if x.strip()]
            except ValueError:
                sv = [-1]
            assert tt > 0 and td <= tt and all(0 <= x <= 100 for x in sv), "Tasks attempted must be above zero and at least the tasks completed; SUS scores are 0 to 100."
            add(dict(kind="usability", users=int(us), tasks_done=int(td), tasks_total=int(tt), sus=sv), "usability test")
        elif kind == "ab":
            assert na > 0 and nb > 0 and ka <= na and kb <= nb, "Visitors must be above zero and conversions cannot exceed visitors."
            add(dict(kind="ab", name="A/B test", nA=int(na), kA=int(ka), nB=int(nb), kB=int(kb)), "A/B test")
        elif kind == "sales":
            try:
                sv = [float(x) for x in txt.replace(";", ",").split(",") if x.strip()]
            except ValueError:
                sv = []
            assert len(sv) >= 4 and min(sv) >= 0, "Enter at least 4 months of sales, none negative."
            add(dict(kind="sales", sales=sv), "sales data")
    except AssertionError as e:
        st.error(str(e))


def upload_form(hid, prefix):
    with st.form(f"{prefix}up", clear_on_submit=True):
        st.caption("Attach the raw material behind a result: survey export, interview notes, screenshots, receipts. It goes into the evidence ledger, linked to this hypothesis.")
        claim = st.text_input("What it shows *", key=f"{prefix}uc")
        c = st.columns(3)
        typ = c[0].selectbox("Type", ["feedback", "behaviour", "transactions", "secondary"], format_func=lambda t: EV.TYPES[t][0], key=f"{prefix}ut")
        n = c[1].number_input("Sample size", 0, key=f"{prefix}un")
        area = c[2].selectbox("Area", list(EV.AREAS), format_func=lambda a: EV.AREAS[a][0], key=f"{prefix}ua")
        f = st.file_uploader("File (5 MB max)", type=["pdf", "png", "jpg", "jpeg", "csv", "xlsx", "docx", "txt"], key=f"{prefix}uf")
        go_ = st.form_submit_button("Upload to ledger")
    if go_:
        if len(claim.strip()) < 5 or not f: st.error("Describe what it shows and choose a file."); return
        blob = f.getvalue()
        if len(blob) > store.MAX_FILE_BYTES: st.error("The file is larger than 5 MB."); return
        store.add_evidence(user_id(), ss.pid, dict(claim=claim.strip()[:500], area=area, description=f"Uploaded in the Validation lab: {f.name}", file_name=f.name[:200],
                                                  file_mime=f.type, collected_on=dt.date.today().isoformat(), geography="target", ev_type=typ, sample_size=int(n) or None,
                                                  verification="partly", confidence="medium", limitations="Self-reported upload.", hypothesis_id=hid), file_bytes=blob)
        refresh("File added to the evidence ledger.")


def compare_chart(h, ev):
    unit = ev["unit"]
    fig = go.Figure()
    xs = ["Expected by the model", "Your threshold", "Actual result"]
    ys = [ev["expected"] or 0, ev["threshold"], ev["actual"] or 0]
    cols = ["#c9cff7", "#f2e6b6", "#bfe3cf" if ev["status"] == "validated" else "#f3c9d1" if ev["status"] == "invalidated" else "#d6e6fa"]
    fig.add_trace(go.Bar(x=xs, y=ys, marker_color=cols, text=[fmt(unit, v) if (i < 2 or ev["actual"] is not None) else "no data" for i, v in enumerate(ys)], textposition="outside", cliponaxis=False))
    fig.update_layout(**{**PLOT, "height": 220}, yaxis=dict(visible=False, range=[0, max(ys + [0.01]) * 1.3]), showlegend=False)
    chart(fig)


def hypothesis_card(h, r, state, kit):
    ev = LB.evaluate(dict(h, price=r["assumptions"]["price"]["likely"]), state.get("experiments") or [])
    if ev["status"] != h["status"]:
        store.update_hypothesis(user_id(), ss.pid, h["id"], dict(status=ev["status"])); h["status"] = ev["status"]
    label, area, method, direction, unit, _ = LB.METRICS[h["metric"]]
    t, tone = STATUS_TONE[ev["status"]]
    with st.container(border=True):
        a, b = st.columns([4, 1.2])
        a.markdown(f"**{esc(h['statement'])}**  \n<span class='pill p-{tone}'>{t}</span><span class='pill'>{esc(label)} {direction} {fmt(unit, h['threshold'])}</span>"
                   f"<span class='pill p-lav'>{esc(LB.METHOD_LABEL[method])}</span>", unsafe_allow_html=True)
        b.markdown(f"<div style='text-align:right'><span class='muted' style='font-size:12.5px'>Data collected</span><br><b>{ev['n']:,}</b> / {ev['needed']:,} needed</div>", unsafe_allow_html=True)
        tabs = st.tabs(["Expected vs actual", "Plan", "Materials", "Record results", "Upload evidence", "Settings"])
        with tabs[0]:
            c1, c2 = st.columns([1.2, 1])
            with c1: compare_chart(h, ev)
            with c2:
                if ev["actual"] is None:
                    st.markdown(soft("No results yet. Nothing has changed: confidence and the forecast move only when you record a result.", "butter"), unsafe_allow_html=True)
                else:
                    st.markdown(f"**Actual:** {fmt(unit, ev['actual'])} <span class='muted'>({esc(ev['detail'])})</span>", unsafe_allow_html=True)
                    if ev["probability"] is not None:
                        st.markdown(f"**Chance the true value meets the threshold:** {pct(ev['probability'])}")
                    if ev["vs_expected"] is not None:
                        st.markdown(f"**Compared with the model's expectation:** {ev['vs_expected']:+.0%}")
                    st.caption("Validated at 90% or more, disproved at 10% or less. Below the planned sample the status stays 'needs more data' unless the result is already decisive.")
        with tabs[1]:
            p = h.get("plan") or LB.plan(h, r, kit)
            st.markdown(f"**Goal:** {esc(p['goal'])}  \n**Method:** {p['method']} · **Success if:** {p['success']} · **Sample:** {p['sample_size']:,} · "
                        f"**About {p['duration_weeks']} weeks**" + (f" · **Budget about {aed(p['budget_aed'])}**" if p["budget_aed"] else ""))
            st.markdown("\n".join(f"{i + 1}. {esc(s)}" for i, s in enumerate(p["steps"])))
            st.markdown(f"**Stop rule:** {esc(p['stop_rule'])}")
            st.markdown("**Avoid bias:** " + " · ".join(p["bias_checks"]))
            if st.button("Regenerate plan from the latest model", key=f"rp{h['id']}"):
                store.update_hypothesis(user_id(), ss.pid, h["id"], dict(plan=LB.plan(h, r, kit))); st.rerun()
        with tabs[2]:
            materials(h, r, kit)
        with tabs[3]:
            kinds = KINDS_FOR[h["metric"]]
            if len(kinds) == 1:
                result_form(kinds[0], r, f"h{h['id'][:8]}", h["id"])
            else:
                for kt, kd in zip(st.tabs([KIND_LABEL[k] for k in kinds]), kinds):
                    with kt: result_form(kd, r, f"h{h['id'][:8]}", h["id"])
        with tabs[4]:
            upload_form(h["id"], f"u{h['id'][:8]}")
        with tabs[5]:
            with st.form(f"set{h['id']}"):
                stmt = st.text_area("Hypothesis", h["statement"])
                thr = st.number_input("Threshold" + (" (as a share, e.g. 0.30 = 30%)" if unit in ("rate", "prob", "growth") else ""), value=float(h["threshold"]), format="%.4f")
                st.caption("Changing the threshold after seeing results weakens the test. The original value is kept in the plan.")
                if st.form_submit_button("Save"):
                    store.update_hypothesis(user_id(), ss.pid, h["id"], dict(statement=stmt.strip()[:500], threshold=float(thr))); st.rerun()
            with st.popover("Delete hypothesis"):
                st.write("Results already recorded stay in the evidence ledger and the forecast.")
                if st.button("Yes, delete", key=f"dh{h['id']}", type="primary"):
                    store.delete_hypothesis(user_id(), ss.pid, h["id"]); st.rerun()


def materials(h, r, kit):
    q = LB.questionnaire(h, r, kit); sv = LB.survey(h, r, kit); lp = kit["landing"]
    t = st.tabs(["Interview questionnaire", "Survey", "Landing page and ads"])
    with t[0]:
        md = f"# {q['title']}\n\n{q['intro']}\n\n" + "\n".join(f"{i + 1}. {x}" for i, x in enumerate(q["questions"])) + f"\n\n**Scoring:** {q['scoring']}\n"
        st.markdown(md); st.download_button("Download questionnaire (.md)", md, file_name="interview-questionnaire.md", key=f"dq{h['id']}")
    with t[1]:
        md = f"# {sv['title']}\n\n**Screening**\n" + "\n".join(f"- {x}" for x in sv["screening"]) + "\n\n**Questions**\n" + "\n".join(f"{i + 1}. {x}" for i, x in enumerate(sv["questions"])) + f"\n\n{sv['note']}\n"
        st.markdown(md); st.download_button("Download survey (.md)", md, file_name="survey.md", key=f"ds{h['id']}")
    with t[2]:
        md = f"# {lp['headline']}\n\n{lp['subheadline']}\n\n" + "\n".join(f"- {b}" for b in lp["bullets"]) + f"\n\n**[{lp['cta']}]**\n\n## Ads for an A/B test\n" + "\n".join(f"- **{a['label']}**: {a['text']}" for a in kit["ads"])
        st.markdown(md); st.download_button("Download landing page copy (.md)", md, file_name="landing-page.md", key=f"dl{h['id']}")
    st.caption(("Written by the AI experiment writer." if kit.get("source") == "ai" else "Generated from templates and your inputs.") + " Materials never change confidence or the forecast.")


def page(r, state):
    kit = r["kit"]
    st.header("Validation lab")
    st.markdown(soft("Turn each risky assumption into a hypothesis with a number, run a cheap test, and record what happened. "
                     "<b>Confidence and the forecast change only when you record real results</b>: suggestions, plans and materials change nothing.", "lavender"), unsafe_allow_html=True)
    hyps = store.list_hypotheses(user_id(), ss.pid)
    evs = [LB.evaluate(dict(h, price=r["assumptions"]["price"]["likely"]), state.get("experiments") or []) for h in hyps]
    k = st.columns(4)
    kpi(k[0], 0, "Hypotheses", str(len(hyps)), "Each with a success threshold")
    kpi(k[1], 1, "Validated", str(sum(e["status"] == "validated" for e in evs)), "90%+ chance of meeting the threshold")
    kpi(k[2], 2, "Disproved", str(sum(e["status"] == "invalidated" for e in evs)), "Rethink the plan around these")
    kpi(k[3], 3, "Waiting for data", str(sum(e["status"] in ("planned", "needs more data", "inconclusive") for e in evs)), "Planned, running or inconclusive")
    G.expander(["Hypothesis", "Conversion rate", "Churn"])
    st.write("")
    existing = {h["metric"] for h in hyps}
    sug = [s for s in LB.suggestions(r) if s["metric"] not in existing]
    if sug:
        section("Suggested hypotheses", "peach", "Based on your biggest evidence gaps. Adding one creates a plan; it does not change any number.")
        cols = st.columns(min(len(sug), 3))
        for i, s in enumerate(sug[:3]):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"{esc(s['statement'])}  \n<span class='muted'>{esc(s['why'])}</span>", unsafe_allow_html=True)
                    if st.button("Add this hypothesis", key=f"sg{i}", width="stretch"):
                        h = dict(s, status="planned", direction=LB.METRICS[s["metric"]][3])
                        h["plan"] = LB.plan(dict(h, id="new"), r, kit)
                        store.add_hypothesis(user_id(), ss.pid, h); st.rerun()
    with st.expander("➕ Write your own hypothesis"):
        with st.form("newh"):
            stmt = st.text_area("Hypothesis *", placeholder="At least 40% of parents we interview will say finding a good Arabic tutor is a top-3 problem.")
            c = st.columns(2)
            metric = c[0].selectbox("What will you measure?", list(LB.METRICS), format_func=lambda m: LB.METRICS[m][0])
            thr = c[1].number_input("Success threshold (share, e.g. 0.40 = 40%)", 0.0, 1.0, .4, .01, format="%.3f")
            go_ = st.form_submit_button("Create hypothesis and plan", type="primary")
        if go_:
            if len(stmt.strip()) < 10: st.error("Write the hypothesis as one sentence with a number.")
            else:
                h = dict(statement=stmt.strip()[:500], metric=metric, area=LB.METRICS[metric][1], method=LB.METRICS[metric][2], threshold=float(thr),
                         expected=LB.expected_values(r)[metric], direction=LB.METRICS[metric][3], status="planned")
                h["plan"] = LB.plan(dict(h, id="new"), r, kit)
                store.add_hypothesis(user_id(), ss.pid, h); st.rerun()
    if hyps:
        section("Your hypotheses", "mint")
        for h in hyps: hypothesis_card(h, r, state, kit)
    with st.expander("Record a result that is not tied to a hypothesis"):
        kinds = list(KIND_LABEL)
        for tb, kd in zip(st.tabs([KIND_LABEL[k] for k in kinds]), kinds):
            with tb: result_form(kd, r, "free", None)
        with st.expander("SUS calculator: score one tester's 10 answers"):
            ans = [st.select_slider(f"{i + 1}. {q}", [1, 2, 3, 4, 5], 3, key=f"sus{i}") for i, q in enumerate(SUS_QUESTIONS)]
            st.markdown(f"**SUS score: {sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(ans)) * 2.5:.1f}**")
    section("All recorded results", "sky")
    ex = state.get("experiments") or []
    if not ex: st.caption("No results yet: every number in the plan is still an estimate.")
    names = {h["id"]: h["statement"][:60] for h in hyps}
    for i, e in enumerate(ex):
        c1, c2 = st.columns([6, 1])
        link = f" · for “{esc(names[e['hypothesis_id']])}”" if e.get("hypothesis_id") in names else ""
        c1.markdown(f"<span class='pill p-good'>Measured</span> **{KIND_LABEL.get(e['kind'], e['kind'])}** · {esc(e.get('date', ''))}{link}<br><span class='muted'>"
                    + esc(", ".join(f"{a}={b}" for a, b in e.items() if a not in ('kind', 'rows', 'points', 'sales', 'sus', 'id', 'hypothesis_id', 'date', 'geography', 'source_url', 'limitations'))[:160])
                    + "</span>", unsafe_allow_html=True)
        if c2.button("Remove", key=f"rmx{i}"):
            remove_experiment(i)
    report.experiment_charts(r)
