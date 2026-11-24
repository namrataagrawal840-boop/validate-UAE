import copy
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import priors as P
from app.synth import market, fingerprint, check
from app.compute import compute, build_assumptions
from app.funnel import checks as C, market_stages as MS
from app.funnel.simulate import simulate
from app.funnel import decide as D


def state(bt="kitchen", **kw):
    it = dict(idea="A cloud kitchen delivering healthy office lunches in Business Bay.", business_type=bt, emirate="Dubai", setup="Mainland",
              budget_aed=600_000, min_payback_probability=.6, max_ruin_probability=.2, horizon_months=36)
    it.update(kw)
    return dict(intake=it, agents={}, overrides={}, experiments=[], settings={})


# ---------- synthetic data must not support the idea ----------
def test_synthetic_market_ignores_the_idea():
    a = compute(state(idea="The most amazing revolutionary kitchen everyone will love, guaranteed huge demand!!!", price=999))
    b = compute(state(idea="A plain kitchen.", price=50, fixed=10))
    assert a["audit"]["synthetic"]["fingerprint"] == b["audit"]["synthetic"]["fingerprint"]
    assert a["stages"]["describe"] == b["stages"]["describe"]


def test_synthetic_market_matches_target_shares():
    c = check(market(2027, "cafe"))
    assert c["passed"] and c["max_gap"] < .02


def test_enthusiastic_wording_does_not_change_the_maths():
    a = compute(state(idea="Revolutionary, world-changing, everyone needs this healthy lunch kitchen in Business Bay!!!"), light=True)
    b = compute(state(idea="A kitchen that delivers lunches to offices in Business Bay, Dubai."), light=True)
    assert a["stages"]["forecast"]["p_payback"] == b["stages"]["forecast"]["p_payback"]


def test_no_evidence_never_gives_a_plain_launch():
    for bt in P.TYPES:
        r = compute(state(bt))
        assert r["decision"]["code"] in ("test", "stop", "pivot"), bt  # priors alone are never enough to say "launch"


# ---------- simulation ----------
BASE = dict(market=(5000,) * 3, arpu=(150,) * 3, var_pct=(40,) * 3, fixed=(30000,) * 3, setup=(100000,) * 3, cac=(50,) * 3,
            churn=(10,) * 3, capacity=(1000,) * 3, p=(.01,) * 3, q=(.05,) * 3, satisfaction=(.5,) * 3)


def test_customers_never_exceed_capacity_or_market():
    s = simulate(BASE, runs=200, shocks=3)
    assert s["paths"]["customers"].max() <= 1000 + 1e-6


def test_common_random_numbers_make_runs_repeatable():
    a = simulate(BASE, runs=300, seed=5); b = simulate(BASE, runs=300, seed=5)
    assert np.array_equal(a["npv"], b["npv"])


def test_higher_fixed_costs_reduce_payback():
    lo = simulate({**BASE, "fixed": (20000,) * 3}, runs=500, seed=1, shocks=0)
    hi = simulate({**BASE, "fixed": (60000,) * 3}, runs=500, seed=1, shocks=0)
    assert hi["p_payback"] <= lo["p_payback"] and hi["npv"].mean() < lo["npv"].mean()


def test_shocks_add_risk():
    calm = simulate({**BASE, "fixed": (45000,) * 3}, runs=1500, seed=2, shocks=0, cycles=False)
    rough = simulate({**BASE, "fixed": (45000,) * 3}, runs=1500, seed=2, shocks=3, cycles=True)
    assert np.std(rough["npv"]) > np.std(calm["npv"])


def test_deterministic_break_even_matches_hand_calculation():
    # No noise, no shocks, instant full market, no acquisition cost: profit = N*arpu*(1-v) - fixed
    s = simulate({**BASE, "cac": (0,) * 3, "p": (1.0,) * 3, "q": (0,) * 3, "churn": (0.2,) * 3, "satisfaction": (.5,) * 3, "setup": (0,) * 3},
                 runs=5, shocks=0, cycles=False, seasonality=False, ramp_months=0)
    assert s["p_payback"] == 1.0


# ---------- stage algorithms ----------
def test_kaplan_meier_known_values():
    # 4 subjects: events at 1 and 2, censored at 3 and 3
    km = C.kaplan_meier([1, 2, 3, 3], [1, 1, 0, 0], 3)
    assert km[0] == pytest.approx(.25) and km[1] == pytest.approx(.5) and km[2] == pytest.approx(.5)


def test_isolation_forest_flags_an_optimistic_plan():
    A, _ = build_assumptions(state("cafe"))
    normal = C.anomaly(A, "cafe")
    A2 = copy.deepcopy(A); A2["cac"]["likely"] = 1; A2["churn"]["likely"] = .3; A2["fixed"]["likely"] = 3000
    odd = C.anomaly(A2, "cafe")
    assert odd["outlier"] and odd["optimistic_count"] >= 2 and odd["score"] < normal["score"]


def test_gmm_picks_k_by_bic():
    seg = MS.segment(market(2027, "cafe"), state("cafe")["intake"])
    assert 2 <= seg["k"] <= 6 and min(seg["bic"], key=lambda b: b["bic"])["k"] == seg["k"]


def test_adoption_falls_as_price_rises():
    m = market(2027, "cafe"); it = state("cafe")["intake"]
    a = MS.adoption(m, it, 80, 0, P.CHOICE_MODEL).sum(); b = MS.adoption(m, it, 200, 0, P.CHOICE_MODEL).sum()
    assert b < a


def test_intercept_calibration_hits_target():
    m = market(2027, "cafe"); it = state("cafe")["intake"]; co = dict(P.CHOICE_MODEL)
    d = MS.calibrate_intercept(m, it, 120, 0, co, .03); co["b0"] += d
    p = MS.adoption(m, it, 120, 0, co); f = MS.focus_mask(m, "Dubai") & m["participates"]
    assert p[f].mean() == pytest.approx(.03, abs=1e-3)


def test_lp_respects_budget_and_prefers_cheap_channels():
    r = D.channel_mix("cafe", 50, 3000)
    assert r["spend"] <= 3000 + 1e-6 and r["blended_cac"] < 50 * 1.4


def test_price_elasticity_recovers_direction():
    b, _ = C.price_elasticity([(80, 100, 30), (120, 100, 15), (160, 100, 6)])
    assert b > .5


def test_ab_compare():
    r = C.ab_compare(1000, 30, 1000, 60)
    assert r["p_b_better"] > .99


def test_tfidf_topics_need_enough_text():
    assert C.text_topics(["too short"], "idea")["status"] == "skipped"
    docs = ["Delivery food arrives cold and late every time"] * 4 + ["Prices are too expensive for a simple salad lunch"] * 4 + ["Hard to find healthy high protein options near office"] * 4
    r = C.text_topics(docs, "healthy high protein lunch delivery to offices")
    assert r["status"] == "ran" and r["k"] >= 2


# ---------- experiments and Bayesian updating ----------
def test_landing_test_replaces_cac_with_measurement():
    s = state("kitchen"); s["experiments"] = [dict(kind="landing", visitors=1000, signups=40, spend=2000, pay_rate=30)]
    r = compute(s)
    assert r["assumptions"]["cac"]["label"] == "measured" and r["stages"]["classify"]["label"] == "measured"
    assert r["stages"]["classify"]["mean_adoption"] == pytest.approx(41 / 1002, rel=.05)


def test_bad_evidence_lowers_the_result():
    base = compute(state("kitchen"))
    s = state("kitchen"); s["experiments"] = [dict(kind="landing", visitors=2000, signups=4, spend=3000, pay_rate=30)]
    bad = compute(s)
    assert bad["stages"]["forecast"]["p_payback"] < base["stages"]["forecast"]["p_payback"]


def test_budget_hard_limit():
    r = compute(state("fitness", budget_aed=100_000))
    assert r["stages"]["forecast"]["p_ruin"] > .9 and r["decision"]["code"] != "launch"


# ---------- API ----------
def test_api_flow(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app import main
    client = TestClient(main.app)
    r = client.post("/api/analyses", json=dict(idea="A cloud kitchen delivering healthy office lunches in Business Bay.", business_type="kitchen", emirate="Dubai"))
    id = r.json()["id"]
    import time
    for _ in range(400):
        d = client.get(f"/api/analyses/{id}").json()
        if d["status"] != "running": break
        time.sleep(.25)
    assert d["status"] == "done" and d["result"]["decision"]["code"] in ("test", "stop", "pivot")
    assert d["result"]["stages"]["forecast"]["abm"]["agents"] >= 1500
    assert client.post(f"/api/analyses/{id}/experiments", json=dict(kind="interviews", n=10, k=11)).status_code == 422
    d2 = client.post(f"/api/analyses/{id}/experiments", json=dict(kind="interviews", n=10, k=8)).json()
    assert len(d2["experiments"]) == 1
    w = client.post(f"/api/analyses/{id}/whatif", json=dict(overrides={"fixed": {"min": 20000, "likely": 25000, "max": 30000}}, settings={"shocks": 0})).json()
    assert "forecast" in w and w["forecast"]["p_payback"] >= 0
    assert client.post("/api/analyses", json=dict(idea="short", business_type="kitchen")).status_code == 422
