from collections.abc import Generator
from dataclasses import dataclass
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit.models import AuditLog
from app.auth.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.uploads.models import DataFile, UploadBatch
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
        self.objects[object_key] = StoredPayload(
            content=content,
            content_type=content_type,
        )
        return StoredObject(bucket="test-bucket", key=object_key)


def build_test_client() -> tuple[TestClient, sessionmaker[Session], FakeStorage]:
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
    return TestClient(app), session_factory, storage


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
        db.add(
            User(
                email="readonly@example.com",
                username="readonly",
                hashed_password=hash_password("ReadonlyPass123!"),
                roles=[readonly_role],
            )
        )
        db.commit()


def upload_file(client: TestClient, token: str, filename: str, content: bytes):
    return client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": (filename, BytesIO(content), "text/csv")},
    )


def test_successful_upload_stores_file_metadata_and_object() -> None:
    client, session_factory, storage = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    response = upload_file(client, token, "sample.csv", b"a,b\n1,2\n")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["files"][0]["original_filename"] == "sample.csv"
    assert body["files"][0]["file_size"] == 8

    with session_factory() as db:
        batch = db.scalar(select(UploadBatch))
        data_file = db.scalar(select(DataFile).where(DataFile.original_filename == "sample.csv"))

        assert batch is not None
        assert data_file is not None
        assert data_file.object_key in storage.objects
        assert storage.objects[data_file.object_key].content == b"a,b\n1,2\n"


def test_invalid_file_extension_is_rejected() -> None:
    client, session_factory, _storage = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    response = upload_file(client, token, "sample.txt", b"not allowed")

    assert response.status_code == 400
    with session_factory() as db:
        assert db.scalar(select(UploadBatch)) is None
        failure_log = db.scalar(
            select(AuditLog)
            .where(AuditLog.operation_type == "upload.create")
            .where(AuditLog.operation_result == "failure")
        )
        assert failure_log is not None


def test_upload_requires_upload_write_permission() -> None:
    client, session_factory, _storage = build_test_client()
    seed_readonly_user(session_factory)
    token = login(client, "readonly", "ReadonlyPass123!")

    response = upload_file(client, token, "sample.csv", b"a,b\n")

    assert response.status_code == 403


def test_upload_creates_audit_log() -> None:
    client, session_factory, _storage = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    response = upload_file(client, token, "sample.fcs", b"FCS payload")

    assert response.status_code == 201
    batch_id = response.json()["id"]
    with session_factory() as db:
        log = db.scalar(
            select(AuditLog)
            .where(AuditLog.operation_type == "upload.create")
            .where(AuditLog.operation_result == "success")
        )

        assert log is not None
        assert log.resource_type == "upload_batch"
        assert log.resource_id == str(batch_id)
        assert log.hash

