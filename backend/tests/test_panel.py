import numpy as np
from app import panel as PN
from app.compute import compute

FIT = dict(idea="A women-only boutique fitness studio in Sharjah with small group classes and childcare.", business_type="fitness", emirate="Sharjah",
           setup="Mainland", target_customer="Women aged 25-50 living in Sharjah", budget_aed=900000, evidence_text="")
R = compute(dict(intake=FIT))


def test_personas_come_from_the_market_and_match_the_audience():
    p = PN.build(R, n=50)
    assert p["n"] == 50 and {x["gender"] for x in p["people"]} == {"f"}
    assert all(x["emirate"] == "Sharjah" for x in p["people"])
    assert len({x["quote"] for x in p["people"]}) > 20  # varied voices


def test_discounted_intent_tracks_the_buying_model():
    p = PN.build(R, n=400, seed=1)
    s = PN.synthesise(p, R)
    assert abs(s["actual_rate"] - p["model_rate"]) < max(.03, p["model_rate"] * .6)


def test_debate_moves_opinions_by_friedkin_johnsen_and_keeps_bounds():
    p = PN.build(R, n=40); d = PN.debate(p, R)
    assert d and len(d["members"]) == 6 and len(d["history"]) == 4
    h = np.array(d["history"]); assert (h >= 0).all() and (h <= 1).all()
    assert sum(d["final_votes"].values()) == 6
    assert d["lines"][0]["who"] == "Moderator"


def test_synthesis_is_labelled_simulated():
    p = PN.build(R, n=40); p["debate"] = PN.debate(p, R); s = PN.synthesise(p, R)
    assert "Simulated" in s["caveat"] and s["questions"] and s["objections"] and s["van_westendorp"]
    assert sum(s["counts"].values()) == 40


def test_mixed_audience_has_both_genders():
    it = dict(FIT, idea="A healthy lunch delivery service for office workers in Dubai.", target_customer="Office workers", business_type="kitchen", emirate="Dubai")
    p = PN.build(compute(dict(intake=it)), n=60)
    assert {x["gender"] for x in p["people"]} == {"f", "m"}


def test_ai_voices_are_cleaned_and_marked(monkeypatch):
    p = PN.build(R, n=8)
    fake = {"people": [{"id": x["id"], "intent": "maybe", "rating": 99, "max_price_aed": 300, "objection": "price", "quote": "Too pricey for a studio.",
                        "change_mind": "A trial."} for x in p["people"]] + [{"id": "intruder", "intent": "yes"}]}
    monkeypatch.setattr(PN, "_ai", lambda prompt, max_tokens=4000: fake)
    PN.ai_voices(p, R)
    assert p["mode"] == "ai" and all(x["source"] == "ai" and x["intent"] == "maybe" and x["rating"] == 10 and x["wtp"] == 300 for x in p["people"])
    monkeypatch.setattr(PN, "_ai", lambda prompt, max_tokens=4000: (_ for _ in ()).throw(RuntimeError("no network")))
    q = PN.build(R, n=8); PN.ai_voices(q, R)
    assert q["mode"] == "model"  # failures fall back to the model-driven panel
