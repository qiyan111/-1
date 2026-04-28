from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.users.models import Permission, Role, User
from app.users.seed import DEFAULT_PERMISSIONS, DEFAULT_ROLES, seed_rbac_defaults


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


def test_user_role_permission_relationships() -> None:
    db = make_session()
    try:
        user = User(
            email="analyst@example.com",
            username="analyst",
            hashed_password="not-a-real-password-hash",
        )
        role = Role(code="analyst", name="分析员", description="测试角色")
        permission = Permission(
            code="analysis:execute",
            name="执行分析",
            module="analysis",
            action="execute",
            description="测试权限",
        )
        role.permissions.append(permission)
        user.roles.append(role)
        db.add(user)
        db.commit()

        saved_user = db.scalar(select(User).where(User.username == "analyst"))

        assert saved_user is not None
        assert saved_user.roles[0].code == "analyst"
        assert saved_user.roles[0].permissions[0].code == "analysis:execute"
    finally:
        db.close()


def test_seed_rbac_defaults_is_idempotent() -> None:
    db = make_session()
    try:
        seed_rbac_defaults(db)
        seed_rbac_defaults(db)

        roles = db.scalars(select(Role)).all()
        permissions = db.scalars(select(Permission)).all()
        admin = db.scalar(select(Role).where(Role.code == "admin"))

        assert len(roles) == len(DEFAULT_ROLES)
        assert len(permissions) == len(DEFAULT_PERMISSIONS)
        assert admin is not None
        assert {permission.code for permission in admin.permissions} == {
            permission["code"] for permission in DEFAULT_PERMISSIONS
        }
    finally:
        db.close()

