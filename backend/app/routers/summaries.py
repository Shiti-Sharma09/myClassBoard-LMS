"""Parent Summary: teachers generate, edit and approve; a parent sees only their own child's approved summary."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import AIService, get_ai_service
from app.db import get_db
from app.deps import require_role
from app.models import Chapter, ParentSummary, ScoreRecord, Student, Topic, User, utcnow
from app.services.metrics import Record, compute_facts
from app.services.settings import weak_threshold
from app.services.summary import Narrative, narrate, problems

router = APIRouter(prefix="/api", tags=["summaries"])

teacher_only = require_role("teacher")
parent_only = require_role("parent")


# ------------------------------------------------------------------ schemas


class SummaryRow(BaseModel):
    student_id: int
    name: str
    class_name: str
    status: str  # none | draft | approved
    source: str | None
    edited: bool
    overall_percent: int | None
    trend: str | None
    weak_topic_count: int | None


class SummaryDetail(BaseModel):
    student_id: int
    name: str
    class_name: str
    status: str
    source: str | None
    edited: bool
    verify_failures: int
    narrative: Narrative | None
    facts: dict | None
    generated_at: datetime | None
    approved_at: datetime | None


class ApproveAllIn(BaseModel):
    class_id: int


class ApproveAllOut(BaseModel):
    approved: int


class ChildSummary(BaseModel):
    available: bool
    child_name: str
    narrative: Narrative | None = None
    facts: dict | None = None
    approved_at: datetime | None = None


# ------------------------------------------------------------------ helpers


def _records(db: Session, student_id: int) -> list[Record]:
    rows = db.execute(
        select(ScoreRecord, Topic.name, Chapter.title)
        .join(Topic, Topic.id == ScoreRecord.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .where(ScoreRecord.student_id == student_id)
    ).all()
    return [Record(topic, chapter, r.test_name, r.test_date, r.marks, r.max_marks) for r, topic, chapter in rows]


def _student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That student wasn't found.")
    return student


def _summary(db: Session, student_id: int) -> ParentSummary | None:
    return db.scalar(select(ParentSummary).where(ParentSummary.student_id == student_id))


def _detail(student: Student, summary: ParentSummary | None, live_facts: dict | None = None) -> SummaryDetail:
    common = dict(student_id=student.id, name=student.user.name, class_name=student.school_class.name)
    if summary is None:
        return SummaryDetail(**common, status="none", source=None, edited=False, verify_failures=0, narrative=None, facts=live_facts, generated_at=None, approved_at=None)
    return SummaryDetail(
        **common,
        status=summary.status,
        source=summary.source,
        edited=summary.edited,
        verify_failures=summary.verify_failures,
        narrative=Narrative.model_validate(summary.narrative),
        facts=summary.facts,
        generated_at=summary.generated_at,
        approved_at=summary.approved_at,
    )


# ------------------------------------------------------------------ teacher


@router.get("/summaries", response_model=list[SummaryRow])
def list_summaries(class_id: int | None = None, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> list[SummaryRow]:
    threshold = weak_threshold(db)
    query = select(Student).order_by(Student.class_id, Student.id)
    if class_id is not None:
        query = query.where(Student.class_id == class_id)
    summaries = {s.student_id: s for s in db.scalars(select(ParentSummary)).all()}
    rows = []
    for student in db.scalars(query).all():
        facts = compute_facts(_records(db, student.id), threshold)
        summary = summaries.get(student.id)
        rows.append(
            SummaryRow(
                student_id=student.id,
                name=student.user.name,
                class_name=student.school_class.name,
                status=summary.status if summary else "none",
                source=summary.source if summary else None,
                edited=summary.edited if summary else False,
                overall_percent=facts["overall_percent"] if facts else None,
                trend=facts["trend"] if facts else None,
                weak_topic_count=len(facts["weak_topics"]) if facts else None,
            )
        )
    return rows


@router.get("/summaries/{student_id}", response_model=SummaryDetail)
def get_summary(student_id: int, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> SummaryDetail:
    student = _student(db, student_id)
    return _detail(student, _summary(db, student_id), compute_facts(_records(db, student_id), weak_threshold(db)))


@router.post("/summaries/{student_id}/generate", response_model=SummaryDetail)
def generate_summary(
    student_id: int,
    user: User = Depends(teacher_only),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> SummaryDetail:
    """Make (or remake) the draft for one student. Always leaves it as a draft for the teacher to approve."""
    student = _student(db, student_id)
    facts = compute_facts(_records(db, student_id), weak_threshold(db))
    if facts is None:
        raise HTTPException(422, f"{student.user.name} has no marks yet, so there is nothing to summarise.")
    result = narrate(ai, facts, student.user.name)
    summary = _summary(db, student_id) or ParentSummary(student_id=student_id)
    summary.facts = facts
    summary.narrative = result.narrative.model_dump()
    summary.source = result.source
    summary.verify_failures = result.verify_failures
    summary.edited = False
    summary.status = "draft"
    summary.generated_at = utcnow()
    summary.approved_at = None
    db.add(summary)
    db.commit()
    return _detail(student, summary)


@router.put("/summaries/{student_id}", response_model=SummaryDetail)
def edit_summary(student_id: int, body: Narrative, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> SummaryDetail:
    """Teacher edits. The same checks as for the AI apply, so a typo can't put a wrong figure in front of a parent."""
    student = _student(db, student_id)
    summary = _summary(db, student_id)
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generate a draft first, then edit it.")
    issues = problems(body, summary.facts)
    if issues:
        raise HTTPException(422, " ".join(issues))
    summary.narrative = body.model_dump()
    summary.edited = True
    summary.status = "draft"  # a changed text has to be approved again
    summary.approved_at = None
    db.commit()
    return _detail(student, summary)


@router.post("/summaries/{student_id}/approve", response_model=SummaryDetail)
def approve_summary(student_id: int, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> SummaryDetail:
    student = _student(db, student_id)
    summary = _summary(db, student_id)
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generate a draft first, then approve it.")
    summary.status = "approved"
    summary.approved_at = utcnow()
    db.commit()
    return _detail(student, summary)


@router.post("/summaries/approve-all", response_model=ApproveAllOut)
def approve_all(body: ApproveAllIn, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> ApproveAllOut:
    """Approve every draft in one class. Students with no draft yet are left alone."""
    drafts = db.scalars(
        select(ParentSummary).join(Student, Student.id == ParentSummary.student_id).where(Student.class_id == body.class_id, ParentSummary.status == "draft")
    ).all()
    for summary in drafts:
        summary.status = "approved"
        summary.approved_at = utcnow()
    db.commit()
    return ApproveAllOut(approved=len(drafts))


# ------------------------------------------------------------------ parent


@router.get("/my-child/summary", response_model=ChildSummary)
def my_child_summary(user: User = Depends(parent_only), db: Session = Depends(get_db)) -> ChildSummary:
    """The only summary a parent can reach: their own child's, and only once approved."""
    student = db.scalar(select(Student).where(Student.parent_user_id == user.id))
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No child is linked to this account.")
    summary = _summary(db, student.id)
    if summary is None or summary.status != "approved":
        return ChildSummary(available=False, child_name=student.user.name)
    return ChildSummary(
        available=True,
        child_name=student.user.name,
        narrative=Narrative.model_validate(summary.narrative),
        facts=summary.facts,
        approved_at=summary.approved_at,
    )
