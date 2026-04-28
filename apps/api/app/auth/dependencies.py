from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db.session import get_db
from app.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        raise credentials_error from None

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active or user.is_locked:
        raise credentials_error
    return user


def get_user_permission_codes(user: User) -> set[str]:
    return {
        permission.code
        for role in user.roles
        for permission in role.permissions
    }


def require_permission(permission_code: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if permission_code not in get_user_permission_codes(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission",
            )
        return current_user

    return dependency


def require_any_permission(permission_codes: set[str]) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if get_user_permission_codes(current_user).isdisjoint(permission_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission",
            )
        return current_user

    return dependency
