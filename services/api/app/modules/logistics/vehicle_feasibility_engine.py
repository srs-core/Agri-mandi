"""
Phase 2E - Step 3: Vehicle Feasibility & Selection Engine.
Determines optimal vehicle archetype and evaluates candidate vehicles based on
payload capacity, commodity perishability/cold-chain needs, multi-stop accessibility,
availability status, and cost certainty.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    Commodity,
    Location,
    LogisticsProvider,
    ShipmentPlan,
    ShipmentPlanPickupStop,
    TransportRateCard,
    Vehicle,
    VehicleTypeEnum,
)
from app.modules.intelligence.transport_cost import (
    DEFAULT_RATE_CARDS,
    calculate_haversine_road_distance,
    calculate_transport_cost,
)
from app.schemas.vehicle_feasibility import (
    DirectVehicleFeasibilityRequest,
    ShipmentVehicleFeasibilityResponse,
    VehicleCandidateOption,
)


ARCHETYPE_DEFINITIONS: Dict[VehicleTypeEnum, Dict[str, Any]] = {
    VehicleTypeEnum.MINI_TRUCK: {
        "label": "Mini Truck (1.0 MT)",
        "models": "Tata Ace Gold / Mahindra Jeeto / Maruti Super Carry",
        "max_payload_quintals": Decimal("10.0"),
        "is_refrigerated": False,
        "multi_stop_rating": "FEASIBLE_AGILE",
        "description": "Compact 4-wheeler optimized for narrow rural farm gates and small harvest consolidation (up to 1,000 kg).",
    },
    VehicleTypeEnum.PICKUP: {
        "label": "Pickup Truck (3.0 MT)",
        "models": "Mahindra Bolero Maxi Truck / Isuzu D-Max / Tata Yodha",
        "max_payload_quintals": Decimal("30.0"),
        "is_refrigerated": False,
        "multi_stop_rating": "FEASIBLE_AGILE",
        "description": "Versatile light commercial pickup suitable for 1 to 3 MT multi-farm pickups on rural terrain.",
    },
    VehicleTypeEnum.REEFER_VAN: {
        "label": "Refrigerated Reefer Van (4.0 MT)",
        "models": "Eicher Pro 2049 Reefer / Tata 407 Cold Chain Carrier",
        "max_payload_quintals": Decimal("40.0"),
        "is_refrigerated": True,
        "multi_stop_rating": "FEASIBLE_AGILE",
        "description": "Active insulated cold-chain van maintained at 2°C–12°C for delicate perishable produce.",
    },
    VehicleTypeEnum.MEDIUM_COMMERCIAL: {
        "label": "Medium Commercial Vehicle (8.0 MT)",
        "models": "Eicher Pro 6-Wheeler / Tata 1109 / Ashok Leyland Boss",
        "max_payload_quintals": Decimal("80.0"),
        "is_refrigerated": False,
        "multi_stop_rating": "FEASIBLE_STANDARD",
        "description": "Heavy-duty 6-wheeler truck for bulk inter-district transport and commercial mandi consolidation (up to 8 MT).",
    },
    VehicleTypeEnum.HEAVY_TRUCK: {
        "label": "Heavy Commercial Taurus (25.0 MT)",
        "models": "Tata Prima 10/12-Wheeler / BharatBenz 2823C Multi-Axle",
        "max_payload_quintals": Decimal("250.0"),
        "is_refrigerated": False,
        "multi_stop_rating": "CHALLENGING_NARROW_ACCESS",
        "description": "Multi-axle long-haul freight carrier for full truckload deliveries to major wholesale terminals (up to 25 MT).",
    },
}


def get_max_configured_vehicle_capacity(
    configured_archetypes: Optional[Dict[VehicleTypeEnum, Dict[str, Any]]] = None,
    live_vehicles: Optional[List[Vehicle]] = None,
) -> Decimal:
    """
    Derives the maximum single-vehicle payload capacity dynamically from currently
    configured vehicle classes and registered live fleet assets, avoiding hard-coded static limits.
    """
    archetypes = configured_archetypes or ARCHETYPE_DEFINITIONS
    max_arch = max((arch["max_payload_quintals"] for arch in archetypes.values()), default=Decimal("250.0"))
    max_live = Decimal("0.0")
    if live_vehicles:
        max_live = max(
            (Decimal(str(round(v.payload_capacity_kg / Decimal("100.0"), 2))) for v in live_vehicles),
            default=Decimal("0.0"),
        )
    return max(max_arch, max_live)


def determine_cold_chain_requirement(
    commodity: Optional[Commodity],
    explicit_is_perishable: Optional[bool] = None,
) -> Tuple[Literal["REQUIRED", "NOT_REQUIRED", "UNKNOWN"], bool]:
    """
    Determines cold-chain requirement from existing commodity metadata/configuration.
    Returns (status_enum, is_hard_cold_chain_required).
    If UNKNOWN: does not falsely assume cold-chain is required.
    """
    if explicit_is_perishable is not None:
        if explicit_is_perishable:
            return "REQUIRED", True
        else:
            return "NOT_REQUIRED", False

    if commodity is None:
        return "UNKNOWN", False

    if commodity.is_perishable is None:
        return "UNKNOWN", False
    elif commodity.is_perishable:
        return "REQUIRED", True
    else:
        return "NOT_REQUIRED", False


def evaluate_vehicle_candidate(
    vehicle_type: VehicleTypeEnum,
    planned_qty_qtl: Decimal,
    cold_chain_req: Literal["REQUIRED", "NOT_REQUIRED", "UNKNOWN"],
    is_hard_cold_chain_required: bool,
    stops_count: int,
    distance_km: Decimal,
    origin_name: str,
    dest_name: str,
    live_vehicle: Optional[Vehicle] = None,
    custom_rate_card: Optional[TransportRateCard] = None,
    configured_archetypes: Optional[Dict[VehicleTypeEnum, Dict[str, Any]]] = None,
) -> VehicleCandidateOption:
    """
    Evaluates a single vehicle candidate (live operational vehicle or reference archetype)
    against payload capacity, cold chain, multi-stop access, availability, and cost certainty.
    """
    archetypes = configured_archetypes or ARCHETYPE_DEFINITIONS
    archetype = archetypes.get(vehicle_type, ARCHETYPE_DEFINITIONS.get(vehicle_type, ARCHETYPE_DEFINITIONS[VehicleTypeEnum.PICKUP]))
    is_live = live_vehicle is not None

    if is_live:
        max_payload_qtl = Decimal(str(round(live_vehicle.payload_capacity_kg / Decimal("100.0"), 2)))
        is_refrigerated = live_vehicle.is_refrigerated
        model_name = live_vehicle.model_name or archetype["models"]
        reg_no = live_vehicle.registration_number
        provider_name = live_vehicle.provider.name if live_vehicle.provider else "Platform Provider"
        availability = "VERIFIED_AVAILABLE" if live_vehicle.is_available else "VERIFIED_BUSY"
        candidate_id = f"VEH-{str(live_vehicle.id)[:8].upper()}"
        candidate_type = "VERIFIED_OPERATIONAL_VEHICLE"
    else:
        max_payload_qtl = archetype["max_payload_quintals"]
        is_refrigerated = archetype["is_refrigerated"]
        model_name = archetype["models"]
        reg_no = None
        provider_name = None
        availability = "UNKNOWN_ARCHETYPE_ONLY"
        candidate_id = f"ARCHETYPE-{vehicle_type.value.upper()}"
        candidate_type = "REFERENCE_ARCHETYPE"

    max_payload_tonnes = Decimal(str(round(max_payload_qtl / Decimal("10.0"), 2)))

    # 1. Payload capacity evaluation
    is_cap_sufficient = max_payload_qtl >= planned_qty_qtl
    deficit_qtl = max(Decimal("0.0"), planned_qty_qtl - max_payload_qtl)
    utilization_pct = (
        Decimal(str(round((planned_qty_qtl / max_payload_qtl) * 100, 2)))
        if max_payload_qtl > Decimal("0.0")
        else Decimal("0.0")
    )

    # 2. Cold chain evaluation
    if is_hard_cold_chain_required:
        if is_refrigerated:
            cold_status = "SATISFIES_PERISHABLE"
            is_cold_chain_compatible = True
        else:
            cold_status = "COLD_CHAIN_REQUIRED_BUT_MISSING"
            is_cold_chain_compatible = False
    else:
        if is_refrigerated:
            cold_status = "REEFER_EXCESS_SURCHARGE"
            is_cold_chain_compatible = True
        else:
            cold_status = "NOT_REQUIRED_DRY"
            is_cold_chain_compatible = True

    # 3. Multi-stop accessibility
    if stops_count <= 1:
        multi_stop_rating = "FEASIBLE_STANDARD" if vehicle_type == VehicleTypeEnum.HEAVY_TRUCK else "FEASIBLE_AGILE"
    elif stops_count <= 4:
        if vehicle_type == VehicleTypeEnum.HEAVY_TRUCK:
            multi_stop_rating = "CHALLENGING_NARROW_ACCESS"
        else:
            multi_stop_rating = "FEASIBLE_AGILE"
    else:
        if vehicle_type == VehicleTypeEnum.HEAVY_TRUCK:
            multi_stop_rating = "RESTRICTED"
        elif vehicle_type == VehicleTypeEnum.MEDIUM_COMMERCIAL:
            multi_stop_rating = "FEASIBLE_STANDARD"
        else:
            multi_stop_rating = "FEASIBLE_AGILE"

    # 4. Cost calculation
    card_dict = None
    if custom_rate_card:
        card_dict = {
            "base_fare": custom_rate_card.base_fare,
            "per_km_rate": custom_rate_card.per_km_rate,
            "min_distance_km": custom_rate_card.min_distance_km,
            "reefer_surcharge_per_km": custom_rate_card.reefer_surcharge_per_km,
            "loading_unloading_charge": custom_rate_card.loading_unloading_charge,
            "provider_name": provider_name,
        }

    cost_breakdown = calculate_transport_cost(
        distance_km=distance_km,
        quantity_quintals=planned_qty_qtl,
        is_perishable=is_refrigerated and (is_hard_cold_chain_required or is_live),
        custom_rate_card=card_dict,
        origin_name=origin_name,
        destination_name=dest_name,
    )

    # 5. Feasibility reasons & disclaimers
    reasons: List[str] = []
    disclaimers: List[str] = []

    if is_cap_sufficient:
        reasons.append(f"Payload capacity ({max_payload_qtl} qtl = {max_payload_tonnes} MT) satisfies shipment ({planned_qty_qtl} qtl, {utilization_pct}% utilization).")
    else:
        reasons.append(f"INSUFFICIENT CAPACITY: Deficit of {deficit_qtl} qtl ({planned_qty_qtl} qtl payload vs {max_payload_qtl} qtl limit).")

    if is_hard_cold_chain_required:
        if is_refrigerated:
            reasons.append("Equipped with active refrigeration meeting perishable produce cold-chain requirements.")
        else:
            reasons.append("FAILS HARD FEASIBILITY: Produce requires active refrigeration, but vehicle is non-refrigerated.")
            disclaimers.append("Transporting temperature-sensitive perishable produce without cold chain leads to accelerated product decay.")
    else:
        if is_refrigerated:
            reasons.append("Reefer vehicle includes temperature control surcharge that is unnecessary for dry commodities.")
        else:
            reasons.append("Standard dry cargo configuration avoids unnecessary cold-chain surcharges.")

    if multi_stop_rating == "CHALLENGING_NARROW_ACCESS":
        disclaimers.append("Heavy multi-axle truck may face narrow turning and bridge weight restrictions on rural village roads.")
    elif multi_stop_rating == "RESTRICTED":
        disclaimers.append("Heavy vehicle cannot execute multi-stop rural collections safely without hub transshipment.")

    if not is_live:
        disclaimers.append("Reference vehicle archetype: real-time truck availability and confirmed quotes must be verified upon dispatch.")

    # 6. Hard feasibility check
    # Must have sufficient capacity, satisfy cold chain if required, and not be physically restricted
    hard_passed = (
        is_cap_sufficient
        and (not (is_hard_cold_chain_required and not is_refrigerated))
        and multi_stop_rating != "RESTRICTED"
    )

    # 7. Suitability score calculation
    if hard_passed:
        score = Decimal("50.0")

        # Capacity fit: tighter fit (closer to 100%) earns higher score
        util_ratio = min(Decimal("1.0"), utilization_pct / Decimal("100.0")) if max_payload_qtl > Decimal("0.0") else Decimal("0.0")
        score += util_ratio * Decimal("30.0")

        # Cold chain match
        if is_hard_cold_chain_required and is_refrigerated:
            score += Decimal("15.0")
        elif not is_hard_cold_chain_required and not is_refrigerated:
            score += Decimal("10.0")
        elif not is_hard_cold_chain_required and is_refrigerated:
            score -= Decimal("20.0")  # Wasteful reefer surcharge

        # Multi-stop fit
        if multi_stop_rating == "FEASIBLE_AGILE":
            score += Decimal("10.0")
        elif multi_stop_rating == "CHALLENGING_NARROW_ACCESS":
            score -= Decimal("15.0")

        # Live asset bonus
        if availability == "VERIFIED_AVAILABLE":
            score += Decimal("10.0")
    else:
        score = Decimal("0.0")

    score = max(Decimal("0.0"), min(Decimal("100.0"), score))

    return VehicleCandidateOption(
        candidate_id=candidate_id,
        candidate_type=candidate_type,
        vehicle_id=live_vehicle.id if live_vehicle else None,
        vehicle_type=vehicle_type,
        vehicle_type_label=archetype["label"],
        model_name=model_name,
        registration_number=reg_no,
        provider_name=provider_name,
        max_payload_quintals=max_payload_qtl,
        max_payload_tonnes=max_payload_tonnes,
        payload_utilization_pct=utilization_pct,
        is_capacity_sufficient=is_cap_sufficient,
        capacity_deficit_quintals=deficit_qtl,
        is_cold_chain_compatible=is_cold_chain_compatible,
        cold_chain_status=cold_status,
        multi_stop_feasibility=multi_stop_rating,
        operational_availability=availability,
        cost_certainty=cost_breakdown.cost_certainty,
        is_verified_quote=cost_breakdown.is_verified_quote,
        estimated_cost=cost_breakdown.total_transport_cost,
        estimated_cost_per_quintal=cost_breakdown.cost_per_quintal,
        cost_explanation=cost_breakdown.explanation,
        suitability_score=score,
        is_recommended=False,
        hard_feasibility_passed=hard_passed,
        feasibility_reasons=reasons,
        disclaimers=disclaimers,
    )


def evaluate_vehicle_options_core(
    db: Session,
    planned_qty_qtl: Decimal,
    commodity: Optional[Commodity],
    stops_count: int,
    distance_km: Decimal,
    origin_name: str,
    dest_name: str,
    origin_district: Optional[str] = None,
    dest_district: Optional[str] = None,
    shipment_plan_id: Optional[UUID] = None,
    plan_code: Optional[str] = None,
    explicit_is_perishable: Optional[bool] = None,
    configured_archetypes: Optional[Dict[VehicleTypeEnum, Dict[str, Any]]] = None,
) -> ShipmentVehicleFeasibilityResponse:
    """
    Core engine that evaluates reference archetypes and live registered vehicles,
    ranks candidate options, and produces a structured feasibility response.
    """
    if planned_qty_qtl <= Decimal("0.0"):
        return ShipmentVehicleFeasibilityResponse(
            shipment_plan_id=shipment_plan_id,
            plan_code=plan_code,
            evaluation_status="VEHICLE_REQUIREMENT_UNKNOWN",
            status_summary="Shipment quantity is zero or missing.",
            planned_quantity_quintals=Decimal("0.0"),
            planned_quantity_tonnes=Decimal("0.0"),
            commodity_name="Unknown",
            is_perishable=False,
            cold_chain_requirement="UNKNOWN",
            stops_count=stops_count,
            estimated_distance_km=distance_km,
            recommended_vehicle_class=None,
            primary_recommendation=None,
            ranked_options=[],
        )

    planned_tonnes = Decimal(str(round(planned_qty_qtl / Decimal("10.0"), 2)))
    cold_req, is_hard_cold_chain_required = determine_cold_chain_requirement(commodity, explicit_is_perishable)
    is_perishable = is_hard_cold_chain_required
    commodity_name = commodity.name if commodity else "Fresh Produce"

    # 1. Fetch live vehicles from DB
    live_vehicles = list(
        db.scalars(
            select(Vehicle)
            .options(
                joinedload(Vehicle.provider).joinedload(LogisticsProvider.rate_cards),
            )
            .where(Vehicle.is_available == True)
        ).unique().all()
    )
    if configured_archetypes is not None:
        live_vehicles = [v for v in live_vehicles if v.vehicle_type in configured_archetypes]

    # 2. Derive maximum single-vehicle capacity dynamically from configured archetypes and live assets
    max_feasible_capacity = get_max_configured_vehicle_capacity(
        configured_archetypes=configured_archetypes,
        live_vehicles=live_vehicles,
    )

    # If payload exceeds all configured/known vehicle capacities
    if planned_qty_qtl > max_feasible_capacity:
        deficit = planned_qty_qtl - max_feasible_capacity
        return ShipmentVehicleFeasibilityResponse(
            shipment_plan_id=shipment_plan_id,
            plan_code=plan_code,
            evaluation_status="VEHICLE_CAPACITY_INSUFFICIENT",
            status_summary=(
                f"Planned payload ({planned_qty_qtl} qtl = {planned_tonnes} MT) exceeds the maximum capacity of any currently configured "
                f"vehicle class ({max_feasible_capacity} qtl = {max_feasible_capacity / 10} MT) by {deficit} quintals ({deficit / 10} MT). "
                f"Multi-vehicle allocation or phased dispatch is required."
            ),
            planned_quantity_quintals=planned_qty_qtl,
            planned_quantity_tonnes=planned_tonnes,
            commodity_id=commodity.id if commodity else None,
            commodity_name=commodity_name,
            is_perishable=is_perishable,
            cold_chain_requirement=cold_req,
            stops_count=stops_count,
            origin_district=origin_district,
            destination_district=dest_district,
            estimated_distance_km=distance_km,
            recommended_vehicle_class=None,
            primary_recommendation=None,
            ranked_options=[],
            operational_guardrails=[
                f"Maximum single-vehicle payload evaluated across active configurations is {max_feasible_capacity} quintals ({max_feasible_capacity / 10} MT).",
                "System configuration capacity reflects platform fleet archetypes and registered carriers.",
                "Multi-vehicle dispatch planning is deferred to subsequent fleet allocation.",
            ],
        )

    candidates: List[VehicleCandidateOption] = []
    archetypes = configured_archetypes or ARCHETYPE_DEFINITIONS

    # 3. Evaluate Reference Archetypes
    for v_type in archetypes.keys():
        opt = evaluate_vehicle_candidate(
            vehicle_type=v_type,
            planned_qty_qtl=planned_qty_qtl,
            cold_chain_req=cold_req,
            is_hard_cold_chain_required=is_hard_cold_chain_required,
            stops_count=stops_count,
            distance_km=distance_km,
            origin_name=origin_name,
            dest_name=dest_name,
            live_vehicle=None,
            custom_rate_card=None,
            configured_archetypes=archetypes,
        )
        candidates.append(opt)

    # 4. Evaluate live registered vehicles
    for lv in live_vehicles:
        rate_card = next(
            (rc for rc in lv.provider.rate_cards if rc.vehicle_type == lv.vehicle_type and rc.is_active),
            None,
        )
        opt_live = evaluate_vehicle_candidate(
            vehicle_type=lv.vehicle_type,
            planned_qty_qtl=planned_qty_qtl,
            cold_chain_req=cold_req,
            is_hard_cold_chain_required=is_hard_cold_chain_required,
            stops_count=stops_count,
            distance_km=distance_km,
            origin_name=origin_name,
            dest_name=dest_name,
            live_vehicle=lv,
            custom_rate_card=rate_card,
            configured_archetypes=archetypes,
        )
        candidates.append(opt_live)

    # 5. Rank Candidates
    # Sorting priority:
    # 1. hard_feasibility_passed (True first)
    # 2. suitability_score descending
    # 3. max_payload_quintals ascending (smallest sufficient vehicle preferred)
    # 4. estimated_cost ascending
    candidates.sort(
        key=lambda c: (
            1 if c.hard_feasibility_passed else 0,
            c.suitability_score,
            -c.max_payload_quintals,
            -(c.estimated_cost or Decimal("999999")),
        ),
        reverse=True,
    )

    # 6. Determine Primary Recommendation
    feasible_candidates = [c for c in candidates if c.hard_feasibility_passed]

    if feasible_candidates:
        primary = feasible_candidates[0]
        for c in candidates:
            if c.candidate_id == primary.candidate_id:
                c.is_recommended = True
                break

        eval_status = "VEHICLE_MATCH_FOUND"
        status_summary = (
            f"Recommended '{primary.vehicle_type_label}' ({primary.model_name}) based on {primary.payload_utilization_pct}% payload fit, "
            f"commodity compatibility ({primary.cold_chain_status.lower().replace('_', ' ')}), and {stops_count}-stop pickup accessibility."
        )
        recommended_class = primary.vehicle_type_label
    else:
        primary = None
        eval_status = "VEHICLE_MATCH_UNAVAILABLE"
        status_summary = "No vehicle option satisfied all hard feasibility constraints."
        recommended_class = None

    operational_guardrails = [
        "Vehicle feasibility evaluation does not book, reserve, or dispatch a carrier.",
        "Reference archetypes provide modeled market benchmarks. Real transporter availability must be confirmed upon carrier bidding.",
        "Driver assignment, real road routing, and live GPS tracking are deferred to subsequent logistics phases.",
    ]

    return ShipmentVehicleFeasibilityResponse(
        shipment_plan_id=shipment_plan_id,
        plan_code=plan_code,
        evaluation_status=eval_status,
        status_summary=status_summary,
        planned_quantity_quintals=planned_qty_qtl,
        planned_quantity_tonnes=planned_tonnes,
        commodity_id=commodity.id if commodity else None,
        commodity_name=commodity_name,
        is_perishable=is_perishable,
        cold_chain_requirement=cold_req,
        stops_count=stops_count,
        origin_district=origin_district,
        destination_district=dest_district,
        estimated_distance_km=distance_km,
        recommended_vehicle_class=recommended_class,
        primary_recommendation=primary,
        ranked_options=candidates,
        operational_guardrails=operational_guardrails,
    )


def evaluate_shipment_plan_vehicle_feasibility(
    db: Session,
    shipment_plan_id: UUID,
) -> ShipmentVehicleFeasibilityResponse:
    """Evaluates vehicle options and sizing feasibility for an existing ShipmentPlan."""
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
        )
        .where(ShipmentPlan.id == shipment_plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{shipment_plan_id}' not found.",
        )

    stops = plan.pickup_stops
    first_stop = stops[0] if stops else None
    origin_loc = first_stop.pickup_location if first_stop else None
    dest_loc = plan.destination_location

    distance_km = Decimal("35.0")
    if (
        origin_loc
        and dest_loc
        and origin_loc.latitude is not None
        and origin_loc.longitude is not None
        and dest_loc.latitude is not None
        and dest_loc.longitude is not None
    ):
        distance_km = calculate_haversine_road_distance(
            float(origin_loc.latitude),
            float(origin_loc.longitude),
            float(dest_loc.latitude),
            float(dest_loc.longitude),
        )
    elif origin_loc and dest_loc and origin_loc.district and dest_loc.district:
        if origin_loc.district.lower() == dest_loc.district.lower():
            distance_km = Decimal("25.0")
        else:
            distance_km = Decimal("65.0")

    return evaluate_vehicle_options_core(
        db=db,
        planned_qty_qtl=plan.total_planned_quantity_quintals,
        commodity=plan.commodity,
        stops_count=len(stops),
        distance_km=distance_km,
        origin_name=origin_loc.name if origin_loc else "Farm Gate",
        dest_name=dest_loc.name if dest_loc else "Destination Hub",
        origin_district=origin_loc.district if origin_loc else None,
        dest_district=dest_loc.district if dest_loc else None,
        shipment_plan_id=plan.id,
        plan_code=plan.plan_code,
    )


def evaluate_direct_vehicle_feasibility(
    db: Session,
    request: DirectVehicleFeasibilityRequest,
    configured_archetypes: Optional[Dict[VehicleTypeEnum, Dict[str, Any]]] = None,
) -> ShipmentVehicleFeasibilityResponse:
    """Evaluates vehicle options and sizing feasibility on standalone parameters."""
    commodity = None
    if request.commodity_id:
        commodity = db.get(Commodity, request.commodity_id)
    elif request.commodity_name:
        commodity = db.scalar(select(Commodity).where(Commodity.name.ilike(f"%{request.commodity_name}%")))

    return evaluate_vehicle_options_core(
        db=db,
        planned_qty_qtl=request.quantity_quintals,
        commodity=commodity,
        stops_count=request.stops_count,
        distance_km=request.distance_km or Decimal("35.0"),
        origin_name=request.origin_name,
        dest_name=request.destination_name,
        origin_district="Pune",
        dest_district="Pune",
        shipment_plan_id=None,
        plan_code=None,
        explicit_is_perishable=request.is_perishable,
        configured_archetypes=configured_archetypes,
    )
