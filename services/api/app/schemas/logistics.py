from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.entities import ShipmentStatus, StorageType, VehicleTypeEnum
from app.schemas.marketplace import LocationCreate, LocationResponse


# --- Vehicle ---
class VehicleCreate(BaseModel):
    registration_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
    vehicle_type: VehicleTypeEnum = VehicleTypeEnum.MINI_TRUCK
    model_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    payload_capacity_kg: Annotated[Decimal, Field(gt=0)]
    volumetric_capacity_cbm: Annotated[Decimal, Field(gt=0)] | None = None
    is_refrigerated: bool = False
    temp_min_celsius: Decimal | None = None
    temp_max_celsius: Decimal | None = None
    is_available: bool = True


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_id: UUID
    registration_number: str | None = None
    vehicle_type: VehicleTypeEnum
    model_name: str | None = None
    payload_capacity_kg: Decimal
    volumetric_capacity_cbm: Decimal | None = None
    is_refrigerated: bool
    temp_min_celsius: Decimal | None = None
    temp_max_celsius: Decimal | None = None
    is_available: bool
    created_at: datetime


# --- Rate Card ---
class TransportRateCardCreate(BaseModel):
    vehicle_type: VehicleTypeEnum
    base_fare: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    per_km_rate: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    min_distance_km: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    reefer_surcharge_per_km: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    loading_unloading_charge: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    valid_from: date = Field(default_factory=date.today)
    valid_to: date | None = None


class TransportRateCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_id: UUID
    vehicle_type: VehicleTypeEnum
    base_fare: Decimal
    per_km_rate: Decimal
    min_distance_km: Decimal
    reefer_surcharge_per_km: Decimal
    loading_unloading_charge: Decimal
    valid_from: date
    valid_to: date | None = None
    is_active: bool
    created_at: datetime


# --- Logistics Provider ---
class LogisticsProviderCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]
    registered_transporter_profile_id: UUID | None = None
    primary_location: LocationCreate | None = None
    primary_location_id: UUID | None = None
    operating_scope: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = "regional"
    has_cold_chain: bool = False
    contact_phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
    contact_email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)] | None = None
    vehicles: list[VehicleCreate] | None = None
    rate_cards: list[TransportRateCardCreate] | None = None


class LogisticsProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    registered_transporter_profile_id: UUID | None = None
    primary_location: LocationResponse | None = None
    operating_scope: str
    has_cold_chain: bool
    contact_phone: str | None = None
    contact_email: str | None = None
    is_active: bool
    vehicles: list[VehicleResponse] = []
    rate_cards: list[TransportRateCardResponse] = []
    created_at: datetime


# --- Historical Infrastructure Records (Isolated from active logistics) ---
class HistoricalInfrastructureRecordCreate(BaseModel):
    external_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]
    lead_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
    commodity_sector: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
    district_area: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    state: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = "Maharashtra"
    coverage_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    location_granularity: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    evidence_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
    government_project_status: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    evidence_date: date | None = None
    current_service_status: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = "Unknown"
    verification_status: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = "Historical infrastructure evidence"
    location: LocationCreate | None = None
    location_id: UUID | None = None
    notes: str | None = None


class HistoricalInfrastructureRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    name: str
    lead_type: str
    commodity_sector: str
    district_area: str | None = None
    state: str
    coverage_label: str | None = None
    location_granularity: str | None = None
    evidence_type: str
    government_project_status: str | None = None
    evidence_date: date | None = None
    current_service_status: str
    verification_status: str
    location: LocationResponse | None = None
    notes: str | None = None
    created_at: datetime


# --- Storage Facility ---
class StorageFacilityCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]
    facility_type: StorageType = StorageType.DRY_WAREHOUSE
    location: LocationCreate | None = None
    location_id: UUID | None = None
    operator_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    total_capacity_mt: Annotated[Decimal, Field(gt=0)]
    available_capacity_mt: Annotated[Decimal, Field(ge=0)]
    is_cold_chain: bool = False
    temp_min_celsius: Decimal | None = None
    temp_max_celsius: Decimal | None = None
    humidity_controlled: bool = False
    daily_rate_per_mt: Annotated[Decimal, Field(ge=0)] | None = None


class StorageFacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    facility_type: StorageType
    location: LocationResponse
    operator_name: str | None = None
    total_capacity_mt: Decimal
    available_capacity_mt: Decimal
    is_cold_chain: bool
    temp_min_celsius: Decimal | None = None
    temp_max_celsius: Decimal | None = None
    humidity_controlled: bool
    daily_rate_per_mt: Decimal | None = None
    is_active: bool
    created_at: datetime


# --- Collection Centre ---
class CollectionCentreCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]
    location: LocationCreate | None = None
    location_id: UUID | None = None
    operator_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    has_grading_line: bool = False
    has_precooling: bool = False
    weighbridge_capacity_mt: Annotated[Decimal, Field(gt=0)] | None = None
    max_throughput_mt_day: Annotated[Decimal, Field(gt=0)] | None = None


class CollectionCentreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    location: LocationResponse
    operator_name: str | None = None
    has_grading_line: bool
    has_precooling: bool
    weighbridge_capacity_mt: Decimal | None = None
    max_throughput_mt_day: Decimal | None = None
    is_active: bool
    created_at: datetime


# --- Shipment & Tracking ---
class ShipmentEventCreate(BaseModel):
    event_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
    location_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    notes: str | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShipmentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shipment_id: UUID
    event_type: str
    location_name: str | None = None
    notes: str | None = None
    recorded_at: datetime


class ShipmentCreate(BaseModel):
    order_id: UUID | None = None
    shipment_plan_id: UUID | None = None
    vehicle_id: UUID | None = None
    provider_id: UUID | None = None
    origin_location: LocationCreate | None = None
    origin_location_id: UUID | None = None
    destination_location: LocationCreate | None = None
    destination_location_id: UUID | None = None
    storage_facility_id: UUID | None = None
    collection_centre_id: UUID | None = None
    scheduled_pickup_at: datetime | None = None
    estimated_arrival_at: datetime | None = None
    estimated_cost: Annotated[Decimal, Field(ge=0)] | None = None
    driver_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] | None = None
    driver_phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID | None = None
    shipment_plan_id: UUID | None = None
    vehicle_id: UUID | None = None
    provider_id: UUID | None = None
    origin_location: LocationResponse
    destination_location: LocationResponse
    storage_facility_id: UUID | None = None
    collection_centre_id: UUID | None = None
    status: ShipmentStatus
    scheduled_pickup_at: datetime | None = None
    actual_pickup_at: datetime | None = None
    estimated_arrival_at: datetime | None = None
    actual_arrival_at: datetime | None = None
    estimated_cost: Decimal | None = None
    actual_cost: Decimal | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    events: list[ShipmentEventResponse] = []
    created_at: datetime
