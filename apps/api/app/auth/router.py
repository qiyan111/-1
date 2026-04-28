from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_user_permission_codes
from app.auth.schemas import CurrentUserResponse, LoginRequest, TokenResponse
from app.auth.security import create_access_token, verify_password
from app.audit.service import AuditLogService, actor_role_codes
from app.db.session import get_db
from app.users.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(
        select(User).where(
            or_(User.username == payload.username, User.email == payload.username)
        )
    )
    if (
        user is None
        or not user.is_active
        or user.is_locked
        or not verify_password(payload.password, user.hashed_password)
    ):
        AuditLogService(db).create_log(
            actor_user_id=user.id if user else None,
            actor_role=actor_role_codes(user.roles) if user else None,
            operation_type="auth.login",
            resource_type="user",
            resource_id=str(user.id) if user else payload.username,
            before_snapshot=None,
            after_snapshot={"username": payload.username},
            operation_result="failure",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    AuditLogService(db).create_log(
        actor_user_id=user.id,
        actor_role=actor_role_codes(user.roles),
        operation_type="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        before_snapshot=None,
        after_snapshot={"username": user.username},
        operation_result="success",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        roles=[role.code for role in current_user.roles],
        permissions=sorted(get_user_permission_codes(current_user)),
    )
