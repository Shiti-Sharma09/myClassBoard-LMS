"""Question Bank: generate question sets from a note, review them, keep the accepted ones,
export a paper, and assign a test. Teachers only. Everything is scoped to the signed-in teacher."""

import logging
import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import AIService, get_ai_service
from app.db import get_db
from app.deps import require_role
from app.models import Assessment, AssessmentQuestion, Note, Question, QuestionSet, SchoolClass, User
from app.services.chunking import split_sections
from app.services.export_docx import slug
from app.services.notes_access import get_note_or_404
from app.services.paper import PaperItem, PaperSection, build_paper_docx
from app.services.question_edit import EditError, apply_edit
from app.services.question_gen import MAX_VERSIONS, QUESTION_TYPES, VERSION_NAMES, generate, is_recap

log = logging.getLogger("questions")
teacher_only = require_role("teacher")
router = APIRouter(prefix="/api", tags=["questions"], dependencies=[Depends(teacher_only)])


# ------------------------------------------------------------------ schemas


class TopicOut(BaseModel):
    index: int
    title: str
    words: int
    recap: bool  # recap / key-terms sections restate the main text; the UI leaves them unticked


class GenerateIn(BaseModel):
    count: int = Field(ge=1, le=20)
    types: list[str] = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    section_indices: list[int] | None = None

    @field_validator("types")
    @classmethod
    def known_types(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))
        if any(t not in QUESTION_TYPES for t in unique):
            raise ValueError("Unknown question type")
        return unique


class QuestionOut(BaseModel):
    id: int
    set_id: int
    note_id: int
    position: int
    type: str
    text: str
    options: list[str] | None
    answer: str
    explanation: str
    difficulty: str
    bloom: str
    topic: str
    marks: float
    status: str
    edited: bool


class QuestionSetOut(BaseModel):
    id: int
    note_id: int
    version: int
    emphasis: str
    requested_count: int
    types: list[str]
    difficulty: str
    shortfall_message: str | None
    generation_seconds: float | None
    created_at: datetime
    questions: list[QuestionOut]


class QuestionUpdate(BaseModel):
    text: str | None = None
    options: list[str] | None = None
    answer: str | None = None
    explanation: str | None = None
    difficulty: str | None = None
    bloom: str | None = None
    topic: str | None = None
    marks: float | None = None
    status: str | None = None


class BulkIn(BaseModel):
    status: Literal["accepted", "discarded"]


class BankItem(QuestionOut):
    note_title: str
    chapter_id: int | None
    chapter_title: str | None


class TopicCount(BaseModel):
    topic: str
    count: int


class ChapterNode(BaseModel):
    chapter_id: int | None
    chapter_title: str
    count: int
    topics: list[TopicCount]


class SubjectNode(BaseModel):
    subject: str
    count: int
    chapters: list[ChapterNode]


class BankStats(BaseModel):
    accepted: int
    discarded: int
    pending: int
    edited: int
    usable_rate: float | None  # accepted / (accepted + discarded); None until a teacher has reviewed something


class PaperQuestionIn(BaseModel):
    id: int
    marks: float = Field(ge=0, le=100)


class PaperSectionIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    questions: list[PaperQuestionIn]


class PaperIn(BaseModel):
    school: str = Field(default="", max_length=120)
    title: str = Field(min_length=1, max_length=160)
    class_name: str = Field(default="", max_length=40)
    subject: str = Field(default="Science", max_length=60)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    instructions: str = Field(default="", max_length=1000)
    sections: list[PaperSectionIn] = Field(min_length=1)
    include_answer_key: bool = True


class AssessmentItemIn(BaseModel):
    question_id: int
    marks: float = Field(default=1, ge=0, le=100)


class AssessmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    class_id: int
    items: list[AssessmentItemIn] = Field(min_length=1)


class AssessmentOut(BaseModel):
    id: int
    title: str
    class_id: int
    class_name: str
    question_count: int
    total_marks: float
    created_at: datetime


# ------------------------------------------------------------------ helpers


def _q_out(q: Question) -> QuestionOut:
    return QuestionOut.model_validate(q, from_attributes=True)


def _set_out(qs: QuestionSet) -> QuestionSetOut:
    data = {c: getattr(qs, c) for c in QuestionSetOut.model_fields if c != "questions"}
    return QuestionSetOut(**data, questions=[_q_out(q) for q in qs.questions])


def _own_note(db: Session, user: User, note_id: int) -> Note:
    note = get_note_or_404(db, user, note_id, write=True)  # teachers only ever see their own notes anyway
    if note.status != "saved":
        raise HTTPException(422, "Save the note first, then generate questions from it.")
    return note


def _own_question(db: Session, user: User, question_id: int) -> Question:
    q = db.get(Question, question_id)
    if q is None or q.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That question wasn't found.")
    return q


def _own_set(db: Session, user: User, set_id: int) -> QuestionSet:
    qs = db.get(QuestionSet, set_id)
    if qs is None or qs.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That question set wasn't found.")
    return qs


# ------------------------------------------------------------------ generate and review


@router.get("/notes/{note_id}/topics", response_model=list[TopicOut])
def note_topics(note_id: int, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> list[TopicOut]:
    """The note's sections, found in code (no AI call). The teacher can tick which to cover."""
    note = _own_note(db, user, note_id)
    return [TopicOut(index=s.index, title=s.title, words=s.words, recap=is_recap(s.title)) for s in split_sections(note.text, note.title)]


@router.get("/notes/{note_id}/question-sets", response_model=list[QuestionSetOut])
def list_sets(note_id: int, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> list[QuestionSetOut]:
    _own_note(db, user, note_id)
    sets = db.scalars(
        select(QuestionSet).where(QuestionSet.note_id == note_id, QuestionSet.owner_id == user.id).order_by(QuestionSet.version)
    ).all()
    return [_set_out(s) for s in sets]


@router.post("/notes/{note_id}/question-sets", response_model=QuestionSetOut, status_code=status.HTTP_201_CREATED)
def generate_set(
    note_id: int,
    body: GenerateIn,
    user: User = Depends(teacher_only),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> QuestionSetOut:
    """Make the next version (1 balanced, 2 application, 3 recall) of questions for a note."""
    note = _own_note(db, user, note_id)
    existing = db.scalars(select(QuestionSet).where(QuestionSet.note_id == note_id, QuestionSet.owner_id == user.id)).all()
    free = [v for v in range(1, MAX_VERSIONS + 1) if v not in {s.version for s in existing}]
    if not free:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You've already made {MAX_VERSIONS} versions of this note. Discard one to make another.",
        )
    version = free[0]

    sections = split_sections(note.text, note.title)
    if body.section_indices is not None and not {s.index for s in sections} >= set(body.section_indices):
        raise HTTPException(422, "One of the chosen topics doesn't exist in this note.")
    prior = [(q.text, q.answer) for s in existing for q in s.questions]

    started = time.perf_counter()
    result = generate(
        ai,
        note_title=note.title,
        note_text=note.text,
        subject=note.subject,
        grade=6,
        chapter_title=note.chapter.title if note.chapter else None,
        count=body.count,
        types=body.types,
        difficulty=body.difficulty,
        version=version,
        prior=prior,
        section_indices=body.section_indices or None,
    )
    seconds = round(time.perf_counter() - started, 1)
    if not result.questions:
        raise HTTPException(422, result.shortfall or "No questions could be made from this note.")

    qs = QuestionSet(
        note_id=note.id,
        owner_id=user.id,
        version=version,
        emphasis=VERSION_NAMES[version],
        requested_count=body.count,
        types=body.types,
        difficulty=body.difficulty,
        shortfall_message=result.shortfall,
        generation_seconds=seconds,
    )
    for position, q in enumerate(result.questions):
        qs.questions.append(
            Question(
                note_id=note.id,
                owner_id=user.id,
                position=position,
                type=q.type,
                text=q.text,
                options=q.options,
                answer=q.answer,
                explanation=q.explanation,
                difficulty=q.difficulty,
                bloom=q.bloom,
                topic=q.topic,
                marks=q.marks,
            )
        )
    db.add(qs)
    db.commit()
    log.info("question_set note=%s version=%s got=%s/%s in %.1fs (%s AI calls)", note.id, version, len(result.questions), body.count, seconds, result.ai_calls)
    return _set_out(qs)


@router.delete("/question-sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_set(set_id: int, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> Response:
    """Throw a version away (frees its slot). Refused while it still has questions in the Question Bank."""
    qs = _own_set(db, user, set_id)
    if any(q.status == "accepted" for q in qs.questions):
        raise HTTPException(status.HTTP_409_CONFLICT, "This version has accepted questions in your Question Bank. Discard those first.")
    db.delete(qs)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/question-sets/{set_id}/bulk", response_model=QuestionSetOut)
def bulk_review(set_id: int, body: BulkIn, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> QuestionSetOut:
    """Accept or discard every question in the set that has not been reviewed yet."""
    qs = _own_set(db, user, set_id)
    for q in qs.questions:
        if q.status == "draft":
            q.status = body.status
    db.commit()
    return _set_out(qs)


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, body: QuestionUpdate, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> QuestionOut:
    q = _own_question(db, user, question_id)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    try:
        apply_edit(q, changes)
    except EditError as exc:
        raise HTTPException(422, str(exc)) from None
    db.commit()
    return _q_out(q)


# ------------------------------------------------------------------ the bank


def _bank_query(user: User, type: str | None, difficulty: str | None, bloom: str | None):
    query = select(Question).where(Question.owner_id == user.id, Question.status == "accepted")
    if type:
        query = query.where(Question.type == type)
    if difficulty:
        query = query.where(Question.difficulty == difficulty)
    if bloom:
        query = query.where(Question.bloom == bloom)
    return query


@router.get("/question-bank", response_model=list[BankItem])
def bank(
    type: str | None = None,
    difficulty: str | None = None,
    bloom: str | None = None,
    chapter_id: int | None = None,
    no_chapter: bool = False,
    topic: str | None = None,
    user: User = Depends(teacher_only),
    db: Session = Depends(get_db),
) -> list[BankItem]:
    query = _bank_query(user, type, difficulty, bloom)
    if topic:
        query = query.where(Question.topic == topic)
    questions = db.scalars(query.order_by(Question.topic, Question.id)).all()
    items = []
    for q in questions:
        cid = q.note.chapter_id
        if chapter_id is not None and cid != chapter_id:
            continue
        if no_chapter and cid is not None:
            continue
        items.append(
            BankItem(
                **_q_out(q).model_dump(),
                note_title=q.note.title,
                chapter_id=cid,
                chapter_title=q.note.chapter.title if q.note.chapter else None,
            )
        )
    return items


@router.get("/question-bank/tree", response_model=list[SubjectNode])
def bank_tree(
    type: str | None = None,
    difficulty: str | None = None,
    bloom: str | None = None,
    user: User = Depends(teacher_only),
    db: Session = Depends(get_db),
) -> list[SubjectNode]:
    """Subject -> Chapter -> Topic with counts of accepted questions (respecting the filters)."""
    tree: dict[str, dict[int | None, tuple[str, dict[str, int]]]] = {}
    for q in db.scalars(_bank_query(user, type, difficulty, bloom)).all():
        chapters = tree.setdefault(q.note.subject, {})
        cid = q.note.chapter_id
        title, topics = chapters.setdefault(cid, (q.note.chapter.title if q.note.chapter else "No chapter", {}))
        topics[q.topic] = topics.get(q.topic, 0) + 1
    out = []
    for subject, chapters in sorted(tree.items()):
        nodes = [
            ChapterNode(
                chapter_id=cid,
                chapter_title=title,
                count=sum(topics.values()),
                topics=[TopicCount(topic=t, count=c) for t, c in sorted(topics.items())],
            )
            for cid, (title, topics) in sorted(chapters.items(), key=lambda kv: (kv[0] is None, kv[1][0]))
        ]
        out.append(SubjectNode(subject=subject, count=sum(n.count for n in nodes), chapters=nodes))
    return out


@router.get("/question-bank/stats", response_model=BankStats)
def bank_stats(user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> BankStats:
    """Review results across all of this teacher's questions. `usable_rate` is the "usable questions" metric."""
    questions = db.scalars(select(Question).where(Question.owner_id == user.id)).all()
    accepted = sum(q.status == "accepted" for q in questions)
    discarded = sum(q.status == "discarded" for q in questions)
    reviewed = accepted + discarded
    return BankStats(
        accepted=accepted,
        discarded=discarded,
        pending=sum(q.status == "draft" for q in questions),
        edited=sum(q.edited for q in questions),
        usable_rate=round(accepted / reviewed, 3) if reviewed else None,
    )


# ------------------------------------------------------------------ paper and assessments


def _accepted(db: Session, user: User, ids: list[int]) -> dict[int, Question]:
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "A question was added twice.")
    found = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(ids), Question.owner_id == user.id)).all()}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One of those questions wasn't found.")
    if any(q.status != "accepted" for q in found.values()):
        raise HTTPException(422, "Only accepted questions can go on a paper or a test.")
    return found


@router.post("/papers/docx")
def export_paper(body: PaperIn, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> Response:
    ids = [item.id for s in body.sections for item in s.questions]
    if not ids:
        raise HTTPException(422, "Add at least one question to the paper.")
    questions = _accepted(db, user, ids)
    sections = [
        PaperSection(s.title.strip(), [PaperItem(questions[i.id], i.marks) for i in s.questions]) for s in body.sections
    ]
    data = build_paper_docx(
        school=body.school,
        title=body.title,
        class_name=body.class_name,
        subject=body.subject,
        duration_minutes=body.duration_minutes,
        instructions=body.instructions,
        sections=sections,
        include_answer_key=body.include_answer_key,
    )
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{slug(body.title, "question_paper")}.docx"'},
    )


def _assessment_out(a: Assessment) -> AssessmentOut:
    return AssessmentOut(
        id=a.id,
        title=a.title,
        class_id=a.class_id,
        class_name=a.school_class.name,
        question_count=len(a.items),
        total_marks=sum(i.marks for i in a.items),
        created_at=a.created_at,
    )


@router.post("/assessments", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
def create_assessment(body: AssessmentIn, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> AssessmentOut:
    """Turn accepted questions into a test for a class. (Students take it in the Assessment module.)"""
    if db.get(SchoolClass, body.class_id) is None:
        raise HTTPException(422, "That class doesn't exist.")
    questions = _accepted(db, user, [i.question_id for i in body.items])
    assessment = Assessment(title=body.title.strip(), class_id=body.class_id, owner_id=user.id)
    for position, item in enumerate(body.items):
        assessment.items.append(AssessmentQuestion(question_id=questions[item.question_id].id, position=position, marks=item.marks))
    db.add(assessment)
    db.commit()
    return _assessment_out(assessment)


@router.get("/assessments", response_model=list[AssessmentOut])
def list_assessments(user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> list[AssessmentOut]:
    rows = db.scalars(select(Assessment).where(Assessment.owner_id == user.id).order_by(Assessment.created_at.desc(), Assessment.id.desc())).all()
    return [_assessment_out(a) for a in rows]
