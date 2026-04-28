from collections.abc import Generator

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import require_permission
from app.auth.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.users.models import Role, User
from app.users.seed import seed_default_admin, seed_rbac_defaults


def build_test_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = create_app()

    @app.get("/test/admin-only")
    def admin_only(_: User = Depends(require_permission("admin:write"))) -> dict[str, bool]:
        return {"ok": True}

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), session_factory


def seed_admin(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        seed_default_admin(
            db,
            email="admin@example.com",
            username="admin",
            password="AdminPass123!",
        )


def create_readonly_user(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        seed_rbac_defaults(db)
        readonly_role = db.scalar(select(Role).where(Role.code == "readonly"))
        assert readonly_role is not None
        user = User(
            email="readonly@example.com",
            username="readonly",
            hashed_password=hash_password("ReadonlyPass123!"),
            roles=[readonly_role],
        )
        db.add(user)
        db.commit()


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_success_and_me() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)

    token = login(client, "admin", "AdminPass123!")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert "admin" in body["roles"]
    assert "admin:write" in body["permissions"]


def test_login_failure() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_protected_endpoint_requires_login() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_require_permission_returns_403_for_insufficient_permission() -> None:
    client, session_factory = build_test_client()
    create_readonly_user(session_factory)

    token = login(client, "readonly", "ReadonlyPass123!")
    response = client.get(
        "/test/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
