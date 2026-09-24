"""Login, current user, and the demo-account list for the login page."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Student, User
from app.security import create_access_token, verify_password
from app.seed import data
from app.seed.seed import parent_email, student_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class StudentInfo(BaseModel):
    id: int
    name: str
    class_name: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    student: StudentInfo | None = None  # set for students
    child: StudentInfo | None = None  # set for parents


class LoginOut(BaseModel):
    token: str
    user: UserOut


class DemoAccount(BaseModel):
    label: str
    role: str
    email: str
    password: str


def _to_user_out(user: User, db: Session) -> UserOut:
    out = UserOut(id=user.id, name=user.name, email=user.email, role=user.role)
    if user.role == "student":
        s = db.scalar(select(Student).where(Student.user_id == user.id))
        if s:
            out.student = StudentInfo(id=s.id, name=user.name, class_name=s.school_class.name)
    elif user.role == "parent":
        s = db.scalar(select(Student).where(Student.parent_user_id == user.id))
        if s:
            out.child = StudentInfo(id=s.id, name=s.user.name, class_name=s.school_class.name)
    return out


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    return LoginOut(token=create_access_token(user.id, user.role), user=_to_user_out(user, db))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return _to_user_out(user, db)


@router.get("/demo-accounts", response_model=list[DemoAccount])
def demo_accounts() -> list[DemoAccount]:
    """One-click logins shown on the login page. POC only, disabled when DEMO_MODE=false."""
    if not get_settings().demo_mode:
        return []
    pw = data.DEMO_PASSWORD
    accounts = [
        DemoAccount(label=f"Teacher ({data.TEACHER[0]})", role="teacher", email=data.TEACHER[1], password=pw),
        DemoAccount(label="Admin", role="admin", email=data.ADMIN[1], password=pw),
    ]
    personas = {first: persona for first, _, persona, _ in data.STUDENTS}
    for first in data.DEMO_LOGIN_STUDENTS:
        accounts.append(DemoAccount(label=f"Student: {first} ({personas[first]})", role="student", email=student_email(first), password=pw))
        accounts.append(DemoAccount(label=f"Parent of {first}", role="parent", email=parent_email(first), password=pw))
    return accounts
