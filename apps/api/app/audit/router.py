from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.audit.schemas import AuditLogResponse
from app.auth.dependencies import require_permission
from app.db.session import get_db
from app.users.models import User

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    _: Annotated[User, Depends(require_permission("audit:read"))],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog)
            .order_by(AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )

