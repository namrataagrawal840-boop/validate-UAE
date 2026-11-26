"""Social listening: real public posts and comments about the problem, the category and competitors.

Sources
  - YouTube comments      YouTube Data API v3, free key (YOUTUBE_API_KEY)
  - Reddit                official API; needs an approved app (REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET). Reddit closed
                          unauthenticated access in 2026 and requires approval for new API apps since November 2025.
  - Web (AI)              Claude web search finds public Reddit threads, Instagram and TikTok posts, Google reviews, X posts
                          and forums, and quotes short excerpts with their links (ANTHROPIC_API_KEY)
  - Paste or CSV          any platform: copy comments from Instagram, TikTok, Facebook, Google Maps, WhatsApp groups, or upload an export

Analysis (no AI needed): VADER sentiment, TF-IDF + k-means themes, objection types (same categories as the
customer panel), demand signals ("looking for", "any recommendations", "would pay"), and platform mix.
"""
import csv
import datetime as dt
import io
import re

import numpy as np
import requests

from .funnel import checks as C

UA = "ValidateUAE/1.0 (business idea research)"
MAX_POSTS = 600

OBJECTION_WORDS = {
    "price": r"expensive|pric(e|ey|ing)|overpriced|cost(ly|s)?\b|afford|\baed\b|\bdhs?\b|rip.?off|not worth|cheaper",
    "trust": r"scam|trust|fake|unreliable|reliab|quality|hygien|dirty|bad experience|never again|disappoint",
    "convenience": r"far\b|location|parking|traffic|delivery|late\b|slow|waiting|queue|timing|hours|book(ing)?|app (is|was)",
    "time": r"no time|busy|schedule|after work|too long|takes (forever|ages)",
    "switching": r"used to|stick with|already (use|have)|switch",
    "no_pain": r"don.?t need|no need|waste of|pointless|why would",
    "competitor": r"instead|better than|compared to|alternative",
}
NEGATIVE_PHRASES = r"not worth|rip.?off|overpriced|scam|nightmare|never again|waste of (money|time)|too expensive|way too|charged me twice|never refunded|disappointed|terrible|awful"
DEMAND = r"looking for|any (good )?recommend|recommend(ation)?s?\b|where can i|anyone know|need (a|an|some)\b|wish (there|they)|would (pay|love)|is there (a|any)|suggest(ion)?s?\b|best .* in (dubai|abu dhabi|sharjah|uae)"


def _sentiment():
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    except Exception:  # pragma: no cover - fallback if the package is missing
        return None


def post(platform, text, url="", date=None, likes=None, source="pasted", where="uae"):
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return dict(platform=platform, text=t[:1500], url=url if str(url).startswith("http") else "", date=date, likes=likes, source=source, where=where)


# ---------------- collectors ----------------
def youtube(query, key, max_videos=6, per_video=60, region="AE", timeout=15):
    s = requests.get("https://www.googleapis.com/youtube/v3/search", timeout=timeout,
                     params=dict(part="snippet", q=query, type="video", maxResults=max_videos, regionCode=region, relevanceLanguage="en", key=key)).json()
    if "error" in s: raise RuntimeError(s["error"].get("message", "YouTube API error"))
    out = []
    for v in s.get("items", []):
        vid = v["id"].get("videoId")
        if not vid: continue
        c = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", timeout=timeout,
                         params=dict(part="snippet", videoId=vid, maxResults=min(per_video, 100), order="relevance", textFormat="plainText", key=key)).json()
        for it in c.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            out.append(post("YouTube", sn.get("textDisplay"), f"https://www.youtube.com/watch?v={vid}&lc={it['id']}", (sn.get("publishedAt") or "")[:10],
                            sn.get("likeCount"), "youtube_api", "uae" if region == "AE" else "global"))
    return out


def reddit(query, client_id, secret, subreddits=("dubai", "UAE", "abudhabi", "Sharjah", "dubai_expats"), per_sub=15, timeout=15):
    tok = requests.post("https://www.reddit.com/api/v1/access_token", auth=(client_id, secret), data={"grant_type": "client_credentials"},
                        headers={"User-Agent": UA}, timeout=timeout)
    if tok.status_code != 200: raise RuntimeError(f"Reddit refused the app credentials (HTTP {tok.status_code}). New Reddit API apps need approval.")
    h = {"Authorization": f"bearer {tok.json()['access_token']}", "User-Agent": UA}
    out = []
    for sub in subreddits:
        r = requests.get(f"https://oauth.reddit.com/r/{sub}/search", headers=h, timeout=timeout,
                         params=dict(q=query, restrict_sr=1, sort="relevance", t="all", limit=per_sub))
        if r.status_code != 200: continue
        for ch in r.json().get("data", {}).get("children", []):
            d = ch["data"]; link = "https://www.reddit.com" + d.get("permalink", "")
            out.append(post("Reddit", f"{d.get('title', '')}. {d.get('selftext', '')}", link, dt.date.fromtimestamp(d.get("created_utc", 0)).isoformat(),
                            d.get("score"), "reddit_api"))
            cm = requests.get(f"https://oauth.reddit.com/comments/{d['id']}", headers=h, params=dict(limit=20, depth=1, sort="top"), timeout=timeout)
            if cm.status_code == 200 and isinstance(cm.json(), list) and len(cm.json()) > 1:
                for c in cm.json()[1].get("data", {}).get("children", [])[:20]:
                    cd = c.get("data", {})
                    if cd.get("body"):
                        out.append(post("Reddit", cd["body"], "https://www.reddit.com" + cd.get("permalink", d.get("permalink", "")),
                                        dt.date.fromtimestamp(cd.get("created_utc", 0)).isoformat(), cd.get("score"), "reddit_api"))
    return out


PLATFORMS = ("Reddit", "Instagram", "TikTok", "X", "Facebook", "Google reviews", "YouTube", "Forum", "News comments", "Other")


def web_ai(intake, competitors=(), max_searches=8):
    """Claude searches the web for real public posts and returns short excerpts with links (only links it actually found)."""
    from . import agents as AG
    topic = intake["idea"][:300]
    prompt = (f"Find real public posts, comments and reviews written by people in the UAE about the problem or category behind this idea: {topic}\n"
              f"Customer: {intake.get('target_customer') or 'general'}. Area: {intake.get('emirate')}. "
              + (f"Also look for reviews of: {', '.join(competitors[:5])}. " if competitors else "") +
              "Search Reddit (r/dubai, r/UAE, r/abudhabi), Instagram and TikTok posts, Google Maps reviews, X, Facebook groups and local forums. "
              "Quote each person's words exactly, at most 40 words each, and give the URL of the page you found it on. Do not invent anything; only use pages from your searches. "
              'Reply with JSON only: {"posts": [{"platform": "Reddit|Instagram|TikTok|X|Facebook|Google reviews|YouTube|Forum|News comments|Other", '
              '"text": "", "url": "", "date": "YYYY-MM-DD or empty"}]}')
    data, found = AG.call(prompt, max_searches=max_searches, max_tokens=8000)
    out = []
    for p in (data or {}).get("posts") or []:
        u = AG.url_ok(p.get("url"), found)
        if not u or not str(p.get("text", "")).strip(): continue  # no verifiable link -> dropped
        plat = p.get("platform") if p.get("platform") in PLATFORMS else "Other"
        out.append(post(plat, " ".join(str(p["text"]).split()[:60]), u, p.get("date") or None, None, "web_ai"))
    return out


def parse_paste(text, platform="Other", url=""):
    """One comment per line, or comments separated by blank lines."""
    raw = text.replace("\r", "")
    chunks = [c for c in re.split(r"\n\s*\n", raw) if c.strip()] if "\n\n" in raw else raw.split("\n")
    return [post(platform, c, url, source="pasted") for c in chunks if len(c.strip()) >= 3][:MAX_POSTS]


def parse_csv(data, default_platform="Other"):
    """CSV export from any tool. Uses columns named text/comment/body/content/review/message, and optional platform/url/date/likes."""
    txt = data.decode("utf-8-sig", errors="replace") if isinstance(data, (bytes, bytearray)) else data
    rd = csv.DictReader(io.StringIO(txt))
    cols = {c.lower().strip(): c for c in (rd.fieldnames or [])}
    tcol = next((cols[c] for c in ("text", "comment", "body", "content", "review", "message", "caption") if c in cols), None)
    if not tcol: raise ValueError("The CSV needs a column called text, comment, body, content, review or message.")
    get = lambda r, *names: next((r.get(cols[n]) for n in names if n in cols and r.get(cols[n])), None)
    out = []
    for r in rd:
        if not (r.get(tcol) or "").strip(): continue
        likes = get(r, "likes", "like_count", "score", "upvotes")
        try: likes = int(float(likes)) if likes is not None else None
        except ValueError: likes = None
        out.append(post(get(r, "platform", "source") or default_platform, r[tcol], get(r, "url", "link", "permalink") or "", get(r, "date", "created", "timestamp"), likes, "csv"))
        if len(out) >= MAX_POSTS: break
    return out


def merge(existing, new):
    seen = {(p["platform"], p["text"][:120].lower()) for p in existing}
    out = list(existing)
    for p in new:
        k = (p["platform"], p["text"][:120].lower())
        if k in seen or len(p["text"]) < 3: continue
        seen.add(k); out.append(p)
    return out[:MAX_POSTS]


# ---------------- analysis ----------------
def analyse(posts, idea_text="", competitor_names=()):
    if not posts: return None
    sia = _sentiment()
    comp_re = "|".join(re.escape(c.lower()) for c in competitor_names if c and len(c) > 2)
    rows = []
    for p in posts:
        t = p["text"]; tl = t.lower()
        s = sia.polarity_scores(t)["compound"] if sia else 0.0
        demand = bool(re.search(DEMAND, tl))
        if re.search(NEGATIVE_PHRASES, tl): s = min(s, -.45)          # clear complaints VADER can miss ("not worth the price")
        elif demand: s = float(np.clip(s, -.25, .25))                  # requests are asks, not opinions: count as neutral
        objs = [k for k, rx in OBJECTION_WORDS.items() if re.search(rx, tl)]
        if comp_re and re.search(comp_re, tl) and "competitor" not in objs: objs.append("competitor")
        rows.append(dict(p, sentiment=float(s), objections=objs if s < .3 else [o for o in objs if o in ("price",)], demand=demand))
    n = len(rows)
    sent = np.array([r["sentiment"] for r in rows])
    obj = {k: sum(k in r["objections"] for r in rows) / n for k in OBJECTION_WORDS}
    plat = {}
    for r in rows: plat[r["platform"]] = plat.get(r["platform"], 0) + 1
    topics = C.text_topics([r["text"] for r in rows], idea_text) if n >= 8 else dict(status="skipped", reason="Fewer than 8 posts", topics=[])
    def examples(pred, k=4):
        xs = sorted([r for r in rows if pred(r)], key=lambda r: -(r.get("likes") or 0))
        return [dict(text=r["text"][:280], platform=r["platform"], url=r["url"], sentiment=r["sentiment"]) for r in xs[:k]]
    return dict(n=n, platforms=plat, sentiment=float(sent.mean()), positive=float((sent >= .3).mean()), negative=float((sent <= -.3).mean()),
                neutral=float(((sent > -.3) & (sent < .3)).mean()), objections=obj, demand=sum(r["demand"] for r in rows) / n, topics=topics,
                with_links=sum(bool(r["url"]) for r in rows) / n,
                examples=dict(positive=examples(lambda r: r["sentiment"] >= .3), negative=examples(lambda r: r["sentiment"] <= -.3),
                              demand=examples(lambda r: r["demand"]),
                              **{f"obj_{k}": examples(lambda r, k=k: k in r["objections"], 2) for k in OBJECTION_WORDS}),
                rows=rows)


def evidence_record(summary, intake, sources):
    """Ledger record: real public posts are secondary research (self-selected, unverified)."""
    plats = ", ".join(f"{k} {v}" for k, v in sorted(summary["platforms"].items(), key=lambda x: -x[1]))
    return dict(claim=f"{summary['n']} public posts: {summary['positive']:.0%} positive, {summary['negative']:.0%} negative; {summary['demand']:.0%} ask for or recommend something like this",
                area="pain", ev_type="secondary", description=f"Social listening ({plats}). Sources: {', '.join(sorted(sources))}.", source_url="",
                collected_on=dt.date.today().isoformat(), geography="uae", sample_size=int(summary["n"]), verification="unverified", confidence="medium",
                limitations="People who post online are not a random sample; posts are about the category, not your product. Open a few links to verify.")
