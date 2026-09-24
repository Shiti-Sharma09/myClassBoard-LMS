import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base
from app.seed.seed import seed_database


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
def client(_engine):
    """API client backed by an in-memory SQLite copy of the seeded demo school."""
    factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)  # no `with`: skips the startup hook that would seed Postgres
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str = "demo1234") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}
