import json

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai import AIError
from app.models import Assessment, AssessmentQuestion, Attempt, AttemptAnswer, Note, NoteShare, Question, QuestionSet, SchoolClass, User
from tests.conftest import login
from tests.qhelpers import NOTE_TEXT

# (type, text, options, answer, topic, marks)
SPEC = [
    ("mcq", "Which material is attracted by a magnet?", ["Wood", "Iron", "Glass", "Rubber"], "Iron", "Materials", 1),
    ("true_false", "Every magnet has two poles.", ["True", "False"], "True", "Poles", 1),
    ("fill_blank", "Two like poles _____ each other.", None, "repel", "Poles", 1),
    ("short", "Why are bar magnets stored with a keeper?", None, "The keeper helps the magnets keep their strength.", "Keeping", 2),
    ("long", "Explain how an electromagnet is made.", None, "Wind a wire around an iron nail and connect a battery.", "Making", 5),
]


@pytest.fixture
def world(_engine):
    """A saved teacher note, five accepted questions, and a test for class 6-A (Aarav, Diya). Removed afterwards."""
    ids = {}
    with Session(_engine) as s:
        teacher = s.scalar(select(User).where(User.email == "teacher@demo.school"))
        note = Note(owner_id=teacher.id, title="Magnets (test)", subject="Science", source_type="typed", status="saved", text=NOTE_TEXT)
        qset = QuestionSet(note=note, owner_id=teacher.id, version=1, emphasis="balanced", requested_count=5, types=[t[0] for t in SPEC], difficulty="mixed")
        for i, (qtype, text, options, answer, topic, marks) in enumerate(SPEC):
            qset.questions.append(
                Question(note=note, owner_id=teacher.id, position=i, type=qtype, text=text, options=options, answer=answer, explanation=f"Because {answer}.", difficulty="easy", bloom="Remember", topic=topic, marks=marks, status="accepted")
            )
        class_a = s.scalar(select(SchoolClass).where(SchoolClass.name == "6-A"))
        test = Assessment(title="Magnet quiz", class_id=class_a.id, owner_id=teacher.id)
        s.add_all([note, qset, test])
        s.flush()
        for i, q in enumerate(qset.questions):
            test.items.append(AssessmentQuestion(question_id=q.id, position=i, marks=q.marks))
        s.commit()
        ids = {"note": note.id, "test": test.id, "qs": [q.id for q in qset.questions], "class_a": class_a.id, "set": qset.id}
    yield ids
    with Session(_engine) as s:
        s.execute(delete(AttemptAnswer))
        s.execute(delete(Attempt))
        s.execute(delete(AssessmentQuestion))
        s.execute(delete(Assessment))
        s.execute(delete(Question).where(Question.set_id == ids["set"]))
        s.execute(delete(QuestionSet).where(QuestionSet.id == ids["set"]))
        s.execute(delete(NoteShare).where(NoteShare.note_id == ids["note"]))
        s.execute(delete(Note).where(Note.id == ids["note"]))
        s.commit()


@pytest.fixture
def aarav(client):
    return login(client, "aarav@demo.school")


def right(world):
    """Answers that are all correct (the model marks the written ones full)."""
    q = world["qs"]
    return [
        {"question_id": q[0], "answer": "Iron"},
        {"question_id": q[1], "answer": "True"},
        {"question_id": q[2], "answer": "repel"},
        {"question_id": q[3], "answer": "It keeps the magnets strong."},
        {"question_id": q[4], "answer": "Wind wire round an iron nail and join a battery."},
    ]


def written_reply(world, short, long):
    q = world["qs"]
    return json.dumps({"results": [{"id": q[3], "score": short, "reason": "ok"}, {"id": q[4], "score": long, "reason": "ok"}]})


def submit(client, headers, world, answers, test=None):
    return client.post(f"/api/tests/{test or world['test']}/submit", headers=headers, json={"answers": answers})


# ---------------------------------------------------------------- taking a test


def test_student_sees_tests_for_their_own_class_only(client, world, aarav):
    rows = client.get("/api/tests", headers=aarav).json()
    assert [r["title"] for r in rows] == ["Magnet quiz"] and rows[0]["status"] == "todo" and rows[0]["total_marks"] == 10
    rohan = login(client, "rohan@demo.school")  # class 6-B
    assert client.get("/api/tests", headers=rohan).json() == []


def test_the_paper_never_contains_the_answers(client, world, aarav):
    paper = client.get(f"/api/tests/{world['test']}", headers=aarav).json()
    assert len(paper["questions"]) == 5 and not paper["submitted"]
    blob = json.dumps(paper).lower()
    assert '"answer"' not in blob and "explanation" not in blob and "because" not in blob
    assert paper["questions"][0]["options"] and paper["questions"][0]["marks"] == 1


def test_a_test_from_another_class_is_not_found_never_forbidden(client, world):
    rohan = login(client, "rohan@demo.school")
    for method, url in [("get", f"/api/tests/{world['test']}"), ("get", f"/api/tests/{world['test']}/report"), ("post", f"/api/tests/{world['test']}/submit")]:
        resp = client.request(method.upper(), url, headers=rohan, json={"answers": []} if method == "post" else None)
        assert resp.status_code == 404, url


def test_full_marks_when_everything_is_right(client, world, aarav, provider):
    provider.replies.append(written_reply(world, 1, 1))
    resp = submit(client, aarav, world, right(world))
    assert resp.status_code == 201, resp.text
    report = resp.json()
    assert (report["marks"], report["max_marks"], report["percent"]) == (10, 10, 100)
    assert report["priorities"] == [] and not report["ai_fallback"]


def test_wrong_answers_lose_marks_and_the_report_points_at_exactly_those_topics(client, world, aarav, provider):
    """The block's exit check: the weak topics on the report match the questions answered wrongly."""
    answers = right(world)
    answers[0]["answer"] = "Wood"  # mcq wrong (Materials)
    answers[2]["answer"] = "attract"  # fill wrong (Poles)
    provider.replies.append(written_reply(world, 0.5, 0))  # short half of 2, long zero of 5
    report = submit(client, aarav, world, answers).json()
    got = {q["question_id"]: q["marks_awarded"] for q in report["questions"]}
    q = world["qs"]
    assert [got[q[0]], got[q[1]], got[q[2]], got[q[3]], got[q[4]]] == [0, 1, 0, 1, 0]
    assert report["marks"] == 2 and report["percent"] == 20

    by_topic = {t["topic"]: t for t in report["topics"]}
    assert (by_topic["Materials"]["percent"], by_topic["Poles"]["percent"], by_topic["Keeping"]["percent"], by_topic["Making"]["percent"]) == (0, 50, 50, 0)
    wrong_ids = {q[0], q[2], q[3], q[4]}
    assert {m["question_id"] for t in report["topics"] for m in t["missed"]} == wrong_ids
    assert [p["topic"] for p in report["priorities"]] == ["Making", "Materials", "Keeping"]  # 0%, 0%, then 50% (Poles ties, fewer marks lost)
    assert all(t["weak"] for t in report["topics"])


def test_correct_answers_are_revealed_only_after_submitting(client, world, aarav, provider):
    provider.replies.append(written_reply(world, 1, 1))
    report = submit(client, aarav, world, right(world)).json()
    first = report["questions"][0]
    assert first["correct_answer"] == "Iron" and first["explanation"] and first["your_answer"] == "Iron"


def test_a_test_can_only_be_submitted_once(client, world, aarav, provider):
    provider.replies.append(written_reply(world, 1, 1))
    assert submit(client, aarav, world, right(world)).status_code == 201
    again = submit(client, aarav, world, right(world))
    assert again.status_code == 409
    assert client.get(f"/api/tests/{world['test']}/report", headers=aarav).json()["marks"] == 10
    assert client.get("/api/tests", headers=aarav).json()[0]["status"] == "done"


def test_bad_submissions_are_refused_cleanly(client, world, aarav):
    assert submit(client, aarav, world, [{"question_id": 999999, "answer": "x"}]).status_code == 422
    q = world["qs"][0]
    assert submit(client, aarav, world, [{"question_id": q, "answer": "a"}, {"question_id": q, "answer": "b"}]).status_code == 422


def test_leaving_everything_blank_scores_zero_without_any_ai_call(client, world, aarav, provider):
    report = submit(client, aarav, world, []).json()
    assert report["marks"] == 0 and provider.calls == []


def test_ai_outage_still_marks_the_test_and_says_written_answers_were_keyword_marked(client, world, aarav, provider):
    provider.replies.append(AIError("busy"))
    report = submit(client, aarav, world, right(world)).json()
    assert report["ai_fallback"] is True
    written = [q for q in report["questions"] if q["type"] in ("short", "long")]
    assert {q["scored_by"] for q in written} == {"keyword"}
    assert report["questions"][0]["marks_awarded"] == 1  # objective marking is unaffected


def test_a_student_cannot_see_someone_elses_report(client, world, aarav, provider):
    provider.replies.append(written_reply(world, 1, 1))
    submit(client, aarav, world, right(world))
    diya = login(client, "diya@demo.school")  # same class, has not taken it
    assert client.get(f"/api/tests/{world['test']}/report", headers=diya).status_code == 404


def test_the_note_link_appears_only_when_the_note_is_shared_with_the_student(client, world, aarav, provider, _engine):
    provider.replies.append(written_reply(world, 0, 0))
    report = submit(client, aarav, world, right(world)).json()
    assert all(t["note_id"] is None for t in report["topics"])  # not shared: no link, no leak of the title
    with Session(_engine) as s:
        s.add(NoteShare(note_id=world["note"], class_id=world["class_a"]))
        s.commit()
    shared = client.get(f"/api/tests/{world['test']}/report", headers=aarav).json()
    assert {t["note_id"] for t in shared["topics"]} == {world["note"]} and shared["topics"][0]["note_title"] == "Magnets (test)"


# ---------------------------------------------------------------- access by role


def test_only_students_take_tests_and_only_teachers_see_results(client, world):
    for who in ("teacher@demo.school", "parent.aarav@demo.school", "admin@demo.school"):
        h = login(client, who)
        assert client.get("/api/tests", headers=h).status_code == 403
        assert client.post(f"/api/tests/{world['test']}/submit", headers=h, json={"answers": []}).status_code == 403
    assert client.get("/api/tests").status_code == 401
    aarav = login(client, "aarav@demo.school")
    assert client.get(f"/api/assessments/{world['test']}/results", headers=aarav).status_code == 403


def test_teacher_sees_class_results_and_topic_averages(client, world, aarav, provider):
    teacher = login(client, "teacher@demo.school")
    before = client.get(f"/api/assessments/{world['test']}/results", headers=teacher).json()
    assert before["submitted_count"] == 0 and before["student_count"] > 1 and before["class_topics"] == []
    provider.replies.append(written_reply(world, 1, 1))
    submit(client, aarav, world, right(world))
    after = client.get(f"/api/assessments/{world['test']}/results", headers=teacher).json()
    me = next(s for s in after["students"] if s["name"].startswith("Aarav"))
    assert after["submitted_count"] == 1 and me["submitted"] and me["percent"] == 100
    assert {t["topic"]: t["percent"] for t in after["class_topics"]}["Poles"] == 100
    assert client.get("/api/assessments/999999/results", headers=teacher).status_code == 404


# ---------------------------------------------------------------- "practice this topic"


QUIZ = json.dumps({"questions": [{"question": "Which poles repel each other?", "options": ["Like", "Unlike", "None", "All"], "correct_index": 0, "explanation": "Like poles repel."}]})


def test_practice_can_focus_on_one_weak_topic(client, world, aarav, provider, _engine):
    with Session(_engine) as s:
        s.add(NoteShare(note_id=world["note"], class_id=world["class_a"]))
        s.commit()
    provider.replies.append(QUIZ)
    resp = client.post(f"/api/notes/{world['note']}/practice", headers=aarav, json={"topic": "Poles and Directions"})
    assert resp.status_code == 200 and len(resp.json()["questions"]) == 1
    sent = provider.calls[0]["messages"][1]["content"]
    assert 'Ask only about this topic: "Poles and Directions"' in sent
    assert "Like poles repel" in sent and "single touch method" not in sent  # only the relevant part of the note was sent


def test_practice_without_a_topic_still_works(client, world, aarav, provider, _engine):
    with Session(_engine) as s:
        s.add(NoteShare(note_id=world["note"], class_id=world["class_a"]))
        s.commit()
    provider.replies.append(QUIZ)
    assert client.post(f"/api/notes/{world['note']}/practice", headers=aarav).status_code == 200
    assert "Ask only about" not in provider.calls[0]["messages"][1]["content"]
