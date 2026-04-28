from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_engine_from_url, create_sessionmaker, get_db
from app.main import app


def test_database_url_can_be_read_from_settings() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")

    assert settings.database_url == "sqlite+pysqlite:///:memory:"


def test_session_can_execute_minimal_query() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    session_factory = create_sessionmaker(engine)

    with session_factory() as db:
        result = db.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_health_db_uses_injected_session() -> None:
    engine = create_engine_from_url("sqlite+pysqlite:///:memory:")
    session_factory = create_sessionmaker(engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}

