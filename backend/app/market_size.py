"""TAM, SAM and SOM from published population figures, step by step.

    residents of the area (official)                       x base group (adults / online / families / households)
    x audience (e.g. women only, official gender split)    x share who use this kind of service (published)
    = TAM people; x spend per user per year                = TAM in AED
    x share one business can reach (model assumption)      = SAM; x your price per year = SAM in AED
    x share interested in this idea (simulated panel)      = interested people
    customers in the typical simulated future (capped)     = SOM

Every step says where its number comes from. The user can replace any number; their figure is then labelled
"your figure".
"""
import re

from . import priors as P
from . import public_data as PD
from .funnel.market_stages import CATCHMENT


def audience(intake):
    t = f"{intake.get('idea', '')} {intake.get('target_customer', '')}".lower()
    if re.search(r"\b(women|woman|female|ladies|mothers|mums|moms|girls)\b", t): return "women"
    if re.search(r"\b(men|male|gentlemen|fathers|dads|boys)\b", t.replace("women", "")): return "men"
    return None


def _src(x, kind=None):
    return dict(source=x["source"], year=x["year"], url=x["url"], kind=kind or x["kind"])


def size(result, overrides=None, panel=None):
    ov = overrides or {}
    it = result["intake"]; bt = it["business_type"]; area = it.get("emirate") or "All UAE"
    cat = PD.CATEGORY[bt]
    steps = []

    def step(key, label, factor, people, meta, unit="share"):
        if key in ov and ov[key] not in (None, ""):
            v = float(ov[key])
            meta = dict(source="Your figure", year=None, url="", kind="yours")
            people = v if unit == "people" else (steps[-1]["people"] * v if steps else v)
            factor = v
        steps.append(dict(key=key, label=label, factor=factor, people=float(people), unit=unit, **meta))
        return steps[-1]["people"]

    pop = PD.POPULATION.get(area, PD.POPULATION["All UAE"])
    n = step("population", f"People living in {area if area in PD.POPULATION else 'the UAE'}", pop["value"], pop["value"], _src(pop), unit="people")
    base = cat["base"]
    if base == "adults":
        n = step("base", "Adults (18+)", PD.ADULT_SHARE["value"], n * PD.ADULT_SHARE["value"], _src(PD.ADULT_SHARE))
    elif base == "online":
        f = PD.ADULT_SHARE["value"] * PD.INTERNET["value"]
        n = step("base", "Adults who are online", f, n * f, dict(source=f"{PD.INTERNET['source']}; adults share is an assumption", year=PD.INTERNET["year"], url=PD.INTERNET["url"], kind="published"))
    elif base == "families":
        n = step("base", "Parents of school-age children", PD.FAMILY_SHARE["value"], n * PD.FAMILY_SHARE["value"], _src(PD.FAMILY_SHARE))
    else:
        f = 1 / PD.HOUSEHOLD_SIZE["value"]
        n = step("base", "Households", f, n * f, _src(PD.HOUSEHOLD_SIZE))
    aud = audience(it)
    if aud:
        f = PD.WOMEN_SHARE["value"] if aud == "women" else 1 - PD.WOMEN_SHARE["value"]
        n = step("audience", f"Only {aud}", f, n * f, _src(PD.WOMEN_SHARE))
    lo, mid, hi = cat["share"]
    src = cat["share_src"]
    meta = dict(source="; ".join(f"{s['source']} ({s['year']}): {s['value']:.0%}" for s in src), year=max(s["year"] for s in src), url=src[0]["url"],
                kind="assumption" if all(s["kind"] == "assumption" for s in src) else "published")
    tam_people = step("category", f"…who {cat['label']} (TAM)", mid, n * mid, meta)
    if cat["spend"]:
        spend = cat["spend"]["value"]; spend_meta = _src(cat["spend"])
    else:
        spend = float(P.TYPES[bt]["price"][1]); spend_meta = dict(source="Typical monthly spend for this business type in the app's UAE category figures", year=None, url="", kind="assumption")
    if "spend" in ov and ov["spend"] not in (None, ""): spend = float(ov["spend"]); spend_meta = dict(source="Your figure", year=None, url="", kind="yours")
    reach = CATCHMENT[bt] if it.get("setup") != "Online only" else max(CATCHMENT[bt], .5)
    sam_people = step("reach", "…that one business like yours can reach (SAM)", reach, tam_people * reach,
                      dict(source="Model assumption: location, delivery radius and marketing reach of one business of this type", year=None, url="", kind="assumption"))
    if panel and panel.get("people"):
        ps = panel["people"]; interest = sum(p["intent"] in ("yes", "maybe") for p in ps) / len(ps)
        imeta = dict(source=f"Simulated customer panel: {sum(p['intent'] == 'yes' for p in ps)} yes and {sum(p['intent'] == 'maybe' for p in ps)} maybe out of {len(ps)}", year=None, url="", kind="simulated")
    else:
        interest = float(result["stages"]["classify"]["mean_adoption"]) * 3
        imeta = dict(source="Buying model (no panel yet)", year=None, url="", kind="simulated")
    interested = step("interest", "…interested in this idea", interest, sam_people * interest, imeta)
    f = result["stages"]["forecast"]
    cap = float(result["assumptions"]["capacity"]["likely"])
    som_people = min(float(f["customers_end_p50"]), cap) if f.get("customers_end_p50") is not None else min(interested * .45, cap)
    if "som" in ov and ov["som"] not in (None, ""): som_people = float(ov["som"])
    price = float(result["unit"]["arpu"])
    growth = PD.GROWTH.get(area, PD.GROWTH["All UAE"])
    proj = [dict(year=y, tam_people=tam_people * (1 + growth["value"]) ** y, sam_people=sam_people * (1 + growth["value"]) ** y) for y in range(0, 4)]
    # Ranges: each step's uncertainty depends on what kind of number it is. Official counts are tight, published
    # surveys wider, our own assumptions widest. The category share uses its published low and high.
    import math
    U = dict(official=.03, published=.2, assumption=.35, yours=0, simulated=.5)
    pre = [x for x in steps if x["key"] in ("population", "base", "audience")]
    sd = math.sqrt(sum(math.log(1 + (.08 if x["key"] == "base" and x["kind"] == "assumption" else U.get(x["kind"], .3))) ** 2 for x in pre))
    cat_ok = "category" not in ov or ov["category"] in (None, "")
    t_lo = (n * lo if cat_ok else tam_people) * math.exp(-sd); t_hi = (n * hi if cat_ok else tam_people) * math.exp(sd)
    t_lo, t_hi = min(t_lo, tam_people), max(t_hi, tam_people)
    r_unc = (1, 1) if "reach" in ov and ov["reach"] not in (None, "") else (.6, 1.5)
    s_lo, s_hi = min(sam_people, t_lo * reach * r_unc[0]), max(sam_people, t_hi * reach * r_unc[1])
    cb = (f.get("bands") or {}).get("customers")
    if cb and "som" not in ov:
        som_lo, som_hi = min(som_people, float(cb["p10"][-1]), cap), min(max(som_people, float(cb["p90"][-1])), cap)
    else:
        som_lo, som_hi = som_people * .5, som_people * 1.5
    return dict(steps=steps, spend_per_month=spend,
                ranges=dict(tam=(t_lo, t_hi), sam=(s_lo, s_hi), som=(som_lo, som_hi),
                            note="Ranges combine the uncertainty of each step: official counts ±3%, published surveys ±20%, model assumptions ±35-50%, and the spread of simulated futures for SOM."), spend_meta=spend_meta, price_per_month=price,
                tam=dict(people=tam_people, aed=tam_people * spend * 12, range=(n * lo, n * hi)),
                sam=dict(people=sam_people, aed=sam_people * price * 12), interested=dict(people=interested, aed=interested * price * 12),
                som=dict(people=som_people, aed=som_people * price * 12, share_of_sam=som_people / sam_people if sam_people else 0,
                         source=f"Customers in the typical simulated future after {f['horizon']} months (capped at capacity {cap:,.0f})"),
                growth=dict(rate=growth["value"], **_src(growth)), projection=proj, area=area, audience=aud)
