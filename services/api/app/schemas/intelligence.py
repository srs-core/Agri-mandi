from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.entities import BuyerType, CommodityCategory
from app.schemas.marketplace import LocationCreate, LocationResponse


class BuyerPreferredCommodityCreate(BaseModel):
    commodity_id: UUID
    min_quality_grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    typical_volume_quintals: Annotated[Decimal, Field(gt=0)] | None = None
    max_price_per_unit: Annotated[Decimal, Field(ge=0)] | None = None


class BuyerPreferredCommodityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    commodity_id: UUID
    commodity_name: str
    commodity_category: CommodityCategory
    min_quality_grade: str | None = None
    typical_volume_quintals: Decimal | None = None
    max_price_per_unit: Decimal | None = None


class BuyerPreferredCategoryCreate(BaseModel):
    category: CommodityCategory
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None


class BuyerPreferredCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: CommodityCategory
    notes: str | None = None


class BuyerDirectoryCreate(BaseModel):
    external_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    business_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]
    buyer_type: BuyerType = BuyerType.WHOLESALER
    location: LocationCreate | None = None
    location_id: UUID | None = None
    contact_person: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    contact_phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
    contact_email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)] | None = None
    procurement_radius_km: Annotated[Decimal, Field(ge=0)] | None = None
    daily_capacity_mt: Annotated[Decimal, Field(gt=0)] | None = None
    typical_payment_terms: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    notes: str | None = None
    preferred_commodities: list[BuyerPreferredCommodityCreate] | None = None
    preferred_categories: list[BuyerPreferredCategoryCreate] | None = None


class BuyerDirectoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str | None = None
    business_name: str
    buyer_type: BuyerType
    location: LocationResponse
    registered_buyer_profile_id: UUID | None = None
    contact_person: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    procurement_radius_km: Decimal | None = None
    daily_capacity_mt: Decimal | None = None
    typical_payment_terms: str | None = None
    notes: str | None = None
    is_active: bool
    preferred_commodities: list[BuyerPreferredCommodityResponse] = []
    preferred_categories: list[BuyerPreferredCategoryResponse] = []
    created_at: datetime


class MarketPriceRecordCreate(BaseModel):
    commodity_id: UUID
    market_location: LocationCreate | None = None
    market_location_id: UUID | None = None
    data_source_id: UUID | None = None
    price_date: date = Field(default_factory=date.today)
    variety: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    raw_commodity_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    raw_market_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    min_price: Annotated[Decimal, Field(ge=0)] | None = None
    max_price: Annotated[Decimal, Field(ge=0)] | None = None
    modal_price: Annotated[Decimal, Field(ge=0)]
    price_unit: str = "Rs/quintal"
    arrivals_quantity: Annotated[Decimal, Field(ge=0)] | None = None
    arrivals_unit: str = "quintal"


class MarketPriceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    commodity_id: UUID
    commodity_name: str
    commodity_category: CommodityCategory
    market_location: LocationResponse
    data_source_id: UUID | None = None
    price_date: date
    variety: str | None = None
    grade: str | None = None
    raw_commodity_name: str | None = None
    raw_market_name: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    modal_price: Decimal
    price_unit: str
    arrivals_quantity: Decimal | None = None
    arrivals_unit: str
    created_at: datetime


class PriceForecastRequest(BaseModel):
    commodity: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)] = Field(
        ..., description="Standardized commodity name, e.g. 'Potato (Jyoti)' or 'Onion (Nashik Red)'"
    )
    market: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)] = Field(
        ..., description="APMC market name, e.g. 'Pune APMC (Gultekdi)' or 'Lasalgaon APMC'"
    )
    horizon: str = Field(
        default="t+1", description="Forecasting horizon: 't+1' (Next-Day, Production Enabled), 't+3', 't+7'"
    )
    reference_date: date | None = Field(
        default=None, description="Prediction date t (defaults to today)"
    )
    current_modal_price: Annotated[Decimal, Field(ge=0)] | None = Field(
        default=None, description="Optional current observed price override"
    )


class EmpiricalPredictionInterval(BaseModel):
    lower_bound: Decimal
    upper_bound: Decimal
    nominal_coverage_pct: float = 80.0
    historical_test_coverage_pct: float
    uncertainty_label: str = "80% Empirical Prediction Interval (Derived from Validation Residuals)"


class PriceForecastResponse(BaseModel):
    status: str = Field(..., description="'SUCCESS' for enabled models, 'RESTRICTED' for offline/multi-day models")
    commodity: str
    market: str
    horizon: str
    forecast_date: date
    predicted_modal_price: Decimal | None = None
    expected_return_pct: float | None = None
    empirical_prediction_interval: EmpiricalPredictionInterval | None = None
    price_unit: str = "Rs/quintal"
    model_version: str
    model_type: str
    rmse_improvement_over_baseline_pct: float | None = None
    disclaimer: str
    quality_gate_notice: str | None = None


class ForecastModelMetadataResponse(BaseModel):
    active_models: list[dict[str, object]]
    production_enabled_crops: list[str]
    production_enabled_horizons: list[str]
    offline_restricted_models: list[str]
    quality_gate_verdict: str


class LogisticsDeductionBreakdown(BaseModel):
    distance_km: Decimal
    vehicle_type: str
    base_fare: Decimal
    distance_charge: Decimal
    reefer_surcharge: Decimal
    loading_unloading_charge: Decimal
    total_transport_cost: Decimal
    cost_per_quintal: Decimal
    cost_certainty: str = Field(
        default="MODELED_REGIONAL_ESTIMATE",
        description="'VERIFIED_TRANSPORTER_QUOTE', 'MODELED_REGIONAL_ESTIMATE', or 'UNAVAILABLE'"
    )
    is_verified_quote: bool = False
    rate_source: str
    provider_name: str | None = None
    disclaimer: str
    explanation: str


class ForecastPriceReference(BaseModel):
    is_forecast_available: bool
    forecast_horizon: str | None = None
    predicted_price_per_quintal: Decimal | None = None
    interval_lower_bound: Decimal | None = None
    interval_upper_bound: Decimal | None = None
    interval_coverage_pct: float | None = None
    quality_gate_status: str = Field(
        default="APPROVED_TIER_1_MODEL",
        description="'APPROVED_TIER_1_MODEL' or 'UNSUPPORTED_OFFLINE'"
    )
    model_version: str
    pricing_source: str


class EconomicOptionBreakdown(BaseModel):
    buyer_id: UUID
    business_name: str
    buyer_type: str
    source_type: str
    buyer_provenance: str = Field(
        default="RESEARCHED_DIRECTORY_RECORD",
        description="'REGISTERED_VERIFIED_BUYER', 'RESEARCHED_DIRECTORY_RECORD', or 'PUBLIC_DIRECTORY_LISTING'"
    )
    is_platform_registered: bool = False
    destination_name: str
    destination_district: str | None = None
    road_distance_km: Decimal
    expected_unit_price: Decimal
    pricing_source: str
    gross_selling_value: Decimal
    logistics_deduction: LogisticsDeductionBreakdown
    expected_net_realization: Decimal
    net_realization_per_quintal: Decimal
    net_realization_certainty: str = Field(
        default="CONDITIONAL_ESTIMATE",
        description="'VERIFIED_QUOTE', 'CONDITIONAL_ESTIMATE', or 'UNAVAILABLE'"
    )
    is_net_realization_estimated: bool = True
    match_score: Decimal
    is_eligible: bool
    is_economically_viable: bool
    verified_facts: list[str] = Field(default_factory=list, description="Explicit facts verified against database")
    modeled_estimates: list[str] = Field(default_factory=list, description="Modeled/inferred economic and transport estimates")
    uncertainties_and_cautions: list[str] = Field(default_factory=list, description="Explicit cautions regarding unverified rates or offline buyer records")
    reasoning_checklist: list[str] = Field(default_factory=list, description="Combined farmer-facing explanation checklist")


class BuyerRecommendationRequest(BaseModel):
    commodity_id: UUID | None = None
    commodity_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    quantity_quintals: Annotated[Decimal, Field(gt=0)] = Field(..., description="Produce quantity in quintals")
    quality_grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    pickup_location_id: UUID | None = None
    pickup_location_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    availability_date: date | None = None


class BuyerRecommendationResponse(BaseModel):
    status: str = Field(..., description="'SUCCESS' or 'NO_ELIGIBLE_BUYER_MATCH'")
    commodity_name: str
    quantity_quintals: Decimal
    quality_grade: str | None = None
    pickup_location_name: str
    recommended_option: EconomicOptionBreakdown | None = None
    alternative_options: list[EconomicOptionBreakdown] = []
    forecast_reference: ForecastPriceReference
    fallback_reason: str | None = None
    data_trust_notice: str = Field(
        default="Economic recommendations distinguish verified platform data from modeled regional estimates and offline research directory records.",
        description="Data trust and economic realism disclaimer"
    )
    explanation: list[str] = []



