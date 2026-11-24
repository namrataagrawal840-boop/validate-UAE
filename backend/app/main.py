"""FastAPI server: runs analyses in the background and serves the website."""
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import agents as AG
from . import priors as P
from .compute import compute, what_if

DB = os.getenv("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "validate.db"))
Path(DB).parent.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()


def db():
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.execute("create table if not exists analyses (id text primary key, created real, status text, state text, result text, progress text, error text, outcome text)")
    return c


def to_json(x):
    def conv(o):
        if isinstance(o, (np.floating,)): return None if not np.isfinite(o) else float(o)
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, np.ndarray): return o.tolist()
        if isinstance(o, float) and not np.isfinite(o): return None
        raise TypeError(type(o))
    def clean(o):
        if isinstance(o, float): return o if np.isfinite(o) else None
        if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [clean(v) for v in o]
        return o
    return json.dumps(clean(json.loads(json.dumps(x, default=conv))))


def save(id, **kw):
    with _lock, db() as c:
        sets = ", ".join(f"{k}=?" for k in kw)
        c.execute(f"update analyses set {sets} where id=?", [*(to_json(v) if k in ("state", "result", "progress", "outcome") else v for k, v in kw.items()), id])


def load(id):
    with db() as c:
        r = c.execute("select * from analyses where id=?", (id,)).fetchone()
    if not r: raise HTTPException(404, "Analysis not found")
    d = dict(r)
    for k in ("state", "result", "progress", "outcome"):
        d[k] = json.loads(d[k]) if d[k] else None
    return d


class Intake(BaseModel):
    idea: str = Field(min_length=20, max_length=2000)
    business_type: Literal["cafe", "kitchen", "retail", "ecommerce", "app", "services", "education", "fitness"]
    emirate: str = "Dubai"
    setup: Literal["Mainland", "Free zone", "Online only", "Home-based"] = "Mainland"
    target_customer: str = Field("", max_length=300)
    budget_aed: float = Field(500_000, gt=0, le=1e9)
    min_payback_probability: float = Field(.6, ge=.05, le=.99)
    max_ruin_probability: float = Field(.2, ge=0, le=.9)
    horizon_months: int = Field(36, ge=12, le=60)
    price: Optional[float] = Field(None, gt=0)
    fixed: Optional[float] = Field(None, gt=0)
    setup_budget: Optional[float] = Field(None, gt=0)
    marketing_budget_aed: Optional[float] = Field(None, gt=0)
    evidence_text: str = Field("", max_length=20000)
    use_ai: bool = True

    @field_validator("emirate")
    @classmethod
    def em(cls, v):
        ok = ["All UAE"] + [e[0] for e in P.EMIRATES]
        if v not in ok: raise ValueError(f"emirate must be one of {ok}")
        return v


app = FastAPI(title="ValidateUAE API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=[o for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return dict(ok=True, ai_enabled=AG.enabled(), model=AG.MODEL if AG.enabled() else None)


@app.get("/api/meta")
def meta():
    return dict(types={k: v["label"] for k, v in P.TYPES.items()}, emirates=["All UAE"] + [e[0] for e in P.EMIRATES], ai_enabled=AG.enabled())


def run_job(id, state, use_ai):
    prog = []
    def progress(stage, status, text):
        prog[:] = [p for p in prog if p["stage"] != stage] + [dict(stage=stage, status=status, text=text, t=time.time())]
        save(id, progress=prog)
    try:
        if use_ai and AG.enabled():
            agents, sources, errors = AG.run_agents(state["intake"], progress)
            state.update(agents=agents, sources=sources, agent_errors=errors)
        else:
            progress("offline", "done", "AI agents off: using category priors for the UAE. Add an API key to enable web research.")
        progress("funnel", "working", "Running the 10-stage funnel and the agent-based market simulation…")
        result = compute(state)
        progress("funnel", "done", f"Decision: {result['decision']['label']}.")
        save(id, state=state, result=result, status="done")
    except Exception as e:  # noqa: BLE001
        save(id, status="error", error=str(e)[:500])


@app.post("/api/analyses")
def create(intake: Intake):
    id = uuid.uuid4().hex[:12]
    state = dict(intake=intake.model_dump(), agents={}, overrides={}, experiments=[], settings={})
    with _lock, db() as c:
        c.execute("insert into analyses values (?,?,?,?,?,?,?,?)", (id, time.time(), "running", to_json(state), None, "[]", None, None))
    threading.Thread(target=run_job, args=(id, state, intake.use_ai), daemon=True).start()
    return dict(id=id)


@app.get("/api/analyses")
def list_analyses():
    with db() as c:
        rows = c.execute("select id, created, status, state from analyses order by created desc limit 30").fetchall()
    return [dict(id=r["id"], created=r["created"], status=r["status"], idea=json.loads(r["state"])["intake"]["idea"][:140]) for r in rows]


@app.get("/api/analyses/{id}")
def get(id: str):
    d = load(id)
    return dict(id=id, status=d["status"], progress=d["progress"], error=d["error"], result=d["result"], outcome=d["outcome"],
                sources=(d["state"] or {}).get("sources", {}), agents=(d["state"] or {}).get("agents", {}), agent_errors=(d["state"] or {}).get("agent_errors", {}),
                experiments=(d["state"] or {}).get("experiments", []), overrides=(d["state"] or {}).get("overrides", {}))


class Point(BaseModel):
    price: float = Field(gt=0); n: int = Field(gt=0); k: int = Field(ge=0)


class Experiment(BaseModel):
    kind: Literal["landing", "pricing", "interviews", "pilot", "ab", "vanwestendorp", "usability", "sales"]
    visitors: Optional[int] = Field(None, gt=0); signups: Optional[int] = Field(None, ge=0); spend: Optional[float] = Field(None, gt=0)
    pay_rate: float = Field(30, gt=0, le=100)
    points: list[Point] = []
    n: Optional[int] = Field(None, gt=0); k: Optional[int] = Field(None, ge=0)
    customers: Optional[int] = Field(None, gt=0); months: Optional[float] = Field(None, gt=0); lost: Optional[int] = Field(None, ge=0)
    promoters: Optional[int] = Field(None, ge=0); passives: Optional[int] = Field(None, ge=0); detractors: Optional[int] = Field(None, ge=0)
    rows: list[list[float]] = []
    users: Optional[int] = Field(None, gt=0); tasks_done: Optional[int] = Field(None, ge=0); tasks_total: Optional[int] = Field(None, gt=0)
    sus: list[float] = []
    sales: list[float] = []
    name: str = ""; label_a: str = "A"; label_b: str = "B"
    nA: Optional[int] = Field(None, gt=0); kA: Optional[int] = Field(None, ge=0); nB: Optional[int] = Field(None, gt=0); kB: Optional[int] = Field(None, ge=0)

    def check(self):
        bad = {"landing": self.visitors is None or self.signups is None or self.spend is None or self.signups > self.visitors,
               "pricing": not self.points or any(p.k > p.n for p in self.points),
               "interviews": self.n is None or self.k is None or self.k > self.n,
               "pilot": self.customers is None or self.months is None or self.lost is None or self.lost > self.customers * self.months,
               "ab": None in (self.nA, self.kA, self.nB, self.kB) or self.kA > self.nA or self.kB > self.nB,
               "vanwestendorp": len(self.rows) < 5 or any(len(r) != 4 or min(r) <= 0 or not (r[0] <= r[1] <= r[2] <= r[3]) for r in self.rows),
               "usability": self.users is None or self.tasks_done is None or self.tasks_total is None or self.tasks_done > self.tasks_total or any(not 0 <= x <= 100 for x in self.sus),
               "sales": len(self.sales) < 4 or min(self.sales) < 0}[self.kind]
        if bad: raise HTTPException(422, {"vanwestendorp": "Enter at least 5 answers, each as four prices in order: too cheap ≤ cheap ≤ expensive ≤ too expensive.",
                                          "usability": "Enter users and tasks; completed tasks cannot exceed the total; SUS scores are 0 to 100.",
                                          "sales": "Enter at least 4 months of sales, none negative."}.get(self.kind, "Check the numbers: counts must be filled in and successes cannot exceed the total."))
        return {k: v for k, v in self.model_dump().items() if v not in (None, [], "")}


def recompute(id, mutate):
    d = load(id)
    if d["status"] != "done": raise HTTPException(409, "Analysis is not finished yet")
    state = d["state"]; mutate(state)
    result = compute(state); save(id, state=state, result=result)
    return get(id)


@app.post("/api/analyses/{id}/experiments")
def add_experiment(id: str, e: Experiment):
    x = e.check()
    return recompute(id, lambda s: s.setdefault("experiments", []).append(x))


@app.delete("/api/analyses/{id}/experiments/{i}")
def remove_experiment(id: str, i: int):
    def m(s):
        if not 0 <= i < len(s.get("experiments", [])): raise HTTPException(404, "No such experiment")
        s["experiments"].pop(i)
    return recompute(id, m)


class Overrides(BaseModel):
    overrides: dict = {}
    settings: dict = {}


ALLOWED_SETTINGS = {"shocks", "cycles", "seasonality", "runs", "seed", "satisfaction"}


def clean_over(o: Overrides):
    ov = {}
    for k, v in o.overrides.items():
        if k not in P.ASSUMPTION_KEYS or not isinstance(v, dict): continue
        try:
            lo, mid, hi = sorted(float(v[f]) for f in ("min", "likely", "max"))
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, f"{k}: min, likely and max must be numbers")
        if lo < 0 or (mid <= 0 and k not in ("var_pct",)): raise HTTPException(422, f"{k}: values must be positive")
        ov[k] = dict(min=lo, likely=mid, max=hi, label=v.get("label") if v.get("label") in ("founder", "benchmarked", "measured") else "founder",
                     source=str(v.get("source") or "Edited by you")[:200])
    st = {k: v for k, v in o.settings.items() if k in ALLOWED_SETTINGS}
    if "runs" in st: st["runs"] = int(min(max(int(st["runs"]), 200), 5000))
    if "shocks" in st: st["shocks"] = int(min(max(int(st["shocks"]), 0), 3))
    if "satisfaction" in st and st["satisfaction"] is not None: st["satisfaction"] = float(min(max(float(st["satisfaction"]), .02), .98))
    return ov, st


@app.post("/api/analyses/{id}/whatif")
def whatif(id: str, o: Overrides):
    d = load(id); ov, st = clean_over(o)
    return to_jsonable(what_if(d["state"], ov, st))


@app.post("/api/analyses/{id}/apply")
def apply(id: str, o: Overrides):
    ov, st = clean_over(o)
    def m(s):
        s["overrides"] = {**s.get("overrides", {}), **ov}; s["settings"] = {**s.get("settings", {}), **st}
    return recompute(id, m)


@app.post("/api/analyses/{id}/reset")
def reset(id: str):
    def m(s): s["overrides"] = {}; s["settings"] = {}
    return recompute(id, m)


class VariantPick(BaseModel):
    variant_id: str = Field(min_length=1, max_length=120)


@app.post("/api/analyses/{id}/variants")
def apply_variant(id: str, v: VariantPick):
    d = load(id)
    found = next((x for x in ((d["result"] or {}).get("improve") or {}).get("variants", []) if x["id"] == v.variant_id), None)
    if not found: raise HTTPException(404, "No such variant")
    def m(s):
        if all(a["id"] != found["id"] for a in s.get("applied", [])):
            s.setdefault("applied", []).append(dict(id=found["id"], name=found["name"], changes=found["changes"]))
    return recompute(id, m)


@app.delete("/api/analyses/{id}/variants/{vid}")
def remove_variant(id: str, vid: str):
    def m(s): s["applied"] = [a for a in s.get("applied", []) if a["id"] != vid]
    return recompute(id, m)


@app.get("/api/sus-questions")
def sus_questions():
    from .funnel.validation import SUS_QUESTIONS
    return SUS_QUESTIONS


class Outcome(BaseModel):
    paid_back: bool
    month: Optional[int] = Field(None, ge=1, le=120)


@app.post("/api/analyses/{id}/outcome")
def outcome(id: str, o: Outcome):
    load(id); save(id, outcome=o.model_dump()); return dict(ok=True)


@app.get("/api/calibration")
def calibration():
    """Step 7, monitoring: once real outcomes are recorded, compare forecasts with what happened."""
    with db() as c:
        rows = c.execute("select result, outcome from analyses where outcome is not null and result is not null").fetchall()
    pairs = []
    for r in rows:
        res, out = json.loads(r["result"]), json.loads(r["outcome"])
        pairs.append((res["stages"]["forecast"]["p_payback"], 1.0 if out["paid_back"] else 0.0))
    if not pairs: return dict(n=0, brier=None, note="No real outcomes recorded yet. Record what happened to each idea to measure how well the forecasts are calibrated.")
    f, y = np.array(pairs).T
    return dict(n=len(pairs), brier=float(np.mean((f - y) ** 2)), base_brier=float(np.mean((y.mean() - y) ** 2)),
                note="Brier score: 0 is perfect; lower than the base score means the forecasts beat simply guessing the average.")


def to_jsonable(x):
    return json.loads(to_json(x))


STATIC = Path(os.getenv("STATIC_DIR", str(Path(__file__).resolve().parents[2] / "frontend" / "out")))
if STATIC.exists():
    app.mount("/_next", StaticFiles(directory=STATIC / "_next"), name="next")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = STATIC / path
        if path and f.is_file(): return FileResponse(f)
        if (STATIC / f"{path}.html").is_file(): return FileResponse(STATIC / f"{path}.html")
        return FileResponse(STATIC / "index.html")
