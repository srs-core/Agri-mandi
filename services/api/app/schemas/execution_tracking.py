from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.entities import CheckpointStatus, CheckpointType, ShipmentStatus
from app.schemas.logistics import ShipmentEventResponse


class ShipmentCheckpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shipment_id: UUID
    checkpoint_type: CheckpointType
    stop_sequence: int
    pickup_stop_id: UUID | None = None
    location_id: UUID
    location_name: str
    seller_user_id: UUID | None = None
    seller_name: str | None = None
    status: CheckpointStatus
    planned_quantity_quintals: Decimal
    loaded_quantity_quintals: Decimal | None = None
    variance_quintals: Decimal | None = None
    variance_reason: str | None = None
    arrived_at: datetime | None = None
    loading_started_at: datetime | None = None
    loading_completed_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class CheckpointArriveRequest(BaseModel):
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class CheckpointLoadingRequest(BaseModel):
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class CheckpointCompleteRequest(BaseModel):
    loaded_quantity_quintals: Annotated[Decimal, Field(gt=0)]
    variance_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class TransitStartRequest(BaseModel):
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class DestinationArriveRequest(BaseModel):
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class DeliveryCompleteRequest(BaseModel):
    delivered_quantity_quintals: Annotated[Decimal, Field(gt=0)]
    receiver_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    variance_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    delivery_notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class ShipmentExceptionRequest(BaseModel):
    checkpoint_id: UUID | None = None
    exception_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class ShipmentExecutionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID | None = None
    plan_code: str | None = None
    order_id: UUID | None = None
    status: ShipmentStatus
    commodity_name: str | None = None
    total_planned_quantity_quintals: Decimal
    total_picked_up_quantity_quintals: Decimal
    delivered_quantity_quintals: Decimal | None = None
    progress_percentage: float
    current_checkpoint_sequence: int
    total_checkpoints_count: int
    completed_checkpoints_count: int
    vehicle_id: UUID | None = None
    vehicle_model: str | None = None
    vehicle_reg_number: str | None = None
    transporter_name: str | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    origin_location_name: str | None = None
    destination_location_name: str | None = None
    delivery_variance_reason: str | None = None
    receiver_name: str | None = None
    delivery_notes: str | None = None
    checkpoints: list[ShipmentCheckpointResponse] = []
    timeline: list[ShipmentEventResponse] = []
    created_at: datetime
    updated_at: datetime
