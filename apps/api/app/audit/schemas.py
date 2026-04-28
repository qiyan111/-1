from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    actor_role: str | None
    operation_type: str
    resource_type: str
    resource_id: str | None
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None
    operation_result: str
    ip_address: str | None
    user_agent: str | None
    previous_hash: str | None
    hash: str
    created_at: datetime

