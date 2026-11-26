"""Search demand: how many people in the UAE search for this kind of product each month.

Sources
  - DataForSEO Google Ads search volume (exact monthly volumes, cost per click, competition, 12-month history).
    Needs DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD; about $0.09 per lookup, $1 free credit on sign-up.
  - Google Keyword Planner CSV export (free; exact numbers or ranges such as "100 - 1K").
  - Google Trends: SerpApi (SERPAPI_KEY, free 250 searches a month) or the CSV you download from trends.google.com.
    Trends values are relative (0-100): used for trend and seasonality, never as volumes.

Analysis: total searches, buying-intent share, 12-month trend, seasonal peaks, average cost per click in AED, and what
search could bring: searches x click share x landing conversion x share who pay (each assumption labelled).
"""
import csv
import datetime as dt
import io
import re

import numpy as np
import requests

USD_AED = 3.6725
UAE_LOCATION = 2784  # Google Ads geo target for the United Arab Emirates
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
BUY_WORDS = r"\b(price|prices|cost|near me|best|book|booking|membership|delivery|order|buy|cheap|offer|deal|subscription|classes|hire|rates?|fees?)\b"

TERMS = {  # category words people actually type, English and Arabic
    "cafe": (["cafe", "coffee shop", "specialty coffee", "breakfast cafe"], ["مقهى", "كافيه"]),
    "kitchen": (["healthy meal delivery", "meal plan", "lunch delivery", "healthy food delivery"], ["توصيل وجبات صحية", "وجبات صحية"]),
    "retail": (["shop", "store", "boutique"], ["متجر"]),
    "ecommerce": (["online shopping", "buy online", "online store"], ["تسوق اونلاين"]),
    "app": (["app", "online platform", "software"], ["تطبيق"]),
    "services": (["cleaning service", "home services", "maintenance service"], ["خدمات تنظيف", "خدمات منزلية"]),
    "education": (["tutor", "private tutor", "tuition", "online classes"], ["مدرس خصوصي", "دروس خصوصية"]),
    "fitness": (["gym", "fitness classes", "fitness studio", "personal trainer"], ["نادي رياضي", "جيم"]),
}
AREA_AR = {"Dubai": "دبي", "Abu Dhabi": "أبوظبي", "Sharjah": "الشارقة", "Ajman": "عجمان", "Ras Al Khaimah": "رأس الخيمة", "Fujairah": "الفجيرة", "Umm Al Quwain": "أم القيوين"}


def suggest_keywords(intake, features=(), limit=24):
    """Search phrases built from the business type, area, audience and features. The user edits them."""
    bt = intake["business_type"]; area = intake.get("emirate") if intake.get("emirate") not in (None, "", "All UAE") else "uae"
    en, ar = TERMS[bt]
    t = f"{intake.get('idea', '')} {intake.get('target_customer', '')}".lower()
    women = bool(re.search(r"\b(women|woman|female|ladies|mothers|girls)\b", t))
    kids = bool(re.search(r"\b(child|children|kids|parents)\b", t))
    out = []
    for w in en:
        out += [f"{w} {area.lower()}", f"{w} near me", f"best {w} {area.lower()}"]
        if women: out += [f"ladies {w} {area.lower()}", f"women only {w}"]
        if kids: out += [f"{w} for kids {area.lower()}"]
    out += [f"{w} price {area.lower()}" for w in en[:2]]
    out += [f"{f.lower()} {area.lower()}" for f in list(features)[:3]]
    a = AREA_AR.get(intake.get("emirate"), "الإمارات")
    out += [f"{w} {a}" for w in ar[:2]]
    seen, res = set(), []
    for k in out:
        k = re.sub(r"\s+", " ", k).strip()
        if k and k not in seen: seen.add(k); res.append(k)
    return res[:limit]


def trends_link(keywords, geo="AE"):
    from urllib.parse import quote
    return "https://trends.google.com/trends/explore?geo=" + geo + "&date=today%2012-m&q=" + quote(",".join(keywords[:5]))


# ---------------- sources ----------------
def dataforseo(keywords, login, password, timeout=60):
    rows = []
    groups = {"ar": [k for k in keywords if re.search(r"[؀-ۿ]", k)]}
    groups["en"] = [k for k in keywords if k not in groups["ar"]]
    for lang, kws in groups.items():
        if not kws: continue
        r = requests.post("https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live", auth=(login, password), timeout=timeout,
                          json=[dict(keywords=kws[:1000], location_code=UAE_LOCATION, language_code=lang)])
        d = r.json()
        if r.status_code != 200 or d.get("status_code") != 20000:
            raise RuntimeError(d.get("status_message") or f"DataForSEO error (HTTP {r.status_code})")
        task = (d.get("tasks") or [{}])[0]
        if task.get("status_code") not in (20000, None): raise RuntimeError(task.get("status_message", "DataForSEO task failed"))
        for it in task.get("result") or []:
            ms = sorted([dict(ym=f"{m['year']}-{m['month']:02d}", v=m.get("search_volume") or 0) for m in it.get("monthly_searches") or []], key=lambda x: x["ym"])
            rows.append(dict(keyword=it["keyword"], volume=it.get("search_volume"), low=it.get("search_volume"), high=it.get("search_volume"),
                             cpc_aed=(it.get("cpc") or 0) * USD_AED or None, competition=it.get("competition"), monthly=ms, source="DataForSEO (Google Ads data)"))
    return rows


def _num(s):
    s = str(s or "").strip().replace(",", "").upper()
    if not s or s in ("-", "--"): return None
    m = re.match(r"^([\d.]+)\s*([KM]?)$", s)
    if not m: return None
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6}[m.group(2)]


def parse_range(s):
    """'1K – 10K' -> (1000, 10000); '320' -> (320, 320)."""
    s = str(s or "").replace("–", "-").replace("—", "-")
    parts = [p for p in re.split(r"\s*-\s*", s) if p.strip()]
    vals = [v for v in (_num(p) for p in parts) if v is not None]
    if not vals: return None, None
    return (vals[0], vals[-1])


def keyword_planner_csv(data):
    """Google Keyword Planner export (UTF-16 tab-separated or UTF-8 CSV, with two title lines)."""
    raw = data if isinstance(data, str) else (data.decode("utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else data.decode("utf-8-sig", errors="replace"))
    lines = raw.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(r'^"?Keyword"?[\t,]', l)), None)
    if start is None: raise ValueError("This doesn't look like a Keyword Planner export: no 'Keyword' column found.")
    body = "\n".join(lines[start:]); delim = "\t" if "\t" in lines[start] else ","
    rd = csv.DictReader(io.StringIO(body), delimiter=delim)
    rows = []
    for r in rd:
        kw = (r.get("Keyword") or "").strip()
        if not kw: continue
        lo, hi = parse_range(r.get("Avg. monthly searches"))
        if lo is None: continue
        ms = []
        for col, val in r.items():
            m = re.match(r"Searches:\s*([A-Za-z]{3})\s+(\d{4})", col or "")
            if m and _num(val) is not None: ms.append(dict(ym=f"{m.group(2)}-{MONTHS.index(m.group(1).title()) + 1:02d}", v=_num(val)))
        lowbid = _num((r.get("Top of page bid (low range)") or "").replace("AED", "").replace("$", ""))
        highbid = _num((r.get("Top of page bid (high range)") or "").replace("AED", "").replace("$", ""))
        cur = "AED" if "AED" in "".join(str(v) for v in r.values()) or "(AED)" in " ".join(rd.fieldnames or []) else "USD"
        cpc = ((lowbid or 0) + (highbid or lowbid or 0)) / (2 if highbid else 1) if lowbid else None
        rows.append(dict(keyword=kw, volume=(lo + hi) / 2 if hi != lo else lo, low=lo, high=hi,
                         cpc_aed=(cpc * (1 if cur == "AED" else USD_AED)) if cpc else None, competition=(r.get("Competition") or "").strip() or None,
                         monthly=sorted(ms, key=lambda x: x["ym"]), source="Google Keyword Planner export" + (" (ranges)" if hi != lo else "")))
    if not rows: raise ValueError("No keyword rows with search volumes were found in the file.")
    return rows


def trends_csv(data):
    """Google Trends 'Interest over time' CSV: relative interest (0-100) per week or month."""
    raw = data if isinstance(data, str) else data.decode("utf-8-sig", errors="replace")
    lines = [l for l in raw.splitlines() if l.strip()]
    start = next((i for i, l in enumerate(lines) if re.match(r"^(Week|Month|Day|Time),", l)), None)
    if start is None: raise ValueError("This doesn't look like a Google Trends 'Interest over time' CSV.")
    rd = csv.reader(io.StringIO("\n".join(lines[start:])))
    head = next(rd); terms = [re.sub(r":\s*\(.*\)$", "", h).strip() for h in head[1:]]
    series = {t: [] for t in terms}
    for r in rd:
        for t, v in zip(terms, r[1:]):
            series[t].append(dict(date=r[0], v=0.5 if v.strip() == "<1" else float(v or 0)))
    return dict(source="Google Trends CSV", series=series)


def serpapi_trends(keywords, key, geo="AE", timeout=30):
    r = requests.get("https://serpapi.com/search.json", timeout=timeout,
                     params=dict(engine="google_trends", q=",".join(keywords[:5]), geo=geo, data_type="TIMESERIES", date="today 12-m", api_key=key))
    d = r.json()
    if d.get("error"): raise RuntimeError(d["error"])
    series = {}
    for p in (d.get("interest_over_time") or {}).get("timeline_data", []):
        for v in p.get("values", []):
            series.setdefault(v["query"], []).append(dict(date=p.get("date"), v=float(v.get("extracted_value") or 0)))
    if not series: raise RuntimeError("Google Trends returned no data for these terms in the UAE (too few searches).")
    return dict(source="Google Trends via SerpApi", series=series)


# ---------------- analysis ----------------
def analyse(rows, trends=None, landing_rate=.04, pay_rate=.30, click_share=.05, cac_assumed=None):
    rows = [r for r in rows or [] if r.get("volume") is not None]
    out = dict(n=len(rows), total=None, total_low=None, total_high=None)
    if rows:
        vol = np.array([r["volume"] for r in rows], float)
        out.update(total=float(vol.sum()), total_low=float(sum(r["low"] for r in rows)), total_high=float(sum(r["high"] for r in rows)),
                   ranges=any(r["low"] != r["high"] for r in rows))
        buy = [r for r in rows if re.search(BUY_WORDS, r["keyword"].lower())]
        out["buy_share"] = float(sum(r["volume"] for r in buy) / max(vol.sum(), 1))
        cp = [(r["cpc_aed"], r["volume"]) for r in rows if r.get("cpc_aed")]
        out["cpc_aed"] = float(sum(c * v for c, v in cp) / max(sum(v for _, v in cp), 1)) if cp else None
        # 12-month pattern from monthly histories
        agg = {}
        for r in rows:
            for m in r.get("monthly") or []: agg[m["ym"]] = agg.get(m["ym"], 0) + m["v"]
        yms = sorted(agg)[-24:]
        out["monthly"] = [dict(ym=k, v=agg[k]) for k in yms]
        if len(yms) >= 6:
            vals = np.array([agg[k] for k in yms[-12:]], float)
            idx = vals / max(vals.mean(), 1e-9)
            months = [MONTHS[int(k[5:7]) - 1] for k in yms[-12:]]
            out["peak"] = months[int(idx.argmax())]; out["low_month"] = months[int(idx.argmin())]; out["swing"] = float(idx.max() - idx.min())
        if len(yms) >= 15:
            last3 = sum(agg[k] for k in yms[-3:]); prior = sum(agg[k] for k in yms[-15:-12])
            out["growth"] = float(last3 / prior - 1) if prior else None
        top = sorted(rows, key=lambda r: -r["volume"])
        out["top"] = [dict(keyword=r["keyword"], volume=r["volume"], low=r["low"], high=r["high"], cpc_aed=r.get("cpc_aed")) for r in top[:12]]
        clicks = out["total"] * click_share
        signups = clicks * landing_rate
        out["funnel"] = dict(searches=out["total"], clicks=clicks, signups=signups, customers=signups * pay_rate, click_share=click_share,
                             landing_rate=landing_rate, pay_rate=pay_rate)
        if out["cpc_aed"]:
            out["cost_per_signup"] = out["cpc_aed"] / max(landing_rate, 1e-6)
            out["cost_per_customer"] = out["cost_per_signup"] / max(pay_rate, 1e-6)
            out["cac_check"] = None if not cac_assumed else float(out["cost_per_customer"] / cac_assumed)
    if trends and trends.get("series"):
        tot = None
        for s in trends["series"].values():
            arr = np.array([p["v"] for p in s], float)
            tot = arr if tot is None else tot[:len(arr)] + arr[:len(tot)]
        if tot is not None and len(tot) >= 8:
            h = len(tot) // 2
            out["trend_change"] = float(tot[h:].mean() / max(tot[:h].mean(), 1e-9) - 1)
            out["trend_points"] = tot.round(1).tolist()
            out["trend_dates"] = [p["date"] for p in next(iter(trends["series"].values()))][:len(tot)]
        out["trend_source"] = trends["source"]
    return out


def evidence_record(summary, sources, exact):
    lo, hi = summary.get("total_low"), summary.get("total_high")
    vol = f"{summary['total']:,.0f}" if not summary.get("ranges") else f"{lo:,.0f}-{hi:,.0f}"
    return dict(claim=f"About {vol} Google searches a month in the UAE for {summary['n']} related phrases", area="market", ev_type="secondary",
                description=f"Search demand from {', '.join(sorted(sources))}." + (f" Average cost per click AED {summary['cpc_aed']:.2f}." if summary.get("cpc_aed") else ""),
                source_url="", collected_on=dt.date.today().isoformat(), geography="uae", sample_size=None,
                verification="verified" if exact else "partly", confidence="medium",
                limitations="Searches are not people (one person searches several phrases); volumes are country-level; " + ("Keyword Planner ranges are wide." if summary.get("ranges") else "Google Ads estimates."))


def localise(summary, emirate):
    """Google Ads volumes are for the whole UAE. Phrases like "near me" mostly come from where people live, so the
    local share is estimated from the emirate's share of the UAE population (an assumption, labelled as such)."""
    from . import public_data as PD
    if not summary or not summary.get("total") or not emirate or emirate == "All UAE" or emirate not in PD.POPULATION: return summary
    share = PD.POPULATION[emirate]["value"] / PD.POPULATION["All UAE"]["value"]
    return dict(summary, local_area=emirate, local_share=share, local_total=summary["total"] * share,
                local_note=f"About {share:.0%} of UAE residents live in {emirate} ({PD.POPULATION[emirate]['source']}); local searches are estimated with that share.")
