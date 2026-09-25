from datetime import date

import pytest
from sqlalchemy import select

from app.models import Chapter, ScoreRecord, Student, Topic, User
from app.routers.summaries import _records
from app.services.metrics import Record, classify_trend, compute_facts, pct


def rec(topic="Poles", chapter="Magnets", test="T1", day=1, marks=5.0, out=10.0):
    return Record(topic, chapter, test, date(2026, 8, day), marks, out)


def test_percentages_round_half_up_to_whole_numbers():
    assert pct(5, 10) == 50
    assert pct(12.5, 100) == 13  # Python's round() would give 12
    assert pct(2, 3) == 67
    assert pct(0, 10) == 0 and pct(5, 0) == 0


def test_no_marks_means_no_facts():
    assert compute_facts([], 60) is None


def test_overall_is_total_marks_over_total_possible_not_an_average_of_averages():
    facts = compute_facts([rec(marks=10, out=10), rec(topic="Uses", marks=0, out=30)], 60)
    assert facts["overall_percent"] == 25


@pytest.mark.parametrize(
    "percents, trend",
    [
        ([50, 60, 70, 80], "improving"),
        ([80, 75, 60, 55], "declining"),
        ([70, 72, 71, 69], "steady"),
        ([60, 66], "improving"),
        ([70], "not_enough_data"),
        ([], "not_enough_data"),
    ],
)
def test_trend_compares_early_with_recent_tests(percents, trend):
    assert classify_trend(percents)[0] == trend


def test_small_changes_are_steady():
    assert classify_trend([70, 74])[0] == "steady"  # 4 points is under the 5-point bar
    assert classify_trend([70, 75])[0] == "improving"


def test_weak_topics_use_the_threshold_and_sort_weakest_first():
    records = [rec(topic="A", marks=3), rec(topic="B", marks=6), rec(topic="C", marks=9)]
    assert [w["topic"] for w in compute_facts(records, 60)["weak_topics"]] == ["A"]
    assert [w["topic"] for w in compute_facts(records, 70)["weak_topics"]] == ["A", "B"]
    assert compute_facts(records, 30)["weak_topics"] == []  # 30% is not below 30%


def test_strongest_topics_are_best_first_and_never_include_weak_ones():
    records = [rec(topic=t, marks=m) for t, m in [("A", 3), ("B", 6), ("C", 9), ("D", 8), ("E", 7)]]
    facts = compute_facts(records, 60)
    assert [s["topic"] for s in facts["strongest"]] == ["C", "D", "E"]


def test_tests_and_chapters_are_in_date_order_and_topics_merge_across_tests():
    records = [
        rec(topic="X", chapter="Later", test="T2", day=10, marks=8),
        rec(topic="Y", chapter="Earlier", test="T1", day=1, marks=4),
        rec(topic="Y", chapter="Earlier", test="T3", day=20, marks=6),
    ]
    facts = compute_facts(records, 60)
    assert [t["name"] for t in facts["tests"]] == ["T1", "T2", "T3"]
    assert [c["chapter"] for c in facts["chapters"]] == ["Earlier", "Later"]
    assert next(t for t in facts["topics"] if t["topic"] == "Y")["percent"] == 50


# ---- against the seeded demo school: the personas were built to behave like this


def facts_for(db, first):
    user = db.scalar(select(User).where(User.email == f"{first.lower()}@demo.school"))
    student = db.scalar(select(Student).where(Student.user_id == user.id))
    return compute_facts(_records(db, student.id), 60)


def test_seed_personas_produce_the_expected_shapes(db):
    assert facts_for(db, "Aarav")["weak_topics"] == [] and facts_for(db, "Aarav")["overall_percent"] >= 80
    assert len(facts_for(db, "Rohan")["weak_topics"]) >= 10
    assert facts_for(db, "Saanvi")["trend"] == "improving"
    assert facts_for(db, "Kavya")["trend"] == "declining"
    tara = facts_for(db, "Tara")
    assert {w["chapter"] for w in tara["weak_topics"]} == {"Exploring Magnets"}


def test_facts_match_the_raw_score_records(db):
    """The exit check for this block: recompute one student's figures by hand from the rows."""
    user = db.scalar(select(User).where(User.email == "diya@demo.school"))
    student = db.scalar(select(Student).where(Student.user_id == user.id))
    rows = db.scalars(select(ScoreRecord).where(ScoreRecord.student_id == student.id)).all()
    facts = compute_facts(_records(db, student.id), 60)
    assert facts["overall_percent"] == pct(sum(r.marks for r in rows), sum(r.max_marks for r in rows))
    for t in facts["topics"]:
        topic = db.scalar(select(Topic).where(Topic.name == t["topic"]))
        mine = [r for r in rows if r.topic_id == topic.id]
        assert t["percent"] == pct(sum(r.marks for r in mine), sum(r.max_marks for r in mine))
    assert len(facts["chapters"]) == len({db.get(Topic, r.topic_id).chapter_id for r in rows})
    assert db.get(Chapter, 1) is not None
