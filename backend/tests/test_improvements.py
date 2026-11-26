"""Tests for the review-driven improvements: payback months, score parts, ranges, desk tests and the desk-checked
decision route, teams and roles, history, imports, calibration, alerts and the report."""
import copy
import datetime as dt

import numpy as np
import pytest

from app import store, desk_tests as DT, history as H, actuals_import as AI, calibration as CAL, alerts as AL, report_export as RX, market_size as MZ
from app.compute import compute, desk_coverage
from app.funnel import finance as FIN, decide as D
from tests.test_funnel import state


@pytest.fixture(scope="module")
def res():
    s = state("kitchen"); return s, compute(s)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db")); monkeypatch.delenv("DATABASE_URL", raising=False)
    store.reset_engine(); yield; store.reset_engine()


# ---------- one payback definition, in months ----------
def test_payback_month_quantiles():
    sim = dict(payback=np.array([5, 10, 12, 20, 30, np.inf, np.inf, 8, 9, 11], float))
    pv = FIN.payback_view(sim, horizon=24, standard=.6)
    assert pv["typical"] == 11 and pv["safe"] == 12 and pv["passes"]
    pv = FIN.payback_view(sim, horizon=10, standard=.6)
    assert not pv["passes"] and pv["months_over"] == 2
    assert FIN.payback_view(dict(payback=np.full(10, np.inf)), 36, .6)["safe"] is None


def test_founder_sets_only_the_time_limit(res):
    s, r = res
    assert r["limits"]["min_payback"] == .6 and r["limits"]["horizon"] == 36
    s2 = copy.deepcopy(s); s2["intake"]["min_payback_probability"] = .95   # ignored: the standard is fixed
    assert compute(s2, light=True)["limits"]["min_payback"] == .6
    pv = r["finance"]["payback"]
    assert pv["safe"] is None or pv["safe"] >= pv["typical"]
    for sc in r["finance"]["scenarios"].values():
        assert sc["payback_month"] is None or sc["payback_month"] >= 1


def test_score_is_capped_when_money_limits_fail(res):
    _, r = res
    v = r["validation"]
    assert set(v["parts"]) == {"market", "customers", "money"}
    if v["capped"]: assert v["score"] <= 49 and v["uncapped"] >= v["score"]
    from app.funnel.validation import validation_score
    sc = dict(market=90, customers=90, competition=90, money=90, usability=None, evidence=0)
    assert validation_score(sc, 0, 0, .3, meets_limits=False)["score"] == 49


def test_market_ranges_contain_the_point_estimate(res):
    _, r = res
    m = MZ.size(r)
    for k in ("tam", "sam", "som"):
        lo, hi = m["ranges"][k]
        assert lo <= m[k]["people"] <= hi and lo < hi


def test_sensitivity_and_run_stamp(res):
    _, r = res
    ps = [x["p_payback"] for x in r["sensitivity"]["market"]]
    assert ps == sorted(ps)  # more buyers never lowers the payback chance
    assert r["run_info"]["seed"] == 2027 and len(r["run_info"]["input_hash"]) == 16
    assert len(r["runs_table"]["rows"]) == r["stages"]["forecast"]["runs"]


# ---------- desk tests: no customers needed ----------
def test_every_desk_test_produces_a_real_record(res):
    _, r = res
    cases = dict(competitor_prices=dict(prices="A, 120, https://a\nB, 200"), review_count=dict(rows="A, 300, 24\nB, 600, 30"),
                 ad_cost=dict(cpc_low=2, cpc_high=4, conv=2), rent_quotes=dict(rents="20000\n25000", staff=10000, other=2000),
                 setup_quotes=dict(fitout="100000\n140000", licence=20000), supplier_quotes=dict(cogs=30, sale=150, commission=15),
                 churn_benchmark=dict(churn=10, geo="uae", url="https://x"), capacity_time=dict(per_hour=30, hours=8, days=26, per_customer=10),
                 licence_check=dict(activity="Cloud kitchen", url="https://det"))
    from app import evidence as EV
    for k, v in cases.items():
        rec, finding, direction = DT.evaluate(k, v, r)
        assert EV.is_real(rec) and rec["area"] == DT.TESTS[k]["area"] and finding and direction in ("better", "worse", "in line")
        assert rec["ev_type"] in ("quote", "observation", "secondary")
    with pytest.raises(ValueError): DT.evaluate("churn_benchmark", dict(churn=10), r)   # a benchmark needs its source


def test_recommendations_follow_the_biggest_uncertainty(res):
    s, r = res
    rec = DT.recommend(r, s, top=3)
    top_input = r["leak"]["rows"][0]["key"]
    assert rec[0]["key"] in DT.FOR_INPUT.get(top_input, [rec[0]["key"]])
    assert all(x["key"] != "rent_quotes" for x in DT.recommend(r, s, done={"rent_quotes"}, top=11))


def test_desk_checked_route_allows_a_decision_without_customers():
    lk = dict(rows=[dict(key="market"), dict(key="arpu"), dict(key="cac"), dict(key="fixed")])
    areas = {a: dict(name=a, ledger=.2) for a in ("market", "price", "cac")}
    cov = desk_coverage(lk, areas)
    assert cov["ok"] and cov["covered"] == ["market", "price", "cac"]
    assert not desk_coverage(lk, {**areas, "cac": dict(name="cac", ledger=.05)})["ok"]
    base = dict(name="plan", p_payback=.8, p_ruin=.05, npv_mean=1e5, payback_median=12)
    lim = dict(min_payback=.6, max_ruin=.2, horizon=36)
    assert D.decide(base, [base], lim, dict(strength=.05), [])["code"] == "test"
    d = D.decide(base, [base], lim, dict(strength=.05), [], cov)
    assert d["code"] == "launch" and "desk-checked" in d["label"] and d["desk_route"]


# ---------- teams, roles, comments, history, account ----------
def test_viewer_reads_and_comments_but_cannot_write(db):
    a = store.create_user("owner1", "s3cure-pass")["id"]; b = store.create_user("viewer1", "s3cure-pass")["id"]; c = store.create_user("stranger", "s3cure-pass")["id"]
    pid = store.create_project(a, "Cafe", {"intake": {"business_type": "cafe"}})
    store.share_project(a, pid, "VIEWER1", "viewer")
    assert store.load_project(b, pid)["role"] == "viewer" and [p["role"] for p in store.list_projects(b)] == ["viewer"]
    with pytest.raises(store.NotFound): store.save_project(b, pid, name="hijack")
    with pytest.raises(store.NotFound): store.add_evidence(b, pid, dict(claim="x"))
    with pytest.raises(store.NotFound): store.load_project(c, pid)
    store.add_comment(b, pid, "Decision", "Looks good")
    assert store.list_comments(a, pid)[0]["username"] == "viewer1"
    store.share_project(a, pid, "viewer1", "editor"); store.save_project(b, pid, name="Cafe v2")
    with pytest.raises(store.NotFound): store.share_project(b, pid, "stranger", "viewer")   # only the owner shares
    with pytest.raises(store.NotFound): store.delete_project(b, pid)
    with pytest.raises(ValueError): store.share_project(a, pid, "nobody-here", "viewer")


def test_history_activity_and_account_deletion(db, res):
    s, r = res
    a = store.create_user("histo", "s3cure-pass")["id"]
    pid = store.create_project(a, "K", s, r)
    store.add_snapshot(a, pid, "first", H.summary(r, s, 0))
    r2 = copy.deepcopy(r); r2["assumptions"]["fixed"]["likely"] *= 1.2; r2["decision"]["code"] = "stop"; r2["decision"]["label"] = "Stop"
    store.add_snapshot(a, pid, "quotes", H.summary(r2, s, 1))
    snaps = store.list_snapshots(a, pid)
    d = H.diff(snaps[0]["summary"], snaps[1]["summary"])
    assert d["moved"] and any("Fixed costs" in x for x in d["changes"])
    store.log(a, pid, "Recalculated", "x"); assert store.list_activity(a, pid)[0]["action"] == "Recalculated"
    assert store.export_account(a)["projects"][0]["project"]["id"] == pid
    store.delete_account(a)
    with pytest.raises(store.NotFound): store.get_user(a)
    with pytest.raises(store.NotFound): store.load_project(a, pid)


def test_benchmarks_need_three_accounts(db):
    for i in range(3):
        u = store.create_user(f"bench{i}", "s3cure-pass")["id"]
        store.create_project(u, "x", {"intake": {"business_type": "cafe", "price": 100 + i * 10}})
        b = store.sector_benchmarks("cafe")
        assert b["enough"] == (i == 2)
    assert b["medians"]["price"] == 110


# ---------- imports, calibration, alerts ----------
def test_stripe_export_becomes_monthly_results():
    csv = ("id,Created date (UTC),Amount,Customer Email,Status\n1,2027-01-03,100,a@x.com,Paid\n2,2027-01-20,150,b@x.com,Paid\n"
           "3,2027-02-02,100,a@x.com,Paid\n4,2027-02-05,999,c@x.com,Failed\n5,2027-02-09,200,d@x.com,Paid\n")
    df = AI.read(csv.encode()); preset = AI.detect(df)
    assert preset == "Stripe payments"
    rows = AI.to_plan_months(AI.monthly(df, AI.mapping(df, preset)), "2027-01")
    assert rows[0]["month"] == 1 and rows[0]["revenue"] == 250 and rows[0]["customers"] == 2 and rows[0]["new_customers"] == 2
    assert rows[1]["revenue"] == 300 and rows[1]["customers"] == 2 and rows[1]["new_customers"] == 1


def test_generic_counts_and_sheet_links():
    df = AI.read(b"Date,Revenue,Customers\n2027-01-15,42000,120\n2027-02-15,61000,170\n")
    rows = AI.to_plan_months(AI.monthly(df, AI.mapping(df, AI.detect(df))), "2027-01")
    assert rows[1]["customers"] == 170 and "new_customers" not in rows[1]
    assert AI.sheet_csv_url("https://docs.google.com/spreadsheets/d/abc_123/edit#gid=42").endswith("/d/abc_123/export?format=csv&gid=42")


def test_calibration_counts_actuals_inside_the_band():
    band = dict(p10=[10] * 12, p50=[20] * 12, p90=[30] * 12)
    acts = [dict(month=m, revenue=v) for m, v in zip(range(1, 13), [15, 25, 22, 5, 28, 19, 21, 35, 18, 24, 26, 12])]
    out = CAL.check([dict(name="P", baseline=dict(bands=dict(revenue=band)), actuals=acts)])
    assert out["n"] == 12 and abs(out["inside"] - 10 / 12) < 1e-9 and "calibrated" in out["verdict"].lower()


def test_overdue_desk_test_raises_an_alert(res):
    s, r = res
    s2 = dict(s, desk_tests={"rent_quotes": dict(name="Rent", status="planned", due=(dt.date.today() - dt.timedelta(days=2)).isoformat())})
    assert any("overdue" in a["text"] for a in AL.for_project("P", s2, r, [], None))
    assert AL.send(dict(email="", whatsapp=""), "x") == []


def test_report_pdf_and_slides(res):
    s, r = res
    c = RX.content(r, s, MZ.size(r), [], [], "Kitchen – test", "me")
    pdf, pptx = RX.pdf(c), RX.slides(c)
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000 and pptx[:2] == b"PK"
