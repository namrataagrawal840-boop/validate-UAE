"""Full details of one simulated future (bad, typical or good case): what it assumed, what happened, month by month.

Each case is one complete future out of all those simulated. The computer drew its costs and conditions from
the plan's ranges, then played out every month customer by customer. Showing the whole future explains
results that look odd at first, such as a "good" case that pays back later than the typical one.
"""
import csv
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.common import esc, aed, pct, approx, chart, soft, section, PLOT, months, kpi

NAMES = {"bad": ("Bad case", "10th"), "typical": ("Typical case", "50th"), "good": ("Good case", "90th")}
ROWS = [  # input key, label, plan assumption key, unit, what it covers
    ("arpu", "Spend per customer", "price", "AED/month", "What one customer pays you each month"),
    ("fixed", "Fixed costs", "fixed", "AED/month", "Rent, staff, licence and other costs you pay every month whatever you sell"),
    ("setup", "Setup cost", "setup", "AED", "One-off: fit-out, equipment, deposits, licence, launch"),
    ("cac", "Marketing cost per customer won", "cac", "AED", "Paid when each new customer is won"),
    ("var_pct", "Variable costs", "var_pct", "% of sales", "Ingredients, delivery, platform and card fees"),
    ("churn", "Customers leaving each month", "churn", "%", "Monthly churn; the rest stay"),
    ("capacity", "Most customers you can serve", "capacity", "customers", "Above this, new customers are turned away"),
    ("market", "Buyers within reach", None, "people", "People who would consider buying if they heard of you"),
    ("p", "Pull from marketing", "p", "", "Monthly chance an unaware person hears of you from marketing"),
    ("q", "Word of mouth", "q", "", "How strongly happy customers spread the word"),
    ("satisfaction", "Customer satisfaction", None, "0-1", "Happier customers stay longer and recommend you"),
]


def _fmt(v, unit):
    if v is None: return "–"
    if unit.startswith("AED"): return aed(v) + ("/month" if unit == "AED/month" else "")
    if unit in ("%", "% of sales"): return f"{v:.1f}%"
    if unit in ("customers", "people"): return approx(v)
    if unit == "0-1": return f"{v:.2f}"
    return f"{v:.3f}"


def why(s, r):
    """The three inputs where this future differs most from the plan, weighted by how much each moves the result."""
    A = r["assumptions"]; swing = {x["key"]: x["swing"] for x in r["finance"]["tornado"]["rows"]}
    plan = lambda k, ak: r["stages"]["classify"]["potential_used"] if k == "market" else (A[ak]["likely"] if ak and ak in A else None)
    good_up = {"arpu", "capacity", "market", "p", "q", "satisfaction"}
    out = []
    for k, label, ak, unit, _ in ROWS:
        pv, v = plan(k, ak), s["inputs"].get(k)
        if not pv or v is None: continue
        d = v / pv - 1
        if abs(d) < .05: continue
        helps = (d > 0) == (k in good_up)
        out.append((abs(d) * swing.get(k, 0), f"{label} {'higher' if d > 0 else 'lower'} than planned ({_fmt(v, unit)} vs {_fmt(pv, unit)}): {'helped' if helps else 'hurt'}"))
    return [t for _, t in sorted(out, reverse=True)[:4]]


@st.dialog("Case details", width="large")
def show(key, r):
    s = r["finance"]["scenarios"][key]; name, pctl = NAMES[key]
    T = len(s["monthly"]["cash"]); tot = s.get("totals") or {}; story = s.get("story") or {}
    st.subheader(f"{name}: one complete simulated future")
    st.markdown(soft(f"The computer drew the costs and conditions below from your plan's ranges, then played out {T} months customer by customer. "
                     f"Out of all the futures simulated, this one ranks at the <b>{pctl} percentile by total value (NPV)</b>. "
                     "Cases are ranked by value, not by speed: a future that grows bigger can be worth more and still take longer to pay back, "
                     "because every new customer costs marketing money up front.", "lavender"), unsafe_allow_html=True)

    section("In short", "butter")
    pb = f"money back in **month {s['payback_month']}**" if s["payback_month"] else f"money **not back within {T} months**"
    st.markdown(f"Worth **{aed(s['npv'])}** over {T} months · {pb} · first profitable month: "
                f"{'month ' + str(s['break_even_month']) if s['break_even_month'] else 'never'} · "
                f"{'budget lasts' if s['budget_lasts'] else 'budget runs out'}.")
    w = why(s, r)
    if w:
        st.markdown("**Why it turned out this way** (biggest effect first):\n" + "\n".join(f"- {esc(x)}" for x in w))
    if story.get("events"):
        ev = [x for x in story["events"] if x["kind"] == "viral"]
        if ev: st.markdown(f"- A viral moment in month {ev[0]['month']} brought a burst of new customers.")

    section("What this future assumed vs your plan", "sky")
    A = r["assumptions"]; rows = []
    for k, label, ak, unit, what in ROWS:
        v = s["inputs"].get(k)
        if v is None: continue
        if k == "market": pv, rng_ = r["stages"]["classify"]["potential_used"], "–"
        elif ak and ak in A: pv, rng_ = A[ak]["likely"], f"{_fmt(A[ak].get('min'), unit)} – {_fmt(A[ak].get('max'), unit)}" if A[ak].get("min") is not None else "–"
        else: pv, rng_ = None, "–"
        diff = f"{(v / pv - 1) * 100:+.0f}%" if pv else "–"
        rows.append({"Assumption": label, "This future": _fmt(v, unit), "Your plan": _fmt(pv, unit), "Plan range": rng_, "Difference": diff, "What it covers": what})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=36 * (len(rows) + 1) + 4)
    churn = s["inputs"].get("churn")
    if churn:
        st.caption(f"Retention: each month {100 - churn:.0f}% of customers stay, so a customer stays about {100 / churn:.1f} months on average "
                   "(less when they are unhappy or the place is overcrowded).")

    section("What happened", "mint")
    src = story.get("sources") or {}
    won = tot.get("acquired") or 0
    k = st.columns(4)
    kpi(k[0], 0, "Customers won", approx(won), f"{src.get('word_of_mouth', 0) / max(won, 1):.0%} by word of mouth" if src else "")
    kpi(k[1], 1, "Most customers at once", approx(tot.get("customers_peak")), f"in month {tot.get('customers_peak_month')}")
    kpi(k[2], 2, "Customers at the end", approx(s["customers_end"]), f"after {T} months")
    kpi(k[3], 3, "Customers who left", approx(tot.get("lost")), f"{src.get('unhappy_left', 0) / max(src.get('left', 1), 1):.0%} of them unhappy" if src else "")
    k = st.columns(4)
    kpi(k[0], 1, "Total sales", aed(tot.get("revenue")), f"over {T} months")
    kpi(k[1], 2, "Marketing spent", aed(tot.get("marketing")), "winning new customers")
    kpi(k[2], 3, "Lowest cash", aed(s["lowest_cash"]), f"in month {s['lowest_cash_month']}")
    kpi(k[3], 0, "Cash at the end", aed(tot.get("final_cash")), "after paying back setup")
    if src.get("turned_away"):
        st.caption(f"About {approx(src['turned_away'])} would-be customers were turned away because the business was full.")

    section("Month by month", "peach")
    m = s["monthly"]; x = list(range(1, T + 1)); lab = months(T)
    ax = dict(tickmode="array", tickvals=x[::3], ticktext=lab[::3], title=None)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=m["new_customers"], name="New customers", marker_color="#c9d3f5"))
    if m.get("lost"): fig.add_trace(go.Bar(x=x, y=[-v for v in m["lost"]], name="Customers who left", marker_color="#f3c7cf"))
    fig.add_trace(go.Scatter(x=x, y=m["customers"], name="Active customers", line=dict(color="#4f5bd5", width=2.5)))
    cap = s["inputs"].get("capacity", 0)
    fig.add_trace(go.Scatter(x=[1, T], y=[cap, cap], mode="lines", name="Capacity", line=dict(color="#a5505f", dash="dot")))
    fig.update_layout(**{**PLOT, "height": 330, "margin": dict(l=10, r=10, t=40, b=10)}, barmode="relative", title="Customers", legend=dict(orientation="h", y=-0.2), xaxis=ax)
    chart(fig)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=m["profit"], name="Profit or loss that month", marker_color=["#bfe3d0" if v >= 0 else "#f3c7cf" for v in m["profit"]]))
    fig.add_trace(go.Scatter(x=x, y=m["cash"], name="Cumulative cash (after setup)", line=dict(color="#2b3047", width=2.5)))
    fig.add_trace(go.Scatter(x=[1, T], y=[0, 0], mode="lines", line=dict(color="#8a90a8", width=1), showlegend=False, hoverinfo="skip"))
    if s["payback_month"]:
        xm = s["payback_month"]
        lo_, hi_ = min(min(m["cash"]), min(m["profit"])), max(max(m["cash"]), max(m["profit"]))
        fig.add_trace(go.Scatter(x=[xm, xm], y=[lo_, hi_], mode="lines", name="Money back", line=dict(color="#3f8f72", dash="dash"), showlegend=False))
        fig.add_annotation(x=xm, y=1, yref="paper", text=f" Money back, month {xm}", showarrow=False, xanchor="left", font=dict(color="#3f8f72"))
    fig.update_layout(**{**PLOT, "height": 330, "margin": dict(l=10, r=10, t=40, b=10)}, title="Money (AED)", legend=dict(orientation="h", y=-0.2), xaxis=ax)
    chart(fig)

    if story:
        section("What happened along the way", "rose")
        evs = story.get("events") or []
        if evs:
            st.markdown("\n".join(f"- **Month {e['month']}:** {esc(e['label'])}" + (f" (lasts about {e['months']} months)" if e.get("months") else "") for e in evs))
        else:
            st.markdown("No shocks or competitor reactions in this future.")
        st.markdown(f"Economy: {story.get('months_in_boom', 0)} months of boom, {story.get('months_in_downturn', 0)} months of downturn, the rest normal.")

    tab = pd.DataFrame({"Month": range(1, T + 1), "Active customers": m["customers"], "New": m["new_customers"], "Left": m.get("lost") or [None] * T,
                        "Sales (AED)": m["revenue"], "Marketing (AED)": m["marketing"], "All costs (AED)": m["costs"], "Profit (AED)": m["profit"],
                        "Cumulative cash (AED)": m["cash"], "Economy": (story.get("economy") or [""] * T)})
    with st.expander("Every month as a table"):
        st.dataframe(tab.round(0), hide_index=True, width="stretch")
    b = io.StringIO(); tab.to_csv(b, index=False)
    st.download_button("Download this future (CSV)", b.getvalue(), file_name=f"{key}-case-future.csv")
    st.caption(f"Before month 1: setup {aed(s['setup'])} and pre-opening costs {aed(s['pre_opening'])}. "
               "This is one simulated future, not a forecast: the typical payback across all futures is shown on the Money page.")


def buttons(cols, r):
    """A 'See full details' button under each case card."""
    for col, key in zip(cols, ("bad", "typical", "good")):
        if col.button("See full details", key=f"case_{key}", width="stretch"):
            show(key, r)
