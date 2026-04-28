from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_sessionmaker
from app.users.models import Permission, Role

DEFAULT_ROLES: tuple[dict[str, str], ...] = (
    {"code": "admin", "name": "管理员", "description": "系统全权限管理员"},
    {"code": "analyst", "name": "分析员", "description": "上传数据并执行分析"},
    {"code": "reviewer", "name": "审核员", "description": "审核并确认分析结果"},
    {"code": "readonly", "name": "只读用户", "description": "只读查看权限"},
    {
        "code": "system_integration",
        "name": "系统集成",
        "description": "业务系统集成调用权限",
    },
)

DEFAULT_PERMISSIONS: tuple[dict[str, str], ...] = (
    {
        "code": "template:read",
        "name": "查看模板",
        "module": "template",
        "action": "read",
        "description": "查看分析模板",
    },
    {
        "code": "template:write",
        "name": "维护模板",
        "module": "template",
        "action": "write",
        "description": "创建和编辑分析模板",
    },
    {
        "code": "upload:write",
        "name": "上传数据",
        "module": "upload",
        "action": "write",
        "description": "上传或接收检测数据",
    },
    {
        "code": "analysis:execute",
        "name": "执行分析",
        "module": "analysis",
        "action": "execute",
        "description": "启动自动化分析任务",
    },
    {
        "code": "review:write",
        "name": "审核调整",
        "module": "review",
        "action": "write",
        "description": "保存审核调整和退回意见",
    },
    {
        "code": "result:confirm",
        "name": "确认结果",
        "module": "result",
        "action": "confirm",
        "description": "确认结果入库",
    },
    {
        "code": "audit:read",
        "name": "查看审计",
        "module": "audit",
        "action": "read",
        "description": "查看审计日志",
    },
    {
        "code": "admin:write",
        "name": "系统管理",
        "module": "admin",
        "action": "write",
        "description": "维护用户、角色、权限和系统配置",
    },
)

ROLE_PERMISSION_CODES: dict[str, tuple[str, ...]] = {
    "admin": tuple(permission["code"] for permission in DEFAULT_PERMISSIONS),
    "analyst": (
        "template:read",
        "template:write",
        "upload:write",
        "analysis:execute",
    ),
    "reviewer": (
        "template:read",
        "review:write",
        "result:confirm",
    ),
    "readonly": (
        "template:read",
    ),
    "system_integration": (
        "upload:write",
        "analysis:execute",
    ),
}


def seed_rbac_defaults(db: Session) -> None:
    roles_by_code: dict[str, Role] = {}
    permissions_by_code: dict[str, Permission] = {}

    for role_data in DEFAULT_ROLES:
        role = db.scalar(select(Role).where(Role.code == role_data["code"]))
        if role is None:
            role = Role(**role_data)
            db.add(role)
        else:
            role.name = role_data["name"]
            role.description = role_data["description"]
        roles_by_code[role_data["code"]] = role

    for permission_data in DEFAULT_PERMISSIONS:
        permission = db.scalar(
            select(Permission).where(Permission.code == permission_data["code"])
        )
        if permission is None:
            permission = Permission(**permission_data)
            db.add(permission)
        else:
            permission.name = permission_data["name"]
            permission.module = permission_data["module"]
            permission.action = permission_data["action"]
            permission.description = permission_data["description"]
        permissions_by_code[permission_data["code"]] = permission

    db.flush()

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role = roles_by_code[role_code]
        desired_permissions = {permissions_by_code[code] for code in permission_codes}
        for permission in desired_permissions:
            if permission not in role.permissions:
                role.permissions.append(permission)

    db.commit()


def main() -> None:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        seed_rbac_defaults(db)


if __name__ == "__main__":
    main()

