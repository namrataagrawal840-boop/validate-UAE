"""Four-step guided onboarding: idea -> market and customer -> money -> existing evidence."""
import datetime as dt
import threading
import time
import uuid

import streamlit as st

from app import agents as AG
from app import priors as P
from app import store
from app import evidence as EV
from ui import glossary as G
from ui.common import ss, esc, aed, NAMES, run_compute, RESULT_VERSION, user_id
from ui_explain import explain

STEPS = ["Business idea", "Market and customer", "Financial information", "Existing evidence"]
EXAMPLES = [
    dict(name="Healthy lunch cloud kitchen", idea="A cloud kitchen in Business Bay delivering healthy, high-protein lunches to office workers, ordered through our own app and the delivery platforms.",
         business_type="kitchen", emirate="Dubai", setup="Mainland", target_customer="Office workers aged 25-45 in Business Bay and DIFC", budget_aed=600000),
    dict(name="Online Arabic tutoring", idea="An online platform that matches children aged 6 to 14 with qualified Arabic tutors for live lessons, with weekly progress reports for parents.",
         business_type="education", emirate="All UAE", setup="Free zone", target_customer="Parents who want their children to improve their Arabic", budget_aed=300000),
    dict(name="Women-only fitness studio", idea="A women-only boutique fitness studio in Sharjah with small group classes, childcare during sessions and flexible class packs.",
         business_type="fitness", emirate="Sharjah", setup="Mainland", target_customer="Women aged 25-50 living in Sharjah", budget_aed=900000),
]
DEFAULTS = dict(name="", idea="", business_type="cafe", problem="", different="", emirate="All UAE", setup="Mainland", target_customer="", competitors="",
                budget_aed=500000, horizon_months=36, min_payback_probability=.6, max_ruin_probability=.2, price=0, fixed=0, setup_budget=0, marketing_budget_aed=0,
                evidence_text="", int_n=0, int_k=0, lp_visitors=0, lp_signups=0, lp_spend=0.0, sales="", links="", use_ai=True)


def _ob():
    if "ob" not in ss:
        draft = store.load_draft(user_id())  # answers saved before a reload
        ss.ob = dict(step=int(draft.get("step", 0)), data={**DEFAULTS, **draft.get("data", {})}) if draft else dict(step=0, data=dict(DEFAULTS))
        ss.ob_restored = bool(draft)
    return ss.ob


def _save_draft():
    store.save_draft(user_id(), ss.ob)


def stepper(i):
    cells = []
    for n, name in enumerate(STEPS):
        cls = "done" if n < i else "now" if n == i else ""
        mark = "✓ " if n < i else ""
        cells.append(f'<div class="step {cls}"><b>Step {n + 1}</b>{mark}{esc(name)}</div>')
    st.markdown('<div class="steps">' + "".join(cells) + "</div>", unsafe_allow_html=True)
    st.progress((i + 1) / len(STEPS), text=f"Step {i + 1} of {len(STEPS)}")


def nav(form_i, optional=True, last=False):
    c = st.columns([1, 1, 1, 2])
    back = c[0].form_submit_button("Back", disabled=form_i == 0, width="stretch")
    skip = c[1].form_submit_button("Skip this step", width="stretch", help="Keep the typical values and move on") if optional and not last else False
    nxt = c[3].form_submit_button("Run the validation" if last else "Next", type="primary", width="stretch")
    return back, skip, nxt


def page():
    ob = _ob(); i = ob["step"]; d = ob["data"]
    c1, c2 = st.columns([4, 1])
    c1.header("New project")
    if c2.button("Start over", width="stretch", help="Clear the answers and begin again"):
        store.delete_draft(user_id()); ss.pop("ob", None); st.rerun()
    if ss.pop("ob_restored", False):
        st.info("Welcome back: your unfinished answers were restored.")
    stepper(i)
    if i == 0:
        st.markdown("**Start from an example** <span class='muted'>(fills in the form; you can change everything)</span>", unsafe_allow_html=True)
        cols = st.columns(3)
        for n, x in enumerate(EXAMPLES):
            if cols[n].button(x["name"], key=f"ex{n}", width="stretch", help=x["idea"]):
                d.update(x); _save_draft(); st.rerun()
        with st.form("ob0"):
            st.subheader("1. The business idea")
            idea = st.text_area("Describe the idea in plain words (required)", d["idea"], height=110,
                                placeholder="A home-cleaning subscription for villas in Arabian Ranches, booked through WhatsApp")
            c1, c2 = st.columns(2)
            types = list(P.TYPES)
            bt = c1.selectbox("Business type (required)", types, types.index(d["business_type"]), format_func=lambda k: P.TYPES[k]["label"],
                              help="Picks the typical costs, prices and customer behaviour used until you add your own evidence.")
            name = c2.text_input("Project name (optional)", d["name"], placeholder="Leave blank to use the start of the idea")
            st.caption("Optional: answer if you know, leave blank if not.")
            prob = st.text_input("What problem does it solve? (optional)", d["problem"], placeholder="Parents can't find reliable Arabic tutors near home")
            diff = st.text_input("What makes it different from what exists? (optional)", d["different"], placeholder="Weekly progress reports and certified tutors only")
            _, _, nxt = nav(0, optional=False)
        if nxt:
            if len(idea.strip()) < 20:
                st.error("Describe the idea in at least one full sentence (20 characters or more).")
            else:
                d.update(idea=idea.strip()[:2000], business_type=bt, name=name.strip()[:120], problem=prob[:300], different=diff[:300]); ob["step"] = 1; _save_draft(); st.rerun()
    elif i == 1:
        with st.form("ob1"):
            st.subheader("2. Market and customer")
            c1, c2 = st.columns(2)
            ems = ["All UAE"] + [e[0] for e in P.EMIRATES]
            em = c1.selectbox("Where will you sell?", ems, ems.index(d["emirate"]) if d["emirate"] in ems else 0)
            setups = ["Mainland", "Free zone", "Online only", "Home-based"]
            setup = c2.selectbox("Business setup", setups, setups.index(d["setup"]), help=G.term("Mainland / Free zone"))
            cust = st.text_input("Who is the customer? (optional)", d["target_customer"], placeholder="Families with young children in Dubai Marina")
            comps = st.text_area("Competitors you already know (optional): one per line, as name, monthly price in AED, what they offer", d["competitors"],
                                 placeholder="ArabicKids Online, 400, live Arabic lessons for children\nKumon, 550, maths and English worksheets")
            G.expander(["Mainland / Free zone", "TAM / SAM / SOM"])
            back, skip, nxt = nav(1)
        if back or skip or nxt:
            if not skip: d.update(emirate=em, setup=setup, target_customer=cust[:300], competitors=comps[:3000])
            ob["step"] = 0 if back else 2; _save_draft(); st.rerun()
    elif i == 2:
        t = P.TYPES[d["business_type"]]
        with st.form("ob2"):
            st.subheader("3. Financial information")
            st.markdown("**Your decision limits**")
            c1, c2 = st.columns(2)
            budget = c1.number_input("Cash you can put in (AED)", 1000, value=int(d["budget_aed"]), step=10000, help="Everything you could invest, including setup and early losses.")
            horizon = c2.selectbox("Time to pay back", [24, 36, 48, 60], [24, 36, 48, 60].index(d["horizon_months"]), format_func=lambda m: f"{m} months", help=G.term("Payback"))
            minp = c1.select_slider("Minimum chance of paying back", [.5, .6, .7, .8], d["min_payback_probability"], format_func=lambda v: f"{v:.0%}",
                                    help="In how many of 100 simulated futures must you get your money back for this to be worth it?")
            maxr = c2.select_slider("Most risk of running out of budget you accept", [.05, .1, .2, .3], d["max_ruin_probability"], format_func=lambda v: f"{v:.0%}",
                                    help=G.term("Chance of running out (budget risk)"))
            st.markdown("**Your numbers (optional)** <span class='muted'>Leave at 0 if you don't know: typical values for this business type are used and labelled as such.</span>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            price = c1.number_input(f"Spend per customer per month (AED) · typical {aed(t['price'][1])}", 0, value=int(d["price"]), help=G.term("ARPU"))
            fixed = c2.number_input(f"Fixed costs per month (AED) · typical {aed(t['fixed'][1])}", 0, value=int(d["fixed"]), help=G.term("Fixed costs"))
            setupc = c1.number_input(f"Setup cost (AED) · typical {aed(t['setup'][1])}", 0, value=int(d["setup_budget"]), help=G.term("Setup cost"))
            mkt = c2.number_input("Marketing budget per month (AED)", 0, value=int(d["marketing_budget_aed"]), help=G.term("CAC"))
            G.expander(["ARPU", "Fixed costs", "Setup cost", "Payback", "Chance of running out (budget risk)", "Break-even"])
            back, skip, nxt = nav(2)
        if back or skip or nxt:
            if not skip:
                d.update(budget_aed=float(budget), horizon_months=horizon, min_payback_probability=minp, max_ruin_probability=maxr, price=price, fixed=fixed,
                         setup_budget=setupc, marketing_budget_aed=mkt)
            ob["step"] = 1 if back else 3; _save_draft(); st.rerun()
    else:
        with st.form("ob3"):
            st.subheader("4. Evidence you already have")
            st.markdown('<p class="muted">Everything here is optional. Real evidence raises confidence; guesses don\'t. Each item becomes a record in your evidence ledger.</p>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            n = c1.number_input("People you have interviewed", 0, value=int(d["int_n"]))
            k = c2.number_input("…of whom described the problem as serious", 0, value=int(d["int_k"]))
            c1, c2, c3 = st.columns(3)
            lv = c1.number_input("Landing page or ad: visitors", 0, value=int(d["lp_visitors"]), help=G.term("Conversion rate"))
            ls = c2.number_input("…sign-ups or pre-orders", 0, value=int(d["lp_signups"]))
            lsp = c3.number_input("…ad spend (AED)", 0.0, value=float(d["lp_spend"]))
            sales = st.text_input("Monthly sales so far, AED, oldest first (if already trading)", d["sales"], placeholder="12000, 15000, 17500, 21000")
            links = st.text_area("Reports or articles that support the idea: one per line, as URL, what it shows", d["links"],
                                 placeholder="https://www.example.ae/report, 62% of UAE parents pay for after-school tutoring")
            ev = st.text_area("Customer reviews, complaints or interview notes (one per line)", d["evidence_text"], height=100)
            ai_ok = AG.enabled()
            use_ai = st.checkbox("Use AI agents with web research", value=ai_ok and d["use_ai"], disabled=not ai_ok,
                                 help="Agents search the web for market, customer, competitor, cost and licence information, with sources. Their numbers are labelled as AI estimates and never count as evidence."
                                 if ai_ok else "Add ANTHROPIC_API_KEY to the app's secrets to enable.")
            back, _, nxt = nav(3, last=True)
        if back:
            ob["step"] = 2; _save_draft(); st.rerun()
        if nxt:
            errs = []
            if k > n: errs.append("Interviewees with a serious problem cannot exceed the number interviewed.")
            if ls > lv: errs.append("Sign-ups cannot exceed visitors.")
            if lv and not lsp: errs.append("Enter the ad spend for the landing-page test (needed to estimate the cost to win a customer), or set visitors to 0.")
            try:
                sales_v = [float(x) for x in sales.replace(";", ",").split(",") if x.strip()]
                if sales_v and (len(sales_v) < 4 or min(sales_v) < 0): errs.append("Enter at least 4 months of sales, none negative.")
            except ValueError:
                errs.append("Sales must be numbers separated by commas."); sales_v = []
            link_rows = []
            for line in links.splitlines():
                if not line.strip(): continue
                url, _, claim = line.partition(",")
                if not url.strip().startswith("http"): errs.append(f"“{line[:40]}”: start each line with a web address (http…)."); continue
                link_rows.append((url.strip()[:500], claim.strip()[:300] or "Supporting report"))
            if errs:
                for e in errs: st.error(e)
            else:
                d.update(int_n=n, int_k=k, lp_visitors=lv, lp_signups=ls, lp_spend=lsp, sales=sales, links=links, evidence_text=ev, use_ai=use_ai)
                finish(d, sales_v, link_rows)


def parse_competitors(text):
    out = []
    for line in (text or "").splitlines()[:15]:
        parts = [x.strip() for x in line.split(",")]
        if parts and len(parts[0]) >= 2:
            pr = next((float(x) for x in parts[1:2] if x.replace(".", "", 1).isdigit()), None)
            out.append(dict(name=parts[0][:120], type="direct", price_aed=pr, rating=None, note=", ".join(parts[2 if pr else 1:])[:240], features=[], url="", strengths=[], weaknesses=[]))
    return out


def run_agents(intake):
    prog, out = {}, {}
    th = threading.Thread(target=lambda: out.update(res=AG.run_agents(intake, lambda s, status, text: prog.__setitem__(s, (status, text)))), daemon=True)
    with st.status("AI agents are researching your idea on the web…", expanded=True) as box:
        ph = st.empty(); th.start()
        while th.is_alive():
            ph.markdown("\n".join(f"- {'✅' if v[0] == 'done' else '⚠️' if v[0] == 'fallback' else '⏳'} **{NAMES.get(k, k)}** {v[1]}" for k, v in prog.items()) or "Starting…")
            time.sleep(1)
        box.update(label="Research done", state="complete")
    agents, sources, errors = out.get("res", ({}, {}, {"all": "failed"}))
    return agents, sources, errors, [(NAMES.get(k, k), v[0], v[1]) for k, v in prog.items()]


def finish(d, sales_v, link_rows):
    extra = " ".join(x for x in (f"Problem: {d['problem']}." if d["problem"] else "", f"Different because: {d['different']}." if d["different"] else "") if x)
    intake = dict(idea=(d["idea"] + (" " + extra if extra else ""))[:2000], business_type=d["business_type"], emirate=d["emirate"], setup=d["setup"],
                  target_customer=d["target_customer"], budget_aed=float(d["budget_aed"]), min_payback_probability=d["min_payback_probability"],
                  max_ruin_probability=d["max_ruin_probability"], horizon_months=d["horizon_months"], price=d["price"] or None, fixed=d["fixed"] or None,
                  setup_budget=d["setup_budget"] or None, marketing_budget_aed=d["marketing_budget_aed"] or None, evidence_text=d["evidence_text"][:20000], use_ai=d["use_ai"])
    today = dt.date.today().isoformat()
    exps = []
    if d["int_n"]: exps.append(dict(id=str(uuid.uuid4()), kind="interviews", n=int(d["int_n"]), k=int(d["int_k"]), date=today))
    if d["lp_visitors"]: exps.append(dict(id=str(uuid.uuid4()), kind="landing", visitors=int(d["lp_visitors"]), signups=int(d["lp_signups"]), spend=float(d["lp_spend"]), pay_rate=30.0, date=today))
    if sales_v: exps.append(dict(id=str(uuid.uuid4()), kind="sales", sales=sales_v, date=today))
    state = dict(intake=intake, agents={}, overrides={}, experiments=exps, settings={}, applied=[], competitors=parse_competitors(d["competitors"]))
    log = [("Offline mode", "done", "AI agents off: using typical figures for this business type in the UAE.")]
    try:
        if d["use_ai"] and AG.enabled():
            agents, sources, errors, log = run_agents(intake)
            state.update(agents=agents, sources=sources, agent_errors=errors)
        state["log"] = log
        name = d["name"] or (d["idea"][:60] + ("…" if len(d["idea"]) > 60 else ""))
        pid = store.create_project(user_id(), name, state)
        for e in exps:
            store.add_evidence(user_id(), pid, EV.from_experiment(e, intake))
        for url, claim in link_rows:
            store.add_evidence(user_id(), pid, dict(claim=claim, area="market", description="Report or article added during onboarding.", source_url=url, collected_on=today,
                                                    geography="uae", ev_type="secondary", verification="unverified", confidence="medium", limitations="Not yet checked: open the source and mark it verified."))
        ss.pid = pid
        with st.spinner("Running the 10-stage funnel and the market simulation…"):
            r = run_compute(state); r["_version"] = RESULT_VERSION
        store.save_project(user_id(), pid, result=r)
        ss.state, ss.result, ss.pname, ss.baseline, ss._explain = state, r, name, None, explain(r)
        from ui.common import ensure_starter
        ensure_starter()
        ss.view = "project"; ss.section = "Decision"; ss.mode = "Simple"; ss.simple_page = "1. Idea"; ss.pop("ob", None); store.delete_draft(user_id())
    except Exception as e:  # keep the user's answers; show what went wrong
        st.error(f"The analysis could not be completed: {e}. Your answers are kept; try again.")
        return
    st.rerun()
