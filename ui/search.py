"""Search demand: how many people in the UAE search for this each month, how it trends, and what ads would cost."""
import copy
import datetime as dt
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import search_demand as SD
from app import store
from ui.common import ss, esc, aed, pct, num, kpi, chart, section, soft, PASTEL, PLOT, LINE, refresh, user_id


def settings(r):
    ev = r["stages"]["experiments"]["evidence"]
    land = next((e for e in reversed(ss.state.get("experiments") or []) if e["kind"] == "landing"), None)
    return dict(landing_rate=float(r["stages"]["experiments"]["predicted_conversion"]), pay_rate=(land["pay_rate"] / 100 if land else .30),
                cac_assumed=float(r["assumptions"]["cac"]["likely"]), measured=bool(ev.get("landing")))


def summary_for(state, r, click_share=None):
    sd = state.get("search") or {}
    if not sd.get("rows") and not sd.get("trends"): return None
    st_ = settings(r)
    out = SD.analyse(sd.get("rows"), sd.get("trends"), st_["landing_rate"], st_["pay_rate"], click_share or sd.get("click_share", .05), st_["cac_assumed"])
    return SD.localise(out, r["intake"].get("emirate")) if out else out


def save(update, message, r):
    s = copy.deepcopy(ss.state); sd = s.setdefault("search", {}); sd.update(update); sd["updated"] = dt.date.today().isoformat()
    summ = summary_for(s, r)
    if sd.get("evidence_id"):
        try: store.delete_evidence(user_id(), ss.pid, evidence_id=sd["evidence_id"])
        except store.NotFound: pass
        sd["evidence_id"] = None
    if summ and summ.get("total"):
        exact = any("DataForSEO" in x for x in sd.get("sources", []))
        sd["evidence_id"] = store.add_evidence(user_id(), ss.pid, SD.evidence_record(summ, sd.get("sources", []), exact))
    refresh(message, s)


def page(r, state):
    st.header("Search demand")
    st.markdown(soft("How many people in the UAE already search Google for what you're offering. Searches are <b>real behaviour</b>: people looking for a "
                     "solution right now. Volumes come from Google Ads data; Google Trends shows whether interest is rising and when it peaks.", "lavender"), unsafe_allow_html=True)
    sd = state.get("search") or {}
    kws = sd.get("keywords") or SD.suggest_keywords(dict(r["intake"], idea=r["idea"]["brief"]), (r.get("competition") or {}).get("yours", []))
    d4s = bool(os.getenv("DATAFORSEO_LOGIN") and os.getenv("DATAFORSEO_PASSWORD")); serp = bool(os.getenv("SERPAPI_KEY"))
    with st.expander("➕ Get search data", expanded=not (sd.get("rows") or sd.get("trends"))):
        with st.form("kw"):
            txt = st.text_area("Search phrases (one per line). Edit them so they match what customers would really type; Arabic phrases are fine.", "\n".join(kws), height=180)
            a, b = st.columns(2)
            save_kw = a.form_submit_button("Save phrases")
            fetch = b.form_submit_button("Get exact volumes from Google Ads data", type="primary", disabled=not d4s,
                                         help="DataForSEO: about $0.09 per lookup; new accounts get $1 free." if d4s else "Add DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in the app's secrets.")
        new_kws = [k.strip() for k in txt.splitlines() if k.strip()][:200]
        if save_kw: save(dict(keywords=new_kws), "Search phrases saved.", r)
        if fetch:
            try:
                with st.spinner("Asking Google Ads data for monthly volumes…"):
                    rows = SD.dataforseo(new_kws, os.environ["DATAFORSEO_LOGIN"], os.environ["DATAFORSEO_PASSWORD"])
                save(dict(keywords=new_kws, rows=rows, sources=sorted(set(sd.get("sources", [])) | {"DataForSEO (Google Ads data)"})),
                     f"Got volumes for {len(rows)} phrases. Added to the evidence ledger.", r)
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not get volumes: {e}")
        t = st.tabs(["Free: Keyword Planner file", "Trends (seasonality)", "Where to get keys"])
        with t[0]:
            st.markdown("1. Open **ads.google.com** and sign in (creating an account is free; you don't have to run ads).  \n"
                        "2. Tools → **Keyword Planner** → **Get search volume and forecasts**.  \n"
                        "3. Paste the phrases above, set the location to **United Arab Emirates**, click **Get started**.  \n"
                        "4. Click **Download keyword ideas** → **.csv**, and upload the file here.  \n"
                        "Without ad spend Google shows ranges such as 1K-10K; the app keeps both ends of each range.")
            up = st.file_uploader("Keyword Planner export (.csv)", type=["csv"], key="kpcsv")
            if up and st.button("Import Keyword Planner file", type="primary"):
                try:
                    rows = SD.keyword_planner_csv(up.getvalue())
                    save(dict(rows=rows, sources=sorted(set(sd.get("sources", [])) | {"Google Keyword Planner"})), f"Imported {len(rows)} phrases. Added to the evidence ledger.", r)
                except (ValueError, UnicodeError) as e:
                    st.error(str(e))
        with t[1]:
            st.markdown(f"[Open these phrases in Google Trends (UAE, last 12 months)]({SD.trends_link(kws)}), then click the download arrow on "
                        "**Interest over time** and upload the CSV here. Trends shows *relative* interest (0-100), used for trend and seasonality only.")
            c1, c2 = st.columns(2)
            up2 = c1.file_uploader("Google Trends CSV", type=["csv"], key="trcsv")
            if up2 and c1.button("Import Trends file"):
                try:
                    save(dict(trends=SD.trends_csv(up2.getvalue()), sources=sorted(set(sd.get("sources", [])) | {"Google Trends"})), "Trends imported.", r)
                except ValueError as e:
                    c1.error(str(e))
            if c2.button("Fetch Trends automatically", disabled=not serp, help=None if serp else "Add SERPAPI_KEY (free plan: 250 searches a month)."):
                try:
                    save(dict(trends=SD.serpapi_trends(kws, os.environ["SERPAPI_KEY"]), sources=sorted(set(sd.get("sources", [])) | {"Google Trends"})), "Trends fetched.", r)
                except Exception as e:  # noqa: BLE001
                    c2.error(f"Could not fetch Trends: {e}")
        with t[2]:
            st.markdown("**Exact volumes, DataForSEO** (pay as you go, $1 free credit, about $0.09 per lookup): sign up at dataforseo.com → **API Access** → copy the API login and "
                        "password → in Streamlit **Settings → Secrets** add `DATAFORSEO_LOGIN = \"...\"` and `DATAFORSEO_PASSWORD = \"...\"`.  \n"
                        "**Trends, SerpApi** (free plan, 250 searches a month): sign up at serpapi.com → copy your key → add `SERPAPI_KEY = \"...\"`.")
    s = summary_for(state, r)
    if not s:
        st.markdown(soft("<b>No search data yet.</b> The quickest free route: the Keyword Planner file (about 5 minutes), or open Google Trends from the link above to look right away.", "butter"),
                    unsafe_allow_html=True)
        return
    stt = settings(r)
    st.caption(f"Sources: {', '.join(sd.get('sources', []))} · updated {sd.get('updated', '')}")
    if s.get("total") is not None:
        k = st.columns(4)
        tot = num(s["total"]) if not s.get("ranges") else f"{num(s['total_low'])}–{num(s['total_high'])}"
        kpi(k[0], 0, "Searches per month (UAE)", tot, f"for {s['n']} phrases · searches, not people")
        kpi(k[1], 1, "With buying intent", pct(s["buy_share"]), "Phrases like price, near me, best, book")
        kpi(k[2], 2, "Trend", ("–" if s.get("growth") is None and s.get("trend_change") is None else f"{(s.get('growth') if s.get('growth') is not None else s['trend_change']):+.0%}"),
            "vs a year ago" if s.get("growth") is not None else "second half vs first half of the year" if s.get("trend_change") is not None else "Needs 15 months of history or a Trends file")
        kpi(k[3], 3, "Cost per click on Google ads", aed(s["cpc_aed"]) if s.get("cpc_aed") else "–", f"Busiest month: {s['peak']} · quietest: {s['low_month']}" if s.get("peak") else "")
    elif s.get("trend_change") is not None:
        k = st.columns(2)
        kpi(k[0], 0, "Interest trend (Google Trends)", f"{s['trend_change']:+.0%}", "Second half of the year vs the first")
        kpi(k[1], 1, "Volumes", "Not yet", "Add a Keyword Planner file or DataForSEO")
    st.write("")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        with st.container(border=True):
            if s.get("monthly"):
                section("Searches by month", "sky")
                fig = go.Figure(go.Bar(x=[m["ym"] for m in s["monthly"]], y=[m["v"] for m in s["monthly"]], marker_color="#c9d9f3"))
                fig.update_layout(**{**PLOT, "height": 260}, yaxis=dict(gridcolor="#f1f2f7")); chart(fig)
                if s.get("swing", 0) > .4: st.caption(f"Strong seasonality: plan launches and ad spend around {s['peak']}, expect a dip in {s['low_month']}.")
            elif s.get("trend_points"):
                section("Interest over time (Google Trends, relative)", "sky")
                fig = go.Figure(go.Scatter(x=s["trend_dates"], y=s["trend_points"], line=dict(color=LINE, width=2.5)))
                fig.update_layout(**{**PLOT, "height": 260}, yaxis=dict(gridcolor="#f1f2f7")); chart(fig)
    with c2:
        with st.container(border=True):
            if s.get("top"):
                section("Top phrases", "mint")
                st.dataframe(pd.DataFrame([dict(Phrase=x["keyword"], **{"Searches/month": num(x["volume"]) if x["low"] == x["high"] else f"{num(x['low'])}–{num(x['high'])}"},
                                                **{"Cost per click": aed(x["cpc_aed"]) if x.get("cpc_aed") else "–"}) for x in s["top"]]), hide_index=True, width="stretch")
    if s.get("funnel"):
        with st.container(border=True):
            section("What search could bring you each month", "peach", "Searches × share of clicks you win × sign-up rate × share who pay. The three shares are assumptions you can change.")
            cs = st.slider("Share of these searches that click on you", .01, .30, float(sd.get("click_share", .05)), .01, format="%.2f",
                           help="A new business with ads typically wins a few percent of clicks; a top Google result wins more.")
            if abs(cs - sd.get("click_share", .05)) > 1e-9:
                s2 = copy.deepcopy(ss.state); s2.setdefault("search", {})["click_share"] = cs; store.save_project(user_id(), ss.pid, state=s2); ss.state = s2; st.rerun()
            f = s["funnel"]; k = st.columns(4)
            kpi(k[0], 0, "Searches", num(f["searches"]))
            kpi(k[1], 1, "Clicks to you", num(f["clicks"]), f"{pct(f['click_share'])} of searches (assumption)")
            kpi(k[2], 2, "Sign-ups", num(f["signups"]), f"{pct(f['landing_rate'], 1)} of clicks ({'measured' if stt['measured'] else 'model estimate'})")
            kpi(k[3], 3, "New customers per month", num(f["customers"]), f"{pct(f['pay_rate'])} of sign-ups pay (assumption)")
            if s.get("cost_per_customer"):
                chk = s.get("cac_check")
                msg = (f"With Google ads, each customer would cost about **{aed(s['cost_per_customer'])}** (cost per click {aed(s['cpc_aed'])} ÷ sign-up rate ÷ share who pay). "
                       f"Your plan assumes **{aed(stt['cac_assumed'])}**")
                msg += "." if chk is None else (": search ads look cheaper than planned." if chk < .8 else ": about the same." if chk <= 1.25 else ": search ads look more expensive than planned, so lean on cheaper channels.")
                st.markdown(msg)
                if st.button("Use this as evidence for the cost to win a customer", help="Adds a ledger record (secondary research) with this cost; the forecast is recalculated."):
                    store.add_evidence(user_id(), ss.pid, dict(claim=f"Google search ads: about AED {s['cost_per_customer']:,.0f} per paying customer", area="cac", ev_type="secondary",
                                                              description=f"Cost per click AED {s['cpc_aed']:.2f} from {', '.join(sd.get('sources', []))}; sign-up rate {f['landing_rate']:.1%}; {f['pay_rate']:.0%} pay.",
                                                              collected_on=dt.date.today().isoformat(), geography="uae", verification="partly", confidence="medium",
                                                              value_min=s["cost_per_customer"] * .6, value_likely=s["cost_per_customer"], value_max=s["cost_per_customer"] * 1.6,
                                                              limitations="Depends on the sign-up and paying rates; test with a small ad budget."))
                    refresh("Cost to win a customer updated from search ad prices.")
    if st.button("Delete search data"):
        s3 = copy.deepcopy(ss.state)
        if (s3.get("search") or {}).get("evidence_id"):
            try: store.delete_evidence(user_id(), ss.pid, evidence_id=s3["search"]["evidence_id"])
            except store.NotFound: pass
        s3.pop("search", None); refresh("Search data deleted.", s3)
