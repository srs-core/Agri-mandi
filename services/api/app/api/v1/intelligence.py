from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID


from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import CommodityCategory
from app.modules.intelligence.service import (
    get_buyer_directory_entry,
    list_buyer_directory_entries,
    list_market_prices,
)
from app.schemas.aggregation import (
    AggregationBatchResponse,
    AggregationOpportunityResponse,
    AggregationScanRequest,
)
from app.schemas.intelligence import (
    BuyerDirectoryResponse,
    BuyerRecommendationRequest,
    BuyerRecommendationResponse,
    ForecastModelMetadataResponse,
    MarketPriceRecordResponse,
    PriceForecastRequest,
    PriceForecastResponse,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])



@router.get("/buyers", response_model=list[BuyerDirectoryResponse], summary="List researched and directory market buyers")
def get_buyer_directory(
    db: Annotated[Session, Depends(get_db)],
    commodity_id: UUID | None = None,
    category: CommodityCategory | None = None,
    taluka: str | None = None,
    district: str | None = None,
) -> list[BuyerDirectoryResponse]:
    return list_buyer_directory_entries(
        db,
        commodity_id=commodity_id,
        category=category,
        taluka=taluka,
        district=district,
    )


@router.get("/buyers/{entry_id}", response_model=BuyerDirectoryResponse, summary="Get buyer directory details")
def get_buyer_directory_detail(
    entry_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> BuyerDirectoryResponse:
    return get_buyer_directory_entry(db, entry_id)


@router.get("/market-prices", response_model=list[MarketPriceRecordResponse], summary="List historical/APMC market price arrival records")
def get_market_prices(
    db: Annotated[Session, Depends(get_db)],
    commodity_id: UUID | None = None,
    market_location_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[MarketPriceRecordResponse]:
    return list_market_prices(
        db,
        commodity_id=commodity_id,
        market_location_id=market_location_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("/forecast/price", response_model=PriceForecastResponse, summary="Forecast next-day market modal price with empirical prediction intervals")
def post_price_forecast(
    request: PriceForecastRequest
) -> PriceForecastResponse:
    from app.modules.intelligence.forecast_service import forecast_engine
    return forecast_engine.forecast_price(request)


@router.get("/forecast/models", response_model=ForecastModelMetadataResponse, summary="Get metadata of active and restricted forecasting models")
def get_forecast_models() -> ForecastModelMetadataResponse:
    from app.modules.intelligence.forecast_service import forecast_engine
    return forecast_engine.get_models_metadata()


@router.post("/recommendation", response_model=BuyerRecommendationResponse, summary="Generate economically optimized buyer recommendation with net realization")
def post_buyer_recommendation(
    request: BuyerRecommendationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> BuyerRecommendationResponse:
    from app.modules.intelligence.decision_engine import evaluate_produce_decision
    return evaluate_produce_decision(db, request)


@router.post("/aggregation/opportunities", response_model=AggregationBatchResponse, summary="Scan and discover multi-farmer supply aggregation opportunities for active buyer requirements")
def post_aggregation_opportunities(
    db: Annotated[Session, Depends(get_db)],
    request: AggregationScanRequest | None = None,
) -> AggregationBatchResponse:
    from app.modules.intelligence.aggregation_engine import scan_aggregation_opportunities
    return scan_aggregation_opportunities(db, request=request)


@router.get("/aggregation/requirements/{requirement_id}", response_model=AggregationOpportunityResponse, summary="Evaluate multi-farmer supply aggregation for a specific buyer requirement")
def get_requirement_aggregation(
    requirement_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    max_cluster_radius_km: Decimal = Query(default=Decimal("50.0"), ge=Decimal("5.0"), le=Decimal("200.0")),
) -> AggregationOpportunityResponse:
    from fastapi import HTTPException, status
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.entities import BuyerRequirement
    from app.modules.intelligence.aggregation_engine import evaluate_single_requirement_aggregation

    requirement = db.scalar(
        select(BuyerRequirement)
        .options(
            joinedload(BuyerRequirement.buyer_profile),
            joinedload(BuyerRequirement.delivery_location),
            joinedload(BuyerRequirement.commodity),
        )
        .where(BuyerRequirement.id == requirement_id)
    )
    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Buyer requirement '{requirement_id}' not found.",
        )

    return evaluate_single_requirement_aggregation(
        db=db,
        requirement=requirement,
        max_cluster_radius_km=max_cluster_radius_km,
    )



