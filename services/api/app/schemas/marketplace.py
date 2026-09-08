from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.models.entities import (
    BuyerRequirementStatus,
    CommodityCategory,
    OfferStatus,
    OrderStatus,
    ProduceLotStatus,
    RoleName,
    VerificationStatus,
)


class LocationCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    village: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    taluka: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    district: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    state: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    country_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2)] = "IN"
    postal_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=16)] | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class LocationResponse(BaseModel):
    id: UUID
    name: str
    village: str | None = None
    taluka: str | None = None
    district: str | None = None
    state: str
    country_code: str = "IN"
    postal_code: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class CommodityResponse(BaseModel):
    id: UUID
    name: str
    category: CommodityCategory
    default_unit: str
    is_perishable: bool
    storage_guidance: str | None = None
    is_active: bool


class UserProfileResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    phone_number: str | None = None
    roles: list[str]
    status: str
    farm_name: str | None = None
    land_area_hectares: Decimal | None = None
    legal_name: str | None = None
    registration_number: str | None = None
    organization_name: str | None = None
    gstin: str | None = None
    verification_status: VerificationStatus
    primary_location: LocationResponse | None = None


class ProfileUpdateRequest(BaseModel):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)] | None = None
    phone_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=32)] | None = None
    farm_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    land_area_hectares: Decimal | None = None
    legal_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    registration_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = None
    organization_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    gstin: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
    primary_location: LocationCreate | None = None


class ProduceLotContributionCreate(BaseModel):
    farmer_profile_id: UUID | None = None
    fpo_profile_id: UUID | None = None
    contributed_quantity: Annotated[Decimal, Field(gt=0)]


class ProduceLotContributionResponse(BaseModel):
    id: UUID
    farmer_profile_id: UUID | None = None
    fpo_profile_id: UUID | None = None
    contributed_quantity: Decimal


class ProduceLotCreate(BaseModel):
    commodity_id: UUID
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]
    available_quantity: Annotated[Decimal, Field(gt=0)]
    unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24)] = "kg"
    quality_grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    quality_notes: str | None = None
    asking_price_per_unit: Annotated[Decimal, Field(ge=0)] | None = None
    available_from: date = Field(default_factory=date.today)
    available_until: date | None = None
    pickup_location: LocationCreate | None = None
    pickup_location_id: UUID | None = None
    is_aggregated: bool = False
    contributions: list[ProduceLotContributionCreate] | None = None


class ProduceLotUpdateRequest(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)] | None = None
    available_quantity: Annotated[Decimal, Field(gt=0)] | None = None
    asking_price_per_unit: Annotated[Decimal, Field(ge=0)] | None = None
    available_from: date | None = None
    available_until: date | None = None
    quality_grade: str | None = None
    quality_notes: str | None = None
    status: ProduceLotStatus | None = None


class ProduceLotSummaryResponse(BaseModel):
    id: UUID
    seller_user_id: UUID
    seller_name: str
    seller_role: str
    seller_verification_status: VerificationStatus
    commodity_id: UUID
    commodity_name: str
    commodity_category: CommodityCategory
    title: str
    available_quantity: Decimal
    unit: str
    quality_grade: str | None = None
    quality_notes: str | None = None
    asking_price_per_unit: Decimal | None = None
    price_mode: str = "FIXED_PRICE"
    available_from: date
    available_until: date | None = None
    is_aggregated: bool
    status: ProduceLotStatus
    pickup_location: LocationResponse | None = None
    contributions_count: int = 0
    created_at: datetime


class ProduceLotDetailResponse(ProduceLotSummaryResponse):
    seller_phone: str | None = None
    seller_email: str | None = None
    contributions: list[ProduceLotContributionResponse] = []


class MarketplaceProduceLotsResponse(BaseModel):
    items: list[ProduceLotSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BuyerRequirementCreate(BaseModel):
    commodity_id: UUID
    required_quantity: Annotated[Decimal, Field(gt=0)]
    unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24)] = "kg"
    minimum_quality_grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    target_price_per_unit: Annotated[Decimal, Field(ge=0)] | None = None
    delivery_by: date | None = None
    delivery_location: LocationCreate | None = None
    delivery_location_id: UUID | None = None


class BuyerRequirementUpdateRequest(BaseModel):
    required_quantity: Annotated[Decimal, Field(gt=0)] | None = None
    target_price_per_unit: Annotated[Decimal, Field(ge=0)] | None = None
    delivery_by: date | None = None
    minimum_quality_grade: str | None = None
    status: BuyerRequirementStatus | None = None


class BuyerRequirementResponse(BaseModel):
    id: UUID
    buyer_user_id: UUID
    buyer_name: str
    buyer_organization: str | None = None
    buyer_verification_status: VerificationStatus
    commodity_id: UUID
    commodity_name: str
    commodity_category: CommodityCategory
    required_quantity: Decimal
    unit: str
    minimum_quality_grade: str | None = None
    target_price_per_unit: Decimal | None = None
    delivery_by: date | None = None
    delivery_location: LocationResponse | None = None
    status: BuyerRequirementStatus
    created_at: datetime


class OfferCreate(BaseModel):
    produce_lot_id: UUID
    buyer_requirement_id: UUID | None = None
    offered_quantity: Annotated[Decimal, Field(gt=0)]
    offered_price_per_unit: Annotated[Decimal, Field(gt=0)]
    notes: str | None = None
    expires_at: datetime | None = None


class CounterOfferCreate(BaseModel):
    price_per_unit: Annotated[Decimal, Field(gt=0)]
    quantity: Annotated[Decimal | None, Field(gt=0)] = None
    notes: str | None = None


class NegotiationProposalResponse(BaseModel):
    id: UUID
    proposer_user_id: UUID
    proposer_name: str
    proposer_role: str
    price_per_unit: Decimal
    quantity: Decimal
    total_amount: Decimal
    notes: str | None = None
    status_at_step: str
    created_at: datetime


class OfferResponse(BaseModel):
    id: UUID
    produce_lot_id: UUID
    produce_title: str
    commodity_name: str
    buyer_user_id: UUID
    buyer_name: str
    seller_user_id: UUID
    seller_name: str
    offered_quantity: Decimal
    unit: str
    offered_price_per_unit: Decimal
    current_price_per_unit: Decimal
    current_quantity: Decimal
    total_amount: Decimal
    price_mode: str = "FIXED_PRICE"
    current_proposer_user_id: UUID
    current_proposer_name: str
    current_proposer_role: str
    response_required_from_user_id: UUID
    response_required_from_name: str | None = None
    expires_at: datetime | None = None
    status: OfferStatus
    history: list[NegotiationProposalResponse] = []
    created_at: datetime


class OrderItemResponse(BaseModel):
    id: UUID
    produce_lot_id: UUID
    commodity_id: UUID
    commodity_name: str
    quantity: Decimal
    unit: str
    agreed_price_per_unit: Decimal
    total_item_amount: Decimal


class OrderResponse(BaseModel):
    id: UUID
    buyer_user_id: UUID
    buyer_name: str
    seller_user_id: UUID
    seller_name: str
    accepted_offer_id: UUID | None = None
    status: OrderStatus
    total_amount: Decimal
    confirmed_at: datetime | None = None
    delivery_location: LocationResponse | None = None
    items: list[OrderItemResponse]
    created_at: datetime


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus


class VerificationReviewRequest(BaseModel):
    status: VerificationStatus
    reviewer_notes: str | None = None


class VerificationRequestResponse(BaseModel):
    id: UUID
    requested_by_user_id: UUID | None = None
    user_name: str
    user_email: str
    user_role: str
    subject_type: str
    subject_id: UUID
    status: VerificationStatus
    document_reference: str | None = None
    reviewer_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class VerificationCreateRequest(BaseModel):
    document_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2048)] | None = None


class PlatformMetricsResponse(BaseModel):
    total_users: int
    total_farmers: int
    total_fpos: int
    total_buyers: int
    total_commodities: int
    active_produce_lots: int
    active_buyer_requirements: int
    total_offers: int
    pending_offers: int
    confirmed_orders: int
    total_gmv: Decimal
    pending_verifications: int


class AuditEventResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None = None
    event_type: str
    entity_type: str
    entity_id: UUID | None = None
    metadata_json: dict[str, Any] | None = None
    ip_address: str | None = None
    created_at: datetime


class NotificationResponse(BaseModel):
    id: UUID
    notification_type: str
    title: str
    body: str
    data_json: dict[str, Any] | None = None
    read_at: datetime | None = None
    created_at: datetime
