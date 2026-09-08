from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlannedLotAllocation(BaseModel):
    """Specific lot and allocated quantity submitted for shipment planning."""
    produce_lot_id: UUID
    allocated_quantity: Decimal = Field(..., gt=0, description="Quantity to allocate from this produce lot")
    unit: str = Field(default="quintal", description="Unit of allocated quantity (kg, quintal, tonnes)")


class ShipmentPlanFromRequirementRequest(BaseModel):
    """Request to create a shipment plan fulfilling an active Buyer Requirement."""
    buyer_requirement_id: UUID
    aggregation_opportunity_id: Optional[str] = None
    lot_allocations: List[PlannedLotAllocation] = Field(..., min_length=1, description="List of contributing produce lots and quantities")
    earliest_pickup_date: Optional[date] = None


class ShipmentPlanFromOrderRequest(BaseModel):
    """Request to create a shipment plan from an existing confirmed Order."""
    order_id: UUID
    earliest_pickup_date: Optional[date] = None


class ShipmentPlanContributorResponse(BaseModel):
    """Lineage object for each contributing lot allocation."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    produce_lot_id: UUID
    seller_user_id: UUID
    fpo_member_id: Optional[UUID] = None
    lot_allocated_quantity_quintals: Decimal
    asking_price_per_quintal: Optional[Decimal] = None
    quality_grade: Optional[str] = None
    notes: Optional[str] = None


class ShipmentPlanPickupStopResponse(BaseModel):
    """Representation of an individual farm/depot pickup stop."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stop_sequence: int
    seller_user_id: UUID
    seller_name: str
    seller_role: str
    pickup_location_id: UUID
    pickup_location_name: Optional[str] = None
    pickup_district: Optional[str] = None
    pickup_state: str = "Maharashtra"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    allocated_quantity_quintals: Decimal
    earliest_pickup_date: date
    latest_pickup_date: Optional[date] = None
    is_exact_gps: bool = True
    contributors: List[ShipmentPlanContributorResponse] = Field(default_factory=list)


class ShipmentPlanResponse(BaseModel):
    """Complete Shipment Plan response model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_code: str
    planning_status: str
    buyer_requirement_id: Optional[UUID] = None
    order_id: Optional[UUID] = None
    aggregation_opportunity_id: Optional[str] = None
    buyer_user_id: Optional[UUID] = None
    buyer_name: Optional[str] = None
    buyer_organization_name: Optional[str] = None
    commodity_id: UUID
    commodity_name: Optional[str] = None
    variety: Optional[str] = None
    quality_grade: Optional[str] = None
    total_planned_quantity_quintals: Decimal
    destination_location_id: UUID
    destination_location_name: Optional[str] = None
    destination_district: Optional[str] = None
    destination_state: str = "Maharashtra"
    destination_latitude: Optional[float] = None
    destination_longitude: Optional[float] = None
    earliest_pickup_date: date
    delivery_deadline: Optional[date] = None
    estimated_gross_merchandise_value: Optional[Decimal] = None
    is_geographic_distance_exact: bool = True
    geographic_precision_notes: Optional[str] = None
    economic_disclaimer: str
    pickup_stops: List[ShipmentPlanPickupStopResponse] = Field(default_factory=list)
    total_stops_count: int = 0
    total_contributors_count: int = 0
    created_at: datetime
    updated_at: datetime


class ShipmentPlanListResponse(BaseModel):
    """List response for queried shipment plans."""
    total_count: int
    plans: List[ShipmentPlanResponse]
