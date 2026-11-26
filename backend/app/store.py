"""Persistent storage for users, projects, the evidence ledger, hypotheses and monitoring actuals.

Database: DATABASE_URL (PostgreSQL, e.g. from Neon or Supabase) when set, otherwise a local SQLite
file (DB_PATH, default data/validateuae.db). On Streamlit Community Cloud the local disk is wiped
when the app restarts, so set DATABASE_URL there to keep projects.

Every function that reads or writes project data takes the user id and checks ownership, so one
user can never read or change another user's projects (NotFound is raised instead).
"""
import datetime as dt
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid

from sqlalchemy import (Column, Float, ForeignKey, Integer, LargeBinary, MetaData, String, Table, Text, UniqueConstraint,
                        create_engine, delete, insert, select, update, func)

MAX_FILE_BYTES = 5 * 1024 * 1024
PBKDF2_ROUNDS = 240_000
MAX_FAILED = 5
LOCK_MINUTES = 10

meta = MetaData()
users = Table("users", meta,
              Column("id", String(36), primary_key=True), Column("username", String(64), unique=True, nullable=False),
              Column("pw_hash", String(128), nullable=False), Column("salt", String(64), nullable=False),
              Column("created_at", String(32)), Column("failed", Integer, default=0), Column("locked_until", String(32)))
projects = Table("projects", meta,
                 Column("id", String(36), primary_key=True), Column("user_id", String(36), ForeignKey("users.id"), index=True, nullable=False),
                 Column("name", String(200)), Column("created_at", String(32)), Column("updated_at", String(32)),
                 Column("state", LargeBinary), Column("result", LargeBinary), Column("baseline", LargeBinary),
                 Column("status", String(16)), Column("status_label", String(80)), Column("score", Float), Column("confidence", Float),
                 Column("business_type", String(32)), Column("emirate", String(40)))
evidence = Table("evidence", meta,
                 Column("id", String(36), primary_key=True), Column("project_id", String(36), ForeignKey("projects.id"), index=True, nullable=False),
                 Column("claim", Text), Column("area", String(32)), Column("description", Text), Column("source_url", Text),
                 Column("file_name", String(200)), Column("file_mime", String(100)), Column("file_blob", LargeBinary),
                 Column("collected_on", String(16)), Column("geography", String(16)), Column("ev_type", String(16)), Column("sample_size", Integer),
                 Column("verification", String(16)), Column("confidence", String(8)), Column("limitations", Text),
                 Column("value_min", Float), Column("value_likely", Float), Column("value_max", Float),
                 Column("experiment_id", String(36)), Column("hypothesis_id", String(36)), Column("created_at", String(32)))
hypotheses = Table("hypotheses", meta,
                   Column("id", String(36), primary_key=True), Column("project_id", String(36), ForeignKey("projects.id"), index=True, nullable=False),
                   Column("statement", Text), Column("area", String(32)), Column("metric", String(32)), Column("method", String(32)),
                   Column("expected", Float), Column("threshold", Float), Column("direction", String(4)), Column("status", String(16)),
                   Column("plan", Text), Column("created_at", String(32)), Column("updated_at", String(32)))
kv = Table("app_settings", meta, Column("key", String(120), primary_key=True), Column("value", Text))
actuals = Table("actuals", meta,
                Column("id", String(36), primary_key=True), Column("project_id", String(36), ForeignKey("projects.id"), index=True, nullable=False),
                Column("month", Integer, nullable=False), Column("revenue", Float), Column("expenses", Float), Column("customers", Float),
                Column("new_customers", Float), Column("visitors", Float), Column("conversions", Float), Column("repeat_customers", Float),
                Column("marketing_spend", Float), Column("notes", Text), Column("created_at", String(32)),
                UniqueConstraint("project_id", "month", name="uq_actual_month"))
# Teams: a project is shared with other users as editor (can change it) or viewer (can read and comment).
members = Table("members", meta,
                Column("project_id", String(36), ForeignKey("projects.id"), primary_key=True), Column("user_id", String(36), ForeignKey("users.id"), primary_key=True, index=True),
                Column("role", String(16), nullable=False), Column("added_at", String(32)))
comments = Table("comments", meta,
                 Column("id", String(36), primary_key=True), Column("project_id", String(36), ForeignKey("projects.id"), index=True, nullable=False),
                 Column("user_id", String(36)), Column("section", String(80)), Column("text", Text), Column("resolved", Integer, default=0), Column("created_at", String(32)))
activity = Table("activity", meta,
                 Column("id", String(36), primary_key=True), Column("project_id", String(36), ForeignKey("projects.id"), index=True, nullable=False),
                 Column("user_id", String(36)), Column("action", String(80)), Column("detail", Text), Column("created_at", String(32)))
# Version history: a compact snapshot of inputs and key outputs each time the project is recomputed.
snapshots = Table("snapshots", meta,
                  Column("id", String(36), primary_key=True), Column("project_id", String(36), ForeignKey("projects.id"), index=True, nullable=False),
                  Column("user_id", String(36)), Column("reason", Text), Column("summary", LargeBinary), Column("created_at", String(32)))
ROLES = ("editor", "viewer")


class NotFound(Exception):
    """The record does not exist or belongs to another user."""


class AuthError(Exception):
    pass


_engine = None


config_warning = None  # shown on the login page when DATABASE_URL could not be used


def normalise_db_url(raw):
    """Accept any form Neon, Supabase or Render show: plain postgresql://, postgres://, postgresql+psycopg://,
    or the whole `psql 'postgresql://...'` command, with or without quotes. Always use the psycopg2 driver,
    which is the one installed (requirements.txt)."""
    raw = (raw or "").strip().strip("'\"")
    if not raw: return None
    m = re.search(r"postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^\s'\"]+", raw)
    if not m: raise ValueError("DATABASE_URL does not look like a PostgreSQL connection string (it should start with postgresql://).")
    url = m.group(0)
    return "postgresql+psycopg2://" + url.split("://", 1)[1]


def _sqlite_url():
    path = os.getenv("DB_PATH") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "validateuae.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return f"sqlite:///{path}"


def engine():
    global _engine, config_warning
    if _engine is None:
        url = None
        try:
            url = normalise_db_url(os.getenv("DATABASE_URL"))
        except ValueError as e:
            config_warning = f"{e} Using a temporary local database for now."
        if url:
            try:
                eng = create_engine(url, future=True, pool_pre_ping=True, pool_size=3, max_overflow=2)
                meta.create_all(eng)
                _engine = eng
                return _engine
            except Exception as e:  # wrong password, host unreachable, missing driver...
                config_warning = (f"Could not connect to the database in DATABASE_URL ({type(e).__name__}: {str(e).splitlines()[0][:160]}). "
                                  "Using a temporary local database for now: accounts made now are lost when the app restarts.")
        _engine = create_engine(_sqlite_url(), future=True, connect_args={"check_same_thread": False})
        meta.create_all(_engine)
    return _engine


def reset_engine():
    """For tests: forget the cached engine so a new DB_PATH / DATABASE_URL is used."""
    global _engine, _SECRET, config_warning
    _SECRET = None; config_warning = None
    if _engine is not None: _engine.dispose()
    _engine = None


def backend_name():
    return "PostgreSQL" if engine().url.get_backend_name().startswith("postgres") else "SQLite (local file)"


now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
pack = lambda obj: gzip.compress(json.dumps(obj, default=_default).encode())
unpack = lambda b: json.loads(gzip.decompress(b)) if b else None


def _default(o):
    try:
        import numpy as np
        if isinstance(o, np.generic): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, (dt.date, dt.datetime)): return o.isoformat()
    raise TypeError(f"Cannot store {type(o).__name__}")


# ---------------- users ----------------
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,64}$")


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()


def create_user(username, password):
    username = (username or "").strip().lower()
    if not USERNAME_RE.match(username): raise AuthError("Use 3-64 letters, numbers or . _ @ - for the username.")
    if len(password or "") < 8: raise AuthError("The password needs at least 8 characters.")
    if password.lower() == username or password.isdigit(): raise AuthError("Choose a stronger password (not only numbers, not your username).")
    salt = secrets.token_hex(16); uid = str(uuid.uuid4())
    with engine().begin() as c:
        if c.execute(select(users.c.id).where(users.c.username == username)).first(): raise AuthError("That username is taken.")
        c.execute(insert(users).values(id=uid, username=username, pw_hash=_hash(password, salt), salt=salt, created_at=now(), failed=0))
    return dict(id=uid, username=username)


def authenticate(username, password):
    username = (username or "").strip().lower()
    with engine().begin() as c:
        u = c.execute(select(users).where(users.c.username == username)).mappings().first()
        if not u:
            _hash(password or "x", "00" * 16)  # same work either way, so timing does not reveal which usernames exist
            raise AuthError("Wrong username or password.")
        if u["locked_until"] and u["locked_until"] > now():
            raise AuthError(f"Too many failed attempts. Try again after {LOCK_MINUTES} minutes.")
        if not hmac.compare_digest(_hash(password or "", u["salt"]), u["pw_hash"]):
            failed = (u["failed"] or 0) + 1
            lock = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") if failed >= MAX_FAILED else None
            c.execute(update(users).where(users.c.id == u["id"]).values(failed=0 if lock else failed, locked_until=lock))
            bad = True
        else:
            bad = False
            c.execute(update(users).where(users.c.id == u["id"]).values(failed=0, locked_until=None))
    if bad: raise AuthError("Wrong username or password.")  # raised after the commit, so the failed attempt is recorded
    return dict(id=u["id"], username=u["username"])


def get_user(user_id):
    with engine().connect() as c:
        u = c.execute(select(users.c.id, users.c.username).where(users.c.id == user_id)).mappings().first()
    if not u: raise NotFound("user")
    return dict(u)


# ---------------- signed session tokens (for the API) ----------------
def get_kv(key):
    with engine().connect() as c:
        r = c.execute(select(kv.c.value).where(kv.c.key == key)).first()
    return r[0] if r else None


def set_kv(key, value):
    with engine().begin() as c:
        if c.execute(select(kv.c.key).where(kv.c.key == key)).first(): c.execute(update(kv).where(kv.c.key == key).values(value=value))
        else: c.execute(insert(kv).values(key=key, value=value))


def del_kv(key):
    with engine().begin() as c:
        c.execute(delete(kv).where(kv.c.key == key))


_SECRET = None


def _secret():
    """SECRET_KEY from the environment, otherwise a random key created once and kept in the database,
    so sign-ins survive app restarts without any setup."""
    global _SECRET
    if os.getenv("SECRET_KEY"): return os.environ["SECRET_KEY"].encode()
    if _SECRET is None:
        k = get_kv("secret_key")
        if not k:
            k = secrets.token_hex(32)
            try:
                set_kv("secret_key", k)
            except Exception:  # another process created it at the same moment
                k = get_kv("secret_key") or k
        _SECRET = k
    return _SECRET.encode()


# ---------------- unfinished new-project answers ----------------
def save_draft(user_id, data):
    set_kv(f"draft:{user_id}", json.dumps(data, default=_default))


def load_draft(user_id):
    v = get_kv(f"draft:{user_id}")
    return json.loads(v) if v else None


def delete_draft(user_id):
    del_kv(f"draft:{user_id}")


def make_token(user_id, hours=12):
    exp = int((dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)).timestamp())
    body = f"{user_id}.{exp}"
    return body + "." + hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()


def read_token(token):
    try:
        uid, exp, sig = (token or "").rsplit(".", 2)
    except ValueError:
        raise AuthError("Invalid token.")
    if not hmac.compare_digest(sig, hmac.new(_secret(), f"{uid}.{exp}".encode(), hashlib.sha256).hexdigest()): raise AuthError("Invalid token.")
    if int(exp) < dt.datetime.now(dt.timezone.utc).timestamp(): raise AuthError("Session expired. Log in again.")
    return uid


# ---------------- projects ----------------
def _role(c, user_id, project_id):
    row = c.execute(select(projects.c.user_id).where(projects.c.id == project_id)).first()
    if not row: return None
    if row[0] == user_id: return "owner"
    m = c.execute(select(members.c.role).where(members.c.project_id == project_id, members.c.user_id == user_id)).first()
    return m[0] if m else None


def _own(c, user_id, project_id, need="write"):
    """Owner and editors may write; viewers may only read (and comment). Anyone else gets NotFound."""
    r = _role(c, user_id, project_id)
    if r is None or (need == "write" and r == "viewer"): raise NotFound("project")
    return r


def role_of(user_id, project_id):
    with engine().connect() as c:
        return _role(c, user_id, project_id)


def _summary(result):
    if not result or "decision" not in result: return {}
    return dict(status=result["decision"]["code"], status_label=result["decision"]["label"], score=float(result["validation"]["score"]),
                confidence=float(result["evidence"]["strength"]))


def create_project(user_id, name, state, result=None):
    pid = str(uuid.uuid4()); it = state.get("intake", {})
    with engine().begin() as c:
        c.execute(insert(projects).values(id=pid, user_id=user_id, name=(name or "Untitled idea")[:200], created_at=now(), updated_at=now(),
                                          state=pack(state), result=pack(result) if result else None, business_type=it.get("business_type"),
                                          emirate=it.get("emirate"), **_summary(result)))
    return pid


def save_project(user_id, project_id, state=None, result=None, name=None):
    vals = dict(updated_at=now())
    if state is not None: vals["state"] = pack(state)
    if result is not None: vals.update(result=pack(result), **_summary(result))
    if name: vals["name"] = name[:200]
    with engine().begin() as c:
        _own(c, user_id, project_id)
        c.execute(update(projects).where(projects.c.id == project_id).values(**vals))


def list_projects(user_id):
    """Your own projects and the ones shared with you (role says which)."""
    cols = [projects.c[k] for k in ("id", "name", "created_at", "updated_at", "status", "status_label", "score", "confidence", "business_type", "emirate", "user_id")]
    with engine().connect() as c:
        shared = dict(c.execute(select(members.c.project_id, members.c.role).where(members.c.user_id == user_id)).all())
        rows = c.execute(select(*cols, users.c.username.label("owner")).join(users, users.c.id == projects.c.user_id)
                         .where((projects.c.user_id == user_id) | projects.c.id.in_(list(shared) or [""])).order_by(projects.c.updated_at.desc())).mappings().all()
        ids = [r["id"] for r in rows]
        counts = dict(c.execute(select(evidence.c.project_id, func.count()).where(evidence.c.project_id.in_(ids or [""])).group_by(evidence.c.project_id)).all())
    return [dict({k: v for k, v in r.items() if k != "user_id"}, evidence_count=int(counts.get(r["id"], 0)),
                 role="owner" if r["user_id"] == user_id else shared.get(r["id"])) for r in rows]


def load_project(user_id, project_id):
    with engine().connect() as c:
        role = _own(c, user_id, project_id, "read")
        r = c.execute(select(projects).where(projects.c.id == project_id)).mappings().first()
    return dict(id=r["id"], name=r["name"], state=unpack(r["state"]), result=unpack(r["result"]), baseline=unpack(r["baseline"]),
                updated_at=r["updated_at"], created_at=r["created_at"], role=role)


def project_summaries(user_id, project_ids):
    """Key outputs of several projects for the side-by-side comparison (read access needed for each)."""
    out = []
    for pid in project_ids:
        try: p = load_project(user_id, pid)
        except NotFound: continue
        out.append(dict(id=pid, name=p["name"], result=p["result"], state=p["state"]))
    return out


def delete_project(user_id, project_id):
    with engine().begin() as c:
        if _own(c, user_id, project_id) != "owner": raise NotFound("project")
        for t in (evidence, hypotheses, actuals, members, comments, activity, snapshots):
            c.execute(delete(t).where(t.c.project_id == project_id))
        c.execute(delete(projects).where(projects.c.id == project_id))


def set_baseline(user_id, project_id, baseline):
    with engine().begin() as c:
        _own(c, user_id, project_id)
        c.execute(update(projects).where(projects.c.id == project_id).values(baseline=pack(baseline) if baseline else None, updated_at=now()))


# ---------------- generic child records ----------------
EVIDENCE_FIELDS = ["claim", "area", "description", "source_url", "file_name", "file_mime", "collected_on", "geography", "ev_type", "sample_size",
                   "verification", "confidence", "limitations", "value_min", "value_likely", "value_max", "experiment_id", "hypothesis_id"]
HYP_FIELDS = ["statement", "area", "metric", "method", "expected", "threshold", "direction", "status", "plan"]
ACT_FIELDS = ["month", "revenue", "expenses", "customers", "new_customers", "visitors", "conversions", "repeat_customers", "marketing_spend", "notes"]


def add_evidence(user_id, project_id, rec, file_bytes=None):
    if file_bytes is not None and len(file_bytes) > MAX_FILE_BYTES: raise ValueError("Files must be 5 MB or smaller.")
    eid = str(uuid.uuid4())
    with engine().begin() as c:
        _own(c, user_id, project_id)
        c.execute(insert(evidence).values(id=eid, project_id=project_id, created_at=now(), file_blob=file_bytes, **{k: rec.get(k) for k in EVIDENCE_FIELDS}))
    return eid


def update_evidence(user_id, project_id, evidence_id, changes):
    with engine().begin() as c:
        _own(c, user_id, project_id)
        n = c.execute(update(evidence).where(evidence.c.id == evidence_id, evidence.c.project_id == project_id)
                      .values(**{k: v for k, v in changes.items() if k in EVIDENCE_FIELDS})).rowcount
    if not n: raise NotFound("evidence")


def list_evidence(user_id, project_id):
    cols = [evidence.c[k] for k in ["id", "created_at"] + EVIDENCE_FIELDS]
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        rows = c.execute(select(*cols, (evidence.c.file_blob.isnot(None)).label("has_file")).where(evidence.c.project_id == project_id)
                         .order_by(evidence.c.created_at)).mappings().all()
    return [dict(r) for r in rows]


def evidence_file(user_id, project_id, evidence_id):
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        r = c.execute(select(evidence.c.file_name, evidence.c.file_mime, evidence.c.file_blob)
                      .where(evidence.c.id == evidence_id, evidence.c.project_id == project_id)).first()
    if not r or r[2] is None: raise NotFound("file")
    return r[0], r[1], r[2]


def delete_evidence(user_id, project_id, evidence_id=None, experiment_id=None):
    with engine().begin() as c:
        _own(c, user_id, project_id)
        q = delete(evidence).where(evidence.c.project_id == project_id)
        q = q.where(evidence.c.id == evidence_id) if evidence_id else q.where(evidence.c.experiment_id == experiment_id)
        c.execute(q)


def add_hypothesis(user_id, project_id, rec):
    hid = str(uuid.uuid4())
    with engine().begin() as c:
        _own(c, user_id, project_id)
        c.execute(insert(hypotheses).values(id=hid, project_id=project_id, created_at=now(), updated_at=now(),
                                            **{k: (json.dumps(rec.get(k)) if k == "plan" else rec.get(k)) for k in HYP_FIELDS}))
    return hid


def update_hypothesis(user_id, project_id, hid, changes):
    vals = {k: (json.dumps(v) if k == "plan" else v) for k, v in changes.items() if k in HYP_FIELDS}
    with engine().begin() as c:
        _own(c, user_id, project_id)
        n = c.execute(update(hypotheses).where(hypotheses.c.id == hid, hypotheses.c.project_id == project_id).values(updated_at=now(), **vals)).rowcount
    if not n: raise NotFound("hypothesis")


def list_hypotheses(user_id, project_id):
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        rows = c.execute(select(hypotheses).where(hypotheses.c.project_id == project_id).order_by(hypotheses.c.created_at)).mappings().all()
    return [dict(r, plan=json.loads(r["plan"]) if r["plan"] else None) for r in rows]


def delete_hypothesis(user_id, project_id, hid):
    with engine().begin() as c:
        _own(c, user_id, project_id)
        c.execute(delete(hypotheses).where(hypotheses.c.id == hid, hypotheses.c.project_id == project_id))
        c.execute(update(evidence).where(evidence.c.project_id == project_id, evidence.c.hypothesis_id == hid).values(hypothesis_id=None))


def upsert_actual(user_id, project_id, rec):
    m = int(rec["month"])
    if m < 1 or m > 120: raise ValueError("Month must be between 1 and 120.")
    vals = {k: rec.get(k) for k in ACT_FIELDS}
    with engine().begin() as c:
        _own(c, user_id, project_id)
        ex = c.execute(select(actuals.c.id).where(actuals.c.project_id == project_id, actuals.c.month == m)).first()
        if ex: c.execute(update(actuals).where(actuals.c.id == ex[0]).values(**vals))
        else: c.execute(insert(actuals).values(id=str(uuid.uuid4()), project_id=project_id, created_at=now(), **vals))


def list_actuals(user_id, project_id):
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        rows = c.execute(select(actuals).where(actuals.c.project_id == project_id).order_by(actuals.c.month)).mappings().all()
    return [dict(r) for r in rows]


def delete_actual(user_id, project_id, month):
    with engine().begin() as c:
        _own(c, user_id, project_id)
        c.execute(delete(actuals).where(actuals.c.project_id == project_id, actuals.c.month == int(month)))


# ---------------- teams ----------------
def find_user(username):
    with engine().connect() as c:
        r = c.execute(select(users.c.id, users.c.username).where(func.lower(users.c.username) == (username or "").strip().lower())).first()
    return dict(id=r[0], username=r[1]) if r else None


def share_project(owner_id, project_id, username, role):
    if role not in ROLES: raise ValueError("Role must be editor or viewer.")
    u = find_user(username)
    if not u: raise ValueError(f"No account called {username!r}. Ask them to sign up first, then share again.")
    with engine().begin() as c:
        if _own(c, owner_id, project_id) != "owner": raise NotFound("project")
        if u["id"] == owner_id: raise ValueError("You already own this project.")
        c.execute(delete(members).where(members.c.project_id == project_id, members.c.user_id == u["id"]))
        c.execute(insert(members).values(project_id=project_id, user_id=u["id"], role=role, added_at=now()))
    return u


def unshare_project(owner_id, project_id, member_id):
    with engine().begin() as c:
        if _own(c, owner_id, project_id) != "owner" and owner_id != member_id: raise NotFound("project")
        c.execute(delete(members).where(members.c.project_id == project_id, members.c.user_id == member_id))


def list_members(user_id, project_id):
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        owner = c.execute(select(users.c.id, users.c.username).join(projects, projects.c.user_id == users.c.id).where(projects.c.id == project_id)).first()
        rows = c.execute(select(users.c.id, users.c.username, members.c.role, members.c.added_at).join(members, members.c.user_id == users.c.id)
                         .where(members.c.project_id == project_id)).mappings().all()
    return [dict(id=owner[0], username=owner[1], role="owner", added_at=None)] + [dict(r) for r in rows]


def usernames(ids):
    with engine().connect() as c:
        return dict(c.execute(select(users.c.id, users.c.username).where(users.c.id.in_(list(ids) or [""]))).all())


def add_comment(user_id, project_id, section, text):
    text = (text or "").strip()[:2000]
    if not text: raise ValueError("Write a comment first.")
    cid = str(uuid.uuid4())
    with engine().begin() as c:
        _own(c, user_id, project_id, "read")
        c.execute(insert(comments).values(id=cid, project_id=project_id, user_id=user_id, section=(section or "")[:80], text=text, resolved=0, created_at=now()))
    return cid


def list_comments(user_id, project_id, section=None, include_resolved=False):
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        q = select(comments).where(comments.c.project_id == project_id)
        if section: q = q.where(comments.c.section == section)
        if not include_resolved: q = q.where(comments.c.resolved == 0)
        rows = c.execute(q.order_by(comments.c.created_at)).mappings().all()
    names = usernames({r["user_id"] for r in rows})
    return [dict(r, username=names.get(r["user_id"], "former member")) for r in rows]


def resolve_comment(user_id, project_id, comment_id):
    with engine().begin() as c:
        _own(c, user_id, project_id, "read")
        c.execute(update(comments).where(comments.c.id == comment_id, comments.c.project_id == project_id).values(resolved=1))


def log(user_id, project_id, action, detail=""):
    """Activity log: who changed what. Never raises: logging must not break the action it records."""
    try:
        with engine().begin() as c:
            c.execute(insert(activity).values(id=str(uuid.uuid4()), project_id=project_id, user_id=user_id, action=action[:80], detail=(detail or "")[:1000], created_at=now()))
    except Exception:
        pass


def list_activity(user_id, project_id, limit=200):
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        rows = c.execute(select(activity).where(activity.c.project_id == project_id).order_by(activity.c.created_at.desc()).limit(limit)).mappings().all()
    names = usernames({r["user_id"] for r in rows})
    return [dict(r, username=names.get(r["user_id"], "former member")) for r in rows]


# ---------------- version history ----------------
def add_snapshot(user_id, project_id, reason, summary):
    with engine().begin() as c:
        _own(c, user_id, project_id)
        c.execute(insert(snapshots).values(id=str(uuid.uuid4()), project_id=project_id, user_id=user_id, reason=(reason or "")[:300], summary=pack(summary), created_at=now()))


def list_snapshots(user_id, project_id, limit=100):
    with engine().connect() as c:
        _own(c, user_id, project_id, "read")
        rows = c.execute(select(snapshots).where(snapshots.c.project_id == project_id).order_by(snapshots.c.created_at.desc()).limit(limit)).mappings().all()
    names = usernames({r["user_id"] for r in rows})
    return [dict(id=r["id"], reason=r["reason"], created_at=r["created_at"], username=names.get(r["user_id"], "former member"), summary=unpack(r["summary"])) for r in rows]


# ---------------- benchmarks across projects ----------------
def sector_benchmarks(business_type, min_users=3):
    """Medians of the figures founders entered for this business type, across all accounts, anonymised.
    Only shown when at least `min_users` different accounts contributed, so no one's numbers can be singled out."""
    vals = {}; owners = set()
    with engine().connect() as c:
        rows = c.execute(select(projects.c.user_id, projects.c.state).where(projects.c.business_type == business_type)).all()
    for uid, st_ in rows:
        it = (unpack(st_) or {}).get("intake") or {}
        got = False
        for k in ("price", "fixed", "setup_budget", "marketing_budget_aed", "budget_aed"):
            v = it.get(k)
            if v: vals.setdefault(k, []).append(float(v)); got = True
        if got: owners.add(uid)
    if len(owners) < min_users: return dict(n_accounts=len(owners), enough=False, min_users=min_users)
    import statistics
    return dict(n_accounts=len(owners), enough=True, min_users=min_users,
                medians={k: statistics.median(v) for k, v in vals.items() if len(v) >= min_users}, counts={k: len(v) for k, v in vals.items()})


# ---------------- account ----------------
def export_account(user_id):
    """Everything stored for this account, for backups or moving elsewhere."""
    out = dict(user=get_user(user_id), projects=[])
    for p in list_projects(user_id):
        if p["role"] != "owner": continue
        full = load_project(user_id, p["id"])
        out["projects"].append(dict(project=dict(id=full["id"], name=full["name"], state=full["state"], created_at=full["created_at"]),
                                    evidence=list_evidence(user_id, p["id"]), hypotheses=list_hypotheses(user_id, p["id"]), actuals=list_actuals(user_id, p["id"])))
    return out


def delete_account(user_id):
    """Delete the account, its projects with all their records, and its memberships of other projects."""
    for p in list_projects(user_id):
        if p["role"] == "owner": delete_project(user_id, p["id"])
    with engine().begin() as c:
        c.execute(delete(members).where(members.c.user_id == user_id))
        c.execute(delete(kv).where(kv.c.key.like(f"%{user_id}%")))
        c.execute(delete(users).where(users.c.id == user_id))
