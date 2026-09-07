from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import (
    BuyerProfile,
    FarmerProfile,
    FPOProfile,
    RefreshToken,
    Role,
    RoleName,
    TransporterProfile,
    User,
    UserRole,
    UserStatus,
)
from app.modules.audit.service import record_audit_event
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

PUBLIC_REGISTRATION_ROLES = {RoleName.FARMER, RoleName.FPO, RoleName.BUYER, RoleName.TRANSPORTER}


def ensure_system_roles(db: Session) -> None:
    existing = set(db.scalars(select(Role.name)).all())
    missing = [role for role in RoleName if role not in existing]
    if missing:
        db.add_all([Role(name=role, description=f"System role: {role.value}") for role in missing])
        db.commit()

    admin_user = _load_user_by_email(db, "admin@agrimandi.gov.in")
    if not admin_user:
        admin_role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN))
        if admin_role:
            admin = User(
                email="admin@agrimandi.gov.in",
                password_hash=hash_password("AdminPassword123!"),
                display_name="Mandi Admin Commissioner",
                status=UserStatus.ACTIVE,
                is_email_verified=True,
            )
            db.add(admin)
            db.flush()
            db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
            db.commit()


def _load_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.email == email.lower())
    )


def _role_names(user: User) -> list[str]:
    return sorted({user_role.role.name.value for user_role in user.user_roles if user_role.role is not None})


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status.value,
        roles=_role_names(user),
    )


def issue_token_pair(db: Session, user: User) -> TokenResponse:
    access_token, access_expires_at = create_access_token(user.id, _role_names(user))
    refresh_token, token_jti, refresh_expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_jti=token_jti, expires_at=refresh_expires_at))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
    )


def register_user(db: Session, payload: RegisterRequest, ip_address: str | None = None) -> UserResponse:
    if payload.role not in PUBLIC_REGISTRATION_ROLES:
        raise ApiError(403, "role_not_self_assignable", "This role cannot be assigned during public registration.")
    normalized_email = payload.email.lower()
    if _load_user_by_email(db, normalized_email):
        raise ApiError(409, "email_in_use", "An account with this email already exists.")
    if payload.phone_number:
        existing_phone = db.scalar(select(User).where(User.phone_number == payload.phone_number))
        if existing_phone:
            raise ApiError(409, "phone_in_use", "An account with this phone number already exists.")
    role = db.scalar(select(Role).where(Role.name == payload.role))
    if role is None:
        raise ApiError(503, "roles_not_initialized", "System roles are not initialized. Try again shortly.")

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        phone_number=payload.phone_number,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))

    if payload.role == RoleName.FARMER:
        db.add(FarmerProfile(user_id=user.id))
    elif payload.role == RoleName.FPO:
        db.add(FPOProfile(user_id=user.id, legal_name=payload.display_name))
    elif payload.role == RoleName.BUYER:
        db.add(BuyerProfile(user_id=user.id, organization_name=payload.display_name))
    elif payload.role == RoleName.TRANSPORTER:
        db.add(TransporterProfile(user_id=user.id, organization_name=payload.display_name))

    record_audit_event(
        db,
        event_type="auth.registration",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        metadata={"role": payload.role.value},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, status=user.status.value, roles=[payload.role.value])


def authenticate_user(db: Session, payload: LoginRequest, ip_address: str | None = None) -> tuple[User, TokenResponse]:
    user = _load_user_by_email(db, payload.email.lower())
    if user is None or not verify_password(payload.password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    if user.status != UserStatus.ACTIVE:
        raise ApiError(403, "account_inactive", "This account is not active.")
    user.last_login_at = datetime.now(UTC)
    tokens = issue_token_pair(db, user)
    record_audit_event(
        db,
        event_type="auth.login",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    return user, tokens


def rotate_refresh_token(db: Session, raw_token: str, ip_address: str | None = None) -> TokenResponse:
    payload = decode_token(raw_token, "refresh")
    try:
        user_id = UUID(str(payload["sub"]))
        token_jti = UUID(str(payload["jti"]))
    except (KeyError, ValueError) as error:
        raise ApiError(401, "invalid_token", "The refresh token is invalid.") from error

    stored_token = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == token_jti))
    if stored_token is None or stored_token.user_id != user_id or stored_token.revoked_at is not None:
        raise ApiError(401, "refresh_token_revoked", "The refresh token is no longer valid.")
    user = db.scalar(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise ApiError(401, "invalid_token", "The refresh token is invalid.")
    stored_token.revoked_at = datetime.now(UTC)
    tokens = issue_token_pair(db, user)
    record_audit_event(
        db,
        event_type="auth.refresh_rotated",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    return tokens


def revoke_refresh_token(db: Session, raw_token: str, actor_user_id: UUID, ip_address: str | None = None) -> None:
    payload = decode_token(raw_token, "refresh")
    try:
        user_id = UUID(str(payload["sub"]))
        token_jti = UUID(str(payload["jti"]))
    except (KeyError, ValueError) as error:
        raise ApiError(401, "invalid_token", "The refresh token is invalid.") from error
    if user_id != actor_user_id:
        raise ApiError(403, "token_owner_mismatch", "The refresh token does not belong to this user.")
    stored_token = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == token_jti))
    if stored_token is not None and stored_token.revoked_at is None:
        stored_token.revoked_at = datetime.now(UTC)
        record_audit_event(
            db,
            event_type="auth.logout",
            entity_type="user",
            entity_id=actor_user_id,
            actor_user_id=actor_user_id,
            ip_address=ip_address,
        )
        db.commit()
