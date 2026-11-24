"""Stage 3 (anomaly), stage 6 (survival), stage 8 (text) and stage 9 (experiments)."""
import re
import numpy as np
from scipy.stats import norm
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from .. import priors as P
from ..synth import comparables


# ---------- Stage 3: "Is something unusual?" Isolation Forest on the assumptions ----------
def anomaly(assumptions, business_type, seed=2027):
    keys, ref = comparables(seed, business_type)
    model = IsolationForest(n_estimators=300, contamination="auto", random_state=seed).fit(ref)
    x = np.array([[np.log(max(assumptions[k]["likely"], 1e-6)) for k in keys]])
    ref_scores = model.score_samples(ref); s = float(model.score_samples(x)[0])
    pct_more_normal = float((ref_scores > s).mean())  # share of comparable plans that look more normal than this one
    flags, per = [], []
    for j, k in enumerate(keys):
        q = float((ref[:, j] < x[0, j]).mean())
        direction = P.OPTIMISTIC_DIRECTION.get(k, 0)
        unusual = q < .05 or q > .95
        optimistic = unusual and ((q > .95 and direction > 0) or (q < .05 and direction < 0))
        per.append(dict(key=k, name=P.NAMES[k], percentile=q, unusual=unusual, optimistic=optimistic, value=assumptions[k]["likely"],
                        typical=float(np.exp(np.median(ref[:, j])))))
        if unusual:
            flags.append(dict(key=k, name=P.NAMES[k], percentile=q, optimistic=optimistic, label=assumptions[k].get("label")))
    return dict(score=s, outlier=bool(model.predict(x)[0] == -1), more_normal_share=pct_more_normal, per_assumption=per, flags=flags,
                optimistic_count=sum(f["optimistic"] for f in flags), reference_size=len(ref))


# ---------- Stage 6: "How long do customers stay / how long until payback?" ----------
def kaplan_meier(times, events, horizon):
    """Kaplan-Meier estimate. times: month of event or censoring; events: 1 if it happened."""
    times = np.asarray(times, float); events = np.asarray(events, int)
    out, s = [], 1.0
    for t in range(1, horizon + 1):
        at_risk = np.sum(times >= t); d = np.sum((times == t) & (events == 1))
        if at_risk > 0: s *= 1 - d / at_risk
        out.append(1 - s)  # probability the event has happened by month t
    return out


def customer_survival(segments, churn_pct, satisfaction, horizon=36):
    rows = []
    for s in segments:
        h = churn_pct / 100 * (1.5 - satisfaction) * (0.75 + 0.5 * s["price_sensitivity"])
        h = float(np.clip(h, 1e-4, .95))
        rows.append(dict(segment=s["name"], monthly_hazard=h, median_months=float(np.log(2) / h), mean_months=float(1 / h),
                         survival=[float(np.exp(-h * t)) for t in range(0, horizon + 1, 3)]))
    return rows


# ---------- Stage 8: "What are customers talking about?" TF-IDF topics ----------
NEG = set("expensive costly cold late slow rude dirty crowded hard difficult confusing poor bad worst broken missing unclear wait waiting never "
          "overpriced disappointed problem issue hate annoying unreliable delay delayed cancel cancelled refund".split())


def split_docs(text):
    parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 20]


def text_topics(docs, idea_text, seed=2027):
    docs = [d for d in docs if d][:400]
    if len(docs) < 6:
        return dict(status="skipped", reason=f"Only {len(docs)} pieces of customer text. Paste at least 6 reviews or interview notes to run this stage.", topics=[], n_docs=len(docs))
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, max_features=3000, sublinear_tf=True)
    X = vec.fit_transform(docs); terms = np.array(vec.get_feature_names_out())
    k = int(np.clip(len(docs) // 4, 2, 5))
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)
    idea_v = vec.transform([idea_text])
    topics = []
    for c in range(k):
        members = np.where(km.labels_ == c)[0]
        if not len(members): continue
        cen = km.cluster_centers_[c]; top = terms[np.argsort(cen)[::-1][:6]].tolist()
        sim = float((idea_v @ cen.reshape(-1, 1))[0, 0] / (np.linalg.norm(cen) * (np.sqrt(idea_v.multiply(idea_v).sum()) or 1) or 1))
        neg = float(np.mean([any(w in NEG for w in re.findall(r"[a-z]+", docs[i].lower())) for i in members]))
        rep = members[np.argmax((X[members] @ cen.reshape(-1, 1)).ravel())]
        topics.append(dict(terms=top, size=int(len(members)), share=float(len(members) / len(docs)), negative_share=neg,
                           idea_match=sim, example=docs[rep][:240]))
    topics.sort(key=lambda t: -t["size"])
    match = max((t["idea_match"] for t in topics), default=0)
    return dict(status="ran", n_docs=len(docs), k=k, topics=topics, best_match=match,
                evidence_supports_problem=bool(match >= .12 and any(t["idea_match"] >= .12 and t["share"] >= .15 for t in topics)))


# ---------- Stage 9: "Does our action change it?" experiment design and analysis ----------
def sample_size(p0, rel_lift=0.5, alpha=.05, power=.8):
    p0 = float(np.clip(p0, 1e-4, .9)); p1 = min(p0 * (1 + rel_lift), .99)
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power); pb = (p0 + p1) / 2
    n = ((za * np.sqrt(2 * pb * (1 - pb)) + zb * np.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2) / (p1 - p0) ** 2
    return int(np.ceil(n))


def beta_post(n, k):
    return 1 + k, 1 + n - k


def ab_compare(nA, kA, nB, kB, seed=7, draws=40000):
    rng = np.random.default_rng(seed)
    a = rng.beta(*beta_post(nA, kA), draws); b = rng.beta(*beta_post(nB, kB), draws)
    lift = b / np.maximum(a, 1e-9) - 1
    return dict(p_b_better=float((b > a).mean()), lift_mean=float(lift.mean()), lift_ci=[float(np.quantile(lift, .05)), float(np.quantile(lift, .95))],
                rate_a=float((1 + kA) / (2 + nA)), rate_b=float((1 + kB) / (2 + nB)))


def price_elasticity(points):
    """points: list of (price, n, k). Fits log-odds(accept) = a + b*log(price) by
    maximum likelihood on the binomial counts. Returns -b (the model's value coefficient)."""
    from scipy.optimize import minimize
    pr = np.log([p for p, _, _ in points]); n = np.array([x[1] for x in points], float); k = np.array([x[2] for x in points], float)
    def nll(th):
        z = th[0] + th[1] * pr; pz = 1 / (1 + np.exp(-z)); pz = np.clip(pz, 1e-9, 1 - 1e-9)
        return -np.sum(k * np.log(pz) + (n - k) * np.log(1 - pz)) + 0.01 * th[1] ** 2
    r = minimize(nll, [0.0, -1.0])
    return float(np.clip(-r.x[1], 0.2, 6.0)), float(r.x[0])
