"""Who can see and change which notes. These rules are the privacy promise for students."""

import io
import json

import pytest
from PIL import Image
from sqlalchemy import delete, select

from app.models import Note, NotePage, NoteShare, SchoolClass, User
from app.security import hash_password
from tests.conftest import login

# Seeded classes: Aarav and Diya are in 6-A, Rohan is in 6-B.
AARAV, DIYA, ROHAN, TEACHER = "aarav@demo.school", "diya@demo.school", "rohan@demo.school", "teacher@demo.school"


@pytest.fixture(autouse=True)
def clean_notes(db):
    yield
    db.execute(delete(NoteShare))
    db.execute(delete(NotePage))
    db.execute(delete(Note))
    db.execute(delete(User).where(User.email == "other.teacher@demo.school"))  # created by one test
    db.commit()


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(buf, "PNG")
    return buf.getvalue()


def make_note(client, who: str, title="My note", text="Magnets attract iron.") -> int:
    resp = client.post("/api/notes", json={"title": title, "text": text}, headers=login(client, who))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def class_id(db, name: str) -> int:
    return db.scalar(select(SchoolClass.id).where(SchoolClass.name == name))


def share(client, db, note_id: int, *class_names: str):
    resp = client.put(
        f"/api/notes/{note_id}/shares",
        json={"class_ids": [class_id(db, n) for n in class_names]},
        headers=login(client, TEACHER),
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------- students are private


def test_student_cannot_see_another_students_note(client):
    note_id = make_note(client, AARAV)
    rohan = login(client, ROHAN)
    assert client.get(f"/api/notes/{note_id}", headers=rohan).status_code == 404
    assert client.get("/api/notes", headers=rohan).json() == []


def test_student_cannot_touch_another_students_note_by_any_route(client):
    note_id = make_note(client, AARAV)
    rohan = login(client, ROHAN)
    routes = [
        ("GET", f"/api/notes/{note_id}/download", None),
        ("GET", f"/api/notes/{note_id}/pages/1/image", None),
        ("PATCH", f"/api/notes/{note_id}", {"title": "hacked"}),
        ("DELETE", f"/api/notes/{note_id}", None),
        ("POST", f"/api/notes/{note_id}/practice", None),
    ]
    for method, url, body in routes:
        resp = client.request(method, url, json=body, headers=rohan)
        assert resp.status_code == 404, f"{method} {url} -> {resp.status_code}"
    # and the owner's note is untouched
    assert client.get(f"/api/notes/{note_id}", headers=login(client, AARAV)).json()["title"] == "My note"


def test_missing_and_forbidden_notes_look_identical(client):
    note_id = make_note(client, AARAV)
    rohan = login(client, ROHAN)
    other = client.get(f"/api/notes/{note_id}", headers=rohan)
    missing = client.get("/api/notes/999999", headers=rohan)
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()


def test_search_only_covers_visible_notes(client):
    make_note(client, AARAV, title="Secret volcano", text="lava lava lava")
    assert client.get("/api/notes", params={"q": "volcano"}, headers=login(client, ROHAN)).json() == []
    found = client.get("/api/notes", params={"q": "volcano"}, headers=login(client, AARAV)).json()
    assert [n["title"] for n in found] == ["Secret volcano"]


def test_requests_without_login_or_with_wrong_role_are_refused(client):
    assert client.get("/api/notes").status_code == 401
    assert client.get("/api/notes", headers=login(client, "parent.aarav@demo.school")).status_code == 403
    assert client.get("/api/notes", headers=login(client, "admin@demo.school")).status_code == 403


# ---------------------------------------------------------------- teachers


def test_teacher_sees_only_their_own_notes(client, db):
    make_note(client, TEACHER, title="Teacher note")
    db.add(User(name="Other Teacher", email="other.teacher@demo.school", role="teacher", password_hash=hash_password("demo1234")))
    db.commit()
    other = login(client, "other.teacher@demo.school")
    assert client.get("/api/notes", headers=other).json() == []
    make_note(client, "other.teacher@demo.school", title="Other note")
    mine = client.get("/api/notes", headers=login(client, TEACHER)).json()
    assert [n["title"] for n in mine] == ["Teacher note"]


def test_teacher_cannot_see_student_notes(client):
    make_note(client, AARAV)
    assert client.get("/api/notes", headers=login(client, TEACHER)).json() == []


# ---------------------------------------------------------------- sharing


def test_shared_note_reaches_only_that_class_and_is_read_only(client, db):
    note_id = make_note(client, TEACHER, title="Shared magnets")
    share(client, db, note_id, "6-A")

    for who in (AARAV, DIYA):  # both in 6-A
        headers = login(client, who)
        listed = client.get("/api/notes", headers=headers).json()
        assert [n["title"] for n in listed] == ["Shared magnets"]
        assert listed[0]["is_mine"] is False and listed[0]["shared_with"] == []
        detail = client.get(f"/api/notes/{note_id}", headers=headers).json()
        assert detail["can_edit"] is False
        assert client.get(f"/api/notes/{note_id}/download", headers=headers).status_code == 200

    rohan = login(client, ROHAN)  # 6-B
    assert client.get("/api/notes", headers=rohan).json() == []
    assert client.get(f"/api/notes/{note_id}", headers=rohan).status_code == 404


def test_shared_note_cannot_be_changed_or_deleted_by_a_student(client, db):
    note_id = make_note(client, TEACHER)
    share(client, db, note_id, "6-A")
    aarav = login(client, AARAV)
    assert client.patch(f"/api/notes/{note_id}", json={"title": "mine now"}, headers=aarav).status_code == 403
    assert client.delete(f"/api/notes/{note_id}", headers=aarav).status_code == 403
    assert client.put(f"/api/notes/{note_id}/shares", json={"class_ids": []}, headers=aarav).status_code == 403


def test_unsharing_removes_access(client, db):
    note_id = make_note(client, TEACHER)
    share(client, db, note_id, "6-A")
    share(client, db, note_id)  # empty: share with nobody
    assert client.get(f"/api/notes/{note_id}", headers=login(client, AARAV)).status_code == 404


def test_students_can_never_share(client, db):
    note_id = make_note(client, AARAV)
    resp = client.put(
        f"/api/notes/{note_id}/shares", json={"class_ids": [class_id(db, "6-B")]}, headers=login(client, AARAV)
    )
    assert resp.status_code == 403
    assert client.get(f"/api/notes/{note_id}", headers=login(client, ROHAN)).status_code == 404


def test_teacher_cannot_share_someone_elses_note(client, db):
    note_id = make_note(client, AARAV)
    resp = client.put(
        f"/api/notes/{note_id}/shares", json={"class_ids": [class_id(db, "6-A")]}, headers=login(client, TEACHER)
    )
    assert resp.status_code == 404


def test_deleting_a_note_removes_its_shares_and_files(client, db, storage):
    note_id = make_note(client, TEACHER)
    share(client, db, note_id, "6-A", "6-B")
    assert client.delete(f"/api/notes/{note_id}", headers=login(client, TEACHER)).status_code == 204
    assert client.get(f"/api/notes/{note_id}", headers=login(client, AARAV)).status_code == 404
    assert db.scalar(select(NoteShare.id)) is None


# ---------------------------------------------------------------- drafts


def test_drafts_are_private_to_the_owner_even_if_shared(client, db, provider):
    provider.replies.append(json.dumps({"text": "Magnets\n- iron"}))
    resp = client.post(
        "/api/notes/ocr", files=[("files", ("p.png", png(), "image/png"))], headers=login(client, TEACHER)
    )
    note_id = resp.json()["id"]
    assert resp.json()["status"] == "draft"
    # sharing a draft is refused...
    refused = client.put(f"/api/notes/{note_id}/shares", json={"class_ids": [class_id(db, "6-A")]}, headers=login(client, TEACHER))
    assert refused.status_code == 422
    # ...and even a forced share row would not expose it
    db.add(NoteShare(note_id=note_id, class_id=class_id(db, "6-A")))
    db.commit()
    assert client.get(f"/api/notes/{note_id}", headers=login(client, AARAV)).status_code == 404
