"""Alerts: what needs attention in a project, and sending a digest by email (SMTP) or WhatsApp (Twilio).

Nothing is sent unless the account has saved a contact and the server has the provider's secrets:
    email:    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, ALERT_FROM
    WhatsApp: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (e.g. whatsapp:+14155238886)
Streamlit has no background jobs, so the daily digest runs from scripts/send_alerts.py (a GitHub Actions
schedule is included); the app can also send one on demand.
"""
import datetime as dt
import json
import os
import smtplib
from email.message import EmailMessage

from . import monitoring as MON
from . import store

METRIC = {"revenue": "Revenue", "expenses": "Expenses", "customers": "Customers", "conversion": "Conversion", "repeat": "Repeat purchase", "cac": "Cost to win a customer"}


def for_project(name, state, result, actuals, baseline, today=None):
    today = today or dt.date.today(); out = []
    for k, t in (state.get("desk_tests") or {}).items():
        if t.get("status") == "planned" and t.get("due") and dt.date.fromisoformat(t["due"]) < today:
            out.append(dict(level="warn", project=name, text=f"Test overdue since {t['due']}: {t.get('name', k)}. Log the result or move the date."))
    if baseline and actuals:
        cmp_ = MON.compare(baseline, actuals)
        for a in cmp_["alerts"]:
            out.append(dict(level="bad", project=name, text=f"{METRIC[a['metric']]} off plan in {a['months']} of the last 3 months ({a['deviation']:+.0%})."))
        if cmp_.get("runway_months") is not None and cmp_["runway_months"] < 4:
            out.append(dict(level="bad", project=name, text=f"Cash runway about {cmp_['runway_months']:.1f} months at the current burn."))
    pv = (result.get("finance") or {}).get("payback") or {}
    if pv and not pv.get("passes") and (result.get("decision") or {}).get("code") == "launch":
        out.append(dict(level="warn", project=name, text="Decision says launch but the payback misses your time limit: check the plan."))
    return out


def contact(user_id):
    raw = store.get_kv(f"contact:{user_id}")
    return json.loads(raw) if raw else dict(email="", whatsapp="", daily=False)


def save_contact(user_id, email, whatsapp, daily):
    store.set_kv(f"contact:{user_id}", json.dumps(dict(email=(email or "").strip()[:200], whatsapp=(whatsapp or "").strip()[:30], daily=bool(daily))))


def channels():
    return dict(email=bool(os.getenv("SMTP_HOST") and os.getenv("ALERT_FROM")),
                whatsapp=bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and os.getenv("TWILIO_WHATSAPP_FROM")))


def digest_text(items):
    if not items: return "ValidateUAE: nothing needs your attention today."
    return "ValidateUAE: " + str(len(items)) + " thing(s) need attention\n\n" + "\n".join(f"- {i['project']}: {i['text']}" for i in items)


def send(c, text):
    """Send the digest to the saved contact. Returns a list of (channel, ok, message)."""
    res = []; ch = channels()
    if c.get("email"):
        if not ch["email"]: res.append(("email", False, "Email is not set up on this server (SMTP secrets missing)."))
        else:
            try:
                msg = EmailMessage(); msg["Subject"] = "ValidateUAE alerts"; msg["From"] = os.getenv("ALERT_FROM"); msg["To"] = c["email"]; msg.set_content(text)
                with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT") or 587), timeout=20) as s:
                    s.starttls()
                    if os.getenv("SMTP_USER"): s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD") or "")
                    s.send_message(msg)
                res.append(("email", True, f"Sent to {c['email']}"))
            except Exception as e:  # noqa: BLE001
                res.append(("email", False, f"Email failed: {type(e).__name__}"))
    if c.get("whatsapp"):
        if not ch["whatsapp"]: res.append(("whatsapp", False, "WhatsApp is not set up on this server (Twilio secrets missing)."))
        else:
            import requests
            try:
                sid = os.getenv("TWILIO_ACCOUNT_SID")
                r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, os.getenv("TWILIO_AUTH_TOKEN")), timeout=20,
                                  data=dict(From=os.getenv("TWILIO_WHATSAPP_FROM"), To="whatsapp:" + c["whatsapp"].replace("whatsapp:", ""), Body=text[:1500]))
                res.append(("whatsapp", r.ok, "Sent" if r.ok else f"WhatsApp failed: HTTP {r.status_code}"))
            except Exception as e:  # noqa: BLE001
                res.append(("whatsapp", False, f"WhatsApp failed: {type(e).__name__}"))
    return res


def for_user(user_id):
    items = []
    for p in store.list_projects(user_id):
        try:
            full = store.load_project(user_id, p["id"])
            if not full["result"]: continue
            items += for_project(p["name"], full["state"] or {}, full["result"], store.list_actuals(user_id, p["id"]), full["baseline"])
        except store.NotFound:
            continue
    return items
