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
