from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import CommodityCategory
from app.modules.marketplace.service import list_commodities
from app.schemas.marketplace import CommodityResponse

router = APIRouter(prefix="/commodities", tags=["commodities"])


@router.get("", response_model=list[CommodityResponse], summary="List agricultural commodities")
def get_commodities(
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[CommodityCategory | None, Query(description="Filter by crop category")] = None,
    search: Annotated[str | None, Query(description="Search crop by name")] = None,
) -> list[CommodityResponse]:
    return list_commodities(db, category=category, search=search)
