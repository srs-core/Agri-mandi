from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import RoleName, User, UserRole, UserStatus

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise ApiError(401, "authentication_required", "Authentication is required.")
    payload = decode_token(credentials.credentials, "access")
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError) as error:
        raise ApiError(401, "invalid_token", "The authentication token is invalid.") from error
    user = db.scalar(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise ApiError(401, "invalid_token", "The authentication token is invalid.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*required_roles: RoleName) -> Callable[[User], User]:
    required = set(required_roles)

    def dependency(current_user: CurrentUser) -> User:
        user_roles = {user_role.role.name for user_role in current_user.user_roles if user_role.role is not None}
        if not required.intersection(user_roles):
            raise ApiError(403, "insufficient_permissions", "Your account does not have permission for this action.")
        return current_user

    return dependency
