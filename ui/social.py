"""Social listening: collect real public posts and comments, see what people say, and ground the customer panel in it."""
import copy
import datetime as dt
import json
import os

import plotly.graph_objects as go
import streamlit as st

from app import agents as AG
from app import panel as PN
from app import social as SO
from app import store
from ui.common import ss, esc, pct, num, kpi, chart, section, soft, hbars, PASTEL, PLOT, refresh, user_id

OBJ_LABEL = {"price": "Price", "trust": "Trust and quality", "convenience": "Location, timing, delivery", "time": "No time", "switching": "Happy with current option",
             "no_pain": "Don't need it", "competitor": "Comparing with alternatives"}


@st.cache_data(show_spinner=False, max_entries=20)
def summarise(posts_json, idea, comps):
    return SO.analyse(json.loads(posts_json), idea, comps)


def summary_for(state, r):
    so = state.get("social") or {}
    if not so.get("posts"): return None
    comps = tuple(c["name"] for c in (r.get("competition") or {}).get("competitors", []) if c.get("source") != "typical")
    return summarise(json.dumps(so["posts"]), r["idea"]["brief"], comps)


def default_query(r):
    from app.panel import NOUN
    it = r["intake"]; area = it.get("emirate") if it.get("emirate") not in (None, "", "All UAE") else "UAE"
    return f"{NOUN[it['business_type']]} {area}"


def save_posts(new, label, r):
    st_ = copy.deepcopy(ss.state); so = st_.setdefault("social", {"posts": [], "sources": []})
    before = len(so["posts"]); so["posts"] = SO.merge(so["posts"], new)
    so["sources"] = sorted(set(so.get("sources", [])) | {label}); so["updated"] = dt.date.today().isoformat()
    added = len(so["posts"]) - before
    summ = SO.analyse(so["posts"], r["idea"]["brief"], [])
    if so.get("evidence_id"):
        try: store.delete_evidence(user_id(), ss.pid, evidence_id=so["evidence_id"])
        except store.NotFound: pass
    so["evidence_id"] = store.add_evidence(user_id(), ss.pid, SO.evidence_record(summ, r["intake"], so["sources"])) if summ else None
    refresh(f"Added {added} new post{'s' if added != 1 else ''} from {label}. They are in the evidence ledger as secondary research.", st_)


def page(r, state):
    st.header("Social listening")
    st.markdown(soft("What real people already say online about this problem, this kind of service and your competitors: Reddit, YouTube, Instagram, TikTok, "
                     "Google reviews, X and forums. These are <b>real posts</b>, so they count as (unverified) secondary research in the evidence ledger, "
                     "and they <b>ground the simulated customers</b> in what people actually complain about.", "lavender"), unsafe_allow_html=True)
    yt, rd, ai = bool(os.getenv("YOUTUBE_API_KEY")), bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")), AG.enabled()
    with st.expander("➕ Collect posts", expanded=not (state.get("social") or {}).get("posts")):
        t = st.tabs(["Search automatically", "Paste comments", "Upload a CSV"])
        with t[0]:
            st.markdown(f"{'✅' if ai else '⚪'} **Web search by AI**: Reddit, Instagram, TikTok, Google reviews, X, forums (needs ANTHROPIC_API_KEY)  \n"
                        f"{'✅' if yt else '⚪'} **YouTube comments** (free YOUTUBE_API_KEY from Google Cloud)  \n"
                        f"{'✅' if rd else '⚪'} **Reddit API** (needs an approved Reddit app: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)")
            if not (yt or rd or ai):
                st.info("No automatic source is connected yet. Add a free YouTube key or your Anthropic key in the app's secrets, "
                        "or use **Paste comments** / **Upload a CSV**, which work for any platform right now.")
            with st.form("collect"):
                q = st.text_input("Search words", default_query(r), help="Short words people would actually use, e.g. 'ladies gym Sharjah' or 'healthy lunch delivery Dubai'.")
                c = st.columns(3)
                use_ai = c[0].checkbox("Web search by AI", value=ai, disabled=not ai)
                use_yt = c[1].checkbox("YouTube", value=yt, disabled=not yt)
                use_rd = c[2].checkbox("Reddit API", value=rd, disabled=not rd)
                go_ = st.form_submit_button("Collect posts", type="primary", disabled=not (yt or rd or ai))
            if go_:
                new, errs, used = [], [], []
                comps = [c_["name"] for c_ in (r.get("competition") or {}).get("competitors", []) if c_.get("source") != "typical"]
                with st.status("Collecting public posts…", expanded=True) as box:
                    for flag, name, fn in ((use_ai, "web search", lambda: SO.web_ai(dict(r["intake"], idea=r["idea"]["brief"]), comps)),
                                           (use_yt, "YouTube", lambda: SO.youtube(q, os.environ["YOUTUBE_API_KEY"])),
                                           (use_rd, "Reddit", lambda: SO.reddit(q, os.environ["REDDIT_CLIENT_ID"], os.environ["REDDIT_CLIENT_SECRET"]))):
                        if not flag: continue
                        st.write(f"Searching {name}…")
                        try:
                            got = fn(); new += got; used.append(name); st.write(f"{name}: {len(got)} posts")
                        except Exception as e:  # noqa: BLE001
                            errs.append(f"{name}: {e}")
                    box.update(label="Done", state="complete")
                for e in errs: st.warning(e)
                if new: save_posts(new, " + ".join(used), r)
                elif not errs: st.warning("Nothing found. Try shorter or more common search words.")
        with t[1]:
            with st.form("paste", clear_on_submit=True):
                st.caption("Copy comments from Instagram, TikTok, Facebook groups, Google Maps reviews or anywhere else. One comment per line (or separate them with an empty line).")
                c = st.columns([1, 2])
                plat = c[0].selectbox("Platform", SO.PLATFORMS, index=SO.PLATFORMS.index("Instagram"))
                link = c[1].text_input("Link to the post or page (optional)")
                txt = st.text_area("Comments", height=160, placeholder="Way too expensive for what you get\nAnyone know a good ladies gym in Sharjah?")
                if st.form_submit_button("Add comments", type="primary"):
                    ps = SO.parse_paste(txt, plat, link.strip())
                    if not ps: st.error("Paste at least one comment.")
                    else: save_posts(ps, f"pasted {plat}", r)
        with t[2]:
            st.caption("Exports from any tool. The file needs a column called text, comment, body, content, review or message; platform, url, date and likes are used if present.")
            up = st.file_uploader("CSV file", type=["csv"])
            plat = st.selectbox("Platform (if the file has no platform column)", SO.PLATFORMS, key="csvplat")
            if up and st.button("Import file", type="primary"):
                try:
                    ps = SO.parse_csv(up.getvalue(), plat)
                    save_posts(ps, f"CSV {plat}", r) if ps else st.error("No comments found in the file.")
                except ValueError as e:
                    st.error(str(e))
    s = summary_for(state, r)
    if not s:
        st.markdown(soft("<b>No posts yet.</b> Paste 10-20 comments from an Instagram post or Google reviews of a competitor to see what people care about. "
                         "It takes two minutes and makes the customer panel far more realistic.", "butter"), unsafe_allow_html=True)
        return
    so = state["social"]
    st.caption(f"{s['n']} posts · sources: {', '.join(so.get('sources', []))} · updated {so.get('updated', '')} · {pct(s['with_links'])} have a link you can check")
    k = st.columns(4)
    kpi(k[0], 0, "Posts collected", num(s["n"]), " · ".join(f"{a} {b}" for a, b in sorted(s["platforms"].items(), key=lambda x: -x[1])[:3]))
    kpi(k[1], 1, "Mood", f"{pct(s['positive'])} positive", f"{pct(s['negative'])} negative · {pct(s['neutral'])} neutral")
    kpi(k[2], 2, "Asking for something like this", pct(s["demand"]), "Posts looking for or recommending a solution")
    top = max(s["objections"], key=s["objections"].get)
    kpi(k[3], 3, "Top complaint", OBJ_LABEL[top] if s["objections"][top] > 0 else "None", f"in {pct(s['objections'][top])} of posts")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("What people complain about", "rose")
            rows = sorted(((OBJ_LABEL[k_], v) for k_, v in s["objections"].items() if v > 0), key=lambda x: -x[1])
            hbars(rows or [("No complaints found", 0)], color="#f3d6de", xmax=max([v for _, v in rows] + [.1]))
    with c2:
        with st.container(border=True):
            section("Themes people talk about", "sky")
            if s["topics"]["status"] == "ran":
                for tp in s["topics"]["topics"][:5]:
                    st.markdown(f"**{esc(', '.join(tp['terms'][:4]))}** · {pct(tp['share'])} of posts, {pct(tp['negative_share'])} negative  \n<span class='muted'>“{esc(tp['example'][:160])}”</span>",
                                unsafe_allow_html=True)
            else:
                st.caption(s["topics"].get("reason", "Not enough posts for themes."))
    def cards(items, title, colour):
        if not items: return
        section(title, colour)
        cols = st.columns(2)
        for i, x in enumerate(items):
            link = f' · <a href="{esc(x["url"])}" target="_blank">open</a>' if x["url"] else ""
            cols[i % 2].markdown(soft(f"<span class='pill'>{esc(x['platform'])}</span>{link}<br>“{esc(x['text'])}”", colour), unsafe_allow_html=True)
    cards(s["examples"]["demand"], "People asking for this", "mint")
    cards(s["examples"]["negative"], "Unhappy posts", "rose")
    cards(s["examples"]["positive"], "Happy posts", "sky")
    st.divider()
    c = st.columns([2.6, 1.2, 2])
    if c[0].button("Rebuild the customer panel from these posts", width="stretch", type="primary", help="Simulated customers will raise the complaints real people raise, in the same proportions."):
        pn = PN.build(r, n=(state.get("panel") or {}).get("n", 40), social=s); pn["debate"] = PN.debate(pn, r)
        st_ = copy.deepcopy(ss.state); st_["panel"] = pn
        store.save_project(user_id(), ss.pid, state=st_); ss.state = st_; ss.flash = f"Customer panel rebuilt from {s['n']} real posts."; ss.section = "Customer panel"; st.rerun()
    with c[1].popover("Delete all posts"):
        st.write("Remove every collected post and its ledger record?")
        if st.button("Yes, delete", type="primary"):
            st_ = copy.deepcopy(ss.state)
            if (st_.get("social") or {}).get("evidence_id"):
                try: store.delete_evidence(user_id(), ss.pid, evidence_id=st_["social"]["evidence_id"])
                except store.NotFound: pass
            st_.pop("social", None); refresh("All posts deleted.", st_)
