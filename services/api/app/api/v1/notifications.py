from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.marketplace.service import (
    list_notifications,
    mark_notification_read,
)
from app.schemas.marketplace import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse], summary="List current user's notifications")
def get_user_notifications(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[NotificationResponse]:
    return list_notifications(db, current_user)


@router.patch("/{notification_id}/read", response_model=NotificationResponse, summary="Mark notification as read")
def read_notification(
    notification_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    return mark_notification_read(db, current_user, notification_id)
