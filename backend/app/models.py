"""Database models.

Kept deliberately small. Later blocks add tables (notes, questions, assessments,
summaries, interviews). There are no migrations in the POC: tables are created on
startup and "Reset demo data" drops and reseeds everything.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    teacher = "teacher"
    student = "student"
    parent = "parent"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), index=True)  # a Role value
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SchoolClass(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. "6-A"
    grade: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(5))

    students: Mapped[list[Student]] = relationship(back_populates="school_class")


class Student(Base):
    """A student profile. One parent per student in the POC."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    parent_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    # Demo persona used by the seed script: strong, average, weak, improving, declining, gap
    persona: Mapped[str] = mapped_column(String(20), default="average")

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    parent: Mapped[User | None] = relationship(foreign_keys=[parent_user_id])
    school_class: Mapped[SchoolClass] = relationship(back_populates="students")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(60))
    grade: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))

    topics: Mapped[list[Topic]] = relationship(back_populates="chapter", order_by="Topic.id")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))

    chapter: Mapped[Chapter] = relationship(back_populates="topics")


class ScoreRecord(Base):
    """Seeded school test history. Used only by the Parent Summary module."""

    __tablename__ = "score_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    test_name: Mapped[str] = mapped_column(String(200))
    test_date: Mapped[date] = mapped_column(Date)
    marks: Mapped[float] = mapped_column(Float)
    max_marks: Mapped[float] = mapped_column(Float)


class Note(Base):
    """Any text source: handwritten (OCR), typed, or an uploaded document.

    OCR notes start as status="draft" (so the review screen can show the original
    pages beside the text) and become "saved" once the user confirms them.
    """

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(60), default="Science")
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"))
    topic: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(10))  # ocr | typed | upload
    status: Mapped[str] = mapped_column(String(10), default="saved")  # draft | saved
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship()
    chapter: Mapped[Chapter | None] = relationship()
    pages: Mapped[list[NotePage]] = relationship(
        back_populates="note", order_by="NotePage.page_number", cascade="all, delete-orphan"
    )
    shares: Mapped[list[NoteShare]] = relationship(back_populates="note", cascade="all, delete-orphan")


class NotePage(Base):
    """One original page image of a handwritten note."""

    __tablename__ = "note_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str] = mapped_column(String(300))  # relative to the storage root

    note: Mapped[Note] = relationship(back_populates="pages")


class NoteShare(Base):
    """A teacher's note shared read-only with every student in a class."""

    __tablename__ = "note_shares"
    __table_args__ = (UniqueConstraint("note_id", "class_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)

    note: Mapped[Note] = relationship(back_populates="shares")
    school_class: Mapped[SchoolClass] = relationship()


class QuestionSet(Base):
    """One generated batch of questions for a note. A teacher gets up to 3 versions per note."""

    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)  # 1 balanced, 2 application, 3 recall
    emphasis: Mapped[str] = mapped_column(String(20))
    requested_count: Mapped[int] = mapped_column(Integer)
    types: Mapped[list] = mapped_column(JSON)
    difficulty: Mapped[str] = mapped_column(String(10))
    shortfall_message: Mapped[str | None] = mapped_column(Text)
    generation_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    note: Mapped[Note] = relationship()
    questions: Mapped[list[Question]] = relationship(
        back_populates="question_set", order_by="Question.position", cascade="all, delete-orphan"
    )


class Question(Base):
    """Every AI question starts as a draft. Only accepted ones enter the Question Bank."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("question_sets.id"), index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(15))  # mcq | short | long | fill_blank | true_false
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON)  # mcq and true/false only
    answer: Mapped[str] = mapped_column(Text)  # for mcq: the text of the correct option
    explanation: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(10))
    bloom: Mapped[str] = mapped_column(String(15))
    topic: Mapped[str] = mapped_column(String(200))
    marks: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)  # draft | accepted | discarded
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question_set: Mapped[QuestionSet] = relationship(back_populates="questions")
    note: Mapped[Note] = relationship()


class Assessment(Base):
    """A test a teacher builds from accepted questions and assigns to a class."""

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    school_class: Mapped[SchoolClass] = relationship()
    items: Mapped[list[AssessmentQuestion]] = relationship(
        back_populates="assessment", order_by="AssessmentQuestion.position", cascade="all, delete-orphan"
    )


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    position: Mapped[int] = mapped_column(Integer)
    marks: Mapped[float] = mapped_column(Float, default=1.0)

    assessment: Mapped[Assessment] = relationship(back_populates="items")
    question: Mapped[Question] = relationship()


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))


class ParentSummary(Base):
    """One progress summary per student. Parents only ever see it once a teacher has approved it.

    `facts` is a snapshot of the computed numbers at generation time, so the charts and the words a parent
    sees always agree, even if marks change later. Any change to the text puts the summary back to "draft".
    """

    __tablename__ = "parent_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved
    facts: Mapped[dict] = mapped_column(JSON)
    narrative: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20), default="ai")  # ai | template
    verify_failures: Mapped[int] = mapped_column(Integer, default=0)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[Student] = relationship()
