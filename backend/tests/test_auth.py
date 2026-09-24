from fastapi import Depends, FastAPI

from app.deps import require_role
from app.main import app
from tests.conftest import login


def test_login_returns_token_and_user(client):
    resp = client.post("/api/auth/login", json={"email": "teacher@demo.school", "password": "demo1234"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "teacher" and body["token"]


def test_login_is_case_insensitive_on_email(client):
    resp = client.post("/api/auth/login", json={"email": " Teacher@Demo.School ", "password": "demo1234"})
    assert resp.status_code == 200


def test_wrong_password_and_unknown_user_get_the_same_message(client):
    bad_pw = client.post("/api/auth/login", json={"email": "teacher@demo.school", "password": "nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@demo.school", "password": "demo1234"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json()


def test_me_requires_a_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_student_profile_includes_class(client):
    me = client.get("/api/auth/me", headers=login(client, "aarav@demo.school")).json()
    assert me["role"] == "student" and me["student"]["class_name"] in {"6-A", "6-B"}
    assert me["child"] is None


def test_parent_profile_points_to_their_child(client):
    me = client.get("/api/auth/me", headers=login(client, "parent.aarav@demo.school")).json()
    assert me["role"] == "parent" and me["child"]["name"] == "Aarav Sharma"


def test_role_guard_allows_and_blocks(client):
    guarded = FastAPI()  # tiny app to exercise require_role in isolation
    guarded.dependency_overrides = app.dependency_overrides

    @guarded.get("/teachers-only", dependencies=[Depends(require_role("teacher"))])
    def teachers_only():
        return {"ok": True}

    from fastapi.testclient import TestClient

    other = TestClient(guarded)
    assert other.get("/teachers-only", headers=login(client, "teacher@demo.school")).status_code == 200
    assert other.get("/teachers-only", headers=login(client, "aarav@demo.school")).status_code == 403
    assert other.get("/teachers-only").status_code == 401


def test_demo_accounts_all_work(client):
    accounts = client.get("/api/auth/demo-accounts").json()
    assert {a["role"] for a in accounts} == {"teacher", "admin", "student", "parent"}
    for a in accounts:
        assert client.post("/api/auth/login", json={"email": a["email"], "password": a["password"]}).status_code == 200
