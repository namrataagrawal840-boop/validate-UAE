"""Market size: TAM, SAM and SOM built from published population figures, each step with its source."""
import copy

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import market_size as MZ
from app import store
from ui.common import ss, esc, aed, pct, num, kpi, chart, section, soft, PASTEL, PLOT, user_id

KIND = {"official": ("Official statistic", "good"), "published": ("Published survey or report", "info"), "assumption": ("Assumption", "warn"),
        "simulated": ("Simulated", "lav"), "yours": ("Your figure", "peach")}


def page(r, state):
    st.header("Market size")
    st.markdown('<p class="muted">How many people could buy this, built step by step from published UAE statistics. Every number shows where it comes from; '
                'replace any of them with a better figure and everything updates.</p>', unsafe_allow_html=True)
    ov = state.get("market_overrides") or {}
    m = MZ.size(r, ov, state.get("panel"))
    k = st.columns(4)
    kpi(k[0], 0, "TAM: total market", aed(m["tam"]["aed"]) + "/yr", f"{num(m['tam']['people'])} people who use this kind of service")
    kpi(k[1], 1, "SAM: you can reach", aed(m["sam"]["aed"]) + "/yr", f"{num(m['sam']['people'])} people within reach of one business")
    kpi(k[2], 2, "Interested in this idea", num(m["interested"]["people"]), "From the simulated customer panel")
    kpi(k[3], 3, "SOM: you can win", aed(m["som"]["aed"]) + "/yr", f"{num(m['som']['people'])} customers · {pct(m['som']['share_of_sam'], 1)} of SAM")
    from ui.search import summary_for as search_summary
    sdm = search_summary(state, r)
    if sdm and sdm.get("total"):
        st.markdown(soft(f"<b>Search demand check:</b> people in the UAE search Google for related phrases about "
                         f"{num(sdm['total']) if not sdm.get('ranges') else num(sdm['total_low']) + '–' + num(sdm['total_high'])} times a month "
                         f"({pct(sdm['buy_share'])} with buying intent). That is real, current demand behind the market estimate.", "mint"), unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns([1.25, 1])
    with c1:
        with st.container(border=True):
            section("From the whole population to your customers", "sky")
            labels = [s["label"].replace("…", "") for s in m["steps"]] + ["Customers you can win (SOM)"]
            vals = [s["people"] for s in m["steps"]] + [m["som"]["people"]]
            cols = ["#d6e6fa"] * (len(vals) - 4) + ["#c9cff7", "#d3ecdf", "#e3defb", "#bfe3cf"]
            fig = go.Figure(go.Funnel(y=labels, x=vals, textinfo="value", texttemplate="%{value:,.0f}", marker=dict(color=cols[-len(vals):]), connector=dict(line=dict(color="#eceef4"))))
            fig.update_layout(**{**PLOT, "height": 70 + 48 * len(vals)}, yaxis=dict(tickfont=dict(size=12.5, color="#2b3047")))
            chart(fig)
    with c2:
        with st.container(border=True):
            section("Where each number comes from", "mint")
            for s in m["steps"]:
                t, tone = KIND[s["kind"]]
                f = num(s["factor"]) if s["unit"] == "people" else (pct(s["factor"], 1) if s["factor"] < 1 else f"{s['factor']:.2f}")
                link = f' · <a href="{esc(s["url"])}" target="_blank">source</a>' if s.get("url") else ""
                st.markdown(f"**{esc(s['label'].replace('…', ''))}**: {f} <span class='pill p-{tone}'>{t}</span><br>"
                            f"<span class='muted' style='font-size:12.5px'>{esc(s['source'])}{(' (' + str(s['year']) + ')') if s.get('year') else ''}{link}</span>", unsafe_allow_html=True)
            sm = m["spend_meta"]; t, tone = KIND[sm["kind"]]
            st.markdown(f"**Spend per user**: {aed(m['spend_per_month'])}/month <span class='pill p-{tone}'>{t}</span><br><span class='muted' style='font-size:12.5px'>"
                        f"{esc(sm['source'])}{(' (' + str(sm['year']) + ')') if sm.get('year') else ''}" + (f' · <a href="{esc(sm["url"])}" target="_blank">source</a>' if sm.get("url") else "")
                        + "</span>", unsafe_allow_html=True)
            st.markdown(f"**SOM**: <span class='muted' style='font-size:12.5px'>{esc(m['som']['source'])}</span>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("Next three years", "peach", f"The market grows with the population: {pct(m['growth']['rate'], 1)} a year ({m['growth']['source']}, {m['growth']['year']})")
            pr = m["projection"]
            fig = go.Figure([go.Bar(x=[f"Year {p['year']}" if p["year"] else "Today" for p in pr], y=[p["tam_people"] for p in pr], name="TAM people", marker_color="#d6e6fa"),
                             go.Bar(x=[f"Year {p['year']}" if p["year"] else "Today" for p in pr], y=[p["sam_people"] for p in pr], name="SAM people", marker_color="#d3ecdf")])
            fig.update_layout(**{**PLOT, "height": 260, "margin": dict(l=10, r=10, t=36, b=10)}, legend=dict(orientation="h", y=1.18, x=0), yaxis=dict(gridcolor="#f1f2f7"))
            chart(fig)
            lo, hi = m["tam"]["range"]
            st.caption(f"TAM range from the published low and high usage rates: {num(lo)} to {num(hi)} people.")
    with c2:
        with st.container(border=True):
            section("Use your own figures", "butter", "Leave blank to keep the published or model value")
            with st.form("mkt_ov"):
                c = st.columns(2)
                vals = {}
                vals["population"] = c[0].number_input("People living in the area", 0.0, value=ov.get("population"), placeholder=f"{m['steps'][0]['people']:,.0f}")
                cat = next(s for s in m["steps"] if s["key"] == "category")
                vals["category"] = c[1].number_input("Share who use this kind of service (0-1)", 0.0, 1.0, value=ov.get("category"), placeholder=f"{cat['factor']:.3f}", format="%.3f")
                reach = next(s for s in m["steps"] if s["key"] == "reach")
                vals["reach"] = c[0].number_input("Share one business can reach (0-1)", 0.0, 1.0, value=ov.get("reach"), placeholder=f"{reach['factor']:.3f}", format="%.3f")
                vals["spend"] = c[1].number_input("Spend per user per month (AED)", 0.0, value=ov.get("spend"), placeholder=f"{m['spend_per_month']:,.0f}")
                a, b = st.columns(2)
                save = a.form_submit_button("Update", type="primary"); reset = b.form_submit_button("Back to published figures")
            if save or reset:
                st_ = copy.deepcopy(ss.state)
                st_["market_overrides"] = {} if reset else {k: v for k, v in vals.items() if v is not None}
                store.save_project(user_id(), ss.pid, state=st_); ss.state = st_; ss.flash = "Market size updated."; st.rerun()
    st.markdown(soft("<b>How to read this.</b> TAM is everyone in the area who already uses this kind of service, valued at what they spend. "
                     "SAM is the part one business like yours can realistically reach. SOM is how many you are likely to win, from the market simulation. "
                     "Official statistics and published surveys are facts about the market; assumptions and simulated figures are estimates you should test.", "lavender"),
                unsafe_allow_html=True)
