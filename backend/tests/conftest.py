import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai import AIService, ChatResult, get_ai_service
from app.config import Settings
from app.db import get_db
from app.main import app
from app.models import Base
from app.seed.seed import seed_database
from app.storage import LocalStorage, get_storage


class ScriptedProvider:
    """Stands in for Groq. Queue replies (JSON strings, or exceptions to raise) in `replies`."""

    def __init__(self):
        self.replies: list = []
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if not self.replies:
            raise AssertionError("The code made an AI call the test did not expect")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(text=reply)


@pytest.fixture(scope="session")
def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_database(db)
    return engine


@pytest.fixture
def db(_engine):
    with Session(_engine) as session:
        yield session


@pytest.fixture
def provider() -> ScriptedProvider:
    return ScriptedProvider()


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path)


@pytest.fixture
def client(_engine, provider, storage):
    """API client backed by an in-memory SQLite copy of the seeded demo school,
    temporary file storage, and a scripted AI provider (no network)."""
    factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with factory() as session:
            yield session

    ai = AIService(provider, Settings(groq_api_key="test"), sleep=lambda _: None)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_ai_service] = lambda: ai
    yield TestClient(app)  # no `with`: skips the startup hook that would seed Postgres
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str = "demo1234") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}
