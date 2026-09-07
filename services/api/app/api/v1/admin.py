from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import AuditEvent, RoleName, User, UserRole, VerificationStatus
from app.modules.auth.dependencies import require_roles
from app.modules.marketplace.service import (
    get_platform_metrics,
    list_verification_requests,
    review_verification_request,
)
from app.schemas.marketplace import (
    AuditEventResponse,
    PlatformMetricsResponse,
    UserProfileResponse,
    VerificationRequestResponse,
    VerificationReviewRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


class AdminFoundationStatus(BaseModel):
    status: str


class AdminUserSummary(BaseModel):
    id: UUID
    email: str
    display_name: str
    phone_number: str | None = None
    status: str
    roles: list[str]
    verification_status: str


@router.get("/foundation-status", response_model=AdminFoundationStatus, summary="RBAC check for Admin")
def admin_foundation_status(
    _: Annotated[User, Depends(require_roles(RoleName.ADMIN))],
) -> AdminFoundationStatus:
    return AdminFoundationStatus(status="authorized")


@router.get("/metrics", response_model=PlatformMetricsResponse, summary="Get platform-level metrics summary")
def get_metrics(
    _: Annotated[User, Depends(require_roles(RoleName.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformMetricsResponse:
    return get_platform_metrics(db)


@router.get("/users", response_model=list[AdminUserSummary], summary="List platform users")
def get_admin_users(
    _: Annotated[User, Depends(require_roles(RoleName.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> list[AdminUserSummary]:
    stmt = (
        select(User)
        .options(
            selectinload(User.user_roles).selectinload(UserRole.role),
            selectinload(User.farmer_profile),
            selectinload(User.fpo_profile),
            selectinload(User.buyer_profile),
            selectinload(User.transporter_profile),
        )
        .order_by(User.created_at.desc())
    )
    rows = db.scalars(stmt).all()
    results = []
    for u in rows:
        roles = [ur.role.name.value for ur in u.user_roles]
        vstatus = "pending"
        if u.farmer_profile:
            vstatus = u.farmer_profile.verification_status.value
        elif u.fpo_profile:
            vstatus = u.fpo_profile.verification_status.value
        elif u.buyer_profile:
            vstatus = u.buyer_profile.verification_status.value
        elif u.transporter_profile:
            vstatus = u.transporter_profile.verification_status.value
        results.append(
            AdminUserSummary(
                id=u.id,
                email=u.email,
                display_name=u.display_name,
                phone_number=u.phone_number,
                status=u.status.value,
                roles=roles,
                verification_status=vstatus,
            )
        )
    return results


@router.get("/verifications", response_model=list[VerificationRequestResponse], summary="List verification requests")
def get_admin_verifications(
    _: Annotated[User, Depends(require_roles(RoleName.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[VerificationStatus | None, Query(description="Filter by status")] = None,
) -> list[VerificationRequestResponse]:
    return list_verification_requests(db, status=status)


@router.post("/verifications/{request_id}/review", response_model=VerificationRequestResponse, summary="Approve or reject verification request")
def review_verification(
    request_id: UUID,
    payload: VerificationReviewRequest,
    request: Request,
    admin_user: Annotated[User, Depends(require_roles(RoleName.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> VerificationRequestResponse:
    return review_verification_request(db, admin_user, request_id, payload, request_ip(request))


@router.get("/audit-events", response_model=list[AuditEventResponse], summary="Get recent audit logs")
def get_audit_trail(
    _: Annotated[User, Depends(require_roles(RoleName.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AuditEventResponse]:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return [
        AuditEventResponse(
            id=a.id,
            actor_user_id=a.actor_user_id,
            event_type=a.event_type,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            metadata_json=a.metadata_json,
            ip_address=a.ip_address,
            created_at=a.created_at,
        )
        for a in rows
    ]
