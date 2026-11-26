import json

import pytest
from app import social as SO
from app import panel as PN
from tests.test_panel import R

POSTS = """Way too expensive for what you get, AED 700 a month is a rip off
Anyone know a good women only gym in Sharjah? Looking for one near Al Majaz
Love my studio, the classes are amazing and the coaches are great!
Parking is a nightmare and the location is so far from me
I would pay for childcare at the gym, that's my biggest problem
Not worth the price honestly, cheaper options exist
Booking app was slow and classes are always full
Highly recommend small group classes, much better than big gyms
Any recommendations for ladies fitness in Sharjah?
Scam, they charged me twice and never refunded"""


def test_paste_and_analysis():
    posts = SO.parse_paste(POSTS, "Instagram")
    assert len(posts) == 10 and all(p["platform"] == "Instagram" for p in posts)
    s = SO.analyse(posts, "women-only fitness studio in Sharjah")
    assert s["n"] == 10 and s["objections"]["price"] >= .2 and s["demand"] >= .2
    assert -1 <= s["sentiment"] <= 1 and abs(s["positive"] + s["negative"] + s["neutral"] - 1) < 1e-9
    assert s["examples"]["negative"] and s["topics"]["status"] == "ran"


def test_csv_import_and_merge():
    data = "comment,platform,url,likes\n\"Too pricey\",TikTok,https://tiktok.com/x,12\n\"Need this!\",TikTok,,3\n".encode()
    ps = SO.parse_csv(data)
    assert [p["platform"] for p in ps] == ["TikTok", "TikTok"] and ps[0]["likes"] == 12
    assert len(SO.merge(ps, ps)) == 2
    with pytest.raises(ValueError): SO.parse_csv(b"a,b\n1,2\n")


def test_youtube_collector_parses_api(monkeypatch):
    class Resp:
        def __init__(self, d): self.d = d; self.status_code = 200
        def json(self): return self.d
    def fake_get(url, params=None, timeout=None, headers=None):
        if "search" in url: return Resp({"items": [{"id": {"videoId": "v1"}}]})
        return Resp({"items": [{"id": "c1", "snippet": {"topLevelComment": {"snippet": {"textDisplay": "So expensive in Dubai", "likeCount": 5, "publishedAt": "2026-01-02T00:00:00Z"}}}}]})
    monkeypatch.setattr(SO.requests, "get", fake_get)
    out = SO.youtube("gym dubai", "KEY")
    assert out[0]["platform"] == "YouTube" and out[0]["likes"] == 5 and "watch?v=v1" in out[0]["url"]


def test_web_ai_drops_posts_without_found_links(monkeypatch):
    from app import agents as AG
    monkeypatch.setattr(AG, "call", lambda *a, **k: ({"posts": [{"platform": "Reddit", "text": "real one", "url": "https://reddit.com/r/dubai/1"},
                                                              {"platform": "Instagram", "text": "made up", "url": "https://instagram.com/fake"}]},
                                                    {"https://reddit.com/r/dubai/1": "t"}))
    out = SO.web_ai(dict(idea="gym", emirate="Dubai"))
    assert [p["text"] for p in out] == ["real one"]


def test_panel_grounded_in_real_posts_shifts_objections():
    s = SO.analyse(SO.parse_paste(POSTS * 3, "Reddit"), "gym")
    s["objections"] = {k: (.9 if k == "price" else 0) for k in s["objections"]}
    a, b = PN.build(R, n=80, seed=5), PN.build(R, n=80, seed=5, social=s)
    share = lambda p: sum(x["objection"] == "price" for x in p["people"]) / len(p["people"])
    assert share(b) > share(a) and b["grounded"]["posts"] == s["n"]
    assert any(x["echo"] for x in b["people"])


def test_sentiment_rules_for_complaints_and_requests():
    rows = {r["text"]: r for r in SO.analyse(SO.parse_paste(POSTS, "Instagram"), "gym")["rows"]}
    assert rows["Not worth the price honestly, cheaper options exist"]["sentiment"] < -.3
    assert -.3 < rows["I would pay for childcare at the gym, that's my biggest problem"]["sentiment"] < .3
    assert -.3 < rows["Any recommendations for ladies fitness in Sharjah?"]["sentiment"] < .3
    assert rows["Love my studio, the classes are amazing and the coaches are great!"]["sentiment"] > .3
