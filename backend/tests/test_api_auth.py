import importlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "api.db")); monkeypatch.setenv("SECRET_KEY", "test-secret"); monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app import store, main
    store.reset_engine(); importlib.reload(main)
    yield TestClient(main.app)
    store.reset_engine()


IDEA = dict(idea="A cloud kitchen delivering healthy high-protein lunches to office workers in Business Bay.", business_type="kitchen", use_ai=False)


def token(c, name):
    r = c.post("/api/auth/register", json=dict(username=name, password="s3cure-pass")); assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_project_endpoints_require_login(client):
    assert client.get("/api/analyses").status_code == 401
    assert client.post("/api/analyses", json=IDEA).status_code == 401
    assert client.get("/api/analyses", headers={"Authorization": "Bearer forged.1.abc"}).status_code == 401
    assert client.get("/api/health").status_code == 200


def test_users_cannot_see_each_others_analyses(client):
    a, b = token(client, "alice"), token(client, "bobby")
    aid = client.post("/api/analyses", json=IDEA, headers=a).json()["id"]
    for _ in range(120):
        if client.get(f"/api/analyses/{aid}", headers=a).json()["status"] != "running": break
        time.sleep(1)
    assert client.get(f"/api/analyses/{aid}", headers=a).json()["status"] == "done"
    assert [x["id"] for x in client.get("/api/analyses", headers=a).json()] == [aid]
    assert client.get("/api/analyses", headers=b).json() == []
    assert client.get(f"/api/analyses/{aid}", headers=b).status_code == 404
    assert client.post(f"/api/analyses/{aid}/reset", headers=b).status_code == 404


def test_login_errors(client):
    token(client, "carol")
    assert client.post("/api/auth/login", json=dict(username="carol", password="wrong")).status_code == 401
    assert client.post("/api/auth/login", json=dict(username="carol", password="s3cure-pass")).status_code == 200
