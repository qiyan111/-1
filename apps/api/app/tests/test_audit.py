from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit.models import AuditLog
from app.audit.service import AuditLogService
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

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), session_factory


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def seed_admin(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        seed_default_admin(
            db,
            email="admin@example.com",
            username="admin",
            password="AdminPass123!",
        )


def seed_readonly_user(session_factory: sessionmaker[Session]) -> None:
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


def test_audit_log_creation() -> None:
    _, session_factory = build_test_client()

    with session_factory() as db:
        log = AuditLogService(db).create_log(
            operation_type="test.create",
            resource_type="test",
            operation_result="success",
            after_snapshot={"value": 1},
        )

        assert log.id is not None
        assert log.hash
        assert log.previous_hash is None


def test_audit_hash_chain_is_continuous() -> None:
    _, session_factory = build_test_client()

    with session_factory() as db:
        first = AuditLogService(db).create_log(
            operation_type="test.first",
            resource_type="test",
            operation_result="success",
        )
        second = AuditLogService(db).create_log(
            operation_type="test.second",
            resource_type="test",
            operation_result="success",
        )

        assert second.previous_hash == first.hash
        assert second.hash != first.hash


def test_audit_logs_require_audit_read_permission() -> None:
    client, session_factory = build_test_client()
    seed_readonly_user(session_factory)

    token = login(client, "readonly", "ReadonlyPass123!")
    response = client.get(
        "/api/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_login_actions_create_audit_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)

    success_response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPass123!"},
    )
    failure_response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert success_response.status_code == 200
    assert failure_response.status_code == 401

    with session_factory() as db:
        logs = db.scalars(
            select(AuditLog).where(AuditLog.operation_type == "auth.login")
        ).all()

        assert [log.operation_result for log in logs] == ["success", "failure"]
        assert logs[0].hash
        assert logs[1].previous_hash == logs[0].hash


def test_admin_can_query_audit_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    response = client.get(
        "/api/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()[0]["operation_type"] == "auth.login"

