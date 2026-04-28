from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog


class AuditLogService:
    def __init__(self, db: Session):
        self.db = db

    def create_log(
        self,
        *,
        operation_type: str,
        resource_type: str,
        operation_result: str,
        actor_user_id: int | None = None,
        actor_role: str | None = None,
        resource_id: str | None = None,
        before_snapshot: dict[str, Any] | None = None,
        after_snapshot: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        previous_log = self.db.scalar(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(1)
        )
        previous_hash = previous_log.hash if previous_log else None
        created_at = datetime.now(timezone.utc)
        current_hash = self.calculate_hash(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            operation_type=operation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            operation_result=operation_result,
            ip_address=ip_address,
            user_agent=user_agent,
            previous_hash=previous_hash,
            created_at=created_at,
        )
        audit_log = AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            operation_type=operation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            operation_result=operation_result,
            ip_address=ip_address,
            user_agent=user_agent,
            previous_hash=previous_hash,
            hash=current_hash,
            created_at=created_at,
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log

    @staticmethod
    def calculate_hash(**payload: Any) -> str:
        canonical_payload = json.dumps(
            payload,
            default=str,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def actor_role_codes(roles: list[Any]) -> str | None:
    role_codes = sorted(role.code for role in roles)
    return ",".join(role_codes) if role_codes else None

