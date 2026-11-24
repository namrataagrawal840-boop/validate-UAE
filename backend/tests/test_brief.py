from app.compute import compute

IT = dict(idea="A cloud kitchen delivering healthy high-protein lunches to office workers in Business Bay.", business_type="kitchen", emirate="Dubai",
          setup="Mainland", target_customer="Office workers", budget_aed=600000, evidence_text="")


def test_brief_has_every_part_and_five_actions():
    b = compute(dict(intake=IT))["brief"]
    assert b["code"] in ("launch", "test", "pivot", "stop") and b["label"]
    assert b["score_low"] <= b["score"] <= b["score_high"]
    assert len(b["next5"]) == 5 and all(a["action"] and a["where"] for a in b["next5"])
    assert b["risks"] and b["reasons"] and isinstance(b["missing"], list)
    assert b["strongest"] == []   # no ledger -> no supporting evidence claimed


def test_no_evidence_never_launches():
    r = compute(dict(intake=IT))
    assert r["evidence"]["strength"] < .35 and r["brief"]["code"] != "launch"


def test_disproved_hypothesis_is_reported():
    st = dict(intake=IT, hypotheses=[dict(id="h", statement="Half will sign up", metric="signup_rate", area="market", threshold=.5, expected=.1)],
              experiments=[dict(id="e", kind="landing", visitors=500, signups=5, spend=500, pay_rate=30, hypothesis_id="h")])
    b = compute(st)["brief"]
    assert b["hypotheses"]["disproved"] == 1 and any("Disproved" in w["why"] for w in b["weakest"])
