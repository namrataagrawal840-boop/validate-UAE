from app.funnel import competition as CP

IDEA = "Live online Arabic lessons for children with qualified tutors and weekly progress reports for parents"


def _st(comps=None):
    return dict(competitors=comps or [], agents={})


def test_typical_types_when_nothing_named():
    c = CP.analyse(_st(), "education", IDEA, 450, 450)
    assert c["source"] == "typical" and len(c["competitors"]) == 4
    assert c["derived_rivalry"] is None and c["forces"] == {}


def test_similar_rival_scores_higher_than_unrelated():
    comps = [dict(name="Arabic Tutors Online", type="direct", price_aed=420, note="Live online Arabic lessons for kids with certified tutors", features=["Live online lessons"]),
             dict(name="Car wash", type="direct", price_aed=420, note="Mobile car washing at your building", features=[])]
    c = CP.analyse(_st(comps), "education", IDEA, 450, 450)
    a, b = (next(x for x in c["competitors"] if x["name"] == n) for n in ("Arabic Tutors Online", "Car wash"))
    assert a["similarity"] > b["similarity"] and a["threat"] > b["threat"]


def test_more_close_rivals_raise_rivalry_and_cut_differentiation():
    one = [dict(name="A", type="direct", price_aed=450, note="Live online Arabic lessons for children", features=["Live online lessons"])]
    many = one + [dict(name=x, type="direct", price_aed=430, note="Online Arabic tutors for children with progress reports", features=["Live online lessons", "Progress reports for parents"]) for x in "BCDE"]
    c1, c2 = CP.analyse(_st(one), "education", IDEA, 450, 450), CP.analyse(_st(many), "education", IDEA, 450, 450)
    assert c2["forces"]["rivalry"] > c1["forces"]["rivalry"]
    assert c2["differentiation"] <= c1["differentiation"]


def test_price_benchmark_percentile():
    comps = [dict(name=n, type="direct", price_aed=p, note="tutoring") for n, p in (("A", 200), ("B", 300), ("C", 400))]
    c = CP.analyse(_st(comps), "education", IDEA, 500, 450)
    assert c["price"]["percentile"] == 1.0 and c["price"]["position"] == "premium"


def test_every_category_has_criteria_and_types():
    for bt in CP.CRITERIA:
        c = CP.analyse(_st(), bt, "a new business idea", 100, 100)
        assert c["competitors"] and c["criteria"]
