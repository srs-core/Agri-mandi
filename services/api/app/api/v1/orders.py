from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.marketplace.service import (
    get_order_detail,
    list_orders,
    update_order_status,
)
from app.schemas.marketplace import (
    OrderResponse,
    OrderStatusUpdateRequest,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[OrderResponse], summary="List orders for current user")
def get_orders(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[OrderResponse]:
    return list_orders(db, current_user)


@router.get("/{order_id}", response_model=OrderResponse, summary="Get order details")
def get_order(
    order_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> OrderResponse:
    return get_order_detail(db, current_user, order_id)


@router.patch("/{order_id}/status", response_model=OrderResponse, summary="Advance order lifecycle status")
def patch_order_status(
    order_id: UUID,
    payload: OrderStatusUpdateRequest,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> OrderResponse:
    return update_order_status(db, current_user, order_id, payload.status, request_ip(request))
