"""The shareable report: a PDF (summary, the five answers, evidence, tests, method, sources, run stamp) and a short
slide deck. Both are built from the same content, so they never disagree with the app."""
import datetime as dt
import io
import os

from . import methods as M
from . import evidence as EV

FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")
INK, MUTED = (43, 48, 71), (107, 113, 137)
ACCENT = {"launch": (63, 143, 114), "pivot": (63, 111, 174), "test": (140, 109, 26), "stop": (165, 80, 95)}


def _aed(v):
    if v is None: return "–"
    a = abs(v); s = f"{a / 1e9:.1f}B" if a >= 1e9 else f"{a / 1e6:.1f}M" if a >= 1e6 else f"{round(a / 1e3)}k" if a >= 1e4 else f"{a:,.0f}"
    return ("−" if v < 0 else "") + "AED " + s


def _approx(v):
    if v is None: return "–"
    a = abs(v)
    return f"{a / 1e6:.1f}M" if a >= 1e6 else f"{float(f'{a:.2g}') / 1e3:g}k" if a >= 1e3 else f"{float(f'{a:.2g}'):g}"


def content(r, state, market, ledger, hypotheses, project_name, author=""):
    """Everything the report says, as plain data."""
    b = r["brief"]; f = r["stages"]["forecast"]; F = r["finance"]; pv = F.get("payback") or {}; L = r["limits"]; v = r["validation"]
    R = market.get("ranges") or {}
    rng = lambda k: f"{_approx(R[k][0])}–{_approx(R[k][1])}" if k in R else _approx(market[k]["people"])
    pay = (f"Typical payback in month {pv['typical']}" if pv.get("typical") else f"Typical payback beyond {f['horizon']} months") + \
          (f"; {round(L['min_payback'] * 10)} in 10 futures by month {pv['safe']}" if pv.get("safe") else "") + f"; limit {f['horizon']} months ({'passes' if pv.get('passes') else 'misses'})."
    tests = state.get("desk_tests") or {}
    real = [x for x in ledger if EV.is_real(x)]
    return dict(
        title=project_name, author=author, date=dt.date.today().strftime("%d %B %Y"), code=b["code"], verdict=b["label"], plain=b["plain"], reasons=b["reasons"],
        idea=r["idea"]["brief"], where=f"{r['intake'].get('emirate')} · {r['intake'].get('setup')}",
        numbers=[("Typical payback", f"month {pv['typical']}" if pv.get("typical") else f"> {f['horizon']} months"),
                 ("Budget risk", f"{f['p_ruin']:.0%} (limit {L['max_ruin']:.0%})"), ("Evidence confidence", f"{r['evidence']['strength']:.0%}"),
                 ("Validation score", f"{round(v['score'])}/100" + (" (capped)" if v.get("capped") else ""))],
        parts=[(p["name"], round(p["score"]), p["basis"]) for p in (v.get("parts") or {}).values()],
        answers=[("Is there a market?", f"About {rng('tam')} people use this kind of service ({_aed(market['tam']['aed'])} a year); one business can reach {rng('sam')} and could win {rng('som')} customers."),
                 ("Do customers want it?", ("A simulated panel was run (simulated, zero evidence weight). " if state.get("panel") else "") +
                  f"{sum(1 for t in tests.values() if t.get('status') == 'done')} desk tests done; {len(real)} real-world evidence records."),
                 ("Does the money work?", f"About {_approx(r['unit']['bep_customers'])} customers needed to cover monthly costs. {pay} Have about {_aed(F['runway']['cash_need_p90'])} ready."),
                 ("Who are the rivals?", r["competition"]["headline"])],
        market_steps=[(s["label"].replace("…", ""), _approx(s["people"]), s.get("source") or "", s.get("year")) for s in market["steps"]],
        tests=[(t.get("name", k), t.get("status"), t.get("finding") or "", t.get("direction") or "") for k, t in tests.items()],
        evidence=[(x.get("claim") or "", EV.TYPES.get(x.get("ev_type"), ("",))[0], f"{EV.weight(x)[0]:.2f}", x.get("source_url") or "") for x in real],
        hypotheses=[(h["statement"], h.get("status") or "planned") for h in hypotheses],
        next5=[(a["action"], a["why"]) for a in b["next5"]],
        risks=b["risks"], run=r.get("run_info") or {}, models=M.MODELS, limits=M.LIMITS,
        disclaimer="Decision support, not financial advice. Simulated and AI-generated figures are never real customer behaviour and carry no evidence weight.")


def pdf(c):
    from fpdf import FPDF
    p = FPDF(format="A4"); p.set_margins(18, 16, 18); p.set_auto_page_break(True, 16)
    p.add_font("DV", "", os.path.join(FONT_DIR, "DejaVuSans.ttf")); p.add_font("DV", "B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
    W = p.w - 36

    def h(t, size=13):
        p.ln(3); p.set_font("DV", "B", size); p.set_text_color(*INK); p.multi_cell(W, 7, t, new_x="LMARGIN", new_y="NEXT"); p.ln(1)

    def para(t, size=10, color=INK, bold=False):
        p.set_font("DV", "B" if bold else "", size); p.set_text_color(*color); p.multi_cell(W, 5.2, t, new_x="LMARGIN", new_y="NEXT"); p.ln(1)

    def table(head, rows, widths, size=8.5):
        p.set_font("DV", "B", size); p.set_text_color(*INK); p.set_fill_color(244, 242, 255)
        with p.table(cell_fill_color=(250, 249, 255), cell_fill_mode="ROWS", col_widths=widths, text_align="LEFT", line_height=4.6, first_row_as_headings=True, borders_layout="HORIZONTAL_LINES") as t:
            rw = t.row()
            for x in head: rw.cell(x)
            p.set_font("DV", "", size)
            for row in rows:
                rw = t.row()
                for x in row: rw.cell(str(x if x is not None else ""))
        p.ln(2)

    p.add_page()
    p.set_font("DV", "", 9); p.set_text_color(*MUTED); p.cell(W, 5, f"ValidateUAE report · {c['date']}" + (f" · prepared by {c['author']}" if c["author"] else ""), new_x="LMARGIN", new_y="NEXT")
    p.set_font("DV", "B", 20); p.set_text_color(*INK); p.multi_cell(W, 10, c["title"], new_x="LMARGIN", new_y="NEXT")
    para(c["where"], 9.5, MUTED)
    p.set_fill_color(*[min(255, x + 175) for x in ACCENT[c["code"]]]); p.set_text_color(*ACCENT[c["code"]]); p.set_font("DV", "B", 15)
    p.cell(W, 11, f"  Recommendation: {c['verdict']}", fill=True, new_x="LMARGIN", new_y="NEXT"); p.ln(2)
    para(c["plain"], 10.5)
    for x in c["reasons"]: para("• " + x, 9.5)
    table(["Measure", "Value"], c["numbers"], (45, 55))
    if c["parts"]: table(["Score part", "Score", "Based on"], c["parts"], (35, 12, 53))
    h("The idea"); para(c["idea"])
    h("The four answers")
    for q, a in c["answers"]: para(q, 10.5, bold=True); para(a, 9.8)
    h("Market size, step by step"); table(["Step", "People", "Source", "Year"], c["market_steps"], (30, 12, 50, 8), 8)
    h("Next five actions")
    for i, (a, why) in enumerate(c["next5"]): para(f"{i + 1}. {a}", 9.8, bold=True); para(why, 9, MUTED)
    if c["risks"]: h("Financial risks"); [para("• " + x, 9.5) for x in c["risks"]]
    h("Tests done without customers (desk tests)")
    table(["Test", "Status", "Finding"], [(n, s, fnd) for n, s, fnd, _ in c["tests"]], (32, 12, 56)) if c["tests"] else para("No desk tests logged yet.", 9.5, MUTED)
    h("Real-world evidence")
    table(["Claim", "Type", "Weight", "Source"], c["evidence"], (42, 24, 10, 24), 8) if c["evidence"] else para("No real-world evidence records yet: the recommendation rests on typical figures and estimates.", 9.5, MUTED)
    if c["hypotheses"]: h("Hypotheses"); table(["Statement", "Status"], c["hypotheses"], (80, 20))
    p.add_page(); h("Appendix A · Method", 14)
    for m in c["models"]:
        para(m["name"], 10.5, bold=True); para(f"What it does: {m['what']}", 9); para(f"Assumes: {m['assumes']}", 9); para(f"Limits: {m['limits']}", 9)
        if m["refs"]: para("References: " + "; ".join(m["refs"]), 8.5, MUTED)
    h("Known limits"); [para("• " + x, 9) for x in c["limits"]]
    h("Appendix B · Reproducibility", 14)
    ri = c["run"]
    table(["Item", "Value"], [("Model version", ri.get("model_version", "–")), ("Random seed", ri.get("seed", "–")), ("Simulated futures", ri.get("runs", "–")),
                              ("Safety standard", f"{ri.get('safety_standard', .6):.0%}"), ("Input fingerprint", ri.get("input_hash", "–")),
                              ("Computed at (UTC)", ri.get("computed_at", "–")), ("Published data checked", (ri.get("data_vintage") or {}).get("checked", "–"))], (40, 60))
    para(c["disclaimer"], 8.5, MUTED)
    return bytes(p.output())


def slides(c):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    pr = Presentation(); pr.slide_width, pr.slide_height = Inches(13.333), Inches(7.5)
    blank = pr.slide_layouts[6]

    def slide(title, lines, sub=None, colour=INK):
        s = pr.slides.add_slide(blank)
        tb = s.shapes.add_textbox(Inches(.7), Inches(.5), Inches(12), Inches(1.1)).text_frame; tb.word_wrap = True
        tb.text = title; tb.paragraphs[0].runs[0].font.size = Pt(30); tb.paragraphs[0].runs[0].font.bold = True; tb.paragraphs[0].runs[0].font.color.rgb = RGBColor(*colour)
        if sub:
            q = tb.add_paragraph(); q.text = sub; q.runs[0].font.size = Pt(15); q.runs[0].font.color.rgb = RGBColor(*MUTED)
        body = s.shapes.add_textbox(Inches(.7), Inches(1.9), Inches(12), Inches(5.2)).text_frame; body.word_wrap = True
        for i, l in enumerate(lines):
            para = body.paragraphs[0] if i == 0 else body.add_paragraph()
            bold = l.startswith("**"); para.text = l.strip("*"); para.space_after = Pt(8)
            for run in para.runs: run.font.size = Pt(17 if bold else 15); run.font.bold = bold; run.font.color.rgb = RGBColor(*INK)
        foot = s.shapes.add_textbox(Inches(.7), Inches(7.0), Inches(12), Inches(.4)).text_frame
        foot.text = f"ValidateUAE · {c['title']} · {c['date']}"; foot.paragraphs[0].runs[0].font.size = Pt(10); foot.paragraphs[0].runs[0].font.color.rgb = RGBColor(*MUTED)

    slide(c["title"], [c["idea"], "", c["where"]], f"Validation report · {c['date']}")
    slide(f"Recommendation: {c['verdict']}", [c["plain"]] + ["• " + x for x in c["reasons"]], colour=ACCENT[c["code"]])
    slide("The numbers that decide it", [f"**{k}: {v}" for k, v in c["numbers"]] + [f"{n}: {s}/100 ({b})" for n, s, b in c["parts"]])
    slide("The four answers", sum(([f"**{q}", a] for q, a in c["answers"]), []))
    slide("What we checked without customers", [f"• {n}: {fnd or s}" for n, s, fnd, _ in c["tests"]] or ["No desk tests logged yet."],
          f"{len(c['evidence'])} real-world evidence records · simulations carry no evidence weight")
    slide("Next five actions", [f"{i + 1}. {a}" for i, (a, _) in enumerate(c["next5"])])
    slide("How this was worked out", [f"• {m['name']}: {m['what']}" for m in c["models"][:6]], c["disclaimer"])
    buf = io.BytesIO(); pr.save(buf); return buf.getvalue()
