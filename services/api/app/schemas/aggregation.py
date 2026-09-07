from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AggregationContributorLot(BaseModel):
    """Traceability object for each individual produce lot participating in an aggregation."""
    model_config = ConfigDict(from_attributes=True)

    produce_lot_id: UUID
    seller_user_id: UUID
    seller_name: str
    seller_role: str  # "FARMER" or "FPO"
    owner_fpo_name: Optional[str] = None
    title: str
    available_quantity: Decimal
    unit: str
    quantity_quintals: Decimal
    quality_grade: Optional[str] = None
    asking_price_per_unit: Optional[Decimal] = None
    asking_price_per_quintal: Optional[Decimal] = None
    pickup_location_id: UUID
    pickup_location_name: str
    pickup_village: Optional[str] = None
    pickup_taluka: Optional[str] = None
    pickup_district: Optional[str] = None
    pickup_state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    available_from: date
    available_until: Optional[date] = None
    is_fpo_aggregated: bool = False
    member_contributions_count: int = 0


class AggregationClusterInfo(BaseModel):
    """Geographic clustering metadata for a group of aggregated lots."""
    model_config = ConfigDict(from_attributes=True)

    cluster_id: str
    cluster_center_name: str
    cluster_district: Optional[str] = None
    cluster_state: str = "Maharashtra"
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    max_inter_farm_distance_km: Decimal
    is_geographic_distance_exact: bool
    cluster_note: str


class AggregationEconomics(BaseModel):
    """Basic economic summary for the aggregated supply cluster."""
    model_config = ConfigDict(from_attributes=True)

    total_aggregated_quantity_quintals: Decimal
    required_quantity_quintals: Decimal
    coverage_ratio_pct: Decimal
    weighted_average_asking_price_per_quintal: Optional[Decimal] = None
    buyer_target_price_per_quintal: Optional[Decimal] = None
    expected_gross_value: Decimal
    is_economic_estimate_complete: bool = False
    economic_disclaimer: str = (
        "Logistics consolidation costs and multi-stop collection overhead are not included in this "
        "first-stage supply aggregation estimate."
    )


class AggregationOpportunityResponse(BaseModel):
    """Complete aggregation opportunity representation."""
    model_config = ConfigDict(from_attributes=True)

    opportunity_id: str  # e.g. AGG-REQ-<UUID_PREFIX>-001
    status: str  # "NO_AGGREGATION_NEEDED", "AGGREGATION_POSSIBLE", "AGGREGATION_PARTIAL", "NO_COMPATIBLE_SUPPLY"
    status_explanation: str
    
    # Requirement Details
    buyer_requirement_id: UUID
    buyer_user_id: UUID
    buyer_name: str
    buyer_organization: Optional[str] = None
    commodity_id: UUID
    commodity_name: str
    required_quantity: Decimal
    unit: str
    required_quantity_quintals: Decimal
    minimum_quality_grade: Optional[str] = None
    target_price_per_unit: Optional[Decimal] = None
    delivery_by: Optional[date] = None
    delivery_location_id: UUID
    delivery_location_name: str
    delivery_district: Optional[str] = None
    delivery_state: str = "Maharashtra"
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None

    # Aggregate Supply
    candidate_supply_quintals: Decimal
    contributor_count: int
    contributing_lots: List[AggregationContributorLot] = Field(default_factory=list)
    
    # Clustering & Economics
    cluster_info: Optional[AggregationClusterInfo] = None
    economics: AggregationEconomics
    
    # Explainability & Trust
    verified_constraints: List[str] = Field(default_factory=list)
    traceability_notice: str = (
        "All contributing lots retain distinct seller identity, individual lot IDs, and original DB records without modification."
    )
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AggregationScanRequest(BaseModel):
    """Request payload to scan for aggregation opportunities."""
    buyer_requirement_id: Optional[UUID] = None
    commodity_id: Optional[UUID] = None
    max_cluster_radius_km: Optional[Decimal] = Field(default=Decimal("50.0"), ge=Decimal("5.0"), le=Decimal("200.0"))
    include_partial: bool = True


class AggregationBatchResponse(BaseModel):
    """Response containing multiple scanned aggregation opportunities."""
    total_requirements_evaluated: int
    total_opportunities_found: int
    opportunities: List[AggregationOpportunityResponse]
    scan_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

