"""Daily alert digest for every account that asked for one (Share and report -> Get alerts).

Run by .github/workflows/alerts.yml every morning (UAE time), or by hand:
    DATABASE_URL=... SMTP_HOST=... python scripts/send_alerts.py
Uses the same database as the app; needs the SMTP and/or Twilio secrets described in README.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
from sqlalchemy import select  # noqa: E402

from app import alerts as AL  # noqa: E402
from app import store  # noqa: E402


def main():
    if store.config_warning: print(store.config_warning)
    with store.engine().connect() as c:
        rows = c.execute(select(store.kv.c.key, store.kv.c.value).where(store.kv.c.key.like("contact:%"))).all()
    sent = 0
    for key, raw in rows:
        ct = json.loads(raw)
        if not ct.get("daily"): continue
        uid = key.split(":", 1)[1]
        items = AL.for_user(uid)
        if not items: continue
        for ch, ok, msg in AL.send(ct, AL.digest_text(items)):
            print(f"{uid[:8]} {ch}: {msg}"); sent += ok
    print(f"Done: {sent} message(s) sent.")


if __name__ == "__main__":
    main()
