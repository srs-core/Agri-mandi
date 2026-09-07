from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.models.entities import (
    QuoteStatus,
    TransportOpportunityStatus,
    VehicleTypeEnum,
    VerificationStatus,
)
from app.schemas.route_planning import RouteWaypoint


# ==========================================
# TRANSPORTER PROFILE SCHEMAS
# ==========================================

class TransporterProfileUpdate(BaseModel):
    organization_name: Optional[str] = Field(None, min_length=2, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=32)
    contact_email: Optional[str] = Field(None, max_length=320)
    service_area_districts: Optional[list[str]] = Field(None, description="Districts served by the transporter")
    preferred_commodities: Optional[list[str]] = Field(None, description="Commodities preferred for freight")
    operational_status: Optional[str] = Field(None, description="'active', 'inactive', 'suspended'")


class TransporterProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    organization_name: str
    verification_status: VerificationStatus
    operational_status: str
    service_area_districts: Optional[list[str]] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    preferred_commodities: Optional[list[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==========================================
# VEHICLE SCHEMAS
# ==========================================

class TransporterVehicleCreate(BaseModel):
    registration_number: Optional[str] = Field(None, max_length=32, description="Vehicle registration number (user-supplied)")
    vehicle_type: VehicleTypeEnum = Field(default=VehicleTypeEnum.MINI_TRUCK)
    model_name: Optional[str] = Field(None, max_length=120)
    payload_capacity_kg: Decimal = Field(..., gt=0, description="Payload capacity in kilograms")
    volumetric_capacity_cbm: Optional[Decimal] = Field(None, gt=0)
    is_refrigerated: bool = Field(default=False)
    temp_min_celsius: Optional[Decimal] = None
    temp_max_celsius: Optional[Decimal] = None
    is_available: bool = Field(default=True)
    operational_status: str = Field(default="available", description="'available', 'busy', 'maintenance', 'inactive'")


class TransporterVehicleUpdate(BaseModel):
    registration_number: Optional[str] = Field(None, max_length=32)
    model_name: Optional[str] = Field(None, max_length=120)
    payload_capacity_kg: Optional[Decimal] = Field(None, gt=0)
    volumetric_capacity_cbm: Optional[Decimal] = Field(None, gt=0)
    is_refrigerated: Optional[bool] = None
    temp_min_celsius: Optional[Decimal] = None
    temp_max_celsius: Optional[Decimal] = None
    is_available: Optional[bool] = None
    operational_status: Optional[str] = None


class TransporterVehicleResponse(BaseModel):
    id: UUID
    provider_id: UUID
    registration_number: Optional[str] = None
    vehicle_type: VehicleTypeEnum
    model_name: Optional[str] = None
    payload_capacity_kg: Decimal
    volumetric_capacity_cbm: Optional[Decimal] = None
    is_refrigerated: bool
    temp_min_celsius: Optional[Decimal] = None
    temp_max_celsius: Optional[Decimal] = None
    is_available: bool
    operational_status: str
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def payload_capacity_quintals(self) -> Decimal:
        return Decimal(str(round(float(self.payload_capacity_kg) / 100.0, 2)))

    @computed_field
    @property
    def payload_capacity_tonnes(self) -> Decimal:
        return Decimal(str(round(float(self.payload_capacity_kg) / 1000.0, 2)))

    model_config = {"from_attributes": True}


# ==========================================
# TRANSPORT OPPORTUNITY SCHEMAS
# ==========================================

class TransportOpportunityResponse(BaseModel):
    id: UUID
    shipment_plan_id: Optional[UUID] = None
    shipment_id: Optional[UUID] = None
    transporter_profile_id: UUID
    status: TransportOpportunityStatus
    required_vehicle_class: str
    required_payload_quintals: Decimal
    requires_cold_chain: bool
    pickup_stops_count: int
    origin_district: str
    destination_district: str
    total_distance_km: Decimal
    distance_certainty: str
    estimated_cost: Decimal
    cost_certainty: str
    earliest_pickup_date: date
    delivery_deadline: Optional[date] = None
    eligibility_score: Decimal
    matching_criteria_json: Optional[dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    decline_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def required_payload_tonnes(self) -> Decimal:
        return Decimal(str(round(float(self.required_payload_quintals) / 10.0, 3)))

    model_config = {"from_attributes": True}


class TransportOpportunityDetailResponse(TransportOpportunityResponse):
    plan_code: Optional[str] = None
    commodity_name: Optional[str] = None
    buyer_organization_name: Optional[str] = None
    waypoints: list[RouteWaypoint] = []
    vehicle_options: list[TransporterVehicleResponse] = []
    my_quotes: list[TransporterQuoteResponse] = []
    lineage_summary: Optional[dict[str, Any]] = None


class OpportunityAcceptRequest(BaseModel):
    vehicle_id: UUID = Field(..., description="ID of the transporter's registered vehicle to assign to this shipment")
    driver_name: Optional[str] = Field(None, max_length=160)
    driver_phone: Optional[str] = Field(None, max_length=32)
    notes: Optional[str] = None


class OpportunityDeclineRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Reason for declining the opportunity")


# ==========================================
# TRANSPORTER QUOTE SCHEMAS
# ==========================================

class TransporterQuoteCreate(BaseModel):
    vehicle_id: Optional[UUID] = None
    quote_amount: Decimal = Field(..., gt=0, description="Total quoted freight amount in INR")
    quote_unit: str = Field(default="INR_TOTAL", description="'INR_TOTAL', 'INR_PER_QUINTAL', 'INR_PER_KM'")
    currency: str = Field(default="INR")
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None


class TransporterQuoteResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    transporter_profile_id: UUID
    vehicle_id: Optional[UUID] = None
    quote_amount: Decimal
    quote_unit: str
    currency: str
    status: QuoteStatus
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None
    quote_certainty: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==========================================
# TRANSPORTER ME / DASHBOARD SUMMARY
# ==========================================

class TransporterMeResponse(BaseModel):
    profile: TransporterProfileResponse
    provider_id: Optional[UUID] = None
    provider_name: Optional[str] = None
    total_vehicles_count: int
    available_vehicles_count: int
    open_opportunities_count: int
    active_shipments_count: int
    delivered_shipments_count: int


# ==========================================
# BROADCAST / OPPORTUNITY DISPATCH SCHEMAS
# ==========================================

class BroadcastOpportunitiesRequest(BaseModel):
    plan_id: UUID
    force_rebroadcast: bool = Field(default=False)


class BroadcastOpportunitiesResponse(BaseModel):
    plan_id: UUID
    plan_code: str
    opportunities_created_count: int
    matched_transporters_count: int
    opportunities: list[TransportOpportunityResponse]
