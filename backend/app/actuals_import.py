"""Bring real monthly results in from the tools a business already uses, as CSV exports (or a public Google Sheet).

Recognised exports (detected from the column names): Google Analytics 4, Stripe payments, Shopify orders,
Meta Ads, Google Ads, and a generic sheet. Rows are added up per calendar month and mapped to the plan's
month 1 (the first month of trading, chosen by the user). Nothing is guessed: a column that is not in the
file stays empty.
"""
import csv
import io
import re

import pandas as pd

PRESETS = {  # name: (columns that identify it, {field: candidate column names})
    "Google Analytics 4": ({"sessions", "date"}, dict(date=["date"], visitors=["sessions", "users", "total users"], conversions=["conversions", "key events"])),
    "Stripe payments": ({"amount", "created date (utc)"}, dict(date=["created date (utc)", "created (utc)", "created"], revenue=["amount", "converted amount"],
                                                             customer=["customer id", "customer email", "customer"], status=["status"])),
    "Shopify orders": ({"created at", "total"}, dict(date=["created at"], revenue=["total"], customer=["email", "customer"], order=["name"])),
    "Meta Ads": ({"amount spent (aed)"}, dict(date=["reporting starts", "day", "date"], marketing_spend=["amount spent (aed)"], conversions=["results"])),
    "Google Ads": ({"cost", "day"}, dict(date=["day", "date"], marketing_spend=["cost"], visitors=["clicks"], conversions=["conversions"])),
}
FIELDS = ["date", "revenue", "expenses", "customer", "visitors", "conversions", "marketing_spend", "status", "order"]


def read(data):
    """Parse CSV bytes or text; Google Ads and Meta exports often have a title line above the header."""
    text = data.decode("utf-8-sig", errors="replace") if isinstance(data, (bytes, bytearray)) else data
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines[:10]) if l.count(",") >= 1 and not re.match(r"^\s*#", l) and len(next(csv.reader([l]))) >= 2), 0)
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df.columns = [str(c).strip() for c in df.columns]
    return df


def detect(df):
    cols = {c.lower() for c in df.columns}
    for name, (need, _) in PRESETS.items():
        if need <= cols: return name
    return "Generic"


def mapping(df, preset):
    cols = {c.lower(): c for c in df.columns}
    if preset in PRESETS:
        return {f: next((cols[c] for c in cand if c in cols), None) for f, cand in PRESETS[preset][1].items()}
    guess = dict(date=["date", "month", "day"], revenue=["revenue", "sales", "income"], expenses=["expenses", "costs"], customer=["customers", "customer"],
                 visitors=["visitors", "sessions"], conversions=["conversions", "signups", "orders"], marketing_spend=["marketing", "ad spend", "marketing_spend"])
    return {f: next((cols[c] for c in cand if c in cols), None) for f, cand in guess.items()}


def _money(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")


def monthly(df, mp):
    """Calendar-month totals. If the customer column holds ids/emails, customers = unique buyers and new customers
    = buyers seen for the first time; if it holds numbers, it is taken as the customer count."""
    if not mp.get("date"): raise ValueError("No date column found. Pick it in the column mapping.")
    d = pd.DataFrame({"month": pd.to_datetime(df[mp["date"]], errors="coerce", dayfirst=False).dt.to_period("M")})
    if d["month"].isna().all(): raise ValueError("The date column could not be read as dates.")
    if mp.get("status") and mp["status"] in df:
        ok = df[mp["status"]].astype(str).str.lower().isin(["paid", "succeeded", "complete", "completed"])
        df, d = df[ok], d[ok]
    out = pd.DataFrame(index=sorted(d["month"].dropna().unique()))
    for f in ("revenue", "expenses", "visitors", "conversions", "marketing_spend"):
        if mp.get(f) and mp[f] in df: out[f] = _money(df[mp[f]]).groupby(d["month"]).sum()
    c = mp.get("customer")
    if c and c in df:
        vals = df[c]
        if pd.to_numeric(vals, errors="coerce").notna().mean() > .9:
            out["customers"] = pd.to_numeric(vals, errors="coerce").groupby(d["month"]).sum()
        else:
            ids = pd.DataFrame({"m": d["month"], "c": vals.astype(str)}).dropna()
            out["customers"] = ids.groupby("m")["c"].nunique()
            first = ids.groupby("c")["m"].min()
            out["new_customers"] = first.value_counts()
    return out.fillna(0)


def to_plan_months(monthly_df, first_month):
    """Map calendar months to plan months (1 = first_month, a 'YYYY-MM' string). Months before launch are dropped."""
    p0 = pd.Period(first_month, "M"); rows = []
    for per, x in monthly_df.iterrows():
        m = (per - p0).n + 1
        if 1 <= m <= 120:
            rows.append(dict(month=int(m), **{k: (None if pd.isna(v) else float(v)) for k, v in x.items()}, notes=f"Imported for {per}"))
    return rows


def sheet_csv_url(url):
    """Turn a Google Sheets share link into its CSV export link (the sheet must be shared as 'anyone with the link')."""
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", url or "")
    if not m: raise ValueError("That doesn't look like a Google Sheets link.")
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid.group(1)}" if gid else "")
