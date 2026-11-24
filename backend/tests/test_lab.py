from app import lab as LB
from app.compute import compute
from app.funnel.validation import experiment_kit

IT = dict(idea="An online platform that matches children with qualified Arabic tutors for live lessons and weekly reports.", business_type="education",
          emirate="All UAE", setup="Free zone", target_customer="Parents", budget_aed=300000, evidence_text="")
R = compute(dict(intake=IT))


def H(metric="pain_share", thr=.4, **kw):
    return dict(id="h1", statement="s", metric=metric, threshold=thr, expected=LB.expected_values(R)[metric], **kw)


def test_no_results_means_planned():
    assert LB.evaluate(H(), [])["status"] == "planned"


def test_strong_result_validates_and_weak_result_invalidates():
    good = [dict(kind="interviews", n=20, k=16, hypothesis_id="h1")]
    bad = [dict(kind="interviews", n=20, k=2, hypothesis_id="h1")]
    assert LB.evaluate(H(), good)["status"] == "validated"
    assert LB.evaluate(H(), bad)["status"] == "invalidated"


def test_results_for_other_hypotheses_are_ignored():
    ex = [dict(kind="interviews", n=20, k=16, hypothesis_id="other")]
    assert LB.evaluate(H(), ex)["status"] == "planned"


def test_churn_direction_is_lower_is_better():
    h = H("monthly_churn", .08)
    assert LB.evaluate(h, [dict(kind="pilot", customers=30, months=3, lost=1, hypothesis_id="h1")])["status"] == "validated"
    assert LB.evaluate(h, [dict(kind="pilot", customers=30, months=3, lost=25, hypothesis_id="h1")])["status"] == "invalidated"


def test_suggestions_and_plans_change_nothing():
    before = R["evidence"]["strength"]
    sug = LB.suggestions(R); kit = experiment_kit(IT, {}, 450, 500, .02)
    assert sug and all(s["metric"] in LB.METRICS for s in sug)
    p = LB.plan(dict(sug[0], id="x"), R, kit)
    assert p["sample_size"] >= LB.METRICS[sug[0]["metric"]][5] and p["steps"]
    assert LB.questionnaire(dict(sug[0], id="x"), R, kit)["questions"]
    assert R["evidence"]["strength"] == before
