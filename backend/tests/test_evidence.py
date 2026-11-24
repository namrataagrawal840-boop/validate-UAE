import copy
from app import evidence as EV
from app.compute import compute

IT = dict(idea="A cloud kitchen delivering healthy high-protein lunches to office workers in Business Bay.", business_type="kitchen", emirate="Dubai",
          setup="Mainland", target_customer="Office workers", budget_aed=600000, evidence_text="")


def test_ai_and_synthetic_records_carry_no_weight():
    for t in ("ai", "synthetic"):
        assert EV.weight(dict(ev_type=t, verification="verified", confidence="high", geography="target", sample_size=1000))[0] == 0


def test_weight_rises_with_verification_and_sample():
    base = dict(ev_type="feedback", verification="unverified", confidence="medium", geography="target", sample_size=5)
    assert EV.weight({**base, "verification": "verified"})[0] > EV.weight(base)[0]
    assert EV.weight({**base, "sample_size": 60})[0] > EV.weight(base)[0]
    assert EV.weight({**base, "verification": "disputed"})[0] == 0


def test_ai_agent_output_does_not_raise_confidence():
    s0 = dict(intake=IT)
    s1 = dict(intake=IT, agents={"finance": {"fields": {k: dict(min=v * .8, likely=v, max=v * 1.2, source="AI") for k, v in dict(price=120, fixed=30000, cac=60).items()}}})
    r0, r1 = compute(s0, light=True), compute(s1, light=True)
    assert r1["evidence"]["strength"] <= r0["evidence"]["strength"] + 1e-9
    s2 = copy.deepcopy(s0); s2["ledger"] = [dict(ev_type="ai", area="cac", verification="verified", confidence="high", geography="target", value_likely=10)]
    r2 = compute(s2, light=True)
    assert r2["evidence"]["strength"] == r0["evidence"]["strength"] and r2["assumptions"]["cac"]["likely"] == r0["assumptions"]["cac"]["likely"]


def test_real_evidence_raises_confidence_and_updates_forecast():
    s = dict(intake=IT, ledger=[dict(id="e1", claim="Quotes", ev_type="secondary", area="fixed", verification="verified", confidence="high", geography="target",
                                     value_min=40000, value_likely=45000, value_max=50000, collected_on="2026-11-01")])
    r0, r1 = compute(dict(intake=IT), light=True), compute(s, light=True)
    assert r1["evidence"]["strength"] > r0["evidence"]["strength"]
    assert r1["assumptions"]["fixed"]["likely"] == 45000 and r1["assumptions"]["fixed"]["label"] == "benchmarked"


def test_experiment_records_and_gaps():
    rec = EV.from_experiment(dict(id="x", kind="landing", visitors=400, signups=20, spend=800))
    assert rec["ev_type"] == "behaviour" and rec["area"] == "market" and rec["sample_size"] == 400
    areas = EV.area_confidence([], {})
    g = EV.gaps(areas)
    assert g and g[0]["priority"] >= g[-1]["priority"]


def test_unverified_ledger_number_gets_only_its_own_weight():
    rec = dict(id="e2", claim="Survey", ev_type="feedback", area="price", verification="unverified", confidence="medium", geography="target", sample_size=40, value_likely=420)
    r = compute(dict(intake=IT, ledger=[rec]), light=True)
    assert abs(r["evidence"]["areas"]["price"]["confidence"] - EV.weight(rec)[0]) < 1e-9
