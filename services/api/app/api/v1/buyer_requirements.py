from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import CommodityCategory
from app.modules.auth.dependencies import CurrentUser
from app.modules.marketplace.service import (
    create_buyer_requirement,
    list_buyer_requirements,
)
from app.schemas.marketplace import (
    BuyerRequirementCreate,
    BuyerRequirementResponse,
)

router = APIRouter(prefix="/buyer-requirements", tags=["buyer requirements"])


@router.post("", response_model=BuyerRequirementResponse, status_code=status.HTTP_201_CREATED, summary="Post a new buyer crop requirement")
def post_requirement(
    payload: BuyerRequirementCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> BuyerRequirementResponse:
    return create_buyer_requirement(db, current_user, payload)


@router.get("/my", response_model=list[BuyerRequirementResponse], summary="List requirements posted by current buyer")
def get_my_requirements(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[BuyerRequirementResponse]:
    return list_buyer_requirements(db, user=current_user, my_only=True)


@router.get("", response_model=list[BuyerRequirementResponse], summary="Browse active market buyer requirements")
def browse_requirements(
    db: Annotated[Session, Depends(get_db)],
    commodity_id: Annotated[UUID | None, Query(description="Filter by commodity")] = None,
    category: Annotated[CommodityCategory | None, Query(description="Filter by crop category")] = None,
) -> list[BuyerRequirementResponse]:
    return list_buyer_requirements(db, user=None, my_only=False, commodity_id=commodity_id, category=category)
