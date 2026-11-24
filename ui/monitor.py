"""Monitoring: enter real monthly results and compare them with the forecast frozen at launch."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import monitoring as MO
from app import store
from ui import glossary as G
from ui.common import ss, esc, pct, aed, num, kpi, chart, section, soft, PLOT, LINE, BAND, add_experiment, refresh, user_id

NAMES = {"revenue": "Revenue", "expenses": "Expenses", "customers": "Active customers", "conversion": "Conversion rate", "repeat": "Repeat purchase rate", "cac": "Cost to win a customer"}
GOOD = {"revenue": "above", "customers": "above", "conversion": "above", "repeat": "above", "expenses": "below", "cac": "better"}


def fmtv(k, v):
    return aed(v) if k in ("revenue", "expenses", "cac") else pct(v, 1) if k in ("conversion", "repeat") else num(v)


def band_chart(base, comp, key, band_key, title):
    b = base["bands"][band_key]; n = len(b["p50"])
    last = max([r["month"] for r in comp["rows"]] + [6]); n = min(n, max(12, last + 3))
    x = list(range(1, n + 1))
    fig = go.Figure([go.Scatter(x=x + x[::-1], y=b["p90"][:n] + b["p10"][:n][::-1], fill="toself", fillcolor=BAND, line=dict(width=0), name="Forecast band (bad to good)", hoverinfo="skip"),
                     go.Scatter(x=x, y=b["p50"][:n], line=dict(color=LINE, width=2, dash="dash"), name="Forecast (typical)")])
    pts = [(r["month"], r[key]["actual"], r[key]["flag"]) for r in comp["rows"] if key in r]
    if pts:
        fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="lines+markers", name="Actual", line=dict(color="#2b3047", width=2.5),
                                 marker=dict(size=9, color=["#3f8f72" if p[2] == "within" else "#a5505f" if p[2] != GOOD[key] else "#3f6fae" for p in pts])))
    fig.update_layout(**{**PLOT, "height": 300, "margin": dict(l=10, r=10, t=36, b=10)}, xaxis=dict(title="Month of trading", dtick=1 if n <= 18 else 3), yaxis=dict(gridcolor="#f1f2f7"), legend=dict(orientation="h", y=1.18, x=0))
    st.markdown(f"**{title}**"); chart(fig)


def page(r, state):
    st.header("Monitoring: actual results vs forecast")
    base = ss.get("baseline")
    if not base:
        st.markdown(soft("Once you start trading, enter your real monthly figures here and see how they compare with the forecast. "
                         "Starting monitoring <b>freezes today's forecast</b> as the baseline, so later changes to the plan don't move the goalposts. "
                         "Month 1 is your first month of trading.", "lavender"), unsafe_allow_html=True)
        if st.button("Start monitoring with today's forecast", type="primary"):
            b = MO.baseline(r); store.set_baseline(user_id(), ss.pid, b); ss.baseline = b; st.rerun()
        return
    rows = store.list_actuals(user_id(), ss.pid)
    comp = MO.compare(base, rows)
    st.caption(f"Baseline forecast frozen on {base['created_at'][:10]}. Month 1 = first month of trading.")
    k = st.columns(4)
    kpi(k[0], 0, "Months recorded", str(len(rows)), "Enter one row per month")
    kpi(k[1], 1, "Metrics on track", f"{comp['on_track']} of {comp['tracked']}" if comp["tracked"] else "–", "Within the forecast band, last 3 months")
    last = next((x for x in reversed(comp["rows"]) if "revenue" in x), None)
    kpi(k[2], 2, "Latest revenue vs forecast", f"{last['revenue']['deviation']:+.0%}" if last and last["revenue"]["deviation"] is not None else "–",
        f"Month {last['month']}: {aed(last['revenue']['actual'])} vs {aed(last['revenue']['expected'])}" if last else "No revenue entered yet")
    kpi(k[3], 3, "Cash runway now", "–" if comp["cash_now"] is None else ("Not burning cash" if comp["runway_months"] is None else f"{comp['runway_months']:.1f} months"),
        "" if comp["cash_now"] is None else f"Cash left about {aed(comp['cash_now'])} (budget − setup + results)")
    G.expander(["Conversion rate", "Repeat purchase rate", "CAC", "Cash runway"])
    for a in comp["alerts"]:
        st.warning(f"**{NAMES[a['metric']]}** has been off track in {a['months']} of the last 3 months recorded (average {a['deviation']:+.0%} vs forecast).")
    with st.expander("➕ Enter or update a month", expanded=not rows):
        with st.form("actual", clear_on_submit=True):
            c = st.columns(4)
            m = c[0].number_input("Month of trading *", 1, 120, (max([x["month"] for x in rows]) + 1) if rows else 1)
            rev = c[1].number_input("Revenue (AED)", 0.0, value=None, placeholder="optional")
            exp = c[2].number_input("All expenses (AED)", 0.0, value=None, placeholder="optional", help="Everything paid out this month, including marketing.")
            mk = c[3].number_input("of which marketing (AED)", 0.0, value=None, placeholder="optional")
            c = st.columns(4)
            cu = c[0].number_input("Active customers at month end", 0.0, value=None, placeholder="optional")
            nw = c[1].number_input("New customers this month", 0.0, value=None, placeholder="optional")
            rp = c[2].number_input("Repeat customers", 0.0, value=None, placeholder="optional", help="Last month's customers who bought again this month.")
            c2 = c[3]
            vi = c2.number_input("Website or store visitors", 0.0, value=None, placeholder="optional")
            c = st.columns([1, 3])
            cv = c[0].number_input("Visitors who bought or signed up", 0.0, value=None, placeholder="optional")
            notes = c[1].text_input("Notes", placeholder="e.g. Ramadan month, new ad campaign")
            go_ = st.form_submit_button("Save month", type="primary")
        if go_:
            errs = []
            if cv is not None and vi is not None and cv > vi: errs.append("Conversions cannot exceed visitors.")
            if (cv is None) != (vi is None): errs.append("Enter both visitors and conversions, or neither.")
            if mk is not None and exp is not None and mk > exp: errs.append("Marketing cannot exceed total expenses.")
            prev = next((x for x in rows if x["month"] == m - 1), None)
            if rp is not None and prev and prev.get("customers") is not None and rp > prev["customers"]: errs.append("Repeat customers cannot exceed last month's customers.")
            if all(v is None for v in (rev, exp, cu, nw, vi, rp, mk)): errs.append("Enter at least one figure.")
            if errs:
                for e in errs: st.error(e)
            else:
                store.upsert_actual(user_id(), ss.pid, dict(month=int(m), revenue=rev, expenses=exp, customers=cu, new_customers=nw, visitors=vi, conversions=cv,
                                                            repeat_customers=rp, marketing_spend=mk, notes=notes[:300]))
                ss.flash = f"Month {int(m)} saved."; st.rerun()
    if not rows: return
    c1, c2 = st.columns(2)
    with c1: band_chart(base, comp, "revenue", "revenue", "Revenue (AED)")
    with c2: band_chart(base, comp, "customers", "customers", "Active customers")
    c1, c2 = st.columns(2)
    with c1: band_chart(base, comp, "expenses", "costs", "Expenses (AED)")
    with c2:
        section("Rates and cost to win a customer", "peach")
        for key in ("conversion", "repeat", "cac"):
            pts = [x for x in comp["rows"] if key in x]
            if not pts: st.markdown(f"<span class='muted'>{NAMES[key]}: not entered yet.</span>", unsafe_allow_html=True); continue
            z = pts[-1][key]; tone = "good" if z["flag"] in ("within", GOOD[key]) else "bad"
            st.markdown(f"**{NAMES[key]}** (month {pts[-1]['month']}): {fmtv(key, z['actual'])} vs plan {fmtv(key, z['expected'])} "
                        f"<span class='pill p-{tone}'>{'on track' if z['flag'] == 'within' else z['flag'] + ' plan'}</span>", unsafe_allow_html=True)
    section("Month by month", "sky")
    table = []
    for x in comp["rows"]:
        row = {"Month": x["month"]}
        for key in NAMES:
            if key in x:
                z = x[key]; mark = "✓" if z["flag"] == "within" else ("▲" if z["flag"] in ("above", "worse") else "▼")
                row[NAMES[key]] = f"{fmtv(key, z['actual'])} ({z['deviation']:+.0%}) {mark}" if z["deviation"] is not None else f"{fmtv(key, z['actual'])} {mark}"
        row["Notes"] = x["notes"]; table.append(row)
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    st.caption("✓ within the forecast band · ▲ above · ▼ below. Percentages are the deviation from the typical forecast.")
    c = st.columns([1.4, 1.4, 1, 2])
    with c[0].popover("Delete a month", width="stretch"):
        dm = st.selectbox("Month", [x["month"] for x in rows])
        if st.button("Delete", type="primary"):
            store.delete_actual(user_id(), ss.pid, dm); st.rerun()
    series = MO.revenue_series(rows)
    with c[1].popover("Use as evidence", width="stretch", disabled=len(series) < 4):
        st.write(f"Add your {len(series)} months of revenue to the evidence ledger as observed transactions and recalibrate the forecast with them? "
                 "The frozen baseline stays as it is, so the comparison here does not change.")
        if st.button("Yes, add and recalculate", type="primary"):
            old = next((i for i, e in enumerate(state.get("experiments") or []) if e.get("id") == "monitoring-sales"), None)
            if old is not None:
                store.delete_evidence(user_id(), ss.pid, experiment_id="monitoring-sales"); ss.state["experiments"].pop(old)
            add_experiment(dict(id="monitoring-sales", kind="sales", sales=series, limitations="From your monitoring entries; check against bank statements."),
                           "Revenue history added as evidence; the forecast was recalibrated.")
    if len(series) < 4: c[1].caption("Needs 4 consecutive months from month 1.")
    with c[2].popover("Reset baseline", width="stretch"):
        st.write("Replace the frozen baseline with today's forecast? Your entered months are kept.")
        if st.button("Reset", type="primary"):
            b = MO.baseline(r); store.set_baseline(user_id(), ss.pid, b); ss.baseline = b; st.rerun()
