from app import agents as AG


def test_parse_json_from_text_with_code_block():
    t = 'Some research text.\n```json\n{"a": 1, "b": [2]}\n```'
    assert AG.parse_json(t) == {"a": 1, "b": [2]}


def test_invented_urls_are_dropped():
    found = {"https://www.example.ae/report"}
    out = AG.clean("customer", {"pains": [{"pain": "Food arrives cold", "intensity": 70, "url": "https://made-up.com/x"}],
                                "evidence": [{"quote": "Lunch always late", "url": "https://www.example.ae/report"}]}, found)
    assert out["pains"][0]["url"] == "" and out["evidence"][0]["url"] == "https://www.example.ae/report"


def test_numbers_are_clipped_and_bad_fields_skipped():
    out = AG.clean("finance", {"fields": {"churn": {"min": 5, "likely": 500, "max": 8}, "price": {"min": "x"}}}, set())
    assert out["fields"]["churn"]["max"] <= 60 and "price" not in out["fields"]


def test_critic_bounds():
    out = AG.clean("critic", {"market_haircut": 0.1, "cac_uplift": 9}, set())
    assert out["market_haircut"] == .4 and out["cac_uplift"] == 1.8


def test_web_sourced_numbers_are_labelled_benchmarked():
    from app.compute import build_assumptions
    st = dict(intake=dict(idea="x" * 30, business_type="cafe", emirate="Dubai"),
              agents={"finance": {"fields": {"fixed": dict(min=50000, likely=60000, max=70000, source="Broker report", url="https://x.ae")}}})
    A, _ = build_assumptions(st)
    assert A["fixed"]["label"] == "web" and A["price"]["label"] == "prior"
