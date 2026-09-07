from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.errors import ApiError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: UUID, roles: list[str]) -> tuple[str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "roles": roles, "type": "access", "exp": expires_at}
    return (
        jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm),
        expires_at,
    )


def create_refresh_token(user_id: UUID) -> tuple[str, UUID, datetime]:
    settings = get_settings()
    jti = uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(user_id), "jti": str(jti), "type": "refresh", "exp": expires_at}
    return (
        jwt.encode(
            payload,
            settings.jwt_refresh_secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        ),
        jti,
        expires_at,
    )


def decode_token(token: str, expected_type: str) -> dict[str, str | list[str]]:
    settings = get_settings()
    secret = (
        settings.jwt_secret_key.get_secret_value()
        if expected_type == "access"
        else settings.jwt_refresh_secret_key.get_secret_value()
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as error:
        raise ApiError(401, "invalid_token", "The authentication token is invalid or expired.") from error
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise ApiError(401, "invalid_token", "The authentication token is invalid.")
    return payload
