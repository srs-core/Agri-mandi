from __future__ import annotations

import os
import tempfile
from pathlib import Path
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

test_db_path = Path(tempfile.gettempdir()) / "agrimandi_phase1_tests.sqlite3"
if test_db_path.exists():
    test_db_path.unlink()

os.environ.update(
    {
        "DATABASE_URL": f"sqlite+pysqlite:///{test_db_path.as_posix()}",
        "JWT_SECRET_KEY": "test-access-secret-that-is-long-enough-and-not-production",
        "JWT_REFRESH_SECRET_KEY": "test-refresh-secret-that-is-long-enough-and-not-production",
        "CORS_ORIGINS": "http://localhost:5173",
    }
)

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database_schema() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
