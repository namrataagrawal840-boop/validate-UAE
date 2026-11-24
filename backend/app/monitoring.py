"""Monitoring: compare real monthly results with the forecast that was frozen when monitoring started.

Month 1 is the first month of trading, the same as month 1 of the forecast. For revenue, expenses and
customers the forecast is a band from the simulation (10th to 90th percentile); a result outside the band
is flagged. Rates (conversion, repeat purchase) and CAC are compared with the plan's assumptions.
"""
import datetime as dt

import numpy as np
from scipy.stats import beta as Beta

from .funnel import checks as C


def baseline(r):
    """Snapshot of today's forecast. Stored once, so later recalculations don't move the goalposts."""
    b = r["stages"]["forecast"]["bands"]; A = r["assumptions"]
    return dict(created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                bands={k: b[k] for k in ("revenue", "costs", "customers", "new", "marketing", "cash") if k in b},
                conversion=float(r["stages"]["experiments"]["predicted_conversion"]), churn=float(A["churn"]["likely"]) / 100,
                churn_range=[float(A["churn"]["min"]) / 100, float(A["churn"]["max"]) / 100], cac=float(A["cac"]["likely"]),
                cac_range=[float(A["cac"]["min"]), float(A["cac"]["max"])], budget=float(r["limits"]["budget"]),
                upfront=float((r.get("finance") or {}).get("scenarios", {}).get("typical", {}).get("upfront") or A["setup"]["likely"]),
                horizon=int(r["stages"]["forecast"]["horizon"]))


def _flag(v, lo, hi):
    return "below" if v < lo else "above" if v > hi else "within"


def compare(base, rows):
    rows = sorted(rows, key=lambda x: x["month"])
    out = []; prev_customers = None
    for x in rows:
        m = int(x["month"]); i = m - 1
        rec = dict(month=m, notes=x.get("notes") or "")
        for key, band in (("revenue", "revenue"), ("expenses", "costs"), ("customers", "customers")):
            v = x.get(key)
            if v is None or band not in base["bands"] or i >= len(base["bands"][band]["p50"]): continue
            p10, p50, p90 = (base["bands"][band][q][i] for q in ("p10", "p50", "p90"))
            rec[key] = dict(actual=float(v), expected=float(p50), low=float(p10), high=float(p90),
                            deviation=(float(v) / p50 - 1) if p50 else None, flag=_flag(v, p10, p90))
        if x.get("visitors") and x.get("conversions") is not None:
            n, k = int(x["visitors"]), int(x["conversions"]); a, b = C.beta_post(n, k)
            lo, hi = Beta.ppf([.05, .95], a, b)
            exp = base["conversion"]
            rec["conversion"] = dict(actual=k / n, expected=exp, low=float(lo), high=float(hi), deviation=(k / n) / exp - 1 if exp else None,
                                     flag="below" if hi < exp else "above" if lo > exp else "within")
        if x.get("repeat_customers") is not None and prev_customers:
            rate = float(x["repeat_customers"]) / prev_customers
            exp = 1 - base["churn"]; lo, hi = 1 - base["churn_range"][1], 1 - base["churn_range"][0]
            rec["repeat"] = dict(actual=rate, expected=exp, low=lo, high=hi, deviation=rate / exp - 1, flag=_flag(rate, lo, hi))
        if x.get("marketing_spend") is not None and x.get("new_customers"):
            cac = float(x["marketing_spend"]) / float(x["new_customers"])
            lo, hi = base["cac_range"]
            rec["cac"] = dict(actual=cac, expected=base["cac"], low=lo, high=hi, deviation=cac / base["cac"] - 1,
                              flag="worse" if cac > hi else "better" if cac < lo else "within")
        if x.get("customers") is not None: prev_customers = float(x["customers"])
        out.append(rec)

    # cash and runway from actuals: budget minus upfront spend minus cumulative losses
    have = [x for x in rows if x.get("revenue") is not None and x.get("expenses") is not None]
    cash = None; runway = None; burn = None
    if have:
        cum = sum(float(x["revenue"]) - float(x["expenses"]) for x in have)
        cash = base["budget"] - base["upfront"] + cum
        last = have[-3:]; net = np.mean([float(x["revenue"]) - float(x["expenses"]) for x in last])
        burn = float(-net) if net < 0 else 0.0
        runway = float(cash / burn) if burn > 0 and cash > 0 else (0.0 if cash <= 0 else None)

    metrics = ("revenue", "expenses", "customers", "conversion", "repeat", "cac")
    bad = {"revenue": "below", "customers": "below", "conversion": "below", "repeat": "below", "expenses": "above", "cac": "worse"}
    alerts = []
    for k in metrics:
        recent = [r_[k] for r_ in out[-3:] if k in r_]
        if not recent: continue
        offs = sum(1 for z in recent if z["flag"] == bad[k])
        if offs >= 2 or (len(recent) == 1 and offs == 1):
            dev = np.mean([z["deviation"] for z in recent if z["deviation"] is not None]) if any(z["deviation"] is not None for z in recent) else 0
            alerts.append(dict(metric=k, months=offs, deviation=float(dev)))
    on_track = sum(1 for k in metrics if any(k in r_ for r_ in out) and k not in {a["metric"] for a in alerts})
    tracked = sum(1 for k in metrics if any(k in r_ for r_ in out))
    return dict(rows=out, alerts=alerts, on_track=on_track, tracked=tracked, cash_now=cash, monthly_burn=burn, runway_months=runway)


def revenue_series(rows):
    """Consecutive monthly revenue from month 1, for recalibrating the forecast with real sales."""
    by = {int(x["month"]): x.get("revenue") for x in rows}
    out = []
    for m in range(1, max(by) + 1 if by else 1):
        if by.get(m) is None: break
        out.append(float(by[m]))
    return out
