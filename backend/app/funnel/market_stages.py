"""Stages 1, 2, 4 and 5 of the funnel, run on the blinded synthetic market.

1. Describe  - "What does the market look like?"      descriptive statistics
2. Segment   - "Who is similar?"                      Gaussian mixture, k chosen by BIC
4. Classify  - "Will they buy?"                        logistic choice model, calibrated by experiments
5. Regress   - "How much will they spend?"            weighted linear regression (hurdle: whether, then how much)
"""
import numpy as np
from scipy.optimize import brentq
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from .. import priors as P

CATCHMENT = {"cafe": .03, "kitchen": .08, "retail": .05, "ecommerce": .5, "app": .5, "services": .10, "education": .20, "fitness": .03}
sigmoid = lambda x: 1 / (1 + np.exp(-x))


def focus_mask(m, emirate):
    if emirate in (None, "", "All UAE"):
        return np.ones(len(m["emirate"]), dtype=bool)
    names = [e[0] for e in P.EMIRATES]
    return m["emirate"] == names.index(emirate) if emirate in names else np.ones(len(m["emirate"]), dtype=bool)


def scale_factor(m):
    return P.UAE_POPULATION / len(m["emirate"])


def describe(m, intake):
    t = P.TYPES[intake["business_type"]]
    f = focus_mask(m, intake.get("emirate")); part = f & m["participates"]
    sc = scale_factor(m)
    spend = m["cat_spend"][part]
    tam = float(spend.sum() * 12 * sc)
    return dict(
        people_in_focus=int(f.sum() * sc), category_buyers=int(part.sum() * sc), participation=float(part.sum() / max(1, f.sum())),
        spend_p25=float(np.quantile(spend, .25)), spend_median=float(np.median(spend)), spend_p75=float(np.quantile(spend, .75)),
        pain_mean=float(m["pain"][part].mean()), pain_high_share=float((m["pain"][part] > .6).mean()),
        digital_mean=float(m["digital"][part].mean()), tam_aed=tam,
        income_mix=[dict(band=b[0], share=float((m["income_band"][part] == j).mean())) for j, b in enumerate(P.INCOME_BANDS)],
        note=f"Category spending today on {t['label'].lower()}: what simulated buyers in {intake.get('emirate') or 'the UAE'} already spend, before your idea exists.")


FEATURES = ["log_income", "log_spend", "pain", "price_sens", "digital", "age"]


def feature_matrix(m, idx):
    return np.column_stack([np.log(m["income"][idx]), np.log(m["cat_spend"][idx]), m["pain"][idx], m["price_sens"][idx], m["digital"][idx], m["age"][idx]])


def segment(m, intake, seed=2027, max_k=6, sample=5000):
    f = focus_mask(m, intake.get("emirate")) & m["participates"]
    idx = np.where(f)[0]
    X = feature_matrix(m, idx); scaler = StandardScaler().fit(X); Z = scaler.transform(X)
    rng = np.random.default_rng(seed); sub = rng.choice(len(Z), min(sample, len(Z)), replace=False)
    best, bics = None, []
    for k in range(2, max_k + 1):
        g = GaussianMixture(k, covariance_type="full", random_state=seed, n_init=2).fit(Z[sub])
        b = g.bic(Z[sub]); bics.append(dict(k=k, bic=float(b)))
        if best is None or b < best[1]:
            best = (g, b, k)
    g, _, k = best
    labels = np.full(len(m["emirate"]), -1); labels[idx] = g.predict(Z)
    return dict(k=k, bic=bics, labels=labels, focus_idx=idx)


def segment_profiles(m, seg, p_adopt, arpu_i, intake):
    labels = seg["labels"]; sc = scale_factor(m); out = []
    names = [e[0] for e in P.EMIRATES]
    for s in range(seg["k"]):
        g = labels == s
        if not g.any(): continue
        pa = p_adopt[g]; exp_cust = float(pa.sum() * sc)
        top_em = names[int(np.bincount(m["emirate"][g], minlength=len(names)).argmax())]
        inc = float(np.median(m["income"][g])); age = float(np.median(m["age"][g]))
        dig = float(m["digital"][g].mean()); pain = float(m["pain"][g].mean()); ps = float(m["price_sens"][g].mean())
        name = f"{'High' if inc > 30000 else 'Middle' if inc > 12000 else 'Budget'}-income, {'online-first' if dig > .6 else 'in-person' if dig < .4 else 'mixed-channel'}, age ~{int(round(age))}"
        out.append(dict(id=int(s), name=name, share=float(g.sum() / max(1, (labels >= 0).sum())), people=int(g.sum() * sc), median_income=inc,
                        median_age=age, pain=pain, digital=dig, price_sensitivity=ps, adoption=float(pa.mean()), expected_customers=exp_cust,
                        arpu=float((pa * arpu_i[g]).sum() / max(pa.sum(), 1e-9)), top_emirate=top_em,
                        value=float((pa * arpu_i[g]).sum() * sc)))
    tot = sum(s["value"] for s in out) or 1
    for s in out: s["value_share"] = s["value"] / tot
    out.sort(key=lambda s: -s["value"])
    return out


def wtp(m):
    # What a buyer would pay for a solution in this category: today's spend, lifted by how unhappy they are
    return m["cat_spend"] * (1 + 0.6 * (m["pain"] - 0.5))


def channel_fit(m, intake):
    t = P.TYPES[intake["business_type"]]
    target = 0.95 if intake.get("setup") == "Online only" else t["digital"]
    return 1 - np.abs(m["digital"] - target)


def utility(m, intake, price, comp_pos, coefs):
    return (coefs["b0"] + coefs["b_value"] * np.log(wtp(m) / price) + coefs["b_pain"] * (m["pain"] - 0.5)
            + coefs["b_fit"] * (channel_fit(m, intake) - 0.5) * 2 + coefs["b_comp"] * comp_pos)


def adoption(m, intake, price, comp_pos, coefs):
    f = focus_mask(m, intake.get("emirate")) & m["participates"]
    return np.where(f, sigmoid(utility(m, intake, price, comp_pos, coefs)), 0.0)


def calibrate_intercept(m, intake, price, comp_pos, coefs, target_rate):
    """Shift the intercept so the average predicted adoption in the focus market
    equals an observed rate (Platt-style calibration on the intercept only)."""
    f = focus_mask(m, intake.get("emirate")) & m["participates"]
    u = utility(m, intake, price, comp_pos, coefs)[f]
    g = lambda delta: sigmoid(u + delta).mean() - target_rate
    try:
        return float(brentq(g, -15, 15))
    except ValueError:
        return 0.0


def market_potential(m, intake, p_adopt):
    t = P.TYPES[intake["business_type"]]
    reach = CATCHMENT[intake["business_type"]]
    if intake.get("setup") == "Online only": reach = max(reach, .5)
    total = float(p_adopt.sum() * scale_factor(m))
    return dict(adopters_if_aware=total, catchment=reach, potential=total * reach,
                mean_adoption=float(p_adopt[p_adopt > 0].mean()) if (p_adopt > 0).any() else 0.0)


def spend_model(m, intake, price, p_adopt, seed=2027):
    """Hurdle model, part 2: given that someone buys, how much do they spend a month?
    Spend scales with how much they spend in the category today. A weighted linear
    regression (weights = adoption probability) shows what drives spend."""
    t = P.TYPES[intake["business_type"]]
    raw = np.clip((m["cat_spend"] / t["cat_spend"][1]) ** 0.5, 0.5, 2.0)
    buyers = m["participates"]
    intensity = raw / raw[buyers].mean()  # the average category buyer spends exactly the planned price
    arpu_i = price * intensity
    idx = np.where(p_adopt > 0)[0]
    rng = np.random.default_rng(seed); sub = rng.choice(idx, min(6000, len(idx)), replace=False)
    X = feature_matrix(m, sub); Xs = StandardScaler().fit_transform(X)
    y = np.log(arpu_i[sub]); wgt = p_adopt[sub]
    reg = LinearRegression().fit(Xs, y, sample_weight=wgt)
    r2 = float(reg.score(Xs, y, sample_weight=wgt))
    expected = float((p_adopt * arpu_i).sum() / max(p_adopt.sum(), 1e-9))
    drivers = sorted([dict(feature=f, effect=float(c)) for f, c in zip(FEATURES, reg.coef_)], key=lambda d: -abs(d["effect"]))
    return dict(arpu_i=arpu_i, expected_arpu=expected, r2=r2, drivers=drivers)
