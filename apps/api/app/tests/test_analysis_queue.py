from collections.abc import Generator
from dataclasses import dataclass
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.analysis.models import AnalysisBatch, AnalysisJob, AnalysisStatus
from app.audit.models import AuditLog
from app.auth.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.uploads.storage import ObjectStorage, StoredObject, get_object_storage
from app.users.models import Role, User
from app.users.seed import seed_default_admin, seed_rbac_defaults


@dataclass
class StoredPayload:
    content: bytes
    content_type: str | None


class FakeStorage(ObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, StoredPayload] = {}

    def put_object(
        self,
        *,
        object_key: str,
        data,
        length: int,
        content_type: str | None,
    ) -> StoredObject:
        content = data.read()
        assert len(content) == length
        self.objects[object_key] = StoredPayload(content=content, content_type=content_type)
        return StoredObject(bucket="test-bucket", key=object_key)


def build_test_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    storage = FakeStorage()

    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_object_storage] = lambda: storage
    return TestClient(app), session_factory


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
        db.add(
            User(
                email="readonly@example.com",
                username="readonly",
                hashed_password=hash_password("ReadonlyPass123!"),
                roles=[readonly_role],
            )
        )
        db.commit()


def upload_file(client: TestClient, token: str) -> dict:
    response = client.post(
        "/api/uploads",
        headers=auth_headers(token),
        files={"files": ("sample.csv", BytesIO(b"a,b\n1,2\n"), "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


def start_analysis(client: TestClient, token: str, upload_batch_id: int) -> dict:
    response = client.post(
        f"/api/uploads/{upload_batch_id}/start-analysis",
        headers=auth_headers(token),
        json={},
    )
    assert response.status_code == 201
    return response.json()


def test_start_analysis_batch_creates_queued_jobs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    upload_batch = upload_file(client, token)

    analysis_batch = start_analysis(client, token, upload_batch["id"])

    assert analysis_batch["status"] == AnalysisStatus.QUEUED.value
    assert analysis_batch["upload_batch_id"] == upload_batch["id"]
    assert analysis_batch["total_jobs"] == 1
    assert analysis_batch["jobs"][0]["status"] == AnalysisStatus.QUEUED.value
    assert analysis_batch["jobs"][0]["logs"][0]["message"] == "Analysis job queued"

    with session_factory() as db:
        assert db.scalar(select(AnalysisBatch)) is not None
        assert db.scalar(select(AnalysisJob)) is not None


def test_query_analysis_batch_and_job_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    upload_batch = upload_file(client, token)
    analysis_batch = start_analysis(client, token, upload_batch["id"])
    job_id = analysis_batch["jobs"][0]["id"]

    list_response = client.get("/api/analysis/batches", headers=auth_headers(token))
    detail_response = client.get(f"/api/analysis/batches/{analysis_batch['id']}", headers=auth_headers(token))
    logs_response = client.get(f"/api/analysis/jobs/{job_id}/logs", headers=auth_headers(token))

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == analysis_batch["id"]
    assert detail_response.status_code == 200
    assert detail_response.json()["jobs"][0]["id"] == job_id
    assert logs_response.status_code == 200
    assert logs_response.json()["logs"][0]["message"] == "Analysis job queued"


def test_pause_resume_and_cancel_analysis_batch() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    upload_batch = upload_file(client, token)
    analysis_batch = start_analysis(client, token, upload_batch["id"])

    pause_response = client.post(f"/api/analysis/batches/{analysis_batch['id']}/pause", headers=auth_headers(token))
    resume_response = client.post(f"/api/analysis/batches/{analysis_batch['id']}/resume", headers=auth_headers(token))
    cancel_response = client.post(f"/api/analysis/batches/{analysis_batch['id']}/cancel", headers=auth_headers(token))

    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == AnalysisStatus.PAUSED.value
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == AnalysisStatus.QUEUED.value
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == AnalysisStatus.CANCELLED.value


def test_retry_failed_jobs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    upload_batch = upload_file(client, token)
    analysis_batch = start_analysis(client, token, upload_batch["id"])

    with session_factory() as db:
        batch = db.get(AnalysisBatch, analysis_batch["id"])
        assert batch is not None
        job = batch.jobs[0]
        batch.status = AnalysisStatus.FAILED.value
        batch.failed_jobs = 1
        job.status = AnalysisStatus.FAILED.value
        job.error_message = "parser failed"
        job.logs = [*job.logs, {"timestamp": "test", "level": "ERROR", "message": "parser failed"}]
        db.commit()

    retry_response = client.post(f"/api/analysis/batches/{analysis_batch['id']}/retry", headers=auth_headers(token))

    assert retry_response.status_code == 200
    body = retry_response.json()
    assert body["status"] == AnalysisStatus.QUEUED.value
    assert body["failed_jobs"] == 0
    assert body["jobs"][0]["status"] == AnalysisStatus.QUEUED.value
    assert body["jobs"][0]["attempt"] == 2
    assert body["jobs"][0]["error_message"] is None


def test_start_analysis_requires_analysis_execute_permission() -> None:
    client, session_factory = build_test_client()
    seed_readonly_user(session_factory)
    token = login(client, "readonly", "ReadonlyPass123!")

    response = client.post(
        "/api/uploads/1/start-analysis",
        headers=auth_headers(token),
        json={},
    )

    assert response.status_code == 403


def test_analysis_status_changes_write_audit_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    upload_batch = upload_file(client, token)
    analysis_batch = start_analysis(client, token, upload_batch["id"])

    pause_response = client.post(f"/api/analysis/batches/{analysis_batch['id']}/pause", headers=auth_headers(token))
    resume_response = client.post(f"/api/analysis/batches/{analysis_batch['id']}/resume", headers=auth_headers(token))
    cancel_response = client.post(f"/api/analysis/batches/{analysis_batch['id']}/cancel", headers=auth_headers(token))

    assert pause_response.status_code == 200
    assert resume_response.status_code == 200
    assert cancel_response.status_code == 200
    with session_factory() as db:
        operations = list(
            db.scalars(
                select(AuditLog.operation_type)
                .where(
                    AuditLog.operation_type.in_(
                        ["analysis.start", "analysis.pause", "analysis.resume", "analysis.cancel"]
                    )
                )
                .order_by(AuditLog.id)
            )
        )

        assert operations == ["analysis.start", "analysis.pause", "analysis.resume", "analysis.cancel"]
