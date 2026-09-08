from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.entities import (
    Commodity,
    Location,
    LogisticsProvider,
    Notification,
    ShipmentPlan,
    ShipmentPlanningStatus,
    TransportOpportunity,
    TransportOpportunityStatus,
    TransporterProfile,
    User,
    UserStatus,
    Vehicle,
    VerificationStatus,
)
from app.schemas.transporter import (
    BroadcastOpportunitiesResponse,
    TransportOpportunityResponse,
)


def _compute_haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Standard Haversine formula for distance between two points."""
    r = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 2)


def generate_opportunities_for_plan(
    db: Session,
    plan_id: UUID,
    force_rebroadcast: bool = False,
) -> BroadcastOpportunitiesResponse:
    """
    Evaluates registered transporters and their operational vehicles against
    the requirements of a ShipmentPlan and creates TransportOpportunity records.
    """
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            selectinload(ShipmentPlan.pickup_stops),
            selectinload(ShipmentPlan.commodity),
            selectinload(ShipmentPlan.destination_location),
        )
        .where(ShipmentPlan.id == plan_id)
    )

    if not plan:
        raise ApiError(404, "plan_not_found", f"ShipmentPlan {plan_id} not found.")

    if plan.planning_status == ShipmentPlanningStatus.CANCELLED:
        raise ApiError(400, "plan_cancelled", "Cannot broadcast opportunities for a cancelled shipment plan.")

    if not plan.pickup_stops:
        raise ApiError(400, "no_stops", "Shipment plan has no pickup stops.")

    # 1. Extract shipment constraints
    required_payload_quintals = Decimal(str(plan.total_planned_quantity_quintals))
    required_payload_kg = required_payload_quintals * Decimal("100")
    requires_cold_chain = getattr(plan.commodity, "is_perishable", True) and "frozen" in getattr(plan.commodity, "category", "").lower()
    pickup_stops_count = len(plan.pickup_stops)

    # Resolve origin & destination districts
    first_stop_loc = db.scalar(select(Location).where(Location.id == plan.pickup_stops[0].pickup_location_id))
    dest_loc = plan.destination_location

    origin_district = (first_stop_loc.district or first_stop_loc.name) if first_stop_loc else "Maharashtra Rural"
    destination_district = (dest_loc.district or dest_loc.name) if dest_loc else "Maharashtra Terminal"

    # Compute modeled distance across stops to destination
    total_distance_km = Decimal("45.0")
    if first_stop_loc and dest_loc and first_stop_loc.geo_point and dest_loc.geo_point:
        try:
            # Simple Haversine with 1.25 road terrain factor
            p1 = first_stop_loc.geo_point.replace("POINT(", "").replace(")", "").split()
            p2 = dest_loc.geo_point.replace("POINT(", "").replace(")", "").split()
            crow_fly = _compute_haversine_distance_km(float(p1[1]), float(p1[0]), float(p2[1]), float(p2[0]))
            total_distance_km = Decimal(str(round(crow_fly * 1.25, 1)))
        except Exception:
            total_distance_km = Decimal("55.0")

    # Modeled regional transport cost (base fare Rs. 2500 + Rs. 38/km)
    estimated_cost = Decimal("2500.00") + (total_distance_km * Decimal("38.00")) + (Decimal(str(pickup_stops_count)) * Decimal("400.00"))

    # Determine recommended vehicle class
    if required_payload_quintals <= Decimal("15.0"):
        required_vehicle_class = "Mini Truck (1.5 MT)"
    elif required_payload_quintals <= Decimal("30.0"):
        required_vehicle_class = "Pickup (3.0 MT)"
    elif required_payload_quintals <= Decimal("50.0"):
        required_vehicle_class = "Light Commercial Vehicle (5.0 MT)"
    elif required_payload_quintals <= Decimal("80.0"):
        required_vehicle_class = "Medium Commercial Vehicle (8.0 MT)"
    elif required_payload_quintals <= Decimal("160.0"):
        required_vehicle_class = "Heavy Commercial Vehicle (16.0 MT)"
    else:
        required_vehicle_class = "Multi-Axle Heavy Freight Vehicle (25.0 MT)"

    # 2. Find operational transporters
    transporters = db.scalars(
        select(TransporterProfile)
        .join(User, TransporterProfile.user_id == User.id)
        .where(
            TransporterProfile.operational_status == "active",
            User.status == UserStatus.ACTIVE,
        )
    ).all()

    created_opportunities: list[TransportOpportunity] = []

    for transporter in transporters:
        # Check existing opportunity
        existing_opp = db.scalar(
            select(TransportOpportunity).where(
                TransportOpportunity.shipment_plan_id == plan.id,
                TransportOpportunity.transporter_profile_id == transporter.id,
            )
        )

        if existing_opp and not force_rebroadcast:
            created_opportunities.append(existing_opp)
            continue

        # Check transporter's registered provider and vehicles
        provider = db.scalar(
            select(LogisticsProvider).where(
                LogisticsProvider.registered_transporter_profile_id == transporter.id,
                LogisticsProvider.is_active.is_(True),
            )
        )

        vehicles: list[Vehicle] = []
        if provider:
            vehicles = db.scalars(
                select(Vehicle).where(
                    Vehicle.provider_id == provider.id,
                    Vehicle.is_available.is_(True),
                )
            ).all()

        # Transporter vehicle evaluation
        suitable_vehicles = [
            v for v in vehicles
            if v.payload_capacity_kg >= required_payload_kg and (not requires_cold_chain or v.is_refrigerated)
        ]

        # Calculate eligibility score & match criteria
        eligibility_score = Decimal("100.00")
        match_reasons: list[str] = []

        if transporter.verification_status == VerificationStatus.VERIFIED:
            eligibility_score += Decimal("10.00")
            match_reasons.append("Transporter identity verified on platform")

        if suitable_vehicles:
            eligibility_score += Decimal("15.00")
            match_reasons.append(f"{len(suitable_vehicles)} available vehicle(s) satisfy payload requirement ({required_payload_quintals} qtl)")
        elif vehicles:
            # Has vehicles but capacity insufficient
            eligibility_score -= Decimal("20.00")
            match_reasons.append("Registered vehicles have lower payload than required cargo; fleet expansion recommended")
        else:
            match_reasons.append("No active registered vehicles currently listed")

        # Service area check
        if transporter.service_area_districts:
            origin_match = any(origin_district.lower() in d.lower() for d in transporter.service_area_districts)
            dest_match = any(destination_district.lower() in d.lower() for d in transporter.service_area_districts)
            if origin_match and dest_match:
                eligibility_score += Decimal("15.00")
                match_reasons.append(f"Operating corridor covers both {origin_district} and {destination_district}")
            elif origin_match or dest_match:
                eligibility_score += Decimal("5.00")
                match_reasons.append(f"Operating scope covers {origin_district if origin_match else destination_district}")

        matching_criteria: dict[str, Any] = {
            "suitable_vehicles_count": len(suitable_vehicles),
            "total_fleet_count": len(vehicles),
            "match_reasons": match_reasons,
            "required_vehicle_class": required_vehicle_class,
            "origin_district": origin_district,
            "destination_district": destination_district,
        }

        if existing_opp:
            existing_opp.status = TransportOpportunityStatus.OPEN
            existing_opp.eligibility_score = eligibility_score
            existing_opp.matching_criteria_json = matching_criteria
            existing_opp.total_distance_km = total_distance_km
            existing_opp.estimated_cost = estimated_cost
            opp = existing_opp
        else:
            opp = TransportOpportunity(
                shipment_plan_id=plan.id,
                transporter_profile_id=transporter.id,
                status=TransportOpportunityStatus.OPEN,
                required_vehicle_class=required_vehicle_class,
                required_payload_quintals=required_payload_quintals,
                requires_cold_chain=requires_cold_chain,
                pickup_stops_count=pickup_stops_count,
                origin_district=origin_district,
                destination_district=destination_district,
                total_distance_km=total_distance_km,
                distance_certainty="MODELED_GEOGRAPHIC_DISTANCE",
                estimated_cost=estimated_cost,
                cost_certainty="MODELED_REGIONAL_ESTIMATE",
                earliest_pickup_date=plan.earliest_pickup_date,
                delivery_deadline=plan.delivery_deadline,
                eligibility_score=eligibility_score,
                matching_criteria_json=matching_criteria,
            )
            db.add(opp)

        db.flush()
        created_opportunities.append(opp)

        # Emit in-app notification to transporter idempotently
        from app.modules.marketplace.service import emit_idempotent_notification
        emit_idempotent_notification(
            db=db,
            recipient_user_id=transporter.user_id,
            notification_type="TRANSPORT_OPPORTUNITY_CREATED",
            title=f"New Transport Opportunity: {plan.commodity.name} ({plan.total_planned_quantity_quintals} qtl)",
            body=f"Multi-stop harvest consolidation ({pickup_stops_count} stops in {origin_district}) to {destination_district}. Estimated freight: Rs. {estimated_cost:,.0f}.",
            data_json={
                "opportunity_id": str(opp.id),
                "shipment_plan_id": str(plan.id),
                "plan_code": plan.plan_code,
                "commodity_name": plan.commodity.name,
                "quantity_quintals": float(plan.total_planned_quantity_quintals),
            },
            dedupe_key="opportunity_id",
        )

    db.commit()

    return BroadcastOpportunitiesResponse(
        plan_id=plan.id,
        plan_code=plan.plan_code,
        opportunities_created_count=len(created_opportunities),
        matched_transporters_count=len(transporters),
        opportunities=[
            TransportOpportunityResponse(
                id=o.id,
                shipment_plan_id=o.shipment_plan_id,
                shipment_id=o.shipment_id,
                transporter_profile_id=o.transporter_profile_id,
                status=o.status,
                required_vehicle_class=o.required_vehicle_class,
                required_payload_quintals=o.required_payload_quintals,
                required_payload_tonnes=Decimal(str(round(float(o.required_payload_quintals) / 10.0, 3))),
                requires_cold_chain=o.requires_cold_chain,
                pickup_stops_count=o.pickup_stops_count,
                origin_district=o.origin_district,
                destination_district=o.destination_district,
                total_distance_km=o.total_distance_km,
                distance_certainty=o.distance_certainty,
                estimated_cost=o.estimated_cost,
                cost_certainty=o.cost_certainty,
                earliest_pickup_date=o.earliest_pickup_date,
                delivery_deadline=o.delivery_deadline,
                eligibility_score=o.eligibility_score,
                matching_criteria_json=o.matching_criteria_json,
                expires_at=o.expires_at,
                responded_at=o.responded_at,
                decline_reason=o.decline_reason,
                created_at=o.created_at,
                updated_at=o.updated_at,
            )
            for o in created_opportunities
        ],
    )
