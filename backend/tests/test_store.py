import pytest
from app import store


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db")); monkeypatch.delenv("DATABASE_URL", raising=False)
    store.reset_engine(); yield; store.reset_engine()


def test_register_login_and_bad_password():
    u = store.create_user("Founder1", "s3cure-pass")
    assert store.authenticate("founder1", "s3cure-pass")["id"] == u["id"]
    with pytest.raises(store.AuthError): store.authenticate("founder1", "wrong-pass")
    with pytest.raises(store.AuthError): store.create_user("founder1", "another-pass")
    with pytest.raises(store.AuthError): store.create_user("x", "s3cure-pass")
    with pytest.raises(store.AuthError): store.create_user("someone", "short")


def test_lockout_after_repeated_failures():
    store.create_user("lockme", "s3cure-pass")
    for _ in range(store.MAX_FAILED):
        with pytest.raises(store.AuthError): store.authenticate("lockme", "nope-nope")
    with pytest.raises(store.AuthError, match="Too many"): store.authenticate("lockme", "s3cure-pass")


def test_projects_are_private_to_their_owner():
    a = store.create_user("alice", "s3cure-pass")["id"]; b = store.create_user("bob__", "s3cure-pass")["id"]
    pid = store.create_project(a, "Cafe", {"intake": {"business_type": "cafe"}})
    assert [p["id"] for p in store.list_projects(a)] == [pid] and store.list_projects(b) == []
    for fn, args in [(store.load_project, (pid,)), (store.save_project, (pid, {"x": 1})), (store.list_evidence, (pid,)),
                     (store.add_evidence, (pid, {"claim": "x"})), (store.list_actuals, (pid,)), (store.delete_project, (pid,))]:
        with pytest.raises(store.NotFound): fn(b, *args)
    assert store.load_project(a, pid)["name"] == "Cafe"


def test_evidence_file_hypothesis_and_actuals_roundtrip():
    a = store.create_user("carol", "s3cure-pass")["id"]; pid = store.create_project(a, "Idea", {"intake": {}})
    eid = store.add_evidence(a, pid, {"claim": "People pay 400", "ev_type": "feedback", "sample_size": 12}, file_bytes=b"%PDF-1.4 test")
    assert store.list_evidence(a, pid)[0]["has_file"] and store.evidence_file(a, pid, eid)[2] == b"%PDF-1.4 test"
    with pytest.raises(ValueError): store.add_evidence(a, pid, {"claim": "big"}, file_bytes=b"0" * (store.MAX_FILE_BYTES + 1))
    hid = store.add_hypothesis(a, pid, {"statement": "s", "plan": {"steps": [1]}, "status": "planned"})
    store.update_hypothesis(a, pid, hid, {"status": "validated"})
    assert store.list_hypotheses(a, pid)[0]["status"] == "validated" and store.list_hypotheses(a, pid)[0]["plan"] == {"steps": [1]}
    store.upsert_actual(a, pid, {"month": 1, "revenue": 1000}); store.upsert_actual(a, pid, {"month": 1, "revenue": 1500})
    assert [x["revenue"] for x in store.list_actuals(a, pid)] == [1500]
    store.delete_project(a, pid); assert store.list_projects(a) == []


def test_tokens():
    t = store.make_token("u1"); assert store.read_token(t) == "u1"
    with pytest.raises(store.AuthError): store.read_token(t[:-2] + "00")


def test_signin_key_and_draft_survive_restart(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    u = store.create_user("dana", "s3cure-pass")["id"]
    t = store.make_token(u)
    store.save_draft(u, {"step": 2, "data": {"idea": "x"}})
    store.reset_engine()  # simulates an app restart: in-memory key forgotten, database kept
    assert store.read_token(t) == u
    assert store.load_draft(u)["step"] == 2
    store.delete_draft(u); assert store.load_draft(u) is None


def test_every_neon_url_form_uses_the_installed_driver():
    base = "user:pw@ep-cool-1.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    want = "postgresql+psycopg2://" + base
    for raw in (f"postgresql://{base}", f"postgres://{base}", f"postgresql+psycopg://{base}", f"psql 'postgresql://{base}'", f'"postgresql://{base}"', f"  postgresql://{base}\n"):
        assert store.normalise_db_url(raw) == want
    assert store.normalise_db_url("") is None
    with pytest.raises(ValueError): store.normalise_db_url("not a url")


def test_bad_database_url_falls_back_with_a_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1")
    store.reset_engine()
    assert store.backend_name().startswith("SQLite") and "Could not connect" in store.config_warning
    store.create_user("eve__", "s3cure-pass")  # the app still works
