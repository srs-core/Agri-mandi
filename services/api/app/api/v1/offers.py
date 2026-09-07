from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import OfferStatus
from app.modules.auth.dependencies import CurrentUser
from app.modules.marketplace.service import (
    accept_offer,
    counter_offer,
    create_offer,
    list_offers,
    reject_offer,
    withdraw_offer,
)
from app.schemas.marketplace import (
    CounterOfferCreate,
    OfferCreate,
    OfferResponse,
    OrderResponse,
)

router = APIRouter(prefix="/offers", tags=["offers"])


def request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", response_model=OfferResponse, status_code=status.HTTP_201_CREATED, summary="Submit a commercial offer on a produce lot")
def post_offer(
    payload: OfferCreate,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> OfferResponse:
    return create_offer(db, current_user, payload, request_ip(request))


@router.get("", response_model=list[OfferResponse], summary="List offers sent or received by current user")
def get_offers(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    role_perspective: Annotated[str | None, Query(description="Filter perspective: 'sent' (as buyer) or 'received' (as seller)")] = None,
    status: Annotated[OfferStatus | None, Query(description="Filter by offer status")] = None,
    lot_id: Annotated[UUID | None, Query(description="Filter offers for a specific lot")] = None,
) -> list[OfferResponse]:
    return list_offers(db, current_user, role_perspective=role_perspective, status=status, lot_id=lot_id)


@router.post("/{offer_id}/counter", response_model=OfferResponse, summary="Submit a bilateral counter-offer")
def counter_commercial_offer(
    offer_id: UUID,
    payload: CounterOfferCreate,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> OfferResponse:
    return counter_offer(db, current_user, offer_id, payload, request_ip(request))


@router.post("/{offer_id}/accept", response_model=OrderResponse, summary="Accept current proposal, confirming an order")
def accept_commercial_offer(
    offer_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> OrderResponse:
    return accept_offer(db, current_user, offer_id, request_ip(request))


@router.post("/{offer_id}/reject", response_model=OfferResponse, summary="Decline current proposal")
def decline_commercial_offer(
    offer_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> OfferResponse:
    return reject_offer(db, current_user, offer_id, request_ip(request))


@router.post("/{offer_id}/withdraw", response_model=OfferResponse, summary="Withdraw pending offer or proposal")
def withdraw_commercial_offer(
    offer_id: UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> OfferResponse:
    return withdraw_offer(db, current_user, offer_id, request_ip(request))
