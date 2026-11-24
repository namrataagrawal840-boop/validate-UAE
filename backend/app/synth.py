"""Blinded synthetic market.

The simulated population is generated ONLY from (seed, business type) and the
category priors in priors.py. It never reads the idea text, the founder's
numbers or anything the AI agents say. That makes it a neutral test bed: the
idea is tested against the market, not used to build the market.
`tests/test_synth.py` enforces this.
"""
from functools import lru_cache
import hashlib
import numpy as np
from . import priors as P

N_PEOPLE = 20_000


@lru_cache(maxsize=32)
def market(seed: int, business_type: str):
    t = P.TYPES[business_type]
    rng = np.random.default_rng([seed, sum(map(ord, business_type))])
    n = N_PEOPLE
    em = rng.choice(len(P.EMIRATES), n, p=[e[1] for e in P.EMIRATES])
    age_b = rng.choice(len(P.AGE_BANDS), n, p=[a[1] for a in P.AGE_BANDS])
    age = np.array([a[2] for a in P.AGE_BANDS])[age_b] + rng.uniform(-4, 4, n)
    inc_b = rng.choice(len(P.INCOME_BANDS), n, p=[b[1] for b in P.INCOME_BANDS])
    income = np.array([b[2] for b in P.INCOME_BANDS])[inc_b] * np.exp(rng.normal(0, .25, n))
    inc_rel = income / np.median(income)
    # Category behaviour from priors only
    participates = rng.random(n) < np.clip(t["participation"] * (0.8 + 0.4 * (inc_rel > 1)), 0, 1)
    lo, mid, hi = t["cat_spend"]
    sigma = np.log(hi / lo) / 3.3
    cat_spend = mid * inc_rel ** 0.45 * np.exp(rng.normal(0, sigma, n))
    pain = rng.beta(*t["pain"], n)
    digital = np.clip(rng.beta(4 * t["digital"] + .5, 4 * (1 - t["digital"]) + .5, n) - (age - 35) * 0.006, 0, 1)
    price_sens = np.clip(1 / (1 + inc_rel) + rng.normal(0, .08, n), 0.02, 0.98)
    data = dict(emirate=em, age_band=age_b, age=age, income_band=inc_b, income=income, participates=participates,
                cat_spend=cat_spend, pain=pain, digital=digital, price_sens=price_sens)
    for v in data.values():
        v.setflags(write=False)
    return data


def fingerprint(m) -> str:
    h = hashlib.sha256()
    for k in sorted(m):
        h.update(k.encode()); h.update(np.ascontiguousarray(m[k]).tobytes())
    return h.hexdigest()[:16]


def check(m):
    """Compare simulated shares with the target population shares."""
    rows, worst = [], 0.0
    for name, col, spec in [("Emirate", "emirate", P.EMIRATES), ("Age", "age_band", P.AGE_BANDS), ("Income", "income_band", P.INCOME_BANDS)]:
        for j, s in enumerate(spec):
            actual = float(np.mean(m[col] == j)); worst = max(worst, abs(actual - s[1]))
            rows.append(dict(group=name, category=s[0], target=s[1], actual=actual))
    return dict(rows=rows, max_gap=worst, passed=worst < 0.02, n=len(m["emirate"]))


@lru_cache(maxsize=32)
def comparables(seed: int, business_type: str, n: int = 3000):
    """Reference set of plausible assumption vectors for this business type, sampled
    from the category priors with correlated noise in log space. Used by the
    anomaly stage to see whether an idea's assumptions look like a normal business."""
    t = P.TYPES[business_type]
    rng = np.random.default_rng([seed, 7, sum(map(ord, business_type))])
    keys = ["price", "var_pct", "fixed", "setup", "cac", "churn", "capacity"]
    common = rng.normal(0, .35, n)  # scale factor: bigger businesses cost more and serve more
    out = {}
    for k in keys:
        lo, mid, hi = t[k]
        s = np.log(hi / lo) / 3.3
        z = rng.normal(0, 1, n)
        load = {"fixed": .7, "setup": .7, "capacity": .7, "price": .2}.get(k, 0)
        out[k] = mid * np.exp(s * (load * common + np.sqrt(1 - load ** 2) * z))
    return keys, np.column_stack([np.log(out[k]) for k in keys])
