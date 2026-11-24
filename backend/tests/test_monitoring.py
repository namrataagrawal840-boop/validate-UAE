from app import monitoring as MO
from app.compute import compute

IT = dict(idea="A women-only boutique fitness studio in Sharjah with small classes and childcare.", business_type="fitness", emirate="Sharjah",
          setup="Mainland", target_customer="Women 25-50", budget_aed=900000, evidence_text="")
R = compute(dict(intake=IT)); B = MO.baseline(R)


def test_on_forecast_results_are_within_band():
    rows = [dict(month=m, revenue=B["bands"]["revenue"]["p50"][m - 1], expenses=B["bands"]["costs"]["p50"][m - 1], customers=B["bands"]["customers"]["p50"][m - 1]) for m in (1, 2, 3)]
    c = MO.compare(B, rows)
    assert not c["alerts"] and all(r["revenue"]["flag"] == "within" for r in c["rows"])


def test_low_revenue_and_high_cac_are_flagged():
    ms = [m for m in range(1, B["horizon"] + 1) if B["bands"]["revenue"]["p10"][m - 1] > 0][:3]
    rows = [dict(month=m, revenue=1.0, expenses=B["bands"]["costs"]["p90"][m - 1] * 2, marketing_spend=10000, new_customers=2) for m in ms]
    c = MO.compare(B, rows)
    flagged = {a["metric"] for a in c["alerts"]}
    assert {"revenue", "expenses", "cac"} <= flagged
    assert c["runway_months"] is not None and c["cash_now"] < B["budget"]


def test_conversion_and_repeat_rates():
    rows = [dict(month=1, customers=100), dict(month=2, customers=110, repeat_customers=50, visitors=2000, conversions=2)]
    r2 = MO.compare(B, rows)["rows"][1]
    assert r2["repeat"]["flag"] == "below" and abs(r2["repeat"]["actual"] - .5) < 1e-9
    assert r2["conversion"]["actual"] == .001


def test_revenue_series_stops_at_first_gap():
    assert MO.revenue_series([dict(month=1, revenue=10), dict(month=2, revenue=20), dict(month=4, revenue=40)]) == [10, 20]
