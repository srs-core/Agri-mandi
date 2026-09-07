"""
Phase 2E - Step 1: Multi-Farmer Aggregation Engine.
Deterministic supply aggregation that clusters compatible farmer/FPO produce lots
to satisfy bulk buyer requirements with complete traceability and constraint verification.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    BuyerProfile,
    BuyerRequirement,
    BuyerRequirementStatus,
    Commodity,
    Location,
    ProduceLot,
    ProduceLotStatus,
    User,
)

from app.modules.intelligence.buyer_matching import evaluate_quality_compatibility
from app.modules.intelligence.transport_cost import calculate_haversine_road_distance
from app.schemas.aggregation import (
    AggregationBatchResponse,
    AggregationClusterInfo,
    AggregationContributorLot,
    AggregationEconomics,
    AggregationOpportunityResponse,
    AggregationScanRequest,
)


def convert_quantity_to_quintals(quantity: Decimal, unit: str) -> Decimal:
    """Standardizes produce quantity from arbitrary unit into metric quintals."""
    u = unit.strip().lower()
    if u in ("kg", "kilogram", "kilograms"):
        return Decimal(str(round(quantity / Decimal("100.0"), 3)))
    elif u in ("tonne", "ton", "tonnes", "tons", "mt"):
        return Decimal(str(round(quantity * Decimal("10.0"), 3)))
    elif u in ("quintal", "quintals", "qtl"):
        return Decimal(str(round(quantity, 3)))
    elif u in ("gram", "grams", "g"):
        return Decimal(str(round(quantity / Decimal("100000.0"), 4)))
    # Default 1:1 if already quintal or unrecognized
    return Decimal(str(round(quantity, 3)))


def convert_price_to_per_quintal(price: Optional[Decimal], unit: str) -> Optional[Decimal]:
    """Converts a price per unit into equivalent price per metric quintal."""
    if price is None:
        return None
    u = unit.strip().lower()
    if u in ("kg", "kilogram", "kilograms"):
        return Decimal(str(round(price * Decimal("100.0"), 2)))
    elif u in ("tonne", "ton", "tonnes", "tons", "mt"):
        return Decimal(str(round(price / Decimal("10.0"), 2)))
    elif u in ("quintal", "quintals", "qtl"):
        return Decimal(str(round(price, 2)))
    return Decimal(str(round(price, 2)))


def compute_inter_location_distance(
    loc1: Location,
    loc2: Location,
) -> Tuple[Decimal, bool, str]:
    """
    Computes road distance between two pickup/delivery locations.
    Returns (distance_km, is_exact_gps, note).
    """
    if (
        loc1.latitude is not None
        and loc1.longitude is not None
        and loc2.latitude is not None
        and loc2.longitude is not None
    ):
        dist = calculate_haversine_road_distance(
            float(loc1.latitude),
            float(loc1.longitude),
            float(loc2.latitude),
            float(loc2.longitude),
        )
        return dist, True, f"{dist} km road distance via verified GPS"

    # Textual district matching fallback
    if loc1.district and loc2.district and loc1.district.lower() == loc2.district.lower():
        return Decimal("25.0"), False, f"Estimated intra-district distance ({loc1.district})"

    return Decimal("65.0"), False, "Estimated inter-district Maharashtra distance"


def build_contributor_lot_schema(lot: ProduceLot) -> AggregationContributorLot:
    """Builds a non-destructive, fully traceable contributor lot representation."""
    seller = lot.seller
    pickup = lot.pickup_location
    fpo = lot.owner_fpo_profile
    qty_qtl = convert_quantity_to_quintals(lot.available_quantity, lot.unit)
    price_qtl = convert_price_to_per_quintal(lot.asking_price_per_unit, lot.unit)

    seller_role = "FPO" if (lot.is_aggregated or lot.owner_fpo_profile_id is not None) else "FARMER"

    return AggregationContributorLot(
        produce_lot_id=lot.id,
        seller_user_id=seller.id if seller else lot.seller_user_id,
        seller_name=seller.display_name if seller else "Produce Producer",
        seller_role=seller_role,
        owner_fpo_name=fpo.legal_name if fpo else None,
        title=lot.title,
        available_quantity=lot.available_quantity,
        unit=lot.unit,
        quantity_quintals=qty_qtl,
        quality_grade=lot.quality_grade,
        asking_price_per_unit=lot.asking_price_per_unit,
        asking_price_per_quintal=price_qtl,
        pickup_location_id=pickup.id if pickup else lot.pickup_location_id,
        pickup_location_name=pickup.name if pickup else "Farm Gate Yard",
        pickup_village=pickup.village if pickup else None,
        pickup_taluka=pickup.taluka if pickup else None,
        pickup_district=pickup.district if pickup else None,
        pickup_state=pickup.state if pickup else "Maharashtra",
        latitude=float(pickup.latitude) if pickup and pickup.latitude is not None else None,
        longitude=float(pickup.longitude) if pickup and pickup.longitude is not None else None,
        available_from=lot.available_from,
        available_until=lot.available_until,
        is_fpo_aggregated=lot.is_aggregated,
        member_contributions_count=len(lot.contributions) if lot.contributions else 0,
    )


def cluster_candidate_lots(
    candidate_lots: List[ProduceLot],
    max_cluster_radius_km: Decimal = Decimal("50.0"),
) -> List[List[ProduceLot]]:
    """
    Deterministically partitions candidate lots into geographically compatible clusters.
    If GPS coordinates are available, clusters lots within max_cluster_radius_km of each other.
    If textual only, groups by administrative district.
    """
    if not candidate_lots:
        return []

    # Separate coordinate-backed lots from textual-only lots
    gps_lots = [
        l for l in candidate_lots
        if l.pickup_location and l.pickup_location.latitude is not None and l.pickup_location.longitude is not None
    ]
    textual_lots = [
        l for l in candidate_lots
        if l not in gps_lots
    ]

    clusters: List[List[ProduceLot]] = []

    # 1. Cluster GPS lots using pairwise proximity
    visited_gps_ids: Set[UUID] = set()
    for lot in gps_lots:
        if lot.id in visited_gps_ids:
            continue
        cluster = [lot]
        visited_gps_ids.add(lot.id)
        loc1 = lot.pickup_location

        for other_lot in gps_lots:
            if other_lot.id in visited_gps_ids:
                continue
            loc2 = other_lot.pickup_location
            dist, is_exact, _ = compute_inter_location_distance(loc1, loc2)
            if dist <= max_cluster_radius_km:
                cluster.append(other_lot)
                visited_gps_ids.add(other_lot.id)

        clusters.append(cluster)

    # 2. Cluster textual-only lots by district
    district_map: Dict[str, List[ProduceLot]] = {}
    for lot in textual_lots:
        distr = (lot.pickup_location.district.strip().title() if (lot.pickup_location and lot.pickup_location.district) else "Unspecified Regional Hub")
        district_map.setdefault(distr, []).append(lot)

    for dist_lots in district_map.values():
        clusters.append(dist_lots)

    return clusters


def evaluate_single_requirement_aggregation(
    db: Session,
    requirement: BuyerRequirement,
    max_cluster_radius_km: Decimal = Decimal("50.0"),
    include_partial: bool = True,
) -> AggregationOpportunityResponse:
    """
    Evaluates automated supply aggregation for a single active Buyer Requirement.
    Determines if single lot is sufficient, or if multiple compatible lots can be aggregated.
    """
    req_qty_qtl = convert_quantity_to_quintals(requirement.required_quantity, requirement.unit)
    target_price_qtl = convert_price_to_per_quintal(requirement.target_price_per_unit, requirement.unit)
    delivery_loc = requirement.delivery_location
    buyer_prof = requirement.buyer_profile
    buyer_user = buyer_prof.user if buyer_prof else None
    commodity = requirement.commodity

    # 1. Fetch published produce lots for this exact commodity
    query = (
        select(ProduceLot)
        .options(
            joinedload(ProduceLot.seller),
            joinedload(ProduceLot.pickup_location),
            joinedload(ProduceLot.owner_fpo_profile),
            joinedload(ProduceLot.contributions),
        )
        .where(
            ProduceLot.commodity_id == requirement.commodity_id,
            ProduceLot.status == ProduceLotStatus.PUBLISHED,
            ProduceLot.available_quantity > 0,
        )
    )
    raw_lots = db.scalars(query).unique().all()

    # 2. Hard Constraint Filtering
    compatible_lots: List[ProduceLot] = []
    verified_constraints: List[str] = [
        f"Canonical Commodity Match: '{commodity.name}'",
        f"Buyer Requirement Active (Target: {requirement.required_quantity} {requirement.unit} = {req_qty_qtl} quintals)",
    ]

    for lot in raw_lots:
        # Quality check
        qual_ok, qual_reason = evaluate_quality_compatibility(lot.quality_grade, requirement.minimum_quality_grade)
        if not qual_ok:
            continue

        # Availability window check
        if requirement.delivery_by and lot.available_from > requirement.delivery_by:
            continue
        if lot.available_until and lot.available_until < lot.available_from:
            continue

        # Geographic check against delivery location (max 300 km threshold)
        if delivery_loc and lot.pickup_location:
            dist_to_buyer, is_exact, _ = compute_inter_location_distance(lot.pickup_location, delivery_loc)
            if dist_to_buyer > Decimal("300.0"):
                continue

        compatible_lots.append(lot)

    # If no compatible supply exists at all
    if not compatible_lots:
        economics = AggregationEconomics(
            total_aggregated_quantity_quintals=Decimal("0.0"),
            required_quantity_quintals=req_qty_qtl,
            coverage_ratio_pct=Decimal("0.0"),
            weighted_average_asking_price_per_quintal=None,
            buyer_target_price_per_quintal=target_price_qtl,
            expected_gross_value=Decimal("0.0"),
            is_economic_estimate_complete=False,
        )
        return AggregationOpportunityResponse(
            opportunity_id=f"AGG-REQ-{str(requirement.id)[:8].upper()}-000",
            status="NO_COMPATIBLE_SUPPLY",
            status_explanation=f"No compatible produce lots found satisfying commodity, quality, date, and radius constraints for '{commodity.name}'.",
            buyer_requirement_id=requirement.id,
            buyer_user_id=buyer_user.id if buyer_user else requirement.buyer_profile_id,
            buyer_name=buyer_user.display_name if buyer_user else "Commercial Buyer",
            buyer_organization=buyer_prof.organization_name if buyer_prof else None,
            commodity_id=commodity.id,
            commodity_name=commodity.name,
            required_quantity=requirement.required_quantity,
            unit=requirement.unit,
            required_quantity_quintals=req_qty_qtl,
            minimum_quality_grade=requirement.minimum_quality_grade,
            target_price_per_unit=requirement.target_price_per_unit,
            delivery_by=requirement.delivery_by,
            delivery_location_id=delivery_loc.id if delivery_loc else requirement.delivery_location_id,
            delivery_location_name=delivery_loc.name if delivery_loc else "Mandi Hub",
            delivery_district=delivery_loc.district if delivery_loc else None,
            delivery_state=delivery_loc.state if delivery_loc else "Maharashtra",
            delivery_latitude=float(delivery_loc.latitude) if delivery_loc and delivery_loc.latitude else None,
            delivery_longitude=float(delivery_loc.longitude) if delivery_loc and delivery_loc.longitude else None,
            candidate_supply_quintals=Decimal("0.0"),
            contributor_count=0,
            contributing_lots=[],
            cluster_info=None,
            economics=economics,
            verified_constraints=verified_constraints,
        )

    # 3. Check for Single Lot Sufficiency (NO_AGGREGATION_NEEDED)
    single_satisfying_lots = [
        l for l in compatible_lots
        if convert_quantity_to_quintals(l.available_quantity, l.unit) >= req_qty_qtl
    ]

    if single_satisfying_lots:
        # Sort by asking price ascending (or closest to delivery location)
        single_satisfying_lots.sort(
            key=lambda l: (
                convert_price_to_per_quintal(l.asking_price_per_unit, l.unit) or Decimal("999999"),
                l.available_from,
            )
        )
        best_single_lot = single_satisfying_lots[0]
        single_contrib = build_contributor_lot_schema(best_single_lot)
        single_qtl = single_contrib.quantity_quintals
        cov_pct = Decimal(str(round((single_qtl / max(req_qty_qtl, Decimal("0.01"))) * 100, 2)))

        gross_val = single_qtl * (target_price_qtl or single_contrib.asking_price_per_quintal or Decimal("0.0"))

        economics = AggregationEconomics(
            total_aggregated_quantity_quintals=single_qtl,
            required_quantity_quintals=req_qty_qtl,
            coverage_ratio_pct=cov_pct,
            weighted_average_asking_price_per_quintal=single_contrib.asking_price_per_quintal,
            buyer_target_price_per_quintal=target_price_qtl,
            expected_gross_value=Decimal(str(round(gross_val, 2))),
            is_economic_estimate_complete=False,
        )

        cluster_info = AggregationClusterInfo(
            cluster_id=f"CLUSTER-SINGLE-{str(best_single_lot.id)[:8].upper()}",
            cluster_center_name=single_contrib.pickup_location_name,
            cluster_district=single_contrib.pickup_district,
            cluster_state=single_contrib.pickup_state,
            center_latitude=single_contrib.latitude,
            center_longitude=single_contrib.longitude,
            max_inter_farm_distance_km=Decimal("0.0"),
            is_geographic_distance_exact=single_contrib.latitude is not None,
            cluster_note="Single standalone produce lot satisfies 100%+ of buyer requirement without multi-farmer aggregation overhead.",
        )

        verified_constraints.append(
            f"Single Lot Direct Fulfillment: Lot '{best_single_lot.title}' provides {single_qtl} qtl (Coverage: {cov_pct}%)"
        )

        return AggregationOpportunityResponse(
            opportunity_id=f"AGG-DIR-{str(requirement.id)[:8].upper()}-001",
            status="NO_AGGREGATION_NEEDED",
            status_explanation=f"A single produce lot independently satisfies {cov_pct}% of the buyer requirement. Multi-farmer aggregation is not required.",
            buyer_requirement_id=requirement.id,
            buyer_user_id=buyer_user.id if buyer_user else requirement.buyer_profile_id,
            buyer_name=buyer_user.display_name if buyer_user else "Commercial Buyer",
            buyer_organization=buyer_prof.organization_name if buyer_prof else None,
            commodity_id=commodity.id,
            commodity_name=commodity.name,
            required_quantity=requirement.required_quantity,
            unit=requirement.unit,
            required_quantity_quintals=req_qty_qtl,
            minimum_quality_grade=requirement.minimum_quality_grade,
            target_price_per_unit=requirement.target_price_per_unit,
            delivery_by=requirement.delivery_by,
            delivery_location_id=delivery_loc.id if delivery_loc else requirement.delivery_location_id,
            delivery_location_name=delivery_loc.name if delivery_loc else "Mandi Hub",
            delivery_district=delivery_loc.district if delivery_loc else None,
            delivery_state=delivery_loc.state if delivery_loc else "Maharashtra",
            delivery_latitude=float(delivery_loc.latitude) if delivery_loc and delivery_loc.latitude else None,
            delivery_longitude=float(delivery_loc.longitude) if delivery_loc and delivery_loc.longitude else None,
            candidate_supply_quintals=single_qtl,
            contributor_count=1,
            contributing_lots=[single_contrib],
            cluster_info=cluster_info,
            economics=economics,
            verified_constraints=verified_constraints,
        )

    # 4. Multi-Farmer Geographic Clustering
    clusters = cluster_candidate_lots(compatible_lots, max_cluster_radius_km=max_cluster_radius_km)

    # Evaluate each cluster to find the best candidate group
    best_cluster_lots: List[ProduceLot] = []
    best_cluster_supply: Decimal = Decimal("0.0")
    best_cluster_coverage: Decimal = Decimal("0.0")

    for cluster in clusters:
        # Sort lots in cluster by asking price ascending
        cluster.sort(
            key=lambda l: (
                convert_price_to_per_quintal(l.asking_price_per_unit, l.unit) or Decimal("999999"),
                l.available_from,
            )
        )
        # Select lots to fulfill requirement
        accumulated_qty = Decimal("0.0")
        selected_for_cluster: List[ProduceLot] = []
        for l in cluster:
            q = convert_quantity_to_quintals(l.available_quantity, l.unit)
            selected_for_cluster.append(l)
            accumulated_qty += q
            if accumulated_qty >= req_qty_qtl:
                break

        cov = Decimal(str(round((accumulated_qty / max(req_qty_qtl, Decimal("0.01"))) * 100, 2)))

        # Priority rule: Prefer clusters that achieve >= 100%, otherwise prefer highest coverage
        if accumulated_qty >= req_qty_qtl:
            if best_cluster_supply < req_qty_qtl or cov < best_cluster_coverage:
                best_cluster_lots = selected_for_cluster
                best_cluster_supply = accumulated_qty
                best_cluster_coverage = cov
        elif best_cluster_supply < req_qty_qtl:
            if accumulated_qty > best_cluster_supply:
                best_cluster_lots = selected_for_cluster
                best_cluster_supply = accumulated_qty
                best_cluster_coverage = cov

    if not best_cluster_lots:
        # Fallback to all compatible lots if clustering was empty
        best_cluster_lots = compatible_lots
        best_cluster_supply = sum(convert_quantity_to_quintals(l.available_quantity, l.unit) for l in best_cluster_lots)
        best_cluster_coverage = Decimal(str(round((best_cluster_supply / max(req_qty_qtl, Decimal("0.01"))) * 100, 2)))

    # Build contributor list
    contributors: List[AggregationContributorLot] = [
        build_contributor_lot_schema(lot) for lot in best_cluster_lots
    ]

    # Calculate weighted asking price
    total_asking_val = Decimal("0.0")
    total_priced_qty = Decimal("0.0")
    for c in contributors:
        if c.asking_price_per_quintal is not None:
            total_asking_val += c.quantity_quintals * c.asking_price_per_quintal
            total_priced_qty += c.quantity_quintals

    weighted_asking_price = (
        Decimal(str(round(total_asking_val / total_priced_qty, 2)))
        if total_priced_qty > Decimal("0.0")
        else None
    )

    effective_price = target_price_qtl or weighted_asking_price or Decimal("0.0")
    expected_gross = Decimal(str(round(best_cluster_supply * effective_price, 2)))

    status = "AGGREGATION_POSSIBLE" if best_cluster_supply >= req_qty_qtl else "AGGREGATION_PARTIAL"
    status_exp = (
        f"Aggregated {len(contributors)} compatible farm lots providing {best_cluster_supply} qtl ({best_cluster_coverage}% coverage) to fulfill {req_qty_qtl} qtl requirement."
        if status == "AGGREGATION_POSSIBLE"
        else f"Available {len(contributors)} compatible farm lots provide {best_cluster_supply} qtl ({best_cluster_coverage}% partial coverage) toward {req_qty_qtl} qtl requirement."
    )

    economics = AggregationEconomics(
        total_aggregated_quantity_quintals=best_cluster_supply,
        required_quantity_quintals=req_qty_qtl,
        coverage_ratio_pct=best_cluster_coverage,
        weighted_average_asking_price_per_quintal=weighted_asking_price,
        buyer_target_price_per_quintal=target_price_qtl,
        expected_gross_value=expected_gross,
        is_economic_estimate_complete=False,
    )

    # Compute cluster center and dispersion
    first_contrib = contributors[0]
    has_gps = all(c.latitude is not None and c.longitude is not None for c in contributors)
    center_lat = sum(c.latitude for c in contributors if c.latitude is not None) / len(contributors) if has_gps else None
    center_lon = sum(c.longitude for c in contributors if c.longitude is not None) / len(contributors) if has_gps else None

    # Max inter-farm distance in cluster
    max_dispersion = Decimal("0.0")
    if len(best_cluster_lots) > 1 and has_gps:
        for i in range(len(best_cluster_lots)):
            for j in range(i + 1, len(best_cluster_lots)):
                d, _, _ = compute_inter_location_distance(best_cluster_lots[i].pickup_location, best_cluster_lots[j].pickup_location)
                if d > max_dispersion:
                    max_dispersion = d
    elif not has_gps:
        max_dispersion = Decimal("25.0")  # Intra-district regional assumption

    cluster_info = AggregationClusterInfo(
        cluster_id=f"CLUSTER-AGG-{str(requirement.id)[:8].upper()}-{len(contributors)}LOT",
        cluster_center_name=first_contrib.pickup_location_name,
        cluster_district=first_contrib.pickup_district or "Pune",
        cluster_state=first_contrib.pickup_state,
        center_latitude=round(center_lat, 6) if center_lat is not None else None,
        center_longitude=round(center_lon, 6) if center_lon is not None else None,
        max_inter_farm_distance_km=max_dispersion,
        is_geographic_distance_exact=has_gps,
        cluster_note=(
            f"Supply cluster of {len(contributors)} farms within {max_dispersion} km mutual road distance."
            if has_gps
            else f"Supply cluster of {len(contributors)} farms grouped by administrative district ({first_contrib.pickup_district or 'Regional'})."
        ),
    )

    verified_constraints.extend([
        f"Traceable Contributors: {len(contributors)} distinct farm lots aggregated",
        f"Total Supply: {best_cluster_supply} quintals against {req_qty_qtl} quintals requirement ({best_cluster_coverage}% coverage)",
        f"Geographic Cluster: {cluster_info.cluster_note}",
    ])

    return AggregationOpportunityResponse(
        opportunity_id=f"AGG-OPP-{str(requirement.id)[:8].upper()}-{len(contributors)}P",
        status=status,
        status_explanation=status_exp,
        buyer_requirement_id=requirement.id,
        buyer_user_id=buyer_user.id if buyer_user else requirement.buyer_profile_id,
        buyer_name=buyer_user.display_name if buyer_user else "Commercial Buyer",
        buyer_organization=buyer_prof.organization_name if buyer_prof else None,
        commodity_id=commodity.id,
        commodity_name=commodity.name,
        required_quantity=requirement.required_quantity,
        unit=requirement.unit,
        required_quantity_quintals=req_qty_qtl,
        minimum_quality_grade=requirement.minimum_quality_grade,
        target_price_per_unit=requirement.target_price_per_unit,
        delivery_by=requirement.delivery_by,
        delivery_location_id=delivery_loc.id if delivery_loc else requirement.delivery_location_id,
        delivery_location_name=delivery_loc.name if delivery_loc else "Mandi Hub",
        delivery_district=delivery_loc.district if delivery_loc else None,
        delivery_state=delivery_loc.state if delivery_loc else "Maharashtra",
        delivery_latitude=float(delivery_loc.latitude) if delivery_loc and delivery_loc.latitude else None,
        delivery_longitude=float(delivery_loc.longitude) if delivery_loc and delivery_loc.longitude else None,
        candidate_supply_quintals=best_cluster_supply,
        contributor_count=len(contributors),
        contributing_lots=contributors,
        cluster_info=cluster_info,
        economics=economics,
        verified_constraints=verified_constraints,
    )


def scan_aggregation_opportunities(
    db: Session,
    request: Optional[AggregationScanRequest] = None,
) -> AggregationBatchResponse:
    """
    Scans across active Buyer Requirements to discover multi-farmer aggregation opportunities.
    """
    req_payload = request or AggregationScanRequest()

    query = (
        select(BuyerRequirement)
        .options(
            joinedload(BuyerRequirement.buyer_profile).joinedload(BuyerProfile.user),
            joinedload(BuyerRequirement.delivery_location),
            joinedload(BuyerRequirement.commodity),
        )
        .where(BuyerRequirement.status == BuyerRequirementStatus.ACTIVE)
    )

    if req_payload.buyer_requirement_id:
        query = query.where(BuyerRequirement.id == req_payload.buyer_requirement_id)
    if req_payload.commodity_id:
        query = query.where(BuyerRequirement.commodity_id == req_payload.commodity_id)

    requirements = db.scalars(query).unique().all()

    opportunities: List[AggregationOpportunityResponse] = []
    max_radius = req_payload.max_cluster_radius_km or Decimal("50.0")

    for req in requirements:
        opp = evaluate_single_requirement_aggregation(
            db=db,
            requirement=req,
            max_cluster_radius_km=max_radius,
            include_partial=req_payload.include_partial,
        )
        if not req_payload.include_partial and opp.status == "AGGREGATION_PARTIAL":
            continue
        opportunities.append(opp)

    return AggregationBatchResponse(
        total_requirements_evaluated=len(requirements),
        total_opportunities_found=len(opportunities),
        opportunities=opportunities,
        scan_timestamp=datetime.now(timezone.utc),
    )

