"""Builds the synthetic demo school. Deterministic: same data on every run."""

import random
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import (
    Base,
    Chapter,
    ScoreRecord,
    SchoolClass,
    Setting,
    Student,
    Topic,
    User,
)
from app.security import hash_password
from app.seed import data


def student_email(first: str) -> str:
    return f"{first.lower()}@demo.school"


def parent_email(first: str) -> str:
    return f"parent.{first.lower()}@demo.school"


def _percent(persona: str, test_index: int, test_count: int, chapter_no: int, gap_chapter: int | None, rng: random.Random) -> float:
    """Target percentage for one topic, shaped by the student's persona."""
    progress = test_index / max(test_count - 1, 1)
    if persona == "strong":
        base, spread = 89, 6
    elif persona == "average":
        base, spread = 68, 8
    elif persona == "weak":
        base, spread = 42, 9
    elif persona == "improving":
        base, spread = 48 + 34 * progress, 5
    elif persona == "declining":
        base, spread = 84 - 30 * progress, 5
    elif persona == "gap":
        base, spread = (36 if chapter_no == gap_chapter else 82), 6
    else:
        raise ValueError(f"Unknown persona: {persona}")
    return max(0.0, min(100.0, base + rng.uniform(-spread, spread)))


def _half_marks(percent: float) -> float:
    """Marks out of MARKS_PER_TOPIC, rounded to the nearest half mark."""
    return round(percent / 100 * data.MARKS_PER_TOPIC * 2) / 2


def seed_database(db: Session) -> dict[str, int]:
    """Populate an empty database with the demo school. Returns row counts."""
    rng = random.Random(42)
    password_hash = hash_password(data.DEMO_PASSWORD)  # hashed once; all demo accounts share it

    for key, value in data.DEFAULT_SETTINGS.items():
        db.add(Setting(key=key, value=value))

    db.add(User(name=data.TEACHER[0], email=data.TEACHER[1], role="teacher", password_hash=password_hash))
    db.add(User(name=data.ADMIN[0], email=data.ADMIN[1], role="admin", password_hash=password_hash))

    chapters: dict[int, Chapter] = {}
    for number, title, topic_names in data.CHAPTERS:
        chapter = Chapter(subject=data.SUBJECT, grade=data.GRADE, number=number, title=title)
        chapter.topics = [Topic(name=name) for name in topic_names]
        db.add(chapter)
        chapters[number] = chapter

    classes = [SchoolClass(name=n, grade=g, section=s) for n, g, s in data.CLASSES]
    db.add_all(classes)
    db.flush()

    students: list[tuple[Student, str, int | None]] = []
    for i, (first, last, persona, gap_chapter) in enumerate(data.STUDENTS):
        student_user = User(name=f"{first} {last}", email=student_email(first), role="student", password_hash=password_hash)
        parent_user = User(name=f"Parent of {first}", email=parent_email(first), role="parent", password_hash=password_hash)
        db.add_all([student_user, parent_user])
        db.flush()
        student = Student(
            user_id=student_user.id,
            class_id=classes[i % len(classes)].id,
            parent_user_id=parent_user.id,
            persona=persona,
        )
        db.add(student)
        students.append((student, persona, gap_chapter))
    db.flush()

    score_count = 0
    for student, persona, gap_chapter in students:
        for test_index, (test_name, test_date, chapter_no) in enumerate(data.TESTS):
            for topic in chapters[chapter_no].topics:
                percent = _percent(persona, test_index, len(data.TESTS), chapter_no, gap_chapter, rng)
                db.add(
                    ScoreRecord(
                        student_id=student.id,
                        topic_id=topic.id,
                        test_name=f"{test_name}: {chapters[chapter_no].title}",
                        test_date=date.fromisoformat(test_date),
                        marks=_half_marks(percent),
                        max_marks=data.MARKS_PER_TOPIC,
                    )
                )
                score_count += 1
    db.commit()
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "students": len(students),
        "chapters": len(chapters),
        "score_records": score_count,
    }


def reset_database(db: Session) -> dict[str, int]:
    """Drop every table, recreate it, and reseed. Used by the admin "Reset demo data" button."""
    db.close()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as fresh:
        return seed_database(fresh)


def ensure_seeded() -> None:
    """Create tables, and seed the demo school if the database is empty."""
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if db.scalar(select(func.count(User.id))) == 0:
            seed_database(db)
