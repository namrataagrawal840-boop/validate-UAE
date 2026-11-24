"""Evidence ledger: every claim with its source, type, sample, verification and limits."""
import datetime as dt

import pandas as pd
import streamlit as st

from app import evidence as EV
from app import store
from ui import glossary as G
from ui.common import ss, esc, pct, kpi, hbars, section, soft, refresh, user_id

TYPE_TONE = {"transactions": "good", "behaviour": "good", "feedback": "info", "secondary": "lav", "ai": "", "synthetic": ""}
VER_TONE = {"verified": "good", "partly": "info", "unverified": "warn", "disputed": "bad"}
UNITS = {"price": "AED per customer per month", "var_pct": "% of revenue", "fixed": "AED per month", "setup": "AED one-off", "cac": "AED per customer",
         "churn": "% of customers per month", "capacity": "customers at once"}
FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "csv", "xlsx", "docx", "txt"]


def tag(text, tone):
    return f'<span class="pill p-{tone}">{esc(text)}</span>'


def page(r, state):
    ev = r["evidence"]; areas = ev["areas"]
    st.header("Evidence ledger")
    st.markdown('<p class="muted">Every claim the plan rests on, with where it came from and how far to trust it. Only real-world evidence raises confidence: '
                'AI estimates and simulations are listed for transparency but carry zero weight and never count as customer behaviour.</p>', unsafe_allow_html=True)
    rows = store.list_evidence(user_id(), ss.pid)
    real = [x for x in rows if EV.is_real(x)]
    hyps = store.list_hypotheses(user_id(), ss.pid)
    k = st.columns(4)
    kpi(k[0], 0, "Evidence confidence", pct(ev["strength"]), "Weighted by how much each area matters")
    kpi(k[1], 1, "Real-world records", str(len(real)), "Transactions, behaviour, feedback, research")
    kpi(k[2], 2, "AI and simulated records", str(len(rows) - len(real)), "Stored, zero weight")
    covered = sum(1 for a in areas.values() if a["importance"] > 0 and a["confidence"] >= .5)
    kpi(k[3], 3, "Areas with solid evidence", f"{covered} of {sum(1 for a in areas.values() if a['importance'] > 0)}", "Confidence of 50% or more")
    st.write("")
    c1, c2 = st.columns([1.1, 1])
    with c1:
        with st.container(border=True):
            section("Confidence by area", "mint")
            hbars([(a["name"], a["confidence"]) for k_, a in areas.items() if a["importance"] > 0], color="#bfe3cf", xmax=1)
            with st.popover("How confidence is calculated"):
                st.markdown("Each record's weight = **type × verification × your confidence × geography × sample size × recency**.\n\n"
                            "Type: observed transactions 1.0, observed behaviour 0.85, direct feedback 0.6, secondary research 0.4, AI estimate 0, synthetic simulation 0.  \n"
                            "Verification: verified 1.0, partly 0.6, not yet 0.3, disputed 0.  \nConfidence: high 1.0, medium 0.7, low 0.4.  \n"
                            "Geography: your target area 1.0, elsewhere in the UAE 0.85, GCC 0.6, outside the GCC 0.35.  \n"
                            "Sample size (for transactions, behaviour and feedback): 1 − e^(−n/20). Recency: older than 1 year ×0.8, 2 years ×0.6.\n\n"
                            "Records in one area combine as independent signals: 1 − Π(1 − weight). An area is never below the credit its input already has "
                            "(measured 1.0, your source 0.6, web source 0.25, your own assumption 0.1, AI or typical figures 0). "
                            "Overall confidence is the importance-weighted average, minus 5 points for each assumption flagged as optimistic.")
    with c2:
        with st.container(border=True):
            section("Biggest evidence gaps", "peach", "Where missing evidence matters most for the decision")
            for g in ev.get("gaps", [])[:5]:
                st.markdown(f"**{esc(g['name'])}** {tag(pct(g['confidence']) + ' confidence', 'warn' if g['confidence'] < .3 else 'info')}<br><span class='muted'>{esc(g['how'])}</span>", unsafe_allow_html=True)
            if not ev.get("gaps"): st.markdown("No major gaps left.")
    add_form(hyps)
    st.subheader(f"Records ({len(rows)})")
    if not rows:
        st.caption("No records yet. Add evidence above, or record results in the Validation lab (they are added here automatically).")
    flt = st.segmented_control("Show", ["All", "Real-world", "AI and simulated"], default="All", key="ev_filter")
    for x in rows:
        if flt == "Real-world" and not EV.is_real(x): continue
        if flt == "AI and simulated" and EV.is_real(x): continue
        record(x, hyps)
    with st.expander("What the AI agents and the simulation contributed (for transparency; zero weight)"):
        st.caption("These are generated, not observed. They are never used as evidence of what customers do.")
        sys_rows = EV.system_records(r, state)
        st.dataframe(pd.DataFrame([dict(Claim=x["claim"], Type=EV.TYPES[x["ev_type"]][0], Area=EV.AREAS.get(x["area"], ("Other",))[0], Source=x.get("source_url") or x["description"][:80],
                                        Limitations=x["limitations"]) for x in sys_rows]), hide_index=True, width="stretch")


def record(x, hyps):
    w, parts = EV.weight(x)
    real = EV.is_real(x)
    with st.container(border=True):
        a, b = st.columns([5, 1.3])
        a.markdown(f"**{esc(x['claim'] or 'Untitled claim')}**  \n"
                   f"{tag(EV.TYPES.get(x['ev_type'], ('Unknown',))[0], TYPE_TONE.get(x['ev_type'], ''))}"
                   f"{tag(EV.VERIFICATION.get(x['verification'] or 'unverified', ('',))[0], VER_TONE.get(x['verification'] or 'unverified', ''))}"
                   f"{tag(EV.AREAS.get(x['area'], ('Other',))[0], '')}"
                   + (tag("From the Validation lab", "lav") if x.get("experiment_id") else ""), unsafe_allow_html=True)
        b.markdown(f"<div style='text-align:right'><span class='muted' style='font-size:12.5px'>Weight</span><br><b>{w:.2f}</b></div>", unsafe_allow_html=True)
        if not real:
            st.markdown(soft("<b>Not evidence of customer behaviour.</b> AI estimates and simulations are kept for reference and carry zero weight.", "butter"), unsafe_allow_html=True)
        meta = [f"Collected {esc(x['collected_on'] or '–')}", EV.GEOGRAPHY.get(x["geography"] or "uae", ("",))[0],
                f"Sample {x['sample_size']}" if x.get("sample_size") else "No sample size", f"Your confidence: {EV.CONFIDENCE.get(x['confidence'] or 'medium', ('',))[0]}"]
        st.markdown(f"<span class='muted'>{' · '.join(meta)}</span>", unsafe_allow_html=True)
        if x.get("description"): st.markdown(esc(x["description"]))
        if x.get("value_likely") is not None:
            st.markdown(f"<span class='muted'>Value used in the forecast:</span> {x['value_min'] if x['value_min'] is not None else '–'} / **{x['value_likely']:g}** / {x['value_max'] if x['value_max'] is not None else '–'} {UNITS.get(x['area'], '')}", unsafe_allow_html=True)
        if x.get("limitations"): st.markdown(f"<span class='muted'>Limitations: {esc(x['limitations'])}</span>", unsafe_allow_html=True)
        c = st.columns([1.2, 1.2, 1.2, 1, 3])
        if x.get("source_url", "").startswith("http"): c[0].link_button("Open source", x["source_url"], width="stretch")
        if x.get("has_file"):
            try:
                name, mime, blob = store.evidence_file(user_id(), ss.pid, x["id"])
                c[1].download_button("Download file", blob, file_name=name or "evidence", mime=mime or "application/octet-stream", key=f"dl{x['id']}", width="stretch")
            except store.NotFound:
                pass
        with c[2].popover("Update", width="stretch"):
            with st.form(f"upd{x['id']}"):
                ver = st.selectbox("Verification", list(EV.VERIFICATION), list(EV.VERIFICATION).index(x["verification"] or "unverified"), format_func=lambda k: EV.VERIFICATION[k][0])
                conf = st.selectbox("Your confidence", list(EV.CONFIDENCE), list(EV.CONFIDENCE).index(x["confidence"] or "medium"), format_func=lambda k: EV.CONFIDENCE[k][0])
                lim = st.text_area("Limitations", x.get("limitations") or "")
                hid_opts = [None] + [h["id"] for h in hyps]
                hid = st.selectbox("Supports hypothesis", hid_opts, hid_opts.index(x.get("hypothesis_id")) if x.get("hypothesis_id") in hid_opts else 0,
                                   format_func=lambda i: "None" if i is None else next(h["statement"][:70] for h in hyps if h["id"] == i))
                if st.form_submit_button("Save and recalculate", type="primary"):
                    store.update_evidence(user_id(), ss.pid, x["id"], dict(verification=ver, confidence=conf, limitations=lim[:1000], hypothesis_id=hid))
                    refresh("Evidence updated.")
        if x.get("experiment_id"):
            c[3].caption("Remove it in the Validation lab")
        else:
            with c[3].popover("Delete", width="stretch"):
                st.write("Delete this record?")
                if st.button("Yes, delete", key=f"delev{x['id']}", type="primary"):
                    store.delete_evidence(user_id(), ss.pid, evidence_id=x["id"]); refresh("Record deleted.")


def add_form(hyps):
    with st.expander("➕ Add evidence", expanded=False):
        st.caption("Fields marked * are required. Attach a file or give a link so the claim can be checked later.")
        with st.form("add_ev", clear_on_submit=True):
            claim = st.text_input("Claim or assumption it supports *", placeholder="Parents in Dubai pay AED 350-500 a month for weekly Arabic tutoring")
            c1, c2, c3 = st.columns(3)
            area = c1.selectbox("Area *", [a for a in EV.AREAS], format_func=lambda a: EV.AREAS[a][0])
            typ = c2.selectbox("Evidence type *", list(EV.TYPES), format_func=lambda t: EV.TYPES[t][0],
                               help="Observed transactions: real payments or sales. Observed behaviour: what people did (sign-ups, clicks, visits). "
                                    "Direct feedback: what customers told you. Secondary research: reports, statistics, articles. AI estimates and synthetic simulations carry zero weight.")
            when = c3.date_input("Date collected *", dt.date.today(), max_value=dt.date.today())
            desc = st.text_area("What the evidence shows *", placeholder="Survey of 40 parents at two Dubai schools; 26 already pay for tutoring, median AED 400 a month.")
            c1, c2 = st.columns(2)
            url = c1.text_input("Source URL", placeholder="https://…")
            up = c2.file_uploader("Or upload a document (5 MB max)", type=FILE_TYPES)
            c1, c2, c3, c4 = st.columns(4)
            geo = c1.selectbox("Geographic relevance", list(EV.GEOGRAPHY), format_func=lambda g: EV.GEOGRAPHY[g][0])
            n = c2.number_input("Sample size", 0, help="People, transactions or observations behind it. Leave 0 for reports.")
            ver = c3.selectbox("Verification status", list(EV.VERIFICATION), 2, format_func=lambda k: EV.VERIFICATION[k][0])
            conf = c4.selectbox("Confidence level", list(EV.CONFIDENCE), 1, format_func=lambda k: EV.CONFIDENCE[k][0])
            lim = st.text_input("Limitations", placeholder="Only private-school parents; asked in person, may overstate")
            st.markdown("**Optional: a number for the forecast** <span class='muted'>(only for price, costs, cost to win a customer, churn or capacity; "
                        "AI estimates and simulations are never used)</span>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            vmin = c1.number_input("Low", value=None, placeholder="optional"); vmid = c2.number_input("Likely", value=None, placeholder="optional"); vmax = c3.number_input("High", value=None, placeholder="optional")
            hid_opts = [None] + [h["id"] for h in hyps]
            hid = st.selectbox("Supports hypothesis (optional)", hid_opts, format_func=lambda i: "None" if i is None else next(h["statement"][:80] for h in hyps if h["id"] == i))
            go = st.form_submit_button("Add to ledger", type="primary")
        if go:
            errs = []
            if len(claim.strip()) < 5: errs.append("Write the claim this evidence supports.")
            if len(desc.strip()) < 5: errs.append("Describe what the evidence shows.")
            if url and not url.strip().startswith(("http://", "https://")): errs.append("The source URL must start with http:// or https://.")
            if vmid is not None and area not in EV.VALUE_AREAS: errs.append("A forecast number can only be given for price, costs, cost to win a customer, churn or capacity.")
            if vmid is not None and ((vmin is not None and vmin > vmid) or (vmax is not None and vmax < vmid)): errs.append("Keep low ≤ likely ≤ high.")
            if vmid is not None and vmid < 0: errs.append("Values cannot be negative.")
            blob = up.getvalue() if up else None
            if blob is not None and len(blob) > store.MAX_FILE_BYTES: errs.append("The file is larger than 5 MB.")
            if errs:
                for e in errs: st.error(e)
                return
            if typ in ("ai", "synthetic") and vmid is not None:
                st.info("AI estimates and simulations are stored for reference; the number will not change the forecast."); vmid = vmin = vmax = None
            store.add_evidence(user_id(), ss.pid, dict(claim=claim.strip()[:500], area=area, description=desc.strip()[:4000], source_url=url.strip()[:1000],
                                                      file_name=up.name[:200] if up else None, file_mime=up.type if up else None, collected_on=when.isoformat(),
                                                      geography=geo, ev_type=typ, sample_size=int(n) or None, verification=ver, confidence=conf, limitations=lim[:1000],
                                                      value_min=vmin, value_likely=vmid, value_max=vmax, hypothesis_id=hid), file_bytes=blob)
            refresh("Evidence added. Confidence and the forecast were recalculated.")
