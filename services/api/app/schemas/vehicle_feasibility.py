from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import VehicleTypeEnum


class VehicleCandidateOption(BaseModel):
    """Detailed evaluation representation of an archetype or verified candidate vehicle."""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    candidate_type: Literal["REFERENCE_ARCHETYPE", "VERIFIED_OPERATIONAL_VEHICLE"]
    vehicle_id: Optional[UUID] = None
    vehicle_type: VehicleTypeEnum
    vehicle_type_label: str
    model_name: Optional[str] = None
    registration_number: Optional[str] = None
    provider_name: Optional[str] = None
    max_payload_quintals: Decimal
    max_payload_tonnes: Decimal
    payload_utilization_pct: Decimal
    is_capacity_sufficient: bool
    capacity_deficit_quintals: Decimal
    is_cold_chain_compatible: bool
    cold_chain_status: Literal[
        "SATISFIES_PERISHABLE",
        "NOT_REQUIRED_DRY",
        "COLD_CHAIN_REQUIRED_BUT_MISSING",
        "REEFER_EXCESS_SURCHARGE"
    ]
    multi_stop_feasibility: Literal[
        "FEASIBLE_AGILE",
        "FEASIBLE_STANDARD",
        "CHALLENGING_NARROW_ACCESS",
        "RESTRICTED"
    ]
    operational_availability: Literal[
        "VERIFIED_AVAILABLE",
        "VERIFIED_BUSY",
        "UNKNOWN_ARCHETYPE_ONLY"
    ]
    cost_certainty: Literal[
        "VERIFIED_TRANSPORTER_QUOTE",
        "MODELED_REGIONAL_ESTIMATE",
        "UNAVAILABLE"
    ]
    is_verified_quote: bool = False
    estimated_cost: Optional[Decimal] = None
    estimated_cost_per_quintal: Optional[Decimal] = None
    cost_explanation: str
    suitability_score: Decimal  # 0 to 100
    is_recommended: bool
    hard_feasibility_passed: bool
    feasibility_reasons: List[str] = Field(default_factory=list)
    disclaimers: List[str] = Field(default_factory=list)


class ShipmentVehicleFeasibilityResponse(BaseModel):
    """Full vehicle feasibility and selection report for a ShipmentPlan."""
    model_config = ConfigDict(from_attributes=True)

    shipment_plan_id: Optional[UUID] = None
    plan_code: Optional[str] = None
    evaluation_status: Literal[
        "VEHICLE_MATCH_FOUND",
        "VEHICLE_MATCH_UNAVAILABLE",
        "VEHICLE_CAPACITY_INSUFFICIENT",
        "VEHICLE_REQUIREMENT_UNKNOWN"
    ]
    status_summary: str
    planned_quantity_quintals: Decimal
    planned_quantity_tonnes: Decimal
    commodity_id: Optional[UUID] = None
    commodity_name: str
    is_perishable: bool
    cold_chain_requirement: Literal["REQUIRED", "RECOMMENDED", "NOT_REQUIRED", "UNKNOWN"]
    stops_count: int
    origin_district: Optional[str] = None
    destination_district: Optional[str] = None
    estimated_distance_km: Decimal
    recommended_vehicle_class: Optional[str] = None
    primary_recommendation: Optional[VehicleCandidateOption] = None
    ranked_options: List[VehicleCandidateOption] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operational_guardrails: List[str] = Field(default_factory=list)


class DirectVehicleFeasibilityRequest(BaseModel):
    """Request to evaluate vehicle feasibility for arbitrary quantity/commodity parameters."""
    quantity_quintals: Decimal = Field(..., gt=0, description="Payload weight in metric quintals")
    commodity_id: Optional[UUID] = None
    commodity_name: Optional[str] = None
    is_perishable: Optional[bool] = None
    stops_count: int = Field(default=1, ge=1, description="Number of pickup stops")
    distance_km: Optional[Decimal] = Field(default=Decimal("35.0"), ge=Decimal("1.0"))
    origin_name: str = "Farm Gate Origin"
    destination_name: str = "Buyer Destination Hub"
