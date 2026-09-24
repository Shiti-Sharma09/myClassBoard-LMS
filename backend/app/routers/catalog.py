"""Small read-only lists the UI needs for dropdowns."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models import Chapter, SchoolClass

router = APIRouter(prefix="/api", tags=["catalog"], dependencies=[Depends(get_current_user)])


class ChapterOut(BaseModel):
    id: int
    number: int
    title: str


class ClassOut(BaseModel):
    id: int
    name: str


@router.get("/chapters", response_model=list[ChapterOut])
def chapters(db: Session = Depends(get_db)) -> list[ChapterOut]:
    rows = db.scalars(select(Chapter).order_by(Chapter.number)).all()
    return [ChapterOut(id=c.id, number=c.number, title=c.title) for c in rows]


@router.get("/classes", response_model=list[ClassOut], dependencies=[Depends(require_role("teacher", "admin"))])
def classes(db: Session = Depends(get_db)) -> list[ClassOut]:
    rows = db.scalars(select(SchoolClass).order_by(SchoolClass.name)).all()
    return [ClassOut(id=c.id, name=c.name) for c in rows]
