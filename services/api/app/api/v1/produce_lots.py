from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import CommodityCategory
from app.modules.auth.dependencies import CurrentUser
from app.modules.marketplace.service import (
    create_produce_lot,
    get_produce_lot_detail,
    list_my_produce_lots,
    search_marketplace,
    update_produce_lot,
)
from app.schemas.marketplace import (
    MarketplaceProduceLotsResponse,
    ProduceLotCreate,
    ProduceLotDetailResponse,
    ProduceLotSummaryResponse,
    ProduceLotUpdateRequest,
)

router = APIRouter(tags=["produce lots"])


def request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/produce-lots", response_model=ProduceLotDetailResponse, status_code=status.HTTP_201_CREATED, summary="Create a new produce lot listing")
def create_lot(
    payload: ProduceLotCreate,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProduceLotDetailResponse:
    return create_produce_lot(db, current_user, payload, request_ip(request))


@router.get("/produce-lots/my", response_model=list[ProduceLotSummaryResponse], summary="List current user's produce lots")
def get_my_lots(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[ProduceLotSummaryResponse]:
    return list_my_produce_lots(db, current_user)


@router.get("/produce-lots/{lot_id}", response_model=ProduceLotDetailResponse, summary="Get produce lot details")
def get_lot(
    lot_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ProduceLotDetailResponse:
    return get_produce_lot_detail(db, lot_id)


@router.patch("/produce-lots/{lot_id}", response_model=ProduceLotDetailResponse, summary="Update produce lot listing")
def patch_lot(
    lot_id: UUID,
    payload: ProduceLotUpdateRequest,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProduceLotDetailResponse:
    return update_produce_lot(db, current_user, lot_id, payload)


@router.get("/marketplace/produce-lots", response_model=MarketplaceProduceLotsResponse, summary="Browse and search marketplace produce listings")
def browse_marketplace(
    db: Annotated[Session, Depends(get_db)],
    commodity_id: Annotated[UUID | None, Query(description="Filter by specific commodity")] = None,
    category: Annotated[CommodityCategory | None, Query(description="Filter by crop category")] = None,
    state: Annotated[str | None, Query(description="Filter by state")] = None,
    district: Annotated[str | None, Query(description="Filter by district")] = None,
    min_price: Annotated[Decimal | None, Query(description="Minimum asking price per unit")] = None,
    max_price: Annotated[Decimal | None, Query(description="Maximum asking price per unit")] = None,
    min_quantity: Annotated[Decimal | None, Query(description="Minimum available quantity")] = None,
    quality_grade: Annotated[str | None, Query(description="Filter by quality grade")] = None,
    search: Annotated[str | None, Query(description="Search crop, title, or location")] = None,
    seller_role: Annotated[str | None, Query(description="Filter by seller type (farmer/fpo)")] = None,
    sort_by: Annotated[str | None, Query(description="Sort order: recommended, price_asc, price_desc, newest, qty_desc, qty_asc")] = "recommended",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 12,
) -> MarketplaceProduceLotsResponse:
    return search_marketplace(
        db,
        commodity_id=commodity_id,
        category=category,
        state=state,
        district=district,
        min_price=min_price,
        max_price=max_price,
        min_quantity=min_quantity,
        quality_grade=quality_grade,
        search=search,
        seller_role=seller_role,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
