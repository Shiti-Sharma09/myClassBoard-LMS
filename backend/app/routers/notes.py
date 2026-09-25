"""Notes Library: handwriting OCR, typed and uploaded notes, sharing, download, practice quiz."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import AIService, get_ai_service
from app.db import get_db
from app.deps import require_role
from app.models import Chapter, Note, NotePage, NoteShare, SchoolClass, User
from app.services import ocr as ocr_service
from app.services.export_docx import note_to_docx, slug
from app.services.extract import ExtractionError, extract_text
from app.services.images import MAX_PDF_PAGES, ImageError, pdf_to_images, preprocess
from app.services.notes_access import get_note_or_404, visible_clause
from app.services.practice import MIN_NOTE_CHARS, PracticeQuestion, make_quiz
from app.storage import LocalStorage, get_storage

router = APIRouter(prefix="/api/notes", tags=["notes"])

# Teachers and students use the library. Admins and parents don't.
library_user = require_role("teacher", "student")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


# ------------------------------------------------------------------ schemas


class NoteSummary(BaseModel):
    id: int
    title: str
    subject: str
    chapter_id: int | None
    chapter_title: str | None
    topic: str | None
    source_type: str
    status: str
    owner_name: str
    is_mine: bool
    shared_with: list[str]  # class names, only filled for the owner
    page_count: int
    word_count: int
    snippet: str
    created_at: datetime


class NoteDetail(NoteSummary):
    text: str
    can_edit: bool


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    subject: str = "Science"
    chapter_id: int | None = None
    topic: str | None = Field(default=None, max_length=200)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    text: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    subject: str | None = None
    chapter_id: int | None = None
    topic: str | None = Field(default=None, max_length=200)
    status: str | None = None  # "saved" confirms a reviewed OCR draft


class ShareIn(BaseModel):
    class_ids: list[int]


class PracticeIn(BaseModel):
    topic: str | None = Field(default=None, max_length=200)  # practise one weak topic instead of the whole note


class PracticeOut(BaseModel):
    questions: list[PracticeQuestion]


# ------------------------------------------------------------------ helpers


def _summary(note: Note, user: User) -> NoteSummary:
    is_mine = note.owner_id == user.id
    words = note.text.split()
    return NoteSummary(
        id=note.id,
        title=note.title,
        subject=note.subject,
        chapter_id=note.chapter_id,
        chapter_title=note.chapter.title if note.chapter else None,
        topic=note.topic,
        source_type=note.source_type,
        status=note.status,
        owner_name=note.owner.name,
        is_mine=is_mine,
        shared_with=sorted(s.school_class.name for s in note.shares) if is_mine else [],
        page_count=len(note.pages),
        word_count=len(words),
        snippet=" ".join(words[:30]),
        created_at=note.created_at,
    )


def _detail(note: Note, user: User) -> NoteDetail:
    return NoteDetail(**_summary(note, user).model_dump(), text=note.text, can_edit=note.owner_id == user.id)


def _check_chapter(db: Session, chapter_id: int | None) -> None:
    if chapter_id is not None and db.get(Chapter, chapter_id) is None:
        raise HTTPException(422, "That chapter doesn't exist.")


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That file is too large (10 MB maximum).")
    if not data:
        raise HTTPException(422, "That file is empty.")
    return data


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(422, message)


# ------------------------------------------------------------------ create


@router.post("/ocr", response_model=NoteDetail, status_code=status.HTTP_201_CREATED)
async def digitise_handwriting(
    files: list[UploadFile] = File(...),
    subject: str = Form("Science"),
    chapter_id: int | None = Form(None),
    topic: str | None = Form(None),
    user: User = Depends(library_user),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
    storage: LocalStorage = Depends(get_storage),
) -> NoteDetail:
    """Photos or a PDF of handwritten pages in, an editable DRAFT note out (for the review screen)."""
    _check_chapter(db, chapter_id)
    raw_pages: list[bytes] = []
    for file in files:
        data = await _read_upload(file)
        name = (file.filename or "").lower()
        try:
            if name.endswith(".pdf"):
                raw_pages += await run_in_threadpool(pdf_to_images, data)
            elif any(name.endswith(s) for s in IMAGE_SUFFIXES):
                raw_pages.append(data)
            else:
                raise ImageError("Please upload JPG, PNG or PDF files.")
        except ImageError as exc:
            raise _unprocessable(str(exc)) from None
    if not raw_pages:
        raise _unprocessable("Please choose at least one photo or PDF.")
    if len(raw_pages) > MAX_PDF_PAGES:
        raise _unprocessable(f"Please upload {MAX_PDF_PAGES} pages or fewer at a time.")
    # Blocking work (image processing, slow AI calls with rate-limit waits) runs in a thread pool
    # so one person's OCR never freezes the server for everyone else.
    try:
        pages = await run_in_threadpool(lambda: [preprocess(p) for p in raw_pages])
    except ImageError as exc:
        raise _unprocessable(str(exc)) from None

    text = await run_in_threadpool(ocr_service.read_pages, ai, pages)  # AIError becomes a friendly 503 in main.py
    if not text.strip():
        raise _unprocessable("No writing could be read from that upload. Try a clearer, well-lit photo.")

    note = Note(
        owner_id=user.id,
        title=ocr_service.suggest_title(text),
        subject=subject,
        chapter_id=chapter_id,
        topic=topic or None,
        source_type="ocr",
        status="draft",
        text=text,
    )
    db.add(note)
    db.flush()
    for number, image in enumerate(pages, start=1):
        rel = f"notes/{note.id}/page_{number}.jpg"
        storage.save(rel, image)
        note.pages.append(NotePage(page_number=number, image_path=rel))
    db.commit()
    return _detail(note, user)


@router.post("/upload", response_model=NoteDetail, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    subject: str = Form("Science"),
    chapter_id: int | None = Form(None),
    topic: str | None = Form(None),
    user: User = Depends(library_user),
    db: Session = Depends(get_db),
) -> NoteDetail:
    """A typed document (PDF, DOCX or TXT) becomes a saved note."""
    _check_chapter(db, chapter_id)
    data = await _read_upload(file)
    filename = file.filename or "note.txt"
    try:
        text = extract_text(filename, data)
    except ExtractionError as exc:
        raise _unprocessable(str(exc)) from None
    note = Note(
        owner_id=user.id,
        title=(title or "").strip() or filename.rsplit(".", 1)[0][:200],
        subject=subject,
        chapter_id=chapter_id,
        topic=topic or None,
        source_type="upload",
        status="saved",
        text=text,
    )
    db.add(note)
    db.commit()
    return _detail(note, user)


@router.post("", response_model=NoteDetail, status_code=status.HTTP_201_CREATED)
def create_typed_note(
    body: NoteCreate, user: User = Depends(library_user), db: Session = Depends(get_db)
) -> NoteDetail:
    _check_chapter(db, body.chapter_id)
    note = Note(
        owner_id=user.id,
        title=body.title.strip(),
        subject=body.subject,
        chapter_id=body.chapter_id,
        topic=body.topic or None,
        source_type="typed",
        status="saved",
        text=body.text.strip(),
    )
    db.add(note)
    db.commit()
    return _detail(note, user)


# ------------------------------------------------------------------ read


@router.get("", response_model=list[NoteSummary])
def list_notes(
    q: str | None = None, user: User = Depends(library_user), db: Session = Depends(get_db)
) -> list[NoteSummary]:
    query = select(Note).where(visible_clause(db, user), Note.status == "saved")
    if q and q.strip():
        needle = q.strip().lower()
        query = query.where(
            func.lower(Note.title).contains(needle, autoescape=True)
            | func.lower(Note.text).contains(needle, autoescape=True)
        )
    notes = db.scalars(query.order_by(Note.created_at.desc(), Note.id.desc())).all()
    return [_summary(n, user) for n in notes]


@router.get("/{note_id}", response_model=NoteDetail)
def get_note(note_id: int, user: User = Depends(library_user), db: Session = Depends(get_db)) -> NoteDetail:
    return _detail(get_note_or_404(db, user, note_id), user)


@router.get("/{note_id}/pages/{page_number}/image")
def get_page_image(
    note_id: int,
    page_number: int,
    user: User = Depends(library_user),
    db: Session = Depends(get_db),
    storage: LocalStorage = Depends(get_storage),
) -> Response:
    note = get_note_or_404(db, user, note_id)
    page = next((p for p in note.pages if p.page_number == page_number), None)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That page wasn't found.")
    try:
        data = storage.read(page.image_path)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That page image is missing.") from None
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{note_id}/download")
def download_note(note_id: int, user: User = Depends(library_user), db: Session = Depends(get_db)) -> Response:
    note = get_note_or_404(db, user, note_id)
    return Response(
        note_to_docx(note.title, note.text),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{slug(note.title)}.docx"'},
    )


# ------------------------------------------------------------------ change


@router.patch("/{note_id}", response_model=NoteDetail)
def update_note(
    note_id: int, body: NoteUpdate, user: User = Depends(library_user), db: Session = Depends(get_db)
) -> NoteDetail:
    note = get_note_or_404(db, user, note_id, write=True)
    fields = body.model_dump(exclude_unset=True)
    if "chapter_id" in fields:
        _check_chapter(db, fields["chapter_id"])
    if fields.get("status") not in (None, "saved"):
        raise _unprocessable("A note can only be saved, not moved back to draft.")
    if "text" in fields:
        cleaned = ocr_service.strip_uncertain(fields["text"] or "").strip()
        if not cleaned:
            raise _unprocessable("A note can't be empty.")
        fields["text"] = cleaned
    for key, value in fields.items():
        if value is not None or key in {"chapter_id", "topic"}:
            setattr(note, key, value)
    db.commit()
    return _detail(note, user)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    user: User = Depends(library_user),
    db: Session = Depends(get_db),
    storage: LocalStorage = Depends(get_storage),
) -> Response:
    note = get_note_or_404(db, user, note_id, write=True)
    db.delete(note)
    db.commit()
    storage.delete_dir(f"notes/{note_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{note_id}/shares", response_model=NoteDetail)
def set_shares(
    note_id: int, body: ShareIn, user: User = Depends(require_role("teacher")), db: Session = Depends(get_db)
) -> NoteDetail:
    """Share a saved note read-only with whole classes. Replaces the previous sharing."""
    note = get_note_or_404(db, user, note_id, write=True)
    if note.status != "saved":
        raise _unprocessable("Save the note before sharing it.")
    wanted = set(body.class_ids)
    found = set(db.scalars(select(SchoolClass.id).where(SchoolClass.id.in_(wanted))).all()) if wanted else set()
    if found != wanted:
        raise _unprocessable("One of those classes doesn't exist.")
    note.shares = [NoteShare(class_id=cid) for cid in sorted(wanted)]
    db.commit()
    return _detail(note, user)


# ------------------------------------------------------------------ practice quiz


@router.post("/{note_id}/practice", response_model=PracticeOut)
def practice_quiz(
    note_id: int,
    body: PracticeIn | None = None,
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> PracticeOut:
    """A short self-study quiz from a note the student can see. Nothing is stored."""
    note = get_note_or_404(db, user, note_id)
    if len(note.text.strip()) < MIN_NOTE_CHARS:
        raise _unprocessable("This note is too short to make a quiz from. Add a little more to it first.")
    return PracticeOut(questions=make_quiz(ai, note.text, count=5, topic=(body.topic.strip() if body and body.topic else None)))
