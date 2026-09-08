"""
Phase 2D - Step 1: Buyer Matching Foundation.
Matches produce offerings against live Buyer Requirements and Buyer Directory records
with multi-dimensional compatibility checks and transparent reason codes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    BuyerDirectoryEntry,
    BuyerPreferredCategory,
    BuyerPreferredCommodity,
    BuyerRequirement,
    BuyerRequirementStatus,
    Commodity,
    CommodityCategory,
    Location,
)
from app.modules.intelligence.transport_cost import calculate_haversine_road_distance


@dataclass
class MatchedBuyerCandidate:
    source_type: str  # "LIVE_REQUIREMENT" or "BUYER_DIRECTORY"
    buyer_id: UUID
    business_name: str
    buyer_type: str
    buyer_provenance: str  # "REGISTERED_VERIFIED_BUYER", "RESEARCHED_DIRECTORY_RECORD", or "PUBLIC_DIRECTORY_LISTING"
    is_platform_registered: bool
    verification_status: str
    destination_location_id: UUID
    destination_location_name: str

    destination_taluka: Optional[str]
    destination_district: Optional[str]
    destination_state: str
    destination_latitude: Optional[float]
    destination_longitude: Optional[float]
    
    # Distance
    road_distance_km: Decimal
    procurement_radius_km: Optional[Decimal]
    
    # Matching breakdown
    matched_commodity_name: str
    match_type: str  # "EXACT_COMMODITY" or "CATEGORY_MATCH"
    
    quantity_compatibility: bool
    quantity_reason: str
    
    quality_compatibility: bool
    quality_reason: str
    
    geographic_compatibility: bool
    geographic_reason: str
    
    delivery_compatibility: bool
    delivery_reason: str
    
    # Target / Bid price if available
    buyer_target_price_per_unit: Optional[Decimal]
    payment_terms: Optional[str]
    
    # Overall match score (0 - 100)
    match_score: Decimal
    is_eligible: bool
    reason_codes: List[str] = field(default_factory=list)


def compute_geographic_distance(
    origin_loc: Optional[Location],
    dest_loc: Optional[Location]
) -> Tuple[Decimal, Optional[str]]:
    """Calculates road distance between origin and destination locations."""
    if not origin_loc or not dest_loc:
        return Decimal("35.0"), "Default regional distance (coordinates unassigned)"

    if (
        origin_loc.latitude is not None
        and origin_loc.longitude is not None
        and dest_loc.latitude is not None
        and dest_loc.longitude is not None
    ):
        dist = calculate_haversine_road_distance(
            float(origin_loc.latitude),
            float(origin_loc.longitude),
            float(dest_loc.latitude),
            float(dest_loc.longitude),
        )
        return dist, f"{dist} km road distance via GPS coordinates"

    # If same district
    if origin_loc.district and dest_loc.district and origin_loc.district.lower() == dest_loc.district.lower():
        return Decimal("25.0"), f"Estimated intra-district distance ({origin_loc.district})"

    return Decimal("65.0"), "Estimated inter-district Maharashtra distance"


def evaluate_quality_compatibility(
    produce_grade: Optional[str],
    buyer_min_grade: Optional[str]
) -> Tuple[bool, str]:
    """Evaluates if produce grade satisfies buyer's minimum grade requirement."""
    if not buyer_min_grade:
        return True, "No specific minimum grade required by buyer"

    if not produce_grade:
        return True, f"Buyer requests '{buyer_min_grade}', produce grade unassigned (assumed standard)"

    p_norm = produce_grade.strip().lower()
    b_norm = buyer_min_grade.strip().lower()

    # Simple hierarchical grade check
    grade_ranks = {"grade a": 3, "premium": 3, "grade b": 2, "faq": 2, "grade c": 1, "standard": 2}
    p_rank = grade_ranks.get(p_norm, 2)
    b_rank = grade_ranks.get(b_norm, 2)

    if p_rank >= b_rank:
        return True, f"Quality grade '{produce_grade}' satisfies minimum requirement '{buyer_min_grade}'"
    else:
        return False, f"Quality grade '{produce_grade}' is below required '{buyer_min_grade}'"


def match_buyers_for_produce(
    db: Session,
    commodity_id: UUID,
    quantity_quintals: Decimal,
    quality_grade: Optional[str],
    pickup_location: Optional[Location],
    availability_date: Optional[date] = None,
) -> List[MatchedBuyerCandidate]:
    """
    Finds and scores all eligible buyers for a produce offering.
    Searches both live Active Buyer Requirements and verified Buyer Directory records.
    """
    ref_date = availability_date or date.today()
    candidates: List[MatchedBuyerCandidate] = []

    # 1. Fetch commodity info
    commodity = db.scalar(select(Commodity).where(Commodity.id == commodity_id))
    if not commodity:
        return []

    # 2. Match Live Buyer Requirements
    live_reqs = db.scalars(
        select(BuyerRequirement)
        .options(
            joinedload(BuyerRequirement.buyer_profile),
            joinedload(BuyerRequirement.delivery_location),
            joinedload(BuyerRequirement.commodity),
        )
        .where(
            BuyerRequirement.commodity_id == commodity_id,
            BuyerRequirement.status == BuyerRequirementStatus.ACTIVE,
        )
    ).unique().all()

    for req in live_reqs:
        dest_loc = req.delivery_location
        dist, dist_reason = compute_geographic_distance(pickup_location, dest_loc)
        
        # Quantity check
        q_compat = True
        q_reason = f"Buyer requires {req.required_quantity} {req.unit}; offering {quantity_quintals} qtl"
        if req.required_quantity and quantity_quintals < (req.required_quantity * Decimal("0.1")):
            q_compat = False
            q_reason = f"Offering {quantity_quintals} qtl is too small for required {req.required_quantity} {req.unit}"

        # Quality check
        qual_compat, qual_reason = evaluate_quality_compatibility(quality_grade, req.minimum_quality_grade)

        # Geographic check
        geo_compat = dist <= Decimal("300.0")  # Live requirement default regional threshold
        geo_reason = f"Delivery distance {dist} km is feasible ({dist_reason})"

        # Delivery check
        deliv_compat = True
        deliv_reason = "Delivery window matches"
        if req.delivery_by and ref_date > req.delivery_by:
            deliv_compat = False
            deliv_reason = f"Produce available on {ref_date}, but buyer requires delivery by {req.delivery_by}"

        # Score calculation
        score = Decimal("100.0")
        reason_codes = ["LIVE_BUYER_REQUIREMENT", "EXACT_COMMODITY_MATCH"]
        if not q_compat:
            score -= Decimal("30.0")
            reason_codes.append("QUANTITY_MISMATCH")
        if not qual_compat:
            score -= Decimal("25.0")
            reason_codes.append("QUALITY_GRADE_BELOW_MINIMUM")
        if not geo_compat:
            score -= Decimal("30.0")
            reason_codes.append("DISTANCE_EXCEEDED")
        if not deliv_compat:
            score -= Decimal("40.0")
            reason_codes.append("DELIVERY_DATE_EXPIRED")

        is_elig = q_compat and qual_compat and geo_compat and deliv_compat

        candidates.append(
            MatchedBuyerCandidate(
                source_type="LIVE_REQUIREMENT",
                buyer_id=req.buyer_profile_id,
                business_name=req.buyer_profile.organization_name if req.buyer_profile else "Verified Buyer",
                buyer_type="Commercial Buyer",
                buyer_provenance="REGISTERED_VERIFIED_BUYER",
                is_platform_registered=True,
                verification_status="VERIFIED_PLATFORM_BUYER",
                destination_location_id=dest_loc.id if dest_loc else commodity.id,
                destination_location_name=dest_loc.name if dest_loc else "Mandi Hub",

                destination_taluka=dest_loc.taluka if dest_loc else None,
                destination_district=dest_loc.district if dest_loc else None,
                destination_state=dest_loc.state if dest_loc else "Maharashtra",
                destination_latitude=float(dest_loc.latitude) if dest_loc and dest_loc.latitude else None,
                destination_longitude=float(dest_loc.longitude) if dest_loc and dest_loc.longitude else None,
                road_distance_km=dist,
                procurement_radius_km=Decimal("300.0"),
                matched_commodity_name=commodity.name,
                match_type="EXACT_COMMODITY",
                quantity_compatibility=q_compat,
                quantity_reason=q_reason,
                quality_compatibility=qual_compat,
                quality_reason=qual_reason,
                geographic_compatibility=geo_compat,
                geographic_reason=geo_reason,
                delivery_compatibility=deliv_compat,
                delivery_reason=deliv_reason,
                buyer_target_price_per_unit=req.target_price_per_unit,
                payment_terms="Standard Marketplace Escrow / Direct Transfer",
                match_score=max(Decimal("0.0"), score),
                is_eligible=is_elig,
                reason_codes=reason_codes,
            )
        )

    # 3. Match Buyer Directory Entries (Researched Wholesale Buyers & Aggregators)
    directory_entries = db.scalars(
        select(BuyerDirectoryEntry)
        .options(
            joinedload(BuyerDirectoryEntry.location),
            joinedload(BuyerDirectoryEntry.preferred_commodities).joinedload(BuyerPreferredCommodity.commodity),
            joinedload(BuyerDirectoryEntry.preferred_categories),
        )
        .where(BuyerDirectoryEntry.is_active == True)
    ).unique().all()

    for entry in directory_entries:
        dest_loc = entry.location
        dist, dist_reason = compute_geographic_distance(pickup_location, dest_loc)

        # Check commodity preference
        exact_pref = next((p for p in entry.preferred_commodities if p.commodity_id == commodity_id), None)
        category_pref = next((c for c in entry.preferred_categories if c.category == commodity.category), None)

        if not exact_pref and not category_pref:
            # Not interested in this commodity or category
            continue

        match_type = "EXACT_COMMODITY" if exact_pref else "CATEGORY_MATCH"
        matched_name = commodity.name if exact_pref else f"{commodity.category.value.title()} Category"

        # Quantity check
        q_compat = True
        q_reason = "Produce quantity fits buyer daily procurement profile"
        if entry.daily_capacity_mt:
            cap_quintals = entry.daily_capacity_mt * Decimal("10.0")
            if quantity_quintals > (cap_quintals * Decimal("3.0")):
                q_compat = False
                q_reason = f"Offering {quantity_quintals} qtl exceeds buyer daily capacity ({cap_quintals} qtl)"

        # Quality check
        min_grade = exact_pref.min_quality_grade if exact_pref else None
        qual_compat, qual_reason = evaluate_quality_compatibility(quality_grade, min_grade)

        # Geographic check
        max_rad = entry.procurement_radius_km or Decimal("150.0")
        geo_compat = dist <= max_rad
        geo_reason = (
            f"Distance {dist} km is within procurement radius ({max_rad} km)"
            if geo_compat
            else f"Distance {dist} km exceeds buyer procurement radius ({max_rad} km)"
        )

        # Delivery check
        deliv_compat = True
        deliv_reason = "Regular commercial procurement operating days"

        # Match score calculation
        score = Decimal("90.0") if exact_pref else Decimal("75.0")
        reason_codes = ["BUYER_DIRECTORY_MATCH"]
        if exact_pref:
            reason_codes.append("EXACT_COMMODITY_MATCH")
        else:
            reason_codes.append("BROAD_CATEGORY_MATCH")

        if not q_compat:
            score -= Decimal("25.0")
            reason_codes.append("QUANTITY_EXCEEDS_CAPACITY")
        if not qual_compat:
            score -= Decimal("20.0")
            reason_codes.append("QUALITY_GRADE_BELOW_MINIMUM")
        if not geo_compat:
            score -= Decimal("35.0")
            reason_codes.append("PROCUREMENT_RADIUS_EXCEEDED")

        is_elig = q_compat and qual_compat and geo_compat and deliv_compat

        target_price = exact_pref.max_price_per_unit if exact_pref else None

        is_registered = (entry.registered_buyer_profile_id is not None)
        provenance = "REGISTERED_VERIFIED_BUYER" if is_registered else "RESEARCHED_DIRECTORY_RECORD"
        v_status = "VERIFIED_PLATFORM_BUYER" if is_registered else "OFFLINE_RESEARCH_RECORD"

        candidates.append(
            MatchedBuyerCandidate(
                source_type="BUYER_DIRECTORY",
                buyer_id=entry.id,
                business_name=entry.business_name,
                buyer_type=entry.buyer_type.value.replace("_", " ").title(),
                buyer_provenance=provenance,
                is_platform_registered=is_registered,
                verification_status=v_status,
                destination_location_id=dest_loc.id if dest_loc else commodity.id,
                destination_location_name=dest_loc.name if dest_loc else "Pune Commercial Hub",

                destination_taluka=dest_loc.taluka if dest_loc else None,
                destination_district=dest_loc.district if dest_loc else None,
                destination_state=dest_loc.state if dest_loc else "Maharashtra",
                destination_latitude=float(dest_loc.latitude) if dest_loc and dest_loc.latitude else None,
                destination_longitude=float(dest_loc.longitude) if dest_loc and dest_loc.longitude else None,
                road_distance_km=dist,
                procurement_radius_km=entry.procurement_radius_km,
                matched_commodity_name=matched_name,
                match_type=match_type,
                quantity_compatibility=q_compat,
                quantity_reason=q_reason,
                quality_compatibility=qual_compat,
                quality_reason=qual_reason,
                geographic_compatibility=geo_compat,
                geographic_reason=geo_reason,
                delivery_compatibility=deliv_compat,
                delivery_reason=deliv_reason,
                buyer_target_price_per_unit=target_price,
                payment_terms=entry.typical_payment_terms or "Standard Commercial Terms",
                match_score=max(Decimal("0.0"), score),
                is_eligible=is_elig,
                reason_codes=reason_codes,
            )
        )

    # Sort candidates by match_score descending
    candidates.sort(key=lambda c: (c.is_eligible, c.match_score), reverse=True)
    return candidates
