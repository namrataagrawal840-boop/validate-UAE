import numpy as np
from app.compute import compute

IT = dict(idea="A women-only boutique fitness studio in Sharjah with small classes and childcare.", business_type="fitness", emirate="Sharjah",
          setup="Mainland", target_customer="Women 25-50", budget_aed=900000, evidence_text="")


def test_scenarios_are_ordered_and_consistent():
    r = compute(dict(intake=IT))
    f = r["finance"]; sc = f["scenarios"]
    assert sc["bad"]["npv"] <= sc["typical"]["npv"] <= sc["good"]["npv"]
    for s in sc.values():
        m = s["monthly"]
        assert np.allclose(np.cumsum(m["profit"]) - s["upfront"], m["cash"], atol=len(m["cash"]) * 1.0)
        assert np.allclose(np.array(m["revenue"]) - np.array(m["costs"]), m["profit"], atol=2)
        if s["runway_months"] is not None: assert m["cash"][s["runway_months"]] < -r["limits"]["budget"]
    assert 0 <= f["runway"]["p_runs_out"] <= 1


def test_tornado_signs_make_sense():
    t = compute(dict(intake=IT))["finance"]["tornado"]
    rows = {x["key"]: x for x in t["rows"]}
    assert rows["fixed"]["npv_at_high"] < rows["fixed"]["npv_at_low"]   # higher fixed costs -> lower value
    assert rows["arpu"]["npv_at_high"] > rows["arpu"]["npv_at_low"]     # higher spend per customer -> higher value
    assert t["rows"][0]["swing"] >= t["rows"][-1]["swing"]
