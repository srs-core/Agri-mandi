from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GeographicPrecisionEnum(str, enum.Enum):
    EXACT = "exact"
    ADMINISTRATIVE_ONLY = "administrative_only"
    UNAVAILABLE = "unavailable"


class RoutePlanningStatus(str, enum.Enum):
    ROUTE_FEASIBLE = "route_feasible"
    ROUTE_FEASIBILITY_UNKNOWN = "route_feasibility_unknown"
    ROUTE_INFEASIBLE = "route_infeasible"
    ROUTE_DATA_INCOMPLETE = "route_data_incomplete"


class WaypointTypeEnum(str, enum.Enum):
    PICKUP = "pickup"
    DESTINATION = "destination"


class RouteWaypoint(BaseModel):
    """Represents a single ordered stop in the route plan with location and cargo state."""
    model_config = ConfigDict(from_attributes=True)

    waypoint_sequence: int = Field(..., ge=1, description="Stop sequence index (1, 2, 3...)")
    waypoint_type: WaypointTypeEnum
    pickup_stop_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    location_name: str
    district: Optional[str] = None
    taluka: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    geographic_precision: GeographicPrecisionEnum
    seller_user_id: Optional[UUID] = None
    seller_name: Optional[str] = None
    seller_role: Optional[str] = None
    stop_cargo_quantity_quintals: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"))
    stop_cargo_quantity_tonnes: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"))
    cumulative_onboard_quantity_quintals: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"))
    cumulative_onboard_quantity_tonnes: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"))
    earliest_arrival: Optional[date] = None
    latest_departure: Optional[date] = None
    segment_distance_km: Optional[Decimal] = None
    notes: Optional[str] = None


class RoutePlanResponse(BaseModel):
    """Full structured route plan report for a ShipmentPlan."""
    model_config = ConfigDict(from_attributes=True)

    shipment_plan_id: UUID
    plan_code: str
    route_status: RoutePlanningStatus
    status_summary: str
    overall_geographic_precision: GeographicPrecisionEnum
    is_optimized: bool = False
    routing_strategy: str = "DETERMINISTIC_BASELINE_ORDERING"
    routing_provider_name: str
    waypoints_count: int
    pickup_stops_count: int
    total_cargo_quantity_quintals: Decimal
    total_cargo_quantity_tonnes: Decimal
    total_modeled_distance_km: Optional[Decimal] = None
    distance_certainty: Literal["VERIFIED_ROAD_DISTANCE", "MODELED_GEOGRAPHIC_DISTANCE", "UNAVAILABLE"]
    estimated_transit_hours: Optional[Decimal] = None
    transit_time_certainty: Literal["VERIFIED_ROAD_TIME", "MODELED_TRANSIT_ESTIMATE", "UNAVAILABLE"]
    assigned_vehicle_class: Optional[str] = None
    vehicle_payload_capacity_quintals: Optional[Decimal] = None
    waypoints: List[RouteWaypoint] = Field(default_factory=list)
    feasibility_checks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    operational_limitations: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

