from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.service import (
    authenticate_user,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
    serialize_user,
)
from app.schemas.auth import LoginRequest, MessageResponse, RefreshRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


def request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    return register_user(db, payload, request_ip(request))


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    _, tokens = authenticate_user(db, payload, request_ip(request))
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    return rotate_refresh_token(db, payload.refresh_token, request_ip(request))


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: RefreshRequest,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    revoke_refresh_token(db, payload.refresh_token, current_user.id, request_ip(request))
    return MessageResponse(message="Refresh token revoked.")


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    return serialize_user(current_user)
