"""Version history, methods and calibration, and importing real results from other tools."""
import pandas as pd
import requests
import streamlit as st

from app import actuals_import as AI
from app import calibration as CAL
from app import compute as CO
from app import history as H
from app import methods as M
from app import public_data as PD
from app import store
from app.synth import market, check
from ui.common import ss, esc, pct, aed, section, soft, user_id, can_edit, refresh, approx


def history_page(r, state):
    st.header("Version history")
    st.markdown(soft("Every recalculation is saved with what went in and what came out. Each version says what changed and whether the decision moved.", "lavender"),
                unsafe_allow_html=True)
    snaps = store.list_snapshots(user_id(), ss.pid)
    if not snaps:
        st.markdown("No versions yet: the next recalculation creates the first one."); return
    pm = lambda x: f"month {x}" if x else "beyond plan"
    for i, s in enumerate(snaps):
        older = snaps[i + 1]["summary"] if i + 1 < len(snaps) else None
        d = H.diff(s["summary"], older)
        sm = s["summary"]
        with st.container(border=True):
            a, b = st.columns([4, 2])
            a.markdown(f"**{esc(s['reason'])}**  \n<span class='muted' style='font-size:12.5px'>{esc(s['created_at'][:16].replace('T', ' '))} UTC · {esc(s['username'])}</span>",
                       unsafe_allow_html=True)
            b.markdown(f"<span class='pill p-{'warn' if d['moved'] else ''}'>{esc(sm.get('decision_label') or '–')}</span> payback {pm(sm.get('payback_typical'))} · evidence {pct(sm.get('confidence'))}",
                       unsafe_allow_html=True)
            st.markdown("\n".join(f"- {esc(c)}" for c in d["changes"]))


def methods_page(r, state):
    st.header("Methods, limits and calibration")
    st.markdown(soft("How every number is worked out, what each model assumes, its limits and the published method behind it. "
                     "Then three checks on the model itself: is the simulated population calibrated, how much does the answer move by chance, "
                     "and how well have past forecasts matched real results?", "lavender"), unsafe_allow_html=True)
    section("Model card", "lavender")
    for m in M.MODELS:
        with st.expander(m["name"]):
            st.markdown(f"**What it does.** {esc(m['what'])}\n\n**Assumes.** {esc(m['assumes'])}\n\n**Limits.** {esc(m['limits'])}")
            if m["refs"]: st.markdown("**References.** " + "; ".join(esc(x) for x in m["refs"]))
    section("Known limits", "rose")
    st.markdown("\n".join(f"- {esc(x)}" for x in M.LIMITS))
    v = PD.vintage()
    if v["stale"]:
        st.warning("Published figures more than two years old (still used, flagged so you can replace them): " +
                   "; ".join(f"{x['source']} ({x['year']})" for x in v["stale"]))

    section("Is the simulated population calibrated?", "mint")
    c = check(market(int(r["settings"]["seed"]), r["intake"]["business_type"]))
    st.caption(c.get("note", ""))
    st.dataframe(pd.DataFrame([{"Group": x["group"], "Category": x["category"], "Target": pct(x["target"], 1), "Simulated": pct(x["actual"], 1),
                                "Gap": f"{(x['actual'] - x['target']) * 100:+.1f} pts", "Target from": x.get("source", "")} for x in c["rows"]]),
                 hide_index=True, width="stretch")
    st.markdown(f"Largest gap: **{c['max_gap'] * 100:.1f} points** across {c['n']:,} simulated people ({'passes' if c['passed'] else 'fails'} the 2-point check).")

    section("How much does the answer move by chance?", "sky")
    st.caption("Reruns the forecast with five different random seeds. A small spread means the verdict comes from the inputs, not from luck.")
    if st.button("Run the stability check (about 15 seconds)"):
        with st.spinner("Running five seeds…"):
            ss._stability = CO.stability(dict(ss.state, ledger=[{k: v_ for k, v_ in e.items() if k != "has_file"} for e in store.list_evidence(user_id(), ss.pid)]))
    sb = ss.get("_stability")
    if sb:
        st.dataframe(pd.DataFrame([{"Seed": x["seed"], "Paid back in time": pct(x["p_payback"]), "Budget risk": pct(x["p_ruin"]), "Expected value": aed(x["npv_mean"]),
                                    "Typical payback": f"month {round(x['payback_median'])}" if x["payback_median"] else "beyond plan"} for x in sb["runs"]]), hide_index=True, width="stretch")
        st.markdown(f"The share of futures paid back in time ranges from **{pct(sb['p_payback_min'])} to {pct(sb['p_payback_max'])}** "
                    f"({sb['p_payback_spread'] * 100:.0f} points). " + ("Stable: chance alone does not change the verdict." if sb["p_payback_spread"] < .1 else
                                                                         "Noticeable spread: treat verdicts near the 60% line as uncertain, or set SIM_MODE=full for more replays."))

    section("Calibration log: forecasts vs what really happened", "peach")
    projs = []
    for p in store.list_projects(user_id()):
        try:
            full = store.load_project(user_id(), p["id"]); acts = store.list_actuals(user_id(), p["id"])
        except store.NotFound:
            continue
        if acts: projs.append(dict(name=p["name"], baseline=full["baseline"], actuals=acts))
    cal = CAL.check(projs)
    if not cal["n"]:
        st.markdown("No project has logged real monthly results against a frozen forecast yet. Once you start monitoring and import or enter results, "
                    "each month is checked here: about 8 in 10 actuals should land inside the forecast's 10th-90th percentile band.")
    else:
        k = st.columns(3)
        k[0].metric("Actuals inside the band", pct(cal["inside"]), f"expected about {pct(cal['expected_inside'])}", delta_color="off")
        k[1].metric("Typical error vs the median path", pct(cal["median_abs_error"]) if cal["median_abs_error"] is not None else "–")
        k[2].metric("Data points", f"{cal['n']} from {cal['projects']} project(s)")
        st.markdown(f"**{esc(cal['verdict'])}** {esc(cal['bias'])}")
        with st.expander("Every data point"):
            st.dataframe(pd.DataFrame(cal["rows"]), hide_index=True, width="stretch")


def import_page(r, state):
    st.header("Import results")
    st.markdown(soft("Bring in monthly results from the tools you already use, instead of typing them. Upload a CSV export, or paste a Google Sheets link "
                     "shared as “anyone with the link”. Recognised automatically: Google Analytics 4, Stripe payments, Shopify orders, Meta Ads and Google Ads. "
                     "Any other sheet works too: pick the columns below.", "lavender"), unsafe_allow_html=True)
    if not can_edit():
        st.info("View-only access: the owner or an editor imports results."); return
    if not ss.get("baseline"):
        st.warning("Start monitoring first (Monitoring page) so the forecast is frozen; then imported months are compared with it.")
    src = st.radio("Source", ["Upload a CSV export", "Google Sheets link"], horizontal=True)
    df = None
    try:
        if src.startswith("Upload"):
            f = st.file_uploader("CSV file", type=["csv"])
            if f: df = AI.read(f.getvalue())
        else:
            url = st.text_input("Google Sheets link")
            if url and st.button("Load the sheet"):
                resp = requests.get(AI.sheet_csv_url(url), timeout=20)
                if not resp.ok: raise ValueError(f"Google returned HTTP {resp.status_code}: is the sheet shared as 'anyone with the link'?")
                ss._sheet = resp.content
            if ss.get("_sheet"): df = AI.read(ss._sheet)
    except (ValueError, pd.errors.ParserError, requests.RequestException) as e:
        st.error(f"Could not read it: {e}"); return
    if df is None: return
    preset = AI.detect(df)
    st.markdown(f"Recognised as **{preset}** · {len(df):,} rows")
    mp = AI.mapping(df, preset)
    with st.expander("Column mapping", expanded=preset == "Generic"):
        cols = ["(none)"] + list(df.columns)
        for fld in ["date", "revenue", "expenses", "customer", "visitors", "conversions", "marketing_spend", "status"]:
            cur = mp.get(fld)
            sel = st.selectbox(fld.replace("_", " ").capitalize(), cols, cols.index(cur) if cur in cols else 0, key=f"map_{fld}")
            mp[fld] = None if sel == "(none)" else sel
    try:
        mon = AI.monthly(df, mp)
    except ValueError as e:
        st.error(str(e)); return
    first = st.selectbox("Which calendar month was your first month of trading (plan month 1)?", [str(p) for p in mon.index], 0)
    rows = AI.to_plan_months(mon, first)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if rows and st.button(f"Save {len(rows)} month(s)", type="primary"):
        have = {int(a["month"]): a for a in store.list_actuals(user_id(), ss.pid)}
        for x in rows:
            old = have.get(x["month"], {})
            merged = {k: (x.get(k) if x.get(k) is not None else old.get(k)) for k in store.ACT_FIELDS}
            merged["month"] = x["month"]; merged["notes"] = x.get("notes")
            store.upsert_actual(user_id(), ss.pid, merged)
        store.log(user_id(), ss.pid, "Imported results", f"{len(rows)} months from {preset}")
        refresh(f"Imported {len(rows)} month(s) from {preset}.")
