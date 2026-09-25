import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ai import AIError
from app.models import ParentSummary, Setting
from app.services.summary import template_narrative
from tests.conftest import login


@pytest.fixture(autouse=True)
def clean(_engine):
    def wipe():
        with Session(_engine) as s:
            s.execute(delete(ParentSummary))
            s.merge(Setting(key="weak_topic_threshold", value="60"))
            s.commit()

    wipe()
    yield
    wipe()


@pytest.fixture
def teacher(client):
    return login(client, "teacher@demo.school")


def student_id(client, teacher, first):
    rows = client.get("/api/summaries", headers=teacher).json()
    return next(r["student_id"] for r in rows if r["name"].startswith(first))


def scripted(client, provider, teacher, sid):
    """Queue a model reply that restates the real figures (built from the same facts the API will compute)."""
    detail = client.get(f"/api/summaries/{sid}", headers=teacher).json()
    provider.replies.append(template_narrative(detail["facts"], detail["name"]).model_dump_json())


def generate(client, provider, teacher, first="Aarav"):
    sid = student_id(client, teacher, first)
    scripted(client, provider, teacher, sid)
    resp = client.post(f"/api/summaries/{sid}/generate", headers=teacher)
    assert resp.status_code == 200, resp.text
    return sid, resp.json()


def test_teacher_sees_every_student_with_live_figures(client, teacher):
    rows = client.get("/api/summaries", headers=teacher).json()
    assert len(rows) == 15 and all(r["status"] == "none" and r["overall_percent"] is not None for r in rows)
    only_a = client.get("/api/summaries?class_id=1", headers=teacher).json()
    assert 0 < len(only_a) < 15 and {r["class_name"] for r in only_a} == {"6-A"}


def test_generate_makes_a_draft_with_the_computed_numbers(client, provider, teacher):
    sid, detail = generate(client, provider, teacher)
    assert detail["status"] == "draft" and detail["source"] == "ai" and detail["narrative"]["home_tips"]
    live = client.get(f"/api/summaries/{sid}", headers=teacher).json()
    assert live["facts"]["overall_percent"] == detail["facts"]["overall_percent"]
    row = next(r for r in client.get("/api/summaries", headers=teacher).json() if r["student_id"] == sid)
    assert row["status"] == "draft"


def test_a_wrong_number_from_the_model_never_becomes_a_draft_as_written(client, provider, teacher):
    sid = student_id(client, teacher, "Aarav")
    scripted(client, provider, teacher, sid)
    good = provider.replies.pop()
    bad = good.replace('"overall":"', '"overall":"Scored 3141% ')
    provider.replies += [bad, bad]
    detail = client.post(f"/api/summaries/{sid}/generate", headers=teacher).json()
    assert detail["source"] == "template" and detail["verify_failures"] == 2
    assert "3141" not in detail["narrative"]["overall"]


def test_ai_outage_still_gives_a_draft(client, provider, teacher):
    sid = student_id(client, teacher, "Diya")
    provider.replies.append(AIError("The AI is busy."))
    detail = client.post(f"/api/summaries/{sid}/generate", headers=teacher).json()
    assert detail["status"] == "draft" and detail["source"] == "template"


def test_parent_sees_nothing_until_the_teacher_approves(client, provider, teacher):
    sid, _ = generate(client, provider, teacher)
    parent = login(client, "parent.aarav@demo.school")
    before = client.get("/api/my-child/summary", headers=parent).json()
    assert before["available"] is False and before["narrative"] is None and before["facts"] is None
    assert client.post(f"/api/summaries/{sid}/approve", headers=teacher).json()["status"] == "approved"
    seen = client.get("/api/my-child/summary", headers=parent).json()
    assert seen["available"] and seen["narrative"]["overall"] and seen["facts"]["tests"] and seen["approved_at"]


def test_a_parent_only_ever_gets_their_own_childs_summary(client, provider, teacher):
    sid, _ = generate(client, provider, teacher, "Aarav")
    client.post(f"/api/summaries/{sid}/approve", headers=teacher)
    other = login(client, "parent.rohan@demo.school")
    seen = client.get("/api/my-child/summary", headers=other).json()
    assert seen["child_name"] == "Rohan Verma" and seen["available"] is False  # Aarav's approved summary is not reachable


def test_only_teachers_can_use_the_review_endpoints(client, provider, teacher):
    sid, _ = generate(client, provider, teacher)
    for who in ("parent.aarav@demo.school", "aarav@demo.school", "admin@demo.school"):
        h = login(client, who)
        assert client.get("/api/summaries", headers=h).status_code == 403
        assert client.get(f"/api/summaries/{sid}", headers=h).status_code == 403
        assert client.post(f"/api/summaries/{sid}/approve", headers=h).status_code == 403
        assert client.post(f"/api/summaries/{sid}/generate", headers=h).status_code == 403
    assert client.get("/api/summaries").status_code == 401
    assert client.get("/api/my-child/summary", headers=teacher).status_code == 403
    assert client.get("/api/my-child/summary", headers=login(client, "aarav@demo.school")).status_code == 403


def test_editing_keeps_the_numbers_honest_and_needs_reapproval(client, provider, teacher):
    sid, detail = generate(client, provider, teacher)
    client.post(f"/api/summaries/{sid}/approve", headers=teacher)
    overall = f"Aarav is doing wonderfully well this term, with an overall score of {detail['facts']['overall_percent']}%."
    edited = {**detail["narrative"], "overall": overall}
    ok = client.put(f"/api/summaries/{sid}", headers=teacher, json=edited)
    assert ok.status_code == 200 and ok.json()["status"] == "draft" and ok.json()["edited"] is True
    parent = login(client, "parent.aarav@demo.school")
    assert client.get("/api/my-child/summary", headers=parent).json()["available"] is False  # back in review

    wrong = client.put(f"/api/summaries/{sid}", headers=teacher, json={**edited, "overall": "Aarav scored 99999% overall, which is remarkable."})
    assert wrong.status_code == 422 and "99999" in wrong.json()["detail"]
    ranking = client.put(f"/api/summaries/{sid}", headers=teacher, json={**edited, "overall": "Aarav is the topper of the class, wonderful."})
    assert ranking.status_code == 422


def test_regenerating_an_approved_summary_puts_it_back_in_review(client, provider, teacher):
    sid, _ = generate(client, provider, teacher)
    client.post(f"/api/summaries/{sid}/approve", headers=teacher)
    scripted(client, provider, teacher, sid)
    assert client.post(f"/api/summaries/{sid}/generate", headers=teacher).json()["status"] == "draft"


def test_approve_all_only_touches_drafts_in_that_class(client, provider, teacher):
    a, _ = generate(client, provider, teacher, "Aarav")
    r, _ = generate(client, provider, teacher, "Rohan")
    rows = {x["student_id"]: x["class_name"] for x in client.get("/api/summaries", headers=teacher).json()}
    assert rows[a] != rows[r]  # Aarav and Rohan are in different classes
    class_id = 1 if rows[a] == "6-A" else 2
    assert client.post("/api/summaries/approve-all", headers=teacher, json={"class_id": class_id}).json() == {"approved": 1}
    status = {x["student_id"]: x["status"] for x in client.get("/api/summaries", headers=teacher).json()}
    assert status[a] == "approved" and status[r] == "draft"


def test_missing_things_are_clean_errors(client, teacher):
    assert client.get("/api/summaries/9999", headers=teacher).status_code == 404
    sid = student_id(client, teacher, "Aarav")
    assert client.post(f"/api/summaries/{sid}/approve", headers=teacher).status_code == 404  # nothing to approve yet
    body = {"overall": "x" * 30, "strengths": ["a"], "areas_to_work_on": [], "trend": "steady", "home_tips": ["a", "b"]}
    assert client.put(f"/api/summaries/{sid}", headers=teacher, json=body).status_code == 404


def test_the_weak_topic_threshold_setting_is_respected(client, _engine, teacher):
    sid = student_id(client, teacher, "Diya")
    base = client.get(f"/api/summaries/{sid}", headers=teacher).json()["facts"]["weak_topics"]
    with Session(_engine) as s:
        s.merge(Setting(key="weak_topic_threshold", value="95"))
        s.commit()
    strict = client.get(f"/api/summaries/{sid}", headers=teacher).json()["facts"]["weak_topics"]
    assert len(strict) > len(base)
