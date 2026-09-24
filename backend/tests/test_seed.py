from collections import defaultdict
from statistics import mean

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, Chapter, ScoreRecord, SchoolClass, Setting, Student, Topic, User
from app.seed import data
from app.seed.seed import seed_database


def _percent_by_student(db) -> dict[str, list[float]]:
    rows = db.execute(
        select(Student.persona, ScoreRecord.student_id, ScoreRecord.marks, ScoreRecord.max_marks, ScoreRecord.test_date)
        .join(ScoreRecord, ScoreRecord.student_id == Student.id)
        .order_by(ScoreRecord.test_date)
    ).all()
    out: dict[str, list[float]] = defaultdict(list)
    for persona, _, marks, max_marks, _ in rows:
        out[persona].append(marks / max_marks * 100)
    return out


def test_counts(db):
    assert db.scalar(select(func.count(Student.id))) == 15
    assert db.scalar(select(func.count(SchoolClass.id))) == 2
    assert db.scalar(select(func.count(Chapter.id))) == 12
    assert db.scalar(select(func.count(Topic.id))) == 36
    assert db.scalar(select(func.count(ScoreRecord.id))) == 15 * len(data.TESTS) * 3
    # teacher + admin + 15 students + 15 parents
    assert db.scalar(select(func.count(User.id))) == 32
    assert db.get(Setting, "weak_topic_threshold").value == "60"


def test_one_parent_per_student_and_classes_are_split(db):
    students = db.scalars(select(Student)).all()
    assert len({s.parent_user_id for s in students}) == 15
    sizes = sorted(db.execute(select(func.count(Student.id)).group_by(Student.class_id)).scalars())
    assert sizes == [7, 8]


def test_marks_are_valid_half_marks(db):
    for marks, max_marks in db.execute(select(ScoreRecord.marks, ScoreRecord.max_marks)):
        assert 0 <= marks <= max_marks
        assert (marks * 2) == int(marks * 2)


def test_personas_are_distinct_enough_to_demo(db):
    avg = {p: mean(v) for p, v in _percent_by_student(db).items()}
    assert avg["strong"] > 80
    assert 55 < avg["average"] < 80
    assert avg["weak"] < 55
    assert avg["strong"] > avg["average"] > avg["weak"]


def test_improving_and_declining_personas_have_a_trend(db):
    def first_and_last_test_average(persona):
        rows = db.execute(
            select(ScoreRecord.test_date, ScoreRecord.marks)
            .join(Student, Student.id == ScoreRecord.student_id)
            .where(Student.persona == persona)
        ).all()
        by_date = defaultdict(list)
        for d, m in rows:
            by_date[d].append(m * 10)
        dates = sorted(by_date)
        return mean(by_date[dates[0]]), mean(by_date[dates[-1]])

    first, last = first_and_last_test_average("improving")
    assert last > first + 15
    first, last = first_and_last_test_average("declining")
    assert first > last + 15


def test_gap_students_are_weak_only_in_their_chapter(db):
    tara = db.scalar(select(Student).join(User, User.id == Student.user_id).where(User.name == "Tara Bose"))
    rows = db.execute(
        select(Chapter.number, ScoreRecord.marks)
        .join(Topic, Topic.id == ScoreRecord.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .where(ScoreRecord.student_id == tara.id)
    ).all()
    magnets = [m * 10 for n, m in rows if n == 4]
    others = [m * 10 for n, m in rows if n != 4]
    assert mean(magnets) < 50 < mean(others)


def test_seed_is_deterministic():
    def build():
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            seed_database(session)
            return [r for r in session.execute(select(ScoreRecord.student_id, ScoreRecord.topic_id, ScoreRecord.marks).order_by(ScoreRecord.id))]

    assert build() == build()
