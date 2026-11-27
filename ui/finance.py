"""Financials: assumptions with their origin, three scenarios, break-even, cash runway, sensitivity and money-related evidence gaps."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import glossary as G
from ui.common import ss, esc, aed, pct, num, kpi, chart, section, kind_pill, PLOT, LINE, months

SC = [("bad", "Bad case", "rose", "#e3a3a8"), ("typical", "Typical case", "sky", LINE), ("good", "Good case", "mint", "#7cc4a2")]
UNITS = {"price": "AED/month", "var_pct": "% of revenue", "fixed": "AED/month", "setup": "AED", "cac": "AED", "churn": "%/month", "capacity": "customers", "p": "", "q": ""}


def nice(v):
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.1f}" if abs(v) >= 1 else f"{v:.3g}"


def fmt_input(k, v):
    return aed(v) if k in ("arpu", "fixed", "setup", "cac", "price") else f"{v:.1f}%" if k in ("var_pct", "churn") else f"{v:.0%}" if k == "satisfaction" else f"{v:.4f}" if k in ("p", "q") else num(v)


def page(r, state):
    F, A, u, L = r["finance"], r["assumptions"], r["unit"], r["limits"]
    sc = F["scenarios"]
    st.header("Financials")
    st.markdown('<p class="muted">Three scenarios taken from the market simulation (the replays at the 10th, 50th and 90th percentile of value), '
                'with break-even, cash runway and what moves the result most. Every input shows where it came from.</p>', unsafe_allow_html=True)
    k = st.columns(4)
    be = F["break_even"]; rw = F["runway"]
    kpi(k[0], 0, "Customers needed to break even", num(be["customers"]), f"Each brings {aed(be['contribution'])}/month after variable costs")
    kpi(k[1], 1, "Typical break-even month", f"Month {round(be['median_month'])}" if be["median_month"] else "Not within horizon",
        f"{pct(be['p_by_horizon'])} of replays break even")
    kpi(k[2], 2, "Chance the budget runs out", pct(rw["p_runs_out"]), f"Budget {aed(rw['budget'])}" + (f" · typically after {round(rw['median_months_if_runs_out'])} months" if rw["median_months_if_runs_out"] else ""))
    kpi(k[3], 3, "Cash to have ready", aed(rw["cash_need_p90"]), f"Covers 90% of replays · typical {aed(rw['cash_need_p50'])}")
    G.expander(["Break-even", "Payback", "Cash runway", "NPV", "ARPU", "CAC", "Churn"])

    section("Three scenarios", "sky", "Each is one complete simulated future, so its revenue, costs and cash add up")
    cols = st.columns(3)
    from ui.common import PASTEL
    for col, (key, name, colour, _) in zip(cols, SC):
        s = sc[key]; bg, bd, fg = PASTEL[colour]
        y1 = s["revenue_by_year"][0] if s["revenue_by_year"] else 0
        lines = [("Value (NPV)", aed(s["npv"])), ("Revenue in year 1", aed(y1)), ("Break-even month", f"Month {s['break_even_month']}" if s["break_even_month"] else "Not reached"),
                 ("Payback month", f"Month {s['payback_month']}" if s["payback_month"] else "Not reached"), ("Lowest cash", f"{aed(s['lowest_cash'])} (month {s['lowest_cash_month']})"),
                 ("Budget", "Lasts the whole horizon" if s["budget_lasts"] else "Used up by setup and pre-opening costs" if s["runway_months"] == 0 else f"Runs out after {s['runway_months']} month{'' if s['runway_months'] == 1 else 's'}"), ("Customers at the end", num(s["customers_end"]))]
        col.markdown(f'<div class="pcard" style="background:{bg};border-color:{bd}"><div style="font-weight:700;color:{fg};margin-bottom:6px">{name}</div>'
                     + "".join(f'<div style="display:flex;justify-content:space-between;font-size:14px;padding:2px 0"><span class="muted">{a}</span><b>{esc(b)}</b></div>' for a, b in lines)
                     + "</div>", unsafe_allow_html=True)
    from ui import case_detail
    case_detail.buttons(cols, r)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**Cash over time**")
            fig = go.Figure()
            n = len(sc["typical"]["monthly"]["cash"]); x = months(n)
            for key, name, _, col in SC:
                fig.add_trace(go.Scatter(x=x, y=sc[key]["monthly"]["cash"], name=name, line=dict(color=col, width=2.5 if key == "typical" else 2)))
            fig.add_hline(y=-L["budget"], line=dict(color="#d9a35a", dash="dash"), annotation_text="Budget limit", annotation_position="bottom left")
            fig.add_hline(y=0, line=dict(color="#c9ccd8", width=1))
            fig.update_layout(**{**PLOT, "height": 300}, legend=dict(orientation="h", y=-.2), yaxis=dict(gridcolor="#f1f2f7"))
            chart(fig)
    with c2:
        with st.container(border=True):
            st.markdown("**Monthly revenue and costs (typical case)**")
            m = sc["typical"]["monthly"]
            fig = go.Figure([go.Bar(x=x, y=m["revenue"], name="Revenue", marker_color="#bfe3cf"), go.Bar(x=x, y=[-c for c in m["costs"]], name="Costs", marker_color="#f3c9d1"),
                             go.Scatter(x=x, y=m["profit"], name="Profit", line=dict(color=LINE, width=2))])
            fig.update_layout(**{**PLOT, "height": 300}, barmode="relative", legend=dict(orientation="h", y=-.2), yaxis=dict(gridcolor="#f1f2f7"))
            chart(fig)
    with st.expander("Monthly figures (table and download)"):
        pick = st.radio("Scenario", [s[1] for s in SC], index=1, horizontal=True)
        key = next(s[0] for s in SC if s[1] == pick); m = sc[key]["monthly"]
        df = pd.DataFrame(dict(Month=months(len(m["revenue"])), Revenue=m["revenue"], Costs=m["costs"], **{"of which marketing": m["marketing"]}, Profit=m["profit"], Cash=m["cash"],
                               Customers=m["customers"], **{"New customers": m["new_customers"]}))
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button("Download CSV", df.to_csv(index=False), file_name=f"validateuae-{key}-scenario.csv", mime="text/csv")
        st.caption(f"Before month 1: setup {aed(sc[key]['setup'])} and pre-opening costs {aed(sc[key]['pre_opening'])} ({F['open_months']} months at half the fixed costs).")
        st.markdown("**Inputs this replay drew:** " + " · ".join(f"{k}: {fmt_input(k, v)}" for k, v in sc[key]["inputs"].items()))

    c1, c2 = st.columns([1.1, 1])
    with c1:
        with st.container(border=True):
            section("Sensitivity: what moves the value most", "peach")
            t = F["tornado"]; rows = t["rows"][:8][::-1]
            fig = go.Figure()
            fig.add_trace(go.Bar(y=[x["name"] for x in rows], x=[x["npv_at_low"] - t["base_npv"] for x in rows], base=t["base_npv"], orientation="h", name="Input at its low value", marker_color="#c9cff7"))
            fig.add_trace(go.Bar(y=[x["name"] for x in rows], x=[x["npv_at_high"] - t["base_npv"] for x in rows], base=t["base_npv"], orientation="h", name="Input at its high value", marker_color="#f3c9a8"))
            fig.add_vline(x=t["base_npv"], line=dict(color="#6b7189", width=1))
            fig.update_layout(**{**PLOT, "height": 360, "margin": dict(l=10, r=10, t=40, b=10)}, barmode="overlay", legend=dict(orientation="h", y=1.12, x=0), xaxis=dict(title="Expected value (NPV), AED", gridcolor="#f1f2f7"))
            chart(fig)
            with st.popover("How this is calculated"):
                st.markdown(f"NPV from all {r['stages']['forecast']['runs']} replays is regressed on the inputs each replay drew (R² = {t['r2']:.2f}). "
                            "Each bar moves one input from its 10th to its 90th percentile while the others stay at their average.")
                st.dataframe(pd.DataFrame([dict(Input=x["name"], Low=fmt_input(x["key"], x["low_value"]), High=fmt_input(x["key"], x["high_value"]),
                                                **{"NPV at low": aed(x["npv_at_low"]), "NPV at high": aed(x["npv_at_high"])}) for x in t["rows"]]), hide_index=True, width="stretch")
    with c2:
        with st.container(border=True):
            section("Money-related evidence gaps", "butter")
            gaps = [g for g in r["evidence"].get("gaps", []) if g["area"] in ("price", "cac", "churn", "fixed", "var_pct", "setup", "capacity", "market")]
            for g in gaps[:5]:
                st.markdown(f"**{esc(g['name'])}**: {pct(g['confidence'])} confidence  \n<span class='muted'>{esc(g['how'])}</span>", unsafe_allow_html=True)
            if not gaps: st.markdown("The money inputs are backed by evidence.")
    section("Financial assumptions", "lavender", "Facts, estimates and assumptions are labelled. Change them in Assumptions and sources or by adding evidence.")
    keys = ["price", "var_pct", "fixed", "setup", "cac", "churn", "capacity"]
    rows = "".join(f"<tr><td>{esc(A[k]['name'])}</td><td>{kind_pill(A[k]['label'])}</td><td style='text-align:right'>{nice(A[k]['min'])}</td><td style='text-align:right'><b>{nice(A[k]['likely'])}</b></td>"
                   f"<td style='text-align:right'>{nice(A[k]['max'])}</td><td class='muted'>{UNITS[k]}</td><td class='muted' style='font-size:12.5px'>{esc(A[k].get('source', ''))[:140]}</td></tr>" for k in keys)
    st.markdown("<table style='width:100%;border-collapse:collapse;font-size:14px'><tr class='muted' style='text-align:left'><th>Input</th><th>Kind</th><th style='text-align:right'>Low</th>"
                f"<th style='text-align:right'>Likely</th><th style='text-align:right'>High</th><th>Unit</th><th>Source</th></tr>{rows}</table>", unsafe_allow_html=True)
    st.caption(f"Derived: spend per customer {aed(u['arpu'])}/month (choice and spend models), lifetime value {aed(u['ltv'])}, lifetime value ÷ cost to win {u['ltv_cac']:.1f}×.")
