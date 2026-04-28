from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.audit.models import AuditLog
from app.auth.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.projects.models import CompensationMatrix, MarkerMapping, Tube
from app.uploads.models import DataFile, UploadBatch
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


def create_metadata_chain(client: TestClient, token: str) -> tuple[int, int, int, int]:
    project_response = client.post(
        "/api/projects",
        headers=auth_headers(token),
        json={"code": "P001", "name": "Leukemia Panel"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    experiment_response = client.post(
        "/api/experiments",
        headers=auth_headers(token),
        json={"project_id": project_id, "experiment_no": "EXP-001", "name": "Day 1"},
    )
    assert experiment_response.status_code == 201
    experiment_id = experiment_response.json()["id"]

    sample_response = client.post(
        "/api/samples",
        headers=auth_headers(token),
        json={"experiment_id": experiment_id, "sample_no": "S-001", "subject_identifier": "SUBJ-001"},
    )
    assert sample_response.status_code == 201
    sample_id = sample_response.json()["id"]

    tube_response = client.post(
        "/api/tubes",
        headers=auth_headers(token),
        json={
            "sample_id": sample_id,
            "tube_no": "T-001",
            "group_name": "Lymphocyte",
            "experimental_condition": "fresh sample",
            "antibody_info": {"CD3": "FITC"},
        },
    )
    assert tube_response.status_code == 201
    tube_id = tube_response.json()["id"]

    return project_id, experiment_id, sample_id, tube_id


def test_create_project_experiment_sample_tube() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    project_id, experiment_id, sample_id, tube_id = create_metadata_chain(client, token)

    projects_response = client.get("/api/projects", headers=auth_headers(token))
    experiment_response = client.get(f"/api/experiments/{experiment_id}", headers=auth_headers(token))

    assert projects_response.status_code == 200
    assert projects_response.json()[0]["id"] == project_id
    assert experiment_response.status_code == 200
    assert experiment_response.json()["id"] == experiment_id

    with session_factory() as db:
        tube = db.get(Tube, tube_id)
        assert tube is not None
        assert tube.sample_id == sample_id
        assert tube.sample.experiment.project.id == project_id


def test_create_tube_channel_marker_mapping_and_compensation_model() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    _, _, _, tube_id = create_metadata_chain(client, token)

    channel_response = client.post(
        f"/api/tubes/{tube_id}/channels",
        headers=auth_headers(token),
        json={"name": "FL1-A", "detector": "FL1", "fluorochrome": "FITC", "marker": "CD3", "channel_index": 1},
    )
    mapping_response = client.post(
        f"/api/tubes/{tube_id}/marker-mappings",
        headers=auth_headers(token),
        json={"marker": "CD3", "channel_name": "FL1-A", "fluorochrome": "FITC"},
    )

    assert channel_response.status_code == 201
    assert mapping_response.status_code == 201

    with session_factory() as db:
        tube = db.get(Tube, tube_id)
        assert tube is not None
        tube.compensation_matrices.append(
            CompensationMatrix(version=1, matrix={"FL1-A": {"FL1-A": 1.0}})
        )
        db.commit()
        db.refresh(tube)

        marker_mapping = db.scalar(select(MarkerMapping).where(MarkerMapping.tube_id == tube_id))
        assert marker_mapping is not None
        assert marker_mapping.marker == "CD3"
        assert tube.channels[0].name == "FL1-A"
        assert tube.compensation_matrices[0].version == 1


def test_tube_can_link_uploaded_data_files() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    with session_factory() as db:
        admin = db.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        batch = UploadBatch(uploaded_by_user_id=admin.id)
        db.add(batch)
        db.flush()
        data_file = DataFile(
            upload_batch_id=batch.id,
            uploaded_by_user_id=admin.id,
            original_filename="sample.csv",
            file_extension=".csv",
            content_type="text/csv",
            object_bucket="test-bucket",
            object_key="uploads/sample.csv",
            file_size=12,
            sha256="0" * 64,
        )
        db.add(data_file)
        db.commit()
        data_file_id = data_file.id

    _, _, sample_id, _ = create_metadata_chain(client, token)
    response = client.post(
        "/api/tubes",
        headers=auth_headers(token),
        json={"sample_id": sample_id, "tube_no": "T-002", "data_file_ids": [data_file_id]},
    )

    assert response.status_code == 201
    with session_factory() as db:
        data_file = db.get(DataFile, data_file_id)
        tube = db.get(Tube, response.json()["id"])
        assert data_file is not None
        assert tube is not None
        assert data_file.tube_id == tube.id
        assert tube.data_files[0].id == data_file_id


def test_metadata_create_requires_upload_or_admin_permission() -> None:
    client, session_factory = build_test_client()
    seed_readonly_user(session_factory)
    token = login(client, "readonly", "ReadonlyPass123!")

    response = client.post(
        "/api/projects",
        headers=auth_headers(token),
        json={"code": "P403", "name": "Forbidden"},
    )

    assert response.status_code == 403


def test_metadata_create_writes_audit_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    _, _, _, tube_id = create_metadata_chain(client, token)
    response = client.post(
        f"/api/tubes/{tube_id}/marker-mappings",
        headers=auth_headers(token),
        json={"marker": "CD19", "channel_name": "FL2-A", "fluorochrome": "PE"},
    )

    assert response.status_code == 201
    with session_factory() as db:
        logs = db.scalars(
            select(AuditLog)
            .where(AuditLog.operation_type.in_(["project.create", "marker_mapping.create"]))
            .order_by(AuditLog.id)
        ).all()

        assert [log.operation_type for log in logs] == ["project.create", "marker_mapping.create"]
        assert logs[0].hash
        assert logs[1].previous_hash
