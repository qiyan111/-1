from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit.models import AuditLog
from app.auth.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.templates.models import AnalysisTemplate, AnalysisTemplateVersion
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


def template_payload(name: str = "AML Screening Template") -> dict:
    return {
        "name": name,
        "project_code": "FLOW-AML",
        "change_note": "initial template",
        "plots": [
            {
                "title": "CD45 SSC",
                "tube_no": "T-001",
                "x_channel": "CD45",
                "y_channel": "SSC-A",
                "plot_type": "scatter",
                "config": {"scale": "logicle"},
                "sort_order": 1,
            }
        ],
        "gates": [
            {
                "gate_key": "lym",
                "name": "Lymphocytes",
                "gate_type": "polygon",
                "definition": {"points": [[1, 1], [2, 1], [2, 2]]},
                "sort_order": 1,
            },
            {
                "parent_gate_key": "lym",
                "gate_key": "cd3_positive",
                "name": "CD3 Positive",
                "gate_type": "rectangle",
                "definition": {"x_min": 1, "x_max": 2, "y_min": 1, "y_max": 2},
                "sort_order": 2,
            }
        ],
        "logic_gates": [
            {
                "name": "LYM NOT NK",
                "expression": "LYM NOT NK",
                "definition": {"operator": "NOT", "left": "LYM", "right": "NK"},
                "sort_order": 1,
            }
        ],
        "statistics": [
            {
                "name": "Percent Parent",
                "rule_type": "percent_parent",
                "formula": "event_count / parent_event_count",
                "config": {"format": "percent"},
                "sort_order": 1,
            }
        ],
    }


def create_template(client: TestClient, token: str, name: str = "AML Screening Template") -> dict:
    response = client.post(
        "/api/templates",
        headers=auth_headers(token),
        json=template_payload(name),
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_query_template() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    created = create_template(client, token)
    list_response = client.get("/api/templates", headers=auth_headers(token))
    detail_response = client.get(f"/api/templates/{created['id']}", headers=auth_headers(token))

    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "AML Screening Template"
    assert detail_response.status_code == 200
    assert detail_response.json()["plots"][0]["plot_type"] == "scatter"
    assert detail_response.json()["gates"][0]["gate_key"] == "lym"
    assert detail_response.json()["gates"][1]["parent_gate_key"] == "lym"


def test_update_template_replaces_children_and_increments_version() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)

    payload = template_payload("Updated Template")
    payload["change_note"] = "update plot"
    payload["plots"] = [
        {
            "title": "CD3 CD19",
            "tube_no": "T-002",
            "x_channel": "CD3",
            "y_channel": "CD19",
            "plot_type": "density",
            "sort_order": 1,
        }
    ]
    response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated Template"
    assert body["current_version"] == 2
    assert body["plots"][0]["plot_type"] == "density"
    assert len(body["plots"]) == 1


def test_clone_template() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)

    response = client.post(
        f"/api/templates/{created['id']}/clone",
        headers=auth_headers(token),
        json={"name": "AML Screening Template Clone", "change_note": "clone baseline"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] != created["id"]
    assert body["name"] == "AML Screening Template Clone"
    assert body["plots"][0]["x_channel"] == "CD45"
    assert body["gates"][1]["parent_gate_key"] == "lym"
    assert body["current_version"] == 1


def test_delete_template() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)

    delete_response = client.delete(f"/api/templates/{created['id']}", headers=auth_headers(token))
    detail_response = client.get(f"/api/templates/{created['id']}", headers=auth_headers(token))

    assert delete_response.status_code == 204
    assert detail_response.status_code == 404
    with session_factory() as db:
        assert db.get(AnalysisTemplate, created["id"]) is None


def test_template_write_requires_template_write_permission() -> None:
    client, session_factory = build_test_client()
    seed_readonly_user(session_factory)
    token = login(client, "readonly", "ReadonlyPass123!")

    read_response = client.get("/api/templates", headers=auth_headers(token))
    write_response = client.post(
        "/api/templates",
        headers=auth_headers(token),
        json=template_payload(),
    )

    assert read_response.status_code == 200
    assert write_response.status_code == 403


def test_template_mutations_write_audit_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)
    update_payload = template_payload("Audited Update")
    update_payload["change_note"] = "audit update"

    update_response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=update_payload,
    )
    clone_response = client.post(
        f"/api/templates/{created['id']}/clone",
        headers=auth_headers(token),
        json={"change_note": "audit clone"},
    )
    delete_response = client.delete(f"/api/templates/{created['id']}", headers=auth_headers(token))

    assert update_response.status_code == 200
    assert clone_response.status_code == 201
    assert delete_response.status_code == 204

    with session_factory() as db:
        logs = db.scalars(
            select(AuditLog)
            .where(
                AuditLog.operation_type.in_(
                    ["template.create", "template.update", "template.clone", "template.delete"]
                )
            )
            .order_by(AuditLog.id)
        ).all()

        assert [log.operation_type for log in logs] == [
            "template.create",
            "template.update",
            "template.clone",
            "template.delete",
        ]
        assert all(log.hash for log in logs)
        assert logs[1].before_snapshot["name"] == "AML Screening Template"
        assert logs[1].after_snapshot["name"] == "Audited Update"


def test_create_template_generates_version_1() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")

    created = create_template(client, token)

    with session_factory() as db:
        version = db.scalar(
            select(AnalysisTemplateVersion).where(AnalysisTemplateVersion.template_id == created["id"])
        )
        assert version is not None
        assert version.version == 1
        assert version.change_note == "initial template"
        assert version.snapshot_json["name"] == "AML Screening Template"


def test_update_template_generates_version_2() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)
    payload = template_payload("Version 2")
    payload["change_note"] = "second version"

    response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=payload,
    )

    assert response.status_code == 200
    with session_factory() as db:
        versions = db.scalars(
            select(AnalysisTemplateVersion)
            .where(AnalysisTemplateVersion.template_id == created["id"])
            .order_by(AnalysisTemplateVersion.version)
        ).all()
        assert [version.version for version in versions] == [1, 2]
        assert versions[1].change_note == "second version"
        assert versions[1].snapshot_json["name"] == "Version 2"


def test_change_note_is_required_for_create_update_and_clone() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    payload = template_payload()
    payload.pop("change_note")

    create_response = client.post("/api/templates", headers=auth_headers(token), json=payload)
    created = create_template(client, token)
    update_response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=payload,
    )
    clone_response = client.post(
        f"/api/templates/{created['id']}/clone",
        headers=auth_headers(token),
        json={"name": "Missing Note"},
    )

    assert create_response.status_code == 422
    assert update_response.status_code == 422
    assert clone_response.status_code == 422


def test_query_template_version_history_and_detail() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)
    payload = template_payload("History V2")
    payload["change_note"] = "history update"
    update_response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=payload,
    )
    assert update_response.status_code == 200

    history_response = client.get(f"/api/templates/{created['id']}/versions", headers=auth_headers(token))
    assert history_response.status_code == 200
    versions = history_response.json()
    assert [version["version"] for version in versions] == [1, 2]

    detail_response = client.get(
        f"/api/templates/{created['id']}/versions/{versions[1]['id']}",
        headers=auth_headers(token),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["snapshot_json"]["name"] == "History V2"


def test_diff_template_versions() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)
    payload = template_payload("Diff V2")
    payload["change_note"] = "diff update"
    payload["plots"][0]["x_channel"] = "CD3"
    payload["gates"][0]["definition"] = {"points": [[3, 3], [4, 3], [4, 4]]}
    payload["statistics"][0]["formula"] = "event_count / total_event_count"
    update_response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=payload,
    )
    assert update_response.status_code == 200

    versions = client.get(f"/api/templates/{created['id']}/versions", headers=auth_headers(token)).json()
    diff_response = client.get(
        f"/api/templates/{created['id']}/diff",
        headers=auth_headers(token),
        params={"from_version_id": versions[0]["id"], "to_version_id": versions[1]["id"]},
    )

    assert diff_response.status_code == 200
    body = diff_response.json()
    assert body["plots"]["modified"]
    assert body["gates"]["modified"]
    assert body["statistics"]["modified"]
    assert body["channel_config"]["modified"][0]["after"]["x_channel"] == "CD3"


def test_rollback_generates_new_version_without_overwriting_history() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)
    payload = template_payload("Rollback V2")
    payload["change_note"] = "change before rollback"
    update_response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=payload,
    )
    assert update_response.status_code == 200
    versions = client.get(f"/api/templates/{created['id']}/versions", headers=auth_headers(token)).json()

    rollback_response = client.post(
        f"/api/templates/{created['id']}/rollback",
        headers=auth_headers(token),
        json={"version_id": versions[0]["id"], "change_note": "rollback to initial"},
    )

    assert rollback_response.status_code == 200
    body = rollback_response.json()
    assert body["name"] == "AML Screening Template"
    assert body["current_version"] == 3
    with session_factory() as db:
        version_rows = db.scalars(
            select(AnalysisTemplateVersion)
            .where(AnalysisTemplateVersion.template_id == created["id"])
            .order_by(AnalysisTemplateVersion.version)
        ).all()
        assert [version.version for version in version_rows] == [1, 2, 3]
        assert version_rows[2].change_note == "rollback to initial"


def test_version_operations_write_audit_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    created = create_template(client, token)
    payload = template_payload("Audit Version V2")
    payload["change_note"] = "version audit update"
    update_response = client.put(
        f"/api/templates/{created['id']}",
        headers=auth_headers(token),
        json=payload,
    )
    assert update_response.status_code == 200
    versions = client.get(f"/api/templates/{created['id']}/versions", headers=auth_headers(token)).json()
    detail_response = client.get(
        f"/api/templates/{created['id']}/versions/{versions[0]['id']}",
        headers=auth_headers(token),
    )
    diff_response = client.get(
        f"/api/templates/{created['id']}/diff",
        headers=auth_headers(token),
        params={"from_version_id": versions[0]["id"], "to_version_id": versions[1]["id"]},
    )
    rollback_response = client.post(
        f"/api/templates/{created['id']}/rollback",
        headers=auth_headers(token),
        json={"version_id": versions[0]["id"], "change_note": "audit rollback"},
    )

    assert detail_response.status_code == 200
    assert diff_response.status_code == 200
    assert rollback_response.status_code == 200
    with session_factory() as db:
        operations = set(
            db.scalars(
                select(AuditLog.operation_type).where(
                    AuditLog.operation_type.in_(
                        [
                            "template.version.create",
                            "template.version.list",
                            "template.version.read",
                            "template.version.diff",
                            "template.rollback",
                        ]
                    )
                )
            )
        )

        assert operations == {
            "template.version.create",
            "template.version.list",
            "template.version.read",
            "template.version.diff",
            "template.rollback",
        }
