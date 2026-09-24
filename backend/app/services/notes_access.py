"""Who may see or change a note. Every notes endpoint goes through here.

Rules:
- A teacher sees only their own notes.
- A student sees their own notes, plus notes a teacher has shared with the student's class.
- A draft (an OCR result still being reviewed) is visible only to its owner.
- Shared notes are read-only for the student.
- A note the caller may not see is reported as "not found", never "forbidden", so that
  guessing ids reveals nothing.
"""

from fastapi import HTTPException, status
from sqlalchemy import and_, false, or_, select
from sqlalchemy.orm import Session

from app.models import Note, NoteShare, Student, User


def visible_clause(db: Session, user: User):
    """SQL condition matching the notes this user may see."""
    if user.role == "teacher":
        return Note.owner_id == user.id
    if user.role == "student":
        student = db.scalar(select(Student).where(Student.user_id == user.id))
        if student is not None:
            shared_ids = select(NoteShare.note_id).where(NoteShare.class_id == student.class_id)
            return or_(Note.owner_id == user.id, and_(Note.status == "saved", Note.id.in_(shared_ids)))
        return Note.owner_id == user.id
    return false()


def get_note_or_404(db: Session, user: User, note_id: int, *, write: bool = False) -> Note:
    note = db.scalar(select(Note).where(Note.id == note_id, visible_clause(db, user)))
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That note wasn't found.")
    if write and note.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This note was shared with you, so you can't change it.")
    return note
