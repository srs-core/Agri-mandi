"""
Phase 2E - Step 5: Route Optimization Schemas.
Pydantic V2 schemas for OR-Tools VRP route optimization requests, comparison metrics,
optimization statuses, and response models.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.route_planning import (
    GeographicPrecisionEnum,
    RouteWaypoint,
)


class RouteOptimizationStatus(str, enum.Enum):
    OPTIMIZED_ROUTE_FOUND = "optimized_route_found"
    OPTIMIZATION_INFEASIBLE = "optimization_infeasible"
    ROUTE_DATA_INCOMPLETE = "route_data_incomplete"
    ROUTING_UNAVAILABLE = "routing_unavailable"
    TIME_WINDOW_CONFLICT = "time_window_conflict"
    CAPACITY_CONSTRAINT_FAILURE = "capacity_constraint_failure"


class OptimizationComparisonMetrics(BaseModel):
    """Comparative metrics between baseline heuristic route and OR-Tools optimized route."""
    model_config = ConfigDict(from_attributes=True)

    baseline_distance_km: Decimal = Field(..., ge=Decimal("0.0"))
    optimized_distance_km: Decimal = Field(..., ge=Decimal("0.0"))
    distance_reduction_km: Decimal = Field(..., ge=Decimal("0.0"))
    distance_reduction_pct: Decimal = Field(..., ge=Decimal("0.0"), le=Decimal("100.0"))
    baseline_duration_hours: Decimal = Field(..., ge=Decimal("0.0"))
    optimized_duration_hours: Decimal = Field(..., ge=Decimal("0.0"))
    duration_reduction_pct: Decimal = Field(..., ge=Decimal("0.0"), le=Decimal("100.0"))
    has_improvement: bool = False


class RouteOptimizationResponse(BaseModel):
    """Full structured route optimization report for a ShipmentPlan."""
    model_config = ConfigDict(from_attributes=True)

    shipment_plan_id: UUID
    plan_code: str
    optimization_status: RouteOptimizationStatus
    status_summary: str
    overall_geographic_precision: GeographicPrecisionEnum
    routing_strategy: Literal["OR_TOOLS_VRP", "DETERMINISTIC_BASELINE_ORDERING"] = "OR_TOOLS_VRP"
    optimizer_name: str
    routing_provider_name: str
    optimization_type: Literal["MODELED_ROUTE_OPTIMIZATION", "VERIFIED_ROAD_ROUTE_OPTIMIZATION"]
    waypoints_count: int
    pickup_stops_count: int
    total_cargo_quantity_quintals: Decimal
    total_cargo_quantity_tonnes: Decimal
    assigned_vehicle_class: Optional[str] = None
    vehicle_payload_capacity_quintals: Optional[Decimal] = None
    vehicle_payload_utilization_pct: Optional[Decimal] = None
    total_distance_km: Optional[Decimal] = None
    distance_certainty: Literal["VERIFIED_ROAD_DISTANCE", "MODELED_GEOGRAPHIC_DISTANCE", "UNAVAILABLE"]
    estimated_transit_hours: Optional[Decimal] = None
    transit_time_certainty: Literal["VERIFIED_ROAD_TIME", "MODELED_TRANSIT_ESTIMATE", "UNAVAILABLE"]
    comparison_metrics: Optional[OptimizationComparisonMetrics] = None
    waypoints: List[RouteWaypoint] = Field(default_factory=list)
    feasibility_checks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    operational_limitations: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
