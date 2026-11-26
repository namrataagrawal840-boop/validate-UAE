"""Calibration log: how well did earlier forecasts match what really happened?

For every project with real monthly results, each actual is checked against the forecast that was frozen
when monitoring started (the baseline): was it inside the 10th-90th percentile band, and how far was it from
the typical (median) path? A well-calibrated model has about 80% of actuals inside the band. With few
months the check is weak, and the app says so.
"""
import numpy as np


def check(projects):
    """projects: list of dict(name, baseline, actuals)."""
    rows = []
    for p in projects:
        b = p.get("baseline")
        if not b: continue
        for a in p["actuals"]:
            i = int(a["month"]) - 1
            for key, band in (("revenue", "revenue"), ("customers", "customers")):
                v = a.get(key)
                if v is None or band not in b["bands"] or i >= len(b["bands"][band]["p50"]): continue
                lo, mid, hi = (b["bands"][band][q][i] for q in ("p10", "p50", "p90"))
                rows.append(dict(project=p["name"], month=i + 1, metric=key, actual=float(v), low=float(lo), typical=float(mid), high=float(hi),
                                 inside=bool(lo <= v <= hi), error=(float(v) / mid - 1) if mid else None))
    if not rows: return dict(rows=[], n=0)
    inside = float(np.mean([r["inside"] for r in rows])); errs = [abs(r["error"]) for r in rows if r["error"] is not None]
    above = float(np.mean([r["actual"] > r["typical"] for r in rows]))
    n = len(rows)
    verdict = ("Too few data points to judge calibration yet (fewer than 12)." if n < 12 else
               "Well calibrated: about as many actuals fall inside the band as the model promises." if .7 <= inside <= .9 else
               "Over-confident: too many actuals fall outside the band; the real spread is wider than modelled." if inside < .7 else
               "Under-confident: the bands are wider than needed.")
    bias = ("Forecasts ran optimistic (most actuals below the typical path)." if above < .35 else
            "Forecasts ran pessimistic (most actuals above the typical path)." if above > .65 else "No clear optimistic or pessimistic bias.")
    return dict(rows=rows, n=n, inside=inside, expected_inside=.8, median_abs_error=float(np.median(errs)) if errs else None, share_above=above, verdict=verdict, bias=bias,
                projects=len({r["project"] for r in rows}))
