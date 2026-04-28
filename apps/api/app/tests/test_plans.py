from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit.models import AuditLog
from app.auth.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.plans.models import AnalysisPlan, AnalysisPlanVersion
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


def create_project(client: TestClient, token: str) -> dict:
    response = client.post(
        "/api/projects",
        headers=auth_headers(token),
        json={"code": "FLOW-AML", "name": "AML Flow Project"},
    )
    assert response.status_code == 201
    return response.json()


def template_payload() -> dict:
    return {
        "name": "AML Screening Template",
        "project_code": "FLOW-AML",
        "change_note": "initial template",
        "plots": [
            {
                "title": "CD45 SSC",
                "tube_no": "T-001",
                "x_channel": "CD45",
                "y_channel": "SSC-A",
                "plot_type": "scatter",
            }
        ],
        "gates": [
            {
                "gate_key": "lym",
                "name": "Lymphocytes",
                "gate_type": "polygon",
                "definition": {"points": [[1, 1], [2, 1], [2, 2]]},
            }
        ],
        "logic_gates": [],
        "statistics": [],
    }


def create_template(client: TestClient, token: str) -> dict:
    response = client.post("/api/templates", headers=auth_headers(token), json=template_payload())
    assert response.status_code == 201
    return response.json()


def create_plan(client: TestClient, token: str, project_id: int, name: str = "AML Analysis Plan") -> dict:
    response = client.post(
        "/api/plans",
        headers=auth_headers(token),
        json={
            "name": name,
            "project_id": project_id,
            "description": "Baseline AML analysis plan",
            "change_note": "initial plan",
        },
    )
    assert response.status_code == 201
    return response.json()


def bootstrap_plan(client: TestClient, token: str) -> tuple[dict, dict, dict]:
    project = create_project(client, token)
    template = create_template(client, token)
    plan = create_plan(client, token, project["id"])
    return project, template, plan


def test_create_plan_and_query() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    project = create_project(client, token)

    plan = create_plan(client, token, project["id"])
    list_response = client.get("/api/plans", headers=auth_headers(token))
    detail_response = client.get(f"/api/plans/{plan['id']}", headers=auth_headers(token))

    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "AML Analysis Plan"
    assert detail_response.status_code == 200
    assert detail_response.json()["project_id"] == project["id"]
    assert detail_response.json()["current_version"] == 1


def test_bind_template() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    _, template, plan = bootstrap_plan(client, token)

    response = client.post(
        f"/api/plans/{plan['id']}/template-bindings",
        headers=auth_headers(token),
        json={
            "template_id": template["id"],
            "experiment_no": "EXP-001",
            "tube_no": "T-001",
            "config": {"panel": "screening"},
            "change_note": "bind tube to template",
        },
    )

    assert response.status_code == 201
    assert response.json()["template_id"] == template["id"]
    detail = client.get(f"/api/plans/{plan['id']}", headers=auth_headers(token)).json()
    assert detail["template_bindings"][0]["tube_no"] == "T-001"
    assert detail["current_version"] == 2


def test_create_cell_label_tree() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    _, _, plan = bootstrap_plan(client, token)

    root_response = client.post(
        f"/api/plans/{plan['id']}/cell-labels",
        headers=auth_headers(token),
        json={"code": "lym", "name": "Lymphocytes", "change_note": "add root label"},
    )
    child_response = client.post(
        f"/api/plans/{plan['id']}/cell-labels",
        headers=auth_headers(token),
        json={
            "parent_node_id": root_response.json()["id"],
            "code": "cd3",
            "name": "CD3 Positive",
            "change_note": "add child label",
        },
    )

    assert root_response.status_code == 201
    assert child_response.status_code == 201
    assert child_response.json()["parent_node_id"] == root_response.json()["id"]


def test_create_marker_threshold() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    _, _, plan = bootstrap_plan(client, token)
    label_response = client.post(
        f"/api/plans/{plan['id']}/cell-labels",
        headers=auth_headers(token),
        json={"code": "cd3", "name": "CD3 Positive", "change_note": "add label"},
    )

    response = client.post(
        f"/api/plans/{plan['id']}/marker-thresholds",
        headers=auth_headers(token),
        json={
            "label_node_id": label_response.json()["id"],
            "marker": "CD3",
            "channel_name": "FL1-A",
            "threshold_type": "positive",
            "threshold_value": 120.5,
            "config": {"scale": "logicle"},
            "change_note": "add CD3 threshold",
        },
    )

    assert response.status_code == 201
    assert response.json()["marker"] == "CD3"
    detail = client.get(f"/api/plans/{plan['id']}", headers=auth_headers(token)).json()
    assert detail["marker_thresholds"][0]["threshold_value"] == 120.5


def test_clone_plan_copies_bindings_labels_and_thresholds() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    _, template, plan = bootstrap_plan(client, token)
    client.post(
        f"/api/plans/{plan['id']}/template-bindings",
        headers=auth_headers(token),
        json={"template_id": template["id"], "tube_no": "T-001", "change_note": "bind template"},
    )
    label = client.post(
        f"/api/plans/{plan['id']}/cell-labels",
        headers=auth_headers(token),
        json={"code": "cd3", "name": "CD3 Positive", "change_note": "add label"},
    ).json()
    client.post(
        f"/api/plans/{plan['id']}/marker-thresholds",
        headers=auth_headers(token),
        json={
            "label_node_id": label["id"],
            "marker": "CD3",
            "channel_name": "FL1-A",
            "threshold_value": 100.0,
            "change_note": "add threshold",
        },
    )

    response = client.post(
        f"/api/plans/{plan['id']}/clone",
        headers=auth_headers(token),
        json={"name": "AML Analysis Plan Clone", "change_note": "clone plan"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] != plan["id"]
    assert body["template_bindings"][0]["template_id"] == template["id"]
    assert body["cell_label_nodes"][0]["code"] == "cd3"
    assert body["marker_thresholds"][0]["label_node_id"] == body["cell_label_nodes"][0]["id"]
    assert body["current_version"] == 1


def test_update_plan_saves_new_version_and_inherits_children() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    _, template, plan = bootstrap_plan(client, token)
    client.post(
        f"/api/plans/{plan['id']}/template-bindings",
        headers=auth_headers(token),
        json={"template_id": template["id"], "tube_no": "T-001", "change_note": "bind template"},
    )

    response = client.put(
        f"/api/plans/{plan['id']}",
        headers=auth_headers(token),
        json={"name": "Updated AML Plan", "change_note": "rename plan"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated AML Plan"
    assert body["template_bindings"][0]["tube_no"] == "T-001"
    assert body["current_version"] == 3
    versions = client.get(f"/api/plans/{plan['id']}/versions", headers=auth_headers(token)).json()
    assert [version["version"] for version in versions] == [1, 2, 3]
    assert versions[-1]["snapshot_json"]["template_bindings"][0]["tube_no"] == "T-001"


def test_plan_write_requires_template_write_or_admin_permission() -> None:
    client, session_factory = build_test_client()
    seed_readonly_user(session_factory)
    token = login(client, "readonly", "ReadonlyPass123!")

    read_response = client.get("/api/plans", headers=auth_headers(token))
    write_response = client.post(
        "/api/plans",
        headers=auth_headers(token),
        json={"name": "Forbidden", "project_id": 1, "change_note": "try write"},
    )

    assert read_response.status_code == 200
    assert write_response.status_code == 403


def test_plan_operations_write_audit_logs() -> None:
    client, session_factory = build_test_client()
    seed_admin(session_factory)
    token = login(client, "admin", "AdminPass123!")
    _, template, plan = bootstrap_plan(client, token)

    binding_response = client.post(
        f"/api/plans/{plan['id']}/template-bindings",
        headers=auth_headers(token),
        json={"template_id": template["id"], "tube_no": "T-001", "change_note": "bind template"},
    )
    clone_response = client.post(
        f"/api/plans/{plan['id']}/clone",
        headers=auth_headers(token),
        json={"change_note": "clone for audit"},
    )

    assert binding_response.status_code == 201
    assert clone_response.status_code == 201
    with session_factory() as db:
        operations = set(
            db.scalars(
                select(AuditLog.operation_type).where(
                    AuditLog.operation_type.in_(
                        [
                            "plan.create",
                            "plan.template_binding.create",
                            "plan.clone",
                            "plan.version.create",
                        ]
                    )
                )
            )
        )
        version_count = db.scalar(
            select(func.count())
            .select_from(AnalysisPlanVersion)
            .where(AnalysisPlanVersion.plan_id == plan["id"])
        )
        plan_row = db.get(AnalysisPlan, plan["id"])

        assert operations == {
            "plan.create",
            "plan.template_binding.create",
            "plan.clone",
            "plan.version.create",
        }
        assert plan_row is not None
        assert plan_row.current_version == 2
        assert version_count == 2
