import pytest
from app import search_demand as SD

KP = ("Keyword Stats 2026-11-26 at 12_00_00\nNovember 1, 2025 - October 31, 2026\n"
      "Keyword\tCurrency\tAvg. monthly searches\tCompetition\tTop of page bid (low range)\tTop of page bid (high range)\tSearches: Sep 2026\tSearches: Oct 2026\n"
      "ladies gym sharjah\tAED\t1K – 10K\tHigh\t2.10\t6.30\t1000\t1300\n"
      "women only gym\tAED\t100 – 1K\tMedium\t1.50\t4.00\t300\t400\n")


def test_keyword_suggestions_follow_the_idea():
    ks = SD.suggest_keywords(dict(business_type="fitness", emirate="Sharjah", idea="women-only studio with childcare", target_customer="Women in Sharjah"))
    assert "ladies gym sharjah" in ks and any("الشارقة" in k for k in ks) and len(ks) == len(set(ks))


def test_keyword_planner_export_with_ranges_utf16():
    rows = SD.keyword_planner_csv(KP.encode("utf-16"))
    assert [r["keyword"] for r in rows] == ["ladies gym sharjah", "women only gym"]
    assert rows[0]["low"] == 1000 and rows[0]["high"] == 10000 and rows[0]["cpc_aed"] == pytest.approx(4.2)
    assert rows[0]["monthly"] == [{"ym": "2026-09", "v": 1000}, {"ym": "2026-10", "v": 1300}]
    with pytest.raises(ValueError): SD.keyword_planner_csv(b"a,b\n1,2")


def test_trends_csv_and_analysis():
    tr = SD.trends_csv("Category: All categories\n\nWeek,ladies gym: (United Arab Emirates)\n" + "\n".join(f"2026-0{1 + i // 4}-0{1 + i % 4},{40 + i * 3}" for i in range(12)))
    s = SD.analyse(SD.keyword_planner_csv(KP), tr, landing_rate=.05, pay_rate=.3, cac_assumed=100)
    assert s["total_low"] == 1100 and s["total_high"] == 11000 and s["ranges"]
    assert s["trend_change"] > 0 and s["cost_per_signup"] == pytest.approx(s["cpc_aed"] / .05)
    assert s["funnel"]["customers"] == pytest.approx(s["total"] * .05 * .05 * .3)


def test_dataforseo_parsing(monkeypatch):
    class R:
        status_code = 200
        def json(self): return {"status_code": 20000, "tasks": [{"status_code": 20000, "result": [
            {"keyword": "gym sharjah", "search_volume": 2400, "cpc": 1.2, "competition": "HIGH",
             "monthly_searches": [{"year": 2026, "month": m, "search_volume": 2000 + 100 * m} for m in range(1, 13)]}]}]}
    monkeypatch.setattr(SD.requests, "post", lambda *a, **k: R())
    rows = SD.dataforseo(["gym sharjah"], "l", "p")
    assert rows[0]["volume"] == 2400 and rows[0]["cpc_aed"] == pytest.approx(1.2 * SD.USD_AED) and len(rows[0]["monthly"]) == 12
    s = SD.analyse(rows)
    assert s["peak"] == "Dec" and s["low_month"] == "Jan"


def test_serpapi_error_is_raised(monkeypatch):
    class R:
        def json(self): return {"error": "Invalid API key"}
    monkeypatch.setattr(SD.requests, "get", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="Invalid"): SD.serpapi_trends(["gym"], "bad")
