from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.models.entities import RoleName

Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    role: RoleName
    phone_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=32)] | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: Password


class RefreshRequest(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=20)]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    status: str
    roles: list[str]


class MessageResponse(BaseModel):
    message: str
