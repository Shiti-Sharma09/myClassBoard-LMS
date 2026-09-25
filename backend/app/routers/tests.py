"""Students take the tests teachers assign to their class; a teacher sees how the class did.

A test is taken once. Answers are marked when submitted (code for objective questions, the model for
written ones) and the marks are final. Answer keys and explanations are sent only after submitting.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import AIService, get_ai_service
from app.db import get_db
from app.deps import require_role
from app.models import Assessment, Attempt, AttemptAnswer, Note, Student, User
from app.services.notes_access import visible_clause
from app.services.report import Row, build_report, pct
from app.services.scoring import MAX_ANSWER_CHARS, OBJECTIVE, WRITTEN, WrittenItem, mark_objective, mark_written
from app.services.settings import weak_threshold

router = APIRouter(prefix="/api", tags=["tests"])

student_only = require_role("student")
teacher_only = require_role("teacher")


# ------------------------------------------------------------------ schemas


class TestRow(BaseModel):
    id: int
    title: str
    question_count: int
    total_marks: float
    created_at: datetime
    status: str  # todo | done
    marks: float | None
    percent: int | None


class PaperQuestion(BaseModel):
    id: int
    type: str
    text: str
    options: list[str] | None
    marks: float


class TestPaper(BaseModel):
    id: int
    title: str
    total_marks: float
    submitted: bool
    questions: list[PaperQuestion]


class AnswerIn(BaseModel):
    question_id: int
    answer: str = Field(default="", max_length=MAX_ANSWER_CHARS * 2)


class SubmitIn(BaseModel):
    answers: list[AnswerIn]


class MissedQuestion(BaseModel):
    question_id: int
    text: str


class TopicScore(BaseModel):
    topic: str
    marks: float
    max_marks: float
    percent: int
    weak: bool
    questions: int
    missed: list[MissedQuestion]
    note_id: int | None  # only when this student may open that note
    note_title: str | None


class ReviewedQuestion(BaseModel):
    question_id: int
    position: int
    type: str
    text: str
    options: list[str] | None
    topic: str
    your_answer: str
    correct_answer: str
    explanation: str
    marks_awarded: float
    max_marks: float
    feedback: str | None
    scored_by: str


class Report(BaseModel):
    assessment_id: int
    title: str
    submitted_at: datetime
    marks: float
    max_marks: float
    percent: int
    weak_threshold: int
    ai_fallback: bool
    topics: list[TopicScore]
    priorities: list[TopicScore]
    questions: list[ReviewedQuestion]


class StudentResult(BaseModel):
    student_id: int
    name: str
    submitted: bool
    marks: float | None
    percent: int | None


class ClassTopic(BaseModel):
    topic: str
    percent: int
    weak: bool


class Results(BaseModel):
    assessment_id: int
    title: str
    class_name: str
    max_marks: float
    submitted_count: int
    student_count: int
    students: list[StudentResult]
    class_topics: list[ClassTopic]


# ------------------------------------------------------------------ helpers


def _my_student(db: Session, user: User) -> Student:
    student = db.scalar(select(Student).where(Student.user_id == user.id))
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No student profile is linked to this account.")
    return student


def _my_assessment(db: Session, student: Student, assessment_id: int) -> Assessment:
    """Tests of the student's own class only. Anything else is "not found", never "forbidden"."""
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.class_id != student.class_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That test wasn't found.")
    return assessment


def _attempt(db: Session, student: Student, assessment_id: int) -> Attempt | None:
    return db.scalar(select(Attempt).where(Attempt.assessment_id == assessment_id, Attempt.student_id == student.id))


def _rows(attempt: Attempt, note_of: dict[int, int | None] | None = None) -> list[Row]:
    return [
        Row(a.question_id, a.question.topic, a.question.text, a.marks_awarded, a.max_marks, a.question.note_id if note_of is None else note_of.get(a.question.note_id))
        for a in attempt.answers
    ]


def _report(db: Session, user: User, attempt: Attempt) -> Report:
    threshold = weak_threshold(db)
    # A link to the source note is offered only if this student is allowed to open that note.
    note_ids = {a.question.note_id for a in attempt.answers}
    visible = {
        n.id: n.title for n in db.scalars(select(Note).where(Note.id.in_(note_ids), visible_clause(db, user))).all()
    } if note_ids else {}
    note_of = {nid: (nid if nid in visible else None) for nid in note_ids}
    built = build_report(_rows(attempt, note_of), threshold)

    def topic(t: dict) -> TopicScore:
        return TopicScore(**t, note_title=visible.get(t["note_id"]))

    return Report(
        assessment_id=attempt.assessment_id,
        title=attempt.assessment.title,
        submitted_at=attempt.submitted_at,
        marks=built["marks"],
        max_marks=built["max_marks"],
        percent=built["percent"],
        weak_threshold=threshold,
        ai_fallback=attempt.ai_fallback,
        topics=[topic(t) for t in built["topics"]],
        priorities=[topic(t) for t in built["priorities"]],
        questions=[
            ReviewedQuestion(
                question_id=a.question_id,
                position=a.position,
                type=a.question.type,
                text=a.question.text,
                options=a.question.options,
                topic=a.question.topic,
                your_answer=a.answer,
                correct_answer=a.question.answer,
                explanation=a.question.explanation,
                marks_awarded=a.marks_awarded,
                max_marks=a.max_marks,
                feedback=a.feedback,
                scored_by=a.scored_by,
            )
            for a in attempt.answers
        ],
    )


# ------------------------------------------------------------------ student


@router.get("/tests", response_model=list[TestRow])
def my_tests(user: User = Depends(student_only), db: Session = Depends(get_db)) -> list[TestRow]:
    student = _my_student(db, user)
    tests = db.scalars(select(Assessment).where(Assessment.class_id == student.class_id).order_by(Assessment.created_at.desc(), Assessment.id.desc())).all()
    attempts = {a.assessment_id: a for a in db.scalars(select(Attempt).where(Attempt.student_id == student.id)).all()}
    rows = []
    for t in tests:
        total = sum(i.marks for i in t.items)
        attempt = attempts.get(t.id)
        got = sum(a.marks_awarded for a in attempt.answers) if attempt else None
        rows.append(
            TestRow(
                id=t.id,
                title=t.title,
                question_count=len(t.items),
                total_marks=total,
                created_at=t.created_at,
                status="done" if attempt else "todo",
                marks=got,
                percent=pct(got, total) if got is not None else None,
            )
        )
    return rows


@router.get("/tests/{assessment_id}", response_model=TestPaper)
def get_test(assessment_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)) -> TestPaper:
    """The questions only: no answers and no explanations."""
    student = _my_student(db, user)
    test = _my_assessment(db, student, assessment_id)
    return TestPaper(
        id=test.id,
        title=test.title,
        total_marks=sum(i.marks for i in test.items),
        submitted=_attempt(db, student, assessment_id) is not None,
        questions=[PaperQuestion(id=i.question.id, type=i.question.type, text=i.question.text, options=i.question.options, marks=i.marks) for i in test.items],
    )


@router.post("/tests/{assessment_id}/submit", response_model=Report, status_code=status.HTTP_201_CREATED)
def submit_test(
    assessment_id: int,
    body: SubmitIn,
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> Report:
    student = _my_student(db, user)
    test = _my_assessment(db, student, assessment_id)
    if _attempt(db, student, assessment_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already submitted this test.")
    valid = {i.question_id for i in test.items}
    given: dict[int, str] = {}
    for a in body.answers:
        if a.question_id not in valid:
            raise HTTPException(422, "One of the answers is for a question that isn't in this test.")
        if a.question_id in given:
            raise HTTPException(422, "A question was answered twice.")
        given[a.question_id] = a.answer

    marked = {}
    written = []
    for item in test.items:
        q, answer = item.question, given.get(item.question_id, "")
        if q.type in OBJECTIVE:
            marked[q.id] = mark_objective(q.type, q.answer, answer, item.marks)
        else:
            written.append(WrittenItem(q.id, q.text, q.answer, answer, item.marks))
    written_marks, fallback = mark_written(ai, written)
    marked.update(written_marks)

    attempt = Attempt(assessment_id=test.id, student_id=student.id, ai_fallback=fallback)
    for position, item in enumerate(test.items):
        m = marked[item.question_id]
        attempt.answers.append(
            AttemptAnswer(
                question_id=item.question_id,
                position=position,
                answer=given.get(item.question_id, ""),
                marks_awarded=m.marks,
                max_marks=item.marks,
                feedback=m.feedback,
                scored_by=m.scored_by,
            )
        )
    db.add(attempt)
    db.commit()
    return _report(db, user, attempt)


@router.get("/tests/{assessment_id}/report", response_model=Report)
def my_report(assessment_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)) -> Report:
    student = _my_student(db, user)
    _my_assessment(db, student, assessment_id)
    attempt = _attempt(db, student, assessment_id)
    if attempt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You haven't taken this test yet.")
    return _report(db, user, attempt)


# ------------------------------------------------------------------ teacher


@router.get("/assessments/{assessment_id}/results", response_model=Results)
def class_results(assessment_id: int, user: User = Depends(teacher_only), db: Session = Depends(get_db)) -> Results:
    test = db.get(Assessment, assessment_id)
    if test is None or test.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That test wasn't found.")
    total = sum(i.marks for i in test.items)
    attempts = {a.student_id: a for a in db.scalars(select(Attempt).where(Attempt.assessment_id == test.id)).all()}
    students = db.scalars(select(Student).where(Student.class_id == test.class_id).order_by(Student.id)).all()
    threshold = weak_threshold(db)

    out, pooled = [], []
    for s in students:
        attempt = attempts.get(s.id)
        got = sum(a.marks_awarded for a in attempt.answers) if attempt else None
        out.append(StudentResult(student_id=s.id, name=s.user.name, submitted=attempt is not None, marks=got, percent=pct(got, total) if got is not None else None))
        if attempt:
            pooled += _rows(attempt)
    topics = build_report(pooled, threshold)["topics"] if pooled else []
    return Results(
        assessment_id=test.id,
        title=test.title,
        class_name=test.school_class.name,
        max_marks=total,
        submitted_count=len(attempts),
        student_count=len(students),
        students=out,
        class_topics=[ClassTopic(topic=t["topic"], percent=t["percent"], weak=t["weak"]) for t in topics],
    )
