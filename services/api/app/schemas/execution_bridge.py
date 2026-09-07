from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class LogisticsReadinessStatus(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"
    PARTIALLY_READY = "partially_ready"


class ReadinessCheckResult(BaseModel):
    check_name: str
    status: Literal["passed", "failed", "warning", "skipped"]
    detail: str
    certainty: Literal["verified", "modeled", "unavailable"]


class CostComponent(BaseModel):
    component_name: str
    estimated_amount: Decimal
    certainty: Literal["VERIFIED_TRANSPORTER_QUOTE", "MODELED_REGIONAL_ESTIMATE", "UNAVAILABLE"]
    notes: Optional[str] = None


class LogisticsCostSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shipment_plan_id: UUID
    plan_code: str
    recommended_vehicle_type: Optional[str] = None
    recommended_vehicle_model: Optional[str] = None
    vehicle_certainty: str = "REFERENCE_ARCHETYPE"
    estimated_distance_km: Optional[Decimal] = None
    distance_certainty: str = "MODELED_GEOGRAPHIC_DISTANCE"
    cost_components: List[CostComponent] = Field(default_factory=list)
    total_estimated_cost: Optional[Decimal] = None
    estimated_cost_per_quintal: Optional[Decimal] = None
    cost_certainty: Literal["VERIFIED_TRANSPORTER_QUOTE", "MODELED_REGIONAL_ESTIMATE", "UNAVAILABLE"]
    is_verified_quote: bool = False
    rate_source: str
    disclaimer: str
    explanation: str


class LogisticsReadinessAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shipment_plan_id: UUID
    plan_code: str
    planning_status: str
    overall_status: LogisticsReadinessStatus
    checks: List[ReadinessCheckResult] = Field(default_factory=list)
    estimated_cost_summary: Optional[LogisticsCostSummary] = None
    blocking_issues: List[str] = Field(default_factory=list)
    advisory_warnings: List[str] = Field(default_factory=list)
    disclaimer: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateShipmentFromPlanRequest(BaseModel):
    vehicle_id: Optional[UUID] = None
    provider_id: Optional[UUID] = None
    scheduled_pickup_at: Optional[datetime] = None
    estimated_arrival_at: Optional[datetime] = None
    driver_name: Annotated[Optional[str], StringConstraints(strip_whitespace=True, max_length=160)] = None
    driver_phone: Annotated[Optional[str], StringConstraints(strip_whitespace=True, max_length=32)] = None
    notes: Optional[str] = None
