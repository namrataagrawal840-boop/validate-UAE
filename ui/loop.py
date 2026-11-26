"""Steps 4-6 of the journey: run one test, log the result, share the report.

Tests here are desk tests: the founder runs them alone, without customers (competitor prices and reviews,
written quotes, ad bids, published benchmarks, timed trial runs). Each result becomes an evidence-ledger record
and the verdict is recalculated at once, so the founder sees what the test changed.
"""
import copy
import datetime as dt

import streamlit as st

from app import desk_tests as DT
from app import store
from ui.common import ss, esc, pct, aed, section, soft, PASTEL, user_id, refresh, can_edit, payback_line
from ui.glossary import gloss

SIMPLE = {"Run a test": "6. Run a test", "Share and report": "7. Share"}
AUTO = {"search_check": lambda s: bool((s.get("search") or {}).get("evidence_id")), "social_listening": lambda s: bool((s.get("social") or {}).get("evidence_id"))}


def goto(page):
    if ss.get("mode", "Simple") == "Simple" and page in SIMPLE:
        ss.simple_page = SIMPLE[page]
    else:
        ss.mode = "Full"; ss.section = page
    ss.view = "project"; st.rerun()


def tests(state):
    """Desk tests with their status; page-based tests count as done once their page saved a record."""
    out = copy.deepcopy(state.get("desk_tests") or {})
    for k, f in AUTO.items():
        if f(state): out[k] = dict(out.get(k) or {}, name=DT.TESTS[k]["name"], status="done", finding=out.get(k, {}).get("finding") or "Saved on its own page.")
    return out


def stages(r, state):
    t = tests(state)
    real = r["evidence"].get("real_records", 0)
    code = r["decision"]["code"]
    return [("Idea set up", True), ("First read", True), ("Test running", bool(t)), ("Result logged", any(x.get("status") == "done" for x in t.values()) or real > 0),
            ("Decided", code == "stop" or (code in ("launch", "pivot") and r["evidence"]["strength"] >= .35)), ("Shared", bool(state.get("shared_report")))]


def progress(r, state):
    """A strip showing where the project is, and one bar with the single next step."""
    sts = stages(r, state)
    cells = "".join(f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:14px;font-size:13px;color:{"#3f8f72" if done else "#8a90a8"}">'
                    f'<span style="width:18px;height:18px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:11px;'
                    f'background:{"#d3ecdf" if done else "#eef0f6"}">{"✓" if done else i + 1}</span>{name}</span>' for i, (name, done) in enumerate(sts))
    st.markdown(f'<div style="margin:-6px 0 8px">{cells}</div>', unsafe_allow_html=True)
    label, why, target = next_step(r, state)
    c1, c2 = st.columns([5, 1.3])
    c1.markdown(soft(f"<b>Your next step:</b> {esc(label)} <span class='muted'>· {esc(why)}</span>", "mint"), unsafe_allow_html=True)
    if target and c2.button("Go →", key="nextstep", width="stretch", type="primary"):
        goto(target)


def next_step(r, state):
    t = tests(state); today = dt.date.today().isoformat()
    planned = sorted([(v.get("due") or "9999", k, v) for k, v in t.items() if v.get("status") == "planned"])
    done = {k for k, v in t.items() if v.get("status") == "done"}
    rec = DT.recommend(r, state, done | {k for _, k, _ in planned}, top=1)
    if planned:
        due, k, v = planned[0]
        return (f"Log the result of “{v.get('name', k)}”", "overdue since " + due if due < today else f"due {due}", "Run a test")
    if not t and rec:
        return (f"Start your first test: {rec[0]['name'].lower()}", "no customers needed; it checks " + rec[0]["checks"], "Run a test")
    if r["evidence"]["strength"] < .35 and rec:
        return (f"Next test: {rec[0]['name'].lower()}", "a decision needs the three numbers that move the answer most checked: " + (", ".join(_missing(r)) or "keep going"), "Run a test")
    if not state.get("shared_report"):
        return ("Download the report and share it", "a PDF with the verdict, the evidence and the method", "Share and report")
    return ("Track real results against the plan", "import monthly figures from your tools", "Import results")


def _missing(r):
    rs = r["decision"].get("reasons") or []
    m = next((x for x in rs if x.startswith("Not yet desk-checked: ")), "")
    return [m[len("Not yet desk-checked: "):].split(". ")[0]] if m else []


def _field(key, f, default=None):
    name, kind, label = f[0], f[1], f[2]
    k = f"dt_{key}_{name}"
    if kind == "lines": return st.text_area(label, key=k, height=110)
    if kind in ("money", "number"): return st.number_input(label, min_value=0.0, value=float(f[3]) if len(f) > 3 else 0.0, step=1.0 if kind == "number" else 100.0, key=k)
    if kind == "percent": return st.number_input(label, min_value=0.0, max_value=100.0, value=float(f[3]) if len(f) > 3 else 0.0, step=.5, key=k)
    if kind == "choice": return st.selectbox(label, f[3], key=k, format_func=lambda x: {"uae": "UAE", "gcc": "GCC", "global": "Outside the GCC"}.get(x, x))
    return st.text_input(label, key=k)


def _save_tests(state, message):
    store.save_project(user_id(), ss.pid, state=state); ss.state = state
    store.log(user_id(), ss.pid, "Desk test", message); ss.flash = message; st.rerun()


def _start(key, due, state):
    s = copy.deepcopy(state); s.setdefault("desk_tests", {})[key] = dict(name=DT.TESTS[key]["name"], status="planned", due=due.isoformat(), started=dt.date.today().isoformat())
    _save_tests(s, f"Test started: {DT.TESTS[key]['name']} (due {due:%d %b})")


def _card(t, r, state, i):
    with st.container(border=True):
        a, b = st.columns([4, 1.6])
        share = f" · explains {t['uncertainty_share']:.0%} of the uncertainty in profit" if t.get("uncertainty_share") else ""
        a.markdown(f"**{esc(t['name'])}**  \n<span class='muted'>Checks {esc(t['checks'])} · about {t['days']} day{'s' if t['days'] > 1 else ''}{share}</span>", unsafe_allow_html=True)
        if t.get("page"):
            if b.button(f"Open {t['page']}", key=f"pg{t['key']}{i}", width="stretch"): goto(t["page"])
        elif can_edit():
            due = b.date_input("Due", dt.date.today() + dt.timedelta(days=t["days"]), key=f"due{t['key']}{i}", label_visibility="collapsed")
            if b.button("Start this test", key=f"st{t['key']}{i}", type="primary", width="stretch"): _start(t["key"], due, state)


def page(r, state):
    st.header("Run a test")
    st.markdown(soft(gloss("You don't need customers to test most of your plan. Each desk test below checks one number the forecast depends on, from the desk: "
                           "competitor prices and reviews, written quotes, ad costs, published figures. Log what you find in one box and the verdict updates at once. "
                           "Results count as real-world evidence at their honest weight (written quotes 0.7, observed market data 0.5, published research 0.4); "
                           "simulations still count for nothing."), "lavender"), unsafe_allow_html=True)
    t = tests(state)
    planned = {k: v for k, v in t.items() if v.get("status") == "planned"}
    done = {k: v for k, v in t.items() if v.get("status") == "done"}

    if planned:
        section("Your running tests", "butter")
        for k, v in planned.items():
            spec = DT.TESTS[k]; overdue = v.get("due") and v["due"] < dt.date.today().isoformat()
            with st.container(border=True):
                st.markdown(f"**{esc(spec['name'])}** <span class='pill p-{'bad' if overdue else 'warn'}'>{'Overdue' if overdue else 'Due'} {esc(v.get('due', ''))}</span>", unsafe_allow_html=True)
                c1, c2 = st.columns([1.1, 1])
                with c1:
                    st.markdown("**How to do it**\n" + "\n".join(f"{n + 1}. {esc(x)}" for n, x in enumerate(spec["steps"])))
                    if spec.get("template"):
                        st.markdown("**Message you can send**"); st.code(DT.fill(spec["template"], r), language=None)
                with c2:
                    if not can_edit():
                        st.caption("View-only access: the owner or an editor logs results.")
                        continue
                    with st.form(f"log_{k}"):
                        st.markdown("**Log the result**")
                        vals = {f[0]: _field(k, f) for f in spec["fields"]}
                        go_, drop = st.columns(2)
                        ok = go_.form_submit_button("Save and update the verdict", type="primary")
                        cancel = drop.form_submit_button("Drop this test")
                    if cancel:
                        s = copy.deepcopy(state); s["desk_tests"].pop(k, None); _save_tests(s, f"Test dropped: {spec['name']}")
                    if ok:
                        try:
                            rec, finding, direction = DT.evaluate(k, vals, r)
                        except ValueError as e:
                            st.error(str(e)); continue
                        before = dict(decision=r["decision"]["label"], payback=r["finance"]["payback"].get("typical"), confidence=r["evidence"]["strength"])
                        eid = store.add_evidence(user_id(), ss.pid, rec)
                        s = copy.deepcopy(state)
                        s["desk_tests"][k].update(status="done", finding=finding, direction=direction, evidence_id=eid, before=before, done_on=dt.date.today().isoformat())
                        refresh(f"Result logged: {finding}", s)

    if done:
        section("Results so far", "mint")
        for k, v in done.items():
            tone = {"better": "good", "worse": "bad"}.get(v.get("direction"), "info")
            word = {"better": "Better than the plan", "worse": "Worse than the plan", "in line": "In line with the plan"}.get(v.get("direction"), "Done")
            b = v.get("before")
            now = dict(decision=r["decision"]["label"], payback=r["finance"]["payback"].get("typical"), confidence=r["evidence"]["strength"])
            change = ""
            if b:
                pm = lambda x: f"month {x}" if x else "beyond plan"
                change = (f"<br><span class='muted' style='font-size:13px'>Before this test: {esc(b['decision'])}, payback {pm(b['payback'])}, evidence {pct(b['confidence'])}. "
                          f"Now: {esc(now['decision'])}, payback {pm(now['payback'])}, evidence {pct(now['confidence'])}.</span>")
            with st.container(border=True):
                a, c = st.columns([5, 1])
                a.markdown(f"<span class='pill p-{tone}'>{word}</span> **{esc(v.get('name', k))}**<br>{esc(v.get('finding', ''))}{change}", unsafe_allow_html=True)
                if can_edit() and k not in AUTO and c.button("Undo", key=f"undo{k}", width="stretch"):
                    if v.get("evidence_id"):
                        try: store.delete_evidence(user_id(), ss.pid, evidence_id=v["evidence_id"])
                        except store.NotFound: pass
                    s = copy.deepcopy(state); s["desk_tests"].pop(k, None); refresh(f"Result removed: {v.get('name', k)}", s)

    rec = DT.recommend(r, state, set(t), top=3)
    if rec:
        section("Recommended next", "lavender", "Ordered by how much each number moves the answer and how weak its evidence is.")
        for i, x in enumerate(rec): _card(x, r, state, i)
    rest = [dict(key=k, **v, uncertainty_share=0) for k, v in DT.TESTS.items() if k not in t and k not in {x["key"] for x in rec}]
    if rest:
        with st.expander(f"All other desk tests ({len(rest)})"):
            for i, x in enumerate(rest): _card(x, r, state, 100 + i)
    with st.expander("Optional: tests that need customers"):
        st.markdown("If you can reach a few customers later, the validation lab handles landing-page, pricing, interview and pilot tests. "
                    "They are never required: the verdict works from desk tests alone.")
        if st.button("Open the Validation lab"): goto("Validation lab")
