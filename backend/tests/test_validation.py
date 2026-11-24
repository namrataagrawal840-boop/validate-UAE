import numpy as np
import pytest
from app.funnel import validation as V
from app.compute import compute, build_assumptions


def st(**kw):
    s = dict(intake=dict(idea="A cloud kitchen delivering healthy office lunches in Business Bay.", business_type="kitchen", emirate="Dubai", setup="Mainland",
                         budget_aed=600_000), agents={}, overrides={}, experiments=[], settings={})
    s.update(kw); return s


def test_van_westendorp_crossings():
    rows = [[50, 80, 120, 160]] * 10 + [[70, 100, 140, 190]] * 10
    r = V.van_westendorp(rows)
    assert 50 <= r["opp"] <= 190 and r["pmc"] <= r["pme"]
    k, n = V.accept_at(rows, 100)
    assert (k, n) == (20, 20) and V.accept_at(rows, 175)[0] == 10


def test_sus_scoring_extremes():
    assert V.sus_score([5, 1] * 5) == 100 and V.sus_score([1, 5] * 5) == 0


def test_holt_follows_a_linear_trend():
    f = V.holt_forecast([100, 110, 120, 130, 140, 150])
    assert f["forecast"][0] == pytest.approx(160, abs=3) and f["trend_per_month"] == pytest.approx(10, abs=1.5)


def test_nps():
    assert V.nps(6, 2, 2)["nps"] == pytest.approx(40)


def test_validation_score_ignores_missing_checks():
    v = V.validation_score(dict(market=80, customers=60, competition=40, money=50, usability=None), .5, 2, .5)
    assert 40 < v["score"] < 70 and "usability" not in v["weights"] and abs(sum(v["weights"].values()) - 1) < 1e-9


def test_improve_ranks_and_recombines_and_apply_changes_the_result():
    r = compute(st())
    vs = r["improve"]["variants"]
    assert vs and vs == sorted(vs, key=lambda x: (-x["d_payback"], -x["d_npv"]))
    best = next(v for v in vs if not v.get("combo"))
    s2 = st(applied=[dict(id=best["id"], name=best["name"], changes=best["changes"])])
    r2 = compute(s2)
    assert best["id"] not in {v["id"] for v in r2["improve"]["variants"]}
    assert r2["stages"]["forecast"]["npv_mean"] != r["stages"]["forecast"]["npv_mean"]


def test_new_experiments_feed_the_model():
    ex = [dict(kind="usability", users=5, tasks_done=14, tasks_total=15, sus=[85, 90, 80, 90, 80]),
          dict(kind="pilot", customers=20, months=2, lost=2, promoters=15, passives=3, detractors=2),
          dict(kind="vanwestendorp", rows=[[60, 100, 160, 220]] * 10),
          dict(kind="sales", sales=[10000, 12000, 15000, 16000, 19000])]
    r = compute(st(experiments=ex))
    e = r["stages"]["experiments"]["evidence"]
    assert r["scores"]["usability"] == pytest.approx(e["usability"]["score"]) and e["usability"]["sus_grade"] == "excellent"
    assert r["unit"]["satisfaction"] == pytest.approx(e["nps"]["satisfaction"])
    assert e["acceptance"]["n"] == 10 and r["stages"]["classify"]["calibrated"]
    assert len(e["sales"]["forecast"]) == 12


def test_self_consistency_widens_disagreeing_ranges():
    ag = {"finance": {"fields": {"fixed": dict(min=30000, likely=35000, max=40000, source="Agent", url="")}},
          "consistency": {"fields": {"fixed": dict(min=60000, likely=80000, max=100000, source="Second")}}}
    s = st(agents=ag)
    A, warnings = build_assumptions(s)
    assert A["fixed"]["max"] == 100000 and s["_consistency"][0]["widened"] and warnings


def test_tourism_shock_exists():
    from app import priors as P
    assert "tourism" in P.SHOCKS


def test_outputs_for_the_overview():
    r = compute(st())
    assert r["idea"]["canvas"]["solution"] and len(r["idea"]["assumptions"]) == 5
    assert r["market_sizing"]["sam"] > 0 and r["value"]["wtp_hist"]["counts"]
    assert r["kit"]["landing"]["headline"] and len(r["kit"]["survey"]) >= 4
