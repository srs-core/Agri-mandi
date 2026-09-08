"""
Phase 2E - Step 4: Route Feasibility & Waypoint Sequencing Engine.
Converts a ShipmentPlan into an ordered waypoint sequence, evaluates route feasibility,
tracks cumulative onboard payload, and validates delivery deadlines without claiming live GPS or false global optimality.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    Location,
    ShipmentPlan,
    ShipmentPlanPickupStop,
    VehicleTypeEnum,
)
from app.modules.logistics.route_optimizers import (
    BaseRouteOptimizer,
    DeterministicBaselineRouteOptimizer,
    ORToolsVehicleRoutingOptimizer,
)
from app.modules.logistics.routing_providers import (
    BaseRoutingProvider,
    LocationCoordinate,
    ModeledGeographicRoutingProvider,
    RouteCalculationResult,
)
from app.modules.logistics.vehicle_feasibility_engine import (
    ARCHETYPE_DEFINITIONS,
    evaluate_shipment_plan_vehicle_feasibility,
)
from app.schemas.route_optimization import (
    OptimizationComparisonMetrics,
    RouteOptimizationResponse,
    RouteOptimizationStatus,
)
from app.schemas.route_planning import (
    GeographicPrecisionEnum,
    RoutePlanResponse,
    RoutePlanningStatus,
    RouteWaypoint,
    WaypointTypeEnum,
)



def classify_location_precision(loc: Optional[Location]) -> GeographicPrecisionEnum:
    """Classifies a Location's coordinate completeness into 3 standard states."""
    if loc is None:
        return GeographicPrecisionEnum.UNAVAILABLE
    if loc.latitude is not None and loc.longitude is not None:
        return GeographicPrecisionEnum.EXACT
    if loc.district or loc.taluka or loc.name:
        return GeographicPrecisionEnum.ADMINISTRATIVE_ONLY
    return GeographicPrecisionEnum.UNAVAILABLE


def order_pickup_stops_deterministic(
    stops: List[ShipmentPlanPickupStop],
    destination_loc: Optional[Location],
) -> List[ShipmentPlanPickupStop]:
    """
    Deterministic baseline waypoint ordering heuristic.
    - If all stops have exact GPS: applies Nearest Neighbor ordering starting from first stop.
    - If administrative-only or mixed: preserves the verified stop_sequence from shipment planning.
    Explicitly labeled as a baseline ordering heuristic (not claimed as globally optimal VRP).
    """
    if len(stops) <= 1:
        return stops

    all_have_gps = all(
        s.pickup_location and s.pickup_location.latitude is not None and s.pickup_location.longitude is not None
        for s in stops
    )

    if not all_have_gps:
        # Preserve planned sequence
        return sorted(stops, key=lambda s: s.stop_sequence)

    # Nearest Neighbor ordering heuristic
    ordered: List[ShipmentPlanPickupStop] = []
    remaining = list(sorted(stops, key=lambda s: s.stop_sequence))
    current = remaining.pop(0)
    ordered.append(current)

    while remaining:
        curr_lat = float(current.pickup_location.latitude)
        curr_lon = float(current.pickup_location.longitude)

        def dist_to_current(s: ShipmentPlanPickupStop) -> float:
            s_lat = float(s.pickup_location.latitude)
            s_lon = float(s.pickup_location.longitude)
            return math.hypot(s_lat - curr_lat, s_lon - curr_lon)

        remaining.sort(key=dist_to_current)
        current = remaining.pop(0)
        ordered.append(current)

    return ordered


def build_and_evaluate_route_plan(
    db: Session,
    shipment_plan_id: UUID,
    routing_provider: Optional[BaseRoutingProvider] = None,
    assigned_vehicle_capacity_qtl: Optional[Decimal] = None,
    assigned_vehicle_class: Optional[str] = None,
) -> RoutePlanResponse:
    """
    Constructs an ordered waypoint itinerary from a ShipmentPlan, performs feasibility checks,
    tracks cumulative payload across stops, and calculates modeled distance/transit time.
    """
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.seller),
        )
        .where(ShipmentPlan.id == shipment_plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{shipment_plan_id}' not found.",
        )

    provider = routing_provider or ModeledGeographicRoutingProvider()

    # If vehicle capacity wasn't passed, evaluate vehicle feasibility to get default recommendation
    if assigned_vehicle_capacity_qtl is None:
        try:
            veh_feasibility = evaluate_shipment_plan_vehicle_feasibility(db, plan.id)
            if veh_feasibility.primary_recommendation:
                assigned_vehicle_capacity_qtl = veh_feasibility.primary_recommendation.max_payload_quintals
                assigned_vehicle_class = veh_feasibility.primary_recommendation.vehicle_type_label
        except Exception:
            pass

    stops = list(plan.pickup_stops)
    dest_loc = plan.destination_location

    feasibility_checks: List[str] = []
    warnings: List[str] = []
    operational_limitations: List[str] = [
        "Waypoint sequencing follows a deterministic baseline heuristic (Nearest Neighbor / Planned Sequence).",
        "Distances and transit durations are preliminary modeled estimates; live turn-by-turn road routes are deferred to dispatch.",
        "Vehicle tracking, driver assignment, and live GPS streaming are not implemented in this planning layer.",
    ]

    # 1. Check Data Completeness
    if not dest_loc:
        return RoutePlanResponse(
            shipment_plan_id=plan.id,
            plan_code=plan.plan_code,
            route_status=RoutePlanningStatus.ROUTE_DATA_INCOMPLETE,
            status_summary="Destination location is missing or unresolvable. Route plan cannot be constructed.",
            overall_geographic_precision=GeographicPrecisionEnum.UNAVAILABLE,
            routing_provider_name=provider.provider_name,
            waypoints_count=0,
            pickup_stops_count=len(stops),
            total_cargo_quantity_quintals=plan.total_planned_quantity_quintals,
            total_cargo_quantity_tonnes=Decimal(str(round(plan.total_planned_quantity_quintals / Decimal("10.0"), 2))),
            total_modeled_distance_km=None,
            distance_certainty="UNAVAILABLE",
            estimated_transit_hours=None,
            transit_time_certainty="UNAVAILABLE",
            assigned_vehicle_class=assigned_vehicle_class,
            vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
            waypoints=[],
            feasibility_checks=["FAILED: Missing delivery destination location."],
            warnings=["Destination location entity was not found in the database."],
            operational_limitations=operational_limitations,
        )

    if not stops:
        return RoutePlanResponse(
            shipment_plan_id=plan.id,
            plan_code=plan.plan_code,
            route_status=RoutePlanningStatus.ROUTE_DATA_INCOMPLETE,
            status_summary="Shipment plan contains zero pickup stops.",
            overall_geographic_precision=GeographicPrecisionEnum.UNAVAILABLE,
            routing_provider_name=provider.provider_name,
            waypoints_count=0,
            pickup_stops_count=0,
            total_cargo_quantity_quintals=Decimal("0.0"),
            total_cargo_quantity_tonnes=Decimal("0.0"),
            total_modeled_distance_km=None,
            distance_certainty="UNAVAILABLE",
            estimated_transit_hours=None,
            transit_time_certainty="UNAVAILABLE",
            assigned_vehicle_class=assigned_vehicle_class,
            vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
            waypoints=[],
            feasibility_checks=["FAILED: Zero pickup stops defined."],
            warnings=["No pickup locations to route."],
            operational_limitations=operational_limitations,
        )

    # 2. Check Quantity Reconciliation
    sum_stop_qtl = sum((s.allocated_quantity_quintals for s in stops), Decimal("0.0"))
    if sum_stop_qtl != plan.total_planned_quantity_quintals:
        warnings.append(
            f"Quantity mismatch: Sum of pickup stop allocations ({sum_stop_qtl} qtl) differs from plan header ({plan.total_planned_quantity_quintals} qtl)."
        )
    else:
        feasibility_checks.append(f"Quantity reconciliation passed: {sum_stop_qtl} qtl across {len(stops)} stops.")

    # 3. Check Vehicle Capacity
    hard_infeasible = False
    if assigned_vehicle_capacity_qtl is not None and sum_stop_qtl > assigned_vehicle_capacity_qtl:
        deficit = sum_stop_qtl - assigned_vehicle_capacity_qtl
        feasibility_checks.append(
            f"FAILED CAPACITY: Cumulative cargo ({sum_stop_qtl} qtl) exceeds vehicle capacity ({assigned_vehicle_capacity_qtl} qtl) by {deficit} qtl."
        )
        warnings.append(f"Vehicle capacity exceeded by {deficit} quintals.")
        hard_infeasible = True
    elif assigned_vehicle_capacity_qtl is not None:
        util_pct = round((sum_stop_qtl / assigned_vehicle_capacity_qtl) * 100, 1)
        feasibility_checks.append(f"Vehicle capacity satisfied: {sum_stop_qtl}/{assigned_vehicle_capacity_qtl} qtl ({util_pct}% utilization).")

    # 4. Check Date Windows / Delivery Deadline
    has_deadline_conflict = False
    if plan.earliest_pickup_date and plan.delivery_deadline and plan.earliest_pickup_date > plan.delivery_deadline:
        has_deadline_conflict = True
        feasibility_checks.append(
            f"FAILED DEADLINE: Shipment plan pickup date ({plan.earliest_pickup_date}) is after delivery deadline ({plan.delivery_deadline})."
        )
        warnings.append(f"Shipment pickup date ({plan.earliest_pickup_date}) conflicts with delivery deadline ({plan.delivery_deadline}).")
        hard_infeasible = True

    for s in stops:
        p_date = s.earliest_pickup_date
        if p_date and plan.delivery_deadline and p_date > plan.delivery_deadline:
            has_deadline_conflict = True
            feasibility_checks.append(
                f"FAILED DEADLINE: Pickup date ({p_date}) at stop {s.stop_sequence} is after delivery deadline ({plan.delivery_deadline})."
            )
            warnings.append(f"Pickup window at stop {s.stop_sequence} ({p_date}) conflicts with delivery deadline ({plan.delivery_deadline}).")
            hard_infeasible = True
            break

    if not has_deadline_conflict and plan.delivery_deadline:
        feasibility_checks.append(f"Time window compatible: All pickup dates are within delivery deadline {plan.delivery_deadline}.")
    elif not plan.delivery_deadline:
        feasibility_checks.append("Delivery deadline is open / not specified.")


    # 5. Order Pickups Deterministically
    ordered_stops = order_pickup_stops_deterministic(stops, dest_loc)

    # 6. Build Waypoint Sequence & Track Cumulative Onboard Load
    waypoints: List[RouteWaypoint] = []
    location_coords: List[LocationCoordinate] = []
    cumulative_qtl = Decimal("0.0")

    precision_set = set()

    for idx, stop in enumerate(ordered_stops, start=1):
        loc = stop.pickup_location
        prec = classify_location_precision(loc)
        precision_set.add(prec)

        cumulative_qtl += stop.allocated_quantity_quintals

        wp = RouteWaypoint(
            waypoint_sequence=idx,
            waypoint_type=WaypointTypeEnum.PICKUP,
            pickup_stop_id=stop.id,
            location_id=loc.id if loc else None,
            location_name=loc.name if loc else f"Pickup Stop {idx}",
            district=loc.district if loc else None,
            taluka=loc.taluka if loc else None,
            state=loc.state if loc else None,
            postal_code=loc.postal_code if loc else None,
            latitude=loc.latitude if loc else None,
            longitude=loc.longitude if loc else None,
            geographic_precision=prec,
            seller_user_id=stop.seller_user_id,
            seller_name=stop.seller_name or (stop.seller.display_name if stop.seller else "Farmer"),
            seller_role=stop.seller_role,
            stop_cargo_quantity_quintals=stop.allocated_quantity_quintals,
            stop_cargo_quantity_tonnes=Decimal(str(round(stop.allocated_quantity_quintals / Decimal("10.0"), 2))),
            cumulative_onboard_quantity_quintals=cumulative_qtl,
            cumulative_onboard_quantity_tonnes=Decimal(str(round(cumulative_qtl / Decimal("10.0"), 2))),
            earliest_arrival=stop.earliest_pickup_date,
            latest_departure=stop.latest_pickup_date,
            notes=f"Pickup allocation stop {idx} of {len(ordered_stops)}.",
        )
        waypoints.append(wp)
        location_coords.append(
            LocationCoordinate(
                label=wp.location_name,
                latitude=float(loc.latitude) if loc and loc.latitude is not None else None,
                longitude=float(loc.longitude) if loc and loc.longitude is not None else None,
                district=loc.district if loc else None,
                taluka=loc.taluka if loc else None,
            )
        )

    # Add Destination Waypoint
    dest_prec = classify_location_precision(dest_loc)
    precision_set.add(dest_prec)

    dest_wp = RouteWaypoint(
        waypoint_sequence=len(waypoints) + 1,
        waypoint_type=WaypointTypeEnum.DESTINATION,
        pickup_stop_id=None,
        location_id=dest_loc.id,
        location_name=dest_loc.name,
        district=dest_loc.district,
        taluka=dest_loc.taluka,
        state=dest_loc.state,
        postal_code=dest_loc.postal_code,
        latitude=dest_loc.latitude,
        longitude=dest_loc.longitude,
        geographic_precision=dest_prec,
        seller_user_id=None,
        seller_name=plan.buyer_organization_name or "Buyer Destination Terminal",
        seller_role="BUYER",
        stop_cargo_quantity_quintals=Decimal("0.0"),
        stop_cargo_quantity_tonnes=Decimal("0.0"),
        cumulative_onboard_quantity_quintals=cumulative_qtl,
        cumulative_onboard_quantity_tonnes=Decimal(str(round(cumulative_qtl / Decimal("10.0"), 2))),
        earliest_arrival=plan.earliest_pickup_date,
        latest_departure=plan.delivery_deadline,
        notes="Final buyer delivery destination terminal.",
    )
    waypoints.append(dest_wp)
    location_coords.append(
        LocationCoordinate(
            label=dest_wp.location_name,
            latitude=float(dest_loc.latitude) if dest_loc.latitude is not None else None,
            longitude=float(dest_loc.longitude) if dest_loc.longitude is not None else None,
            district=dest_loc.district,
            taluka=dest_loc.taluka,
        )
    )

    # 7. Calculate Route Distance & Transit Hours via Provider
    calc_result: RouteCalculationResult = provider.calculate_route(location_coords)

    # Assign segment distances to waypoints
    for i, seg_dist in enumerate(calc_result.segment_distances_km):
        if i < len(waypoints) - 1:
            waypoints[i].segment_distance_km = seg_dist

    # 8. Determine Overall Geographic Precision
    if GeographicPrecisionEnum.UNAVAILABLE in precision_set:
        overall_precision = GeographicPrecisionEnum.UNAVAILABLE
    elif GeographicPrecisionEnum.ADMINISTRATIVE_ONLY in precision_set:
        overall_precision = GeographicPrecisionEnum.ADMINISTRATIVE_ONLY
    else:
        overall_precision = GeographicPrecisionEnum.EXACT

    # 9. Determine Overall Route Status
    if hard_infeasible:
        route_status = RoutePlanningStatus.ROUTE_INFEASIBLE
        status_summary = "Route is infeasible due to hard constraint violations (capacity or deadline)."
    elif overall_precision != GeographicPrecisionEnum.EXACT:
        route_status = RoutePlanningStatus.ROUTE_FEASIBILITY_UNKNOWN
        status_summary = (
            "Route feasibility cannot be fully confirmed because one or more stops rely on administrative "
            "district definitions without exact verified GPS coordinates."
        )
        warnings.append("Exact GPS coordinates unavailable for one or more stops; road routing cannot be verified.")
    else:
        route_status = RoutePlanningStatus.ROUTE_FEASIBLE
        status_summary = (
            f"Route is feasible across {len(ordered_stops)} pickup stops ({cumulative_qtl} qtl) to destination '{dest_loc.name}' "
            f"with {calc_result.total_distance_km} km modeled distance."
        )

    return RoutePlanResponse(
        shipment_plan_id=plan.id,
        plan_code=plan.plan_code,
        route_status=route_status,
        status_summary=status_summary,
        overall_geographic_precision=overall_precision,
        is_optimized=False,
        routing_strategy="DETERMINISTIC_BASELINE_ORDERING",
        routing_provider_name=provider.provider_name,
        waypoints_count=len(waypoints),
        pickup_stops_count=len(ordered_stops),
        total_cargo_quantity_quintals=cumulative_qtl,
        total_cargo_quantity_tonnes=Decimal(str(round(cumulative_qtl / Decimal("10.0"), 2))),
        total_modeled_distance_km=calc_result.total_distance_km,
        distance_certainty=calc_result.distance_certainty,
        estimated_transit_hours=calc_result.estimated_transit_hours,
        transit_time_certainty=calc_result.transit_time_certainty,
        assigned_vehicle_class=assigned_vehicle_class,
        vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
        waypoints=waypoints,
        feasibility_checks=feasibility_checks,
        warnings=warnings,
        operational_limitations=operational_limitations,
    )


def optimize_shipment_plan_route(
    db: Session,
    shipment_plan_id: UUID,
    optimizer: Optional[BaseRouteOptimizer] = None,
    routing_provider: Optional[BaseRoutingProvider] = None,
    assigned_vehicle_capacity_qtl: Optional[Decimal] = None,
    assigned_vehicle_class: Optional[str] = None,
) -> RouteOptimizationResponse:
    """
    Optimizes the pickup waypoint sequence of a ShipmentPlan using Google OR-Tools VRP
    (or a pluggable optimizer), tracks cumulative load across the itinerary, and computes
    comparative savings against the baseline deterministic sequence.
    """
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.seller),
        )
        .where(ShipmentPlan.id == shipment_plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{shipment_plan_id}' not found.",
        )

    provider = routing_provider or ModeledGeographicRoutingProvider()
    solver = optimizer or ORToolsVehicleRoutingOptimizer()

    # 1. Determine vehicle capacity
    if assigned_vehicle_capacity_qtl is None:
        try:
            veh_feasibility = evaluate_shipment_plan_vehicle_feasibility(db, plan.id)
            if veh_feasibility.primary_recommendation:
                assigned_vehicle_capacity_qtl = veh_feasibility.primary_recommendation.max_payload_quintals
                assigned_vehicle_class = veh_feasibility.primary_recommendation.vehicle_type_label
        except Exception:
            pass

    stops = list(plan.pickup_stops)
    dest_loc = plan.destination_location

    feasibility_checks: List[str] = []
    warnings: List[str] = []
    operational_limitations: List[str] = [
        "Optimization determines the best visiting sequence of verified farm pickup stops before final buyer delivery.",
        "Distances and travel durations are based on modeled geographic routing (1.25x road factor) until live road provider is attached.",
        "Vehicle booking, live tracking, and driver dispatch are not executed in this planning phase.",
    ]

    total_cargo_qtl = sum((s.allocated_quantity_quintals for s in stops), Decimal("0.0"))
    total_cargo_tonnes = Decimal(str(round(total_cargo_qtl / Decimal("10.0"), 2)))
    precision_set = {classify_location_precision(s.pickup_location) for s in stops}
    if dest_loc is not None:
        precision_set.add(classify_location_precision(dest_loc))

    if GeographicPrecisionEnum.UNAVAILABLE in precision_set:
        overall_precision = GeographicPrecisionEnum.UNAVAILABLE
    elif GeographicPrecisionEnum.ADMINISTRATIVE_ONLY in precision_set:
        overall_precision = GeographicPrecisionEnum.ADMINISTRATIVE_ONLY
    else:
        overall_precision = GeographicPrecisionEnum.EXACT

    optimization_type = (
        "VERIFIED_ROAD_ROUTE_OPTIMIZATION"
        if provider.provider_name.startswith("Verified Road")
        else "MODELED_ROUTE_OPTIMIZATION"
    )

    # 2. Check for Incomplete Route Data
    if dest_loc is None or len(stops) == 0:
        return RouteOptimizationResponse(
            shipment_plan_id=plan.id,
            plan_code=plan.plan_code,
            optimization_status=RouteOptimizationStatus.ROUTE_DATA_INCOMPLETE,
            status_summary="Optimization cannot proceed because destination or pickup stops are missing.",
            overall_geographic_precision=overall_precision,
            routing_strategy="OR_TOOLS_VRP",
            optimizer_name=solver.optimizer_name,
            routing_provider_name=provider.provider_name,
            optimization_type=optimization_type,
            waypoints_count=0,
            pickup_stops_count=len(stops),
            total_cargo_quantity_quintals=total_cargo_qtl,
            total_cargo_quantity_tonnes=total_cargo_tonnes,
            assigned_vehicle_class=assigned_vehicle_class,
            vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
            total_distance_km=None,
            distance_certainty="UNAVAILABLE",
            estimated_transit_hours=None,
            transit_time_certainty="UNAVAILABLE",
            comparison_metrics=None,
            waypoints=[],
            feasibility_checks=["FAILED DATA: Missing destination location or 0 pickup stops."],
            warnings=["Shipment plan has incomplete geographic stops."],
            operational_limitations=operational_limitations,
        )

    # 3. Check Capacity Violation
    if assigned_vehicle_capacity_qtl is not None and total_cargo_qtl > assigned_vehicle_capacity_qtl:
        util_pct = Decimal(str(round((total_cargo_qtl / assigned_vehicle_capacity_qtl) * 100, 1)))
        return RouteOptimizationResponse(
            shipment_plan_id=plan.id,
            plan_code=plan.plan_code,
            optimization_status=RouteOptimizationStatus.CAPACITY_CONSTRAINT_FAILURE,
            status_summary=f"Optimization failed: Total cargo ({total_cargo_qtl} qtl) exceeds vehicle capacity ({assigned_vehicle_capacity_qtl} qtl).",
            overall_geographic_precision=overall_precision,
            routing_strategy="OR_TOOLS_VRP",
            optimizer_name=solver.optimizer_name,
            routing_provider_name=provider.provider_name,
            optimization_type=optimization_type,
            waypoints_count=0,
            pickup_stops_count=len(stops),
            total_cargo_quantity_quintals=total_cargo_qtl,
            total_cargo_quantity_tonnes=total_cargo_tonnes,
            assigned_vehicle_class=assigned_vehicle_class,
            vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
            vehicle_payload_utilization_pct=util_pct,
            total_distance_km=None,
            distance_certainty="UNAVAILABLE",
            estimated_transit_hours=None,
            transit_time_certainty="UNAVAILABLE",
            comparison_metrics=None,
            waypoints=[],
            feasibility_checks=[f"FAILED CAPACITY: Cargo {total_cargo_qtl} qtl exceeds vehicle capacity {assigned_vehicle_capacity_qtl} qtl."],
            warnings=["Vehicle payload capacity exceeded."],
            operational_limitations=operational_limitations,
        )

    # 4. Check Date Windows / Delivery Deadline Conflicts
    has_deadline_conflict = False
    if plan.earliest_pickup_date and plan.delivery_deadline and plan.earliest_pickup_date > plan.delivery_deadline:
        has_deadline_conflict = True
    for s in stops:
        if s.earliest_pickup_date and plan.delivery_deadline and s.earliest_pickup_date > plan.delivery_deadline:
            has_deadline_conflict = True
            break

    if has_deadline_conflict:
        return RouteOptimizationResponse(
            shipment_plan_id=plan.id,
            plan_code=plan.plan_code,
            optimization_status=RouteOptimizationStatus.TIME_WINDOW_CONFLICT,
            status_summary="Optimization failed: One or more pickup dates conflict with the delivery deadline.",
            overall_geographic_precision=overall_precision,
            routing_strategy="OR_TOOLS_VRP",
            optimizer_name=solver.optimizer_name,
            routing_provider_name=provider.provider_name,
            optimization_type=optimization_type,
            waypoints_count=0,
            pickup_stops_count=len(stops),
            total_cargo_quantity_quintals=total_cargo_qtl,
            total_cargo_quantity_tonnes=total_cargo_tonnes,
            assigned_vehicle_class=assigned_vehicle_class,
            vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
            total_distance_km=None,
            distance_certainty="UNAVAILABLE",
            estimated_transit_hours=None,
            transit_time_certainty="UNAVAILABLE",
            comparison_metrics=None,
            waypoints=[],
            feasibility_checks=[f"FAILED DEADLINE: Pickup window occurs after delivery deadline ({plan.delivery_deadline})."],
            warnings=["Time window violation between pickup availability and delivery deadline."],
            operational_limitations=operational_limitations,
        )

    # 5. Compute Baseline Route for Benchmark Comparison
    baseline_plan = build_and_evaluate_route_plan(
        db,
        shipment_plan_id=plan.id,
        routing_provider=provider,
        assigned_vehicle_capacity_qtl=assigned_vehicle_capacity_qtl,
        assigned_vehicle_class=assigned_vehicle_class,
    )
    baseline_dist = baseline_plan.total_modeled_distance_km or Decimal("0.0")
    baseline_duration = baseline_plan.estimated_transit_hours or Decimal("0.0")

    # 6. Execute Optimization Solver
    opt_result = solver.optimize(
        stops=stops,
        destination_loc=dest_loc,
        routing_provider=provider,
        vehicle_capacity_quintals=assigned_vehicle_capacity_qtl,
        delivery_deadline=plan.delivery_deadline,
    )

    if not opt_result.success:
        return RouteOptimizationResponse(
            shipment_plan_id=plan.id,
            plan_code=plan.plan_code,
            optimization_status=RouteOptimizationStatus.OPTIMIZATION_INFEASIBLE,
            status_summary=f"Route optimization infeasible: {opt_result.error_message}",
            overall_geographic_precision=overall_precision,
            routing_strategy="OR_TOOLS_VRP",
            optimizer_name=solver.optimizer_name,
            routing_provider_name=provider.provider_name,
            optimization_type=optimization_type,
            waypoints_count=0,
            pickup_stops_count=len(stops),
            total_cargo_quantity_quintals=total_cargo_qtl,
            total_cargo_quantity_tonnes=total_cargo_tonnes,
            assigned_vehicle_class=assigned_vehicle_class,
            vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
            total_distance_km=None,
            distance_certainty="UNAVAILABLE",
            estimated_transit_hours=None,
            transit_time_certainty="UNAVAILABLE",
            comparison_metrics=None,
            waypoints=[],
            feasibility_checks=[f"FAILED SOLVER: {opt_result.error_message}"],
            warnings=["No feasible routing sequence found by the solver."],
            operational_limitations=operational_limitations,
        )

    # 7. Construct Optimized Waypoints and Calculate Metrics
    ordered_stops = opt_result.ordered_stops
    waypoints: List[RouteWaypoint] = []
    location_coords: List[LocationCoordinate] = []
    cumulative_qtl = Decimal("0.0")

    for idx, stop in enumerate(ordered_stops, start=1):
        loc = stop.pickup_location
        prec = classify_location_precision(loc)
        stop_qtl = Decimal(str(stop.allocated_quantity_quintals))
        cumulative_qtl += stop_qtl

        location_coords.append(
            LocationCoordinate(
                label=loc.name if loc else f"Stop {idx}",
                latitude=float(loc.latitude) if loc and loc.latitude is not None else None,
                longitude=float(loc.longitude) if loc and loc.longitude is not None else None,
                district=loc.district if loc else None,
                taluka=loc.taluka if loc else None,
            )
        )

        waypoints.append(
            RouteWaypoint(
                waypoint_sequence=idx,
                waypoint_type=WaypointTypeEnum.PICKUP,
                location_id=stop.pickup_location_id,
                location_name=loc.name if loc else "Unknown Harvest Yard",
                district=loc.district if loc else None,
                taluka=loc.taluka if loc else None,
                state=loc.state if loc else "Maharashtra",
                postal_code=loc.postal_code if loc else None,
                latitude=loc.latitude if loc else None,
                longitude=loc.longitude if loc else None,
                geographic_precision=prec,
                seller_user_id=stop.seller_user_id,
                seller_name=stop.seller_name,
                seller_role=stop.seller_role,
                stop_cargo_quantity_quintals=stop_qtl,
                stop_cargo_quantity_tonnes=Decimal(str(round(stop_qtl / Decimal("10.0"), 2))),
                cumulative_onboard_quantity_quintals=cumulative_qtl,
                cumulative_onboard_quantity_tonnes=Decimal(str(round(cumulative_qtl / Decimal("10.0"), 2))),
                earliest_arrival=stop.earliest_pickup_date,
                latest_departure=stop.latest_pickup_date,
                segment_distance_km=None,
                notes=f"Pickup for {stop.seller_name} ({stop_qtl} qtl)",
            )
        )

    # Add Destination Waypoint
    dest_prec = classify_location_precision(dest_loc)
    location_coords.append(
        LocationCoordinate(
            label=dest_loc.name,
            latitude=float(dest_loc.latitude) if dest_loc.latitude is not None else None,
            longitude=float(dest_loc.longitude) if dest_loc.longitude is not None else None,
            district=dest_loc.district,
            taluka=dest_loc.taluka,
        )
    )

    waypoints.append(
        RouteWaypoint(
            waypoint_sequence=len(waypoints) + 1,
            waypoint_type=WaypointTypeEnum.DESTINATION,
            location_id=dest_loc.id,
            location_name=dest_loc.name,
            district=dest_loc.district,
            taluka=dest_loc.taluka,
            state=dest_loc.state,
            postal_code=dest_loc.postal_code,
            latitude=dest_loc.latitude,
            longitude=dest_loc.longitude,
            geographic_precision=dest_prec,
            seller_user_id=None,
            seller_name=plan.buyer_organization_name,
            seller_role="BUYER",
            stop_cargo_quantity_quintals=Decimal("0.0"),
            stop_cargo_quantity_tonnes=Decimal("0.0"),
            cumulative_onboard_quantity_quintals=cumulative_qtl,
            cumulative_onboard_quantity_tonnes=Decimal(str(round(cumulative_qtl / Decimal("10.0"), 2))),
            earliest_arrival=None,
            latest_departure=plan.delivery_deadline,
            segment_distance_km=None,
            notes=f"Final delivery to buyer destination ({dest_loc.name})",
        )
    )


    calc_result = provider.calculate_route(location_coords)
    for i, seg_dist in enumerate(calc_result.segment_distances_km):
        if i < len(waypoints) - 1:
            waypoints[i].segment_distance_km = seg_dist

    opt_dist = calc_result.total_distance_km or Decimal("0.0")
    opt_duration = calc_result.estimated_transit_hours or Decimal("0.0")

    # 8. Compute Comparison Metrics
    dist_reduction_km = max(Decimal("0.0"), baseline_dist - opt_dist)
    if baseline_dist > Decimal("0.0"):
        dist_reduction_pct = Decimal(str(round((dist_reduction_km / baseline_dist) * Decimal("100.0"), 2)))
    else:
        dist_reduction_pct = Decimal("0.0")

    duration_reduction_hours = max(Decimal("0.0"), baseline_duration - opt_duration)
    if baseline_duration > Decimal("0.0"):
        duration_reduction_pct = Decimal(str(round((duration_reduction_hours / baseline_duration) * Decimal("100.0"), 2)))
    else:
        duration_reduction_pct = Decimal("0.0")

    has_improvement = dist_reduction_km > Decimal("0.0")

    comparison_metrics = OptimizationComparisonMetrics(
        baseline_distance_km=baseline_dist,
        optimized_distance_km=opt_dist,
        distance_reduction_km=dist_reduction_km,
        distance_reduction_pct=dist_reduction_pct,
        baseline_duration_hours=baseline_duration,
        optimized_duration_hours=opt_duration,
        duration_reduction_pct=duration_reduction_pct,
        has_improvement=has_improvement,
    )

    # Feasibility Checks & Summary
    feasibility_checks.append(f"Quantity reconciliation passed: {cumulative_qtl} qtl collected across {len(ordered_stops)} stops.")
    util_pct = None
    if assigned_vehicle_capacity_qtl:
        util_pct = Decimal(str(round((cumulative_qtl / assigned_vehicle_capacity_qtl) * 100, 1)))
        feasibility_checks.append(f"Vehicle capacity satisfied: {cumulative_qtl}/{assigned_vehicle_capacity_qtl} qtl ({util_pct}% utilization).")
    if plan.delivery_deadline:
        feasibility_checks.append(f"Delivery deadline compatible: {plan.delivery_deadline}.")

    if overall_precision == GeographicPrecisionEnum.EXACT:
        status_summary = (
            f"Optimized route found ({solver.optimizer_name}): {opt_dist} km across {len(ordered_stops)} pickup stops "
            f"to destination '{dest_loc.name}' ({dist_reduction_pct}% distance savings vs baseline)."
        )
    else:
        status_summary = (
            f"Modeled route optimization computed for administrative locations: {opt_dist} km modeled distance "
            f"across {len(ordered_stops)} stops."
        )
        warnings.append("Stops rely on administrative district coordinates; road routing cannot be physically confirmed.")

    return RouteOptimizationResponse(
        shipment_plan_id=plan.id,
        plan_code=plan.plan_code,
        optimization_status=RouteOptimizationStatus.OPTIMIZED_ROUTE_FOUND,
        status_summary=status_summary,
        overall_geographic_precision=overall_precision,
        routing_strategy="OR_TOOLS_VRP",
        optimizer_name=solver.optimizer_name,
        routing_provider_name=provider.provider_name,
        optimization_type=optimization_type,
        waypoints_count=len(waypoints),
        pickup_stops_count=len(ordered_stops),
        total_cargo_quantity_quintals=cumulative_qtl,
        total_cargo_quantity_tonnes=total_cargo_tonnes,
        assigned_vehicle_class=assigned_vehicle_class,
        vehicle_payload_capacity_quintals=assigned_vehicle_capacity_qtl,
        vehicle_payload_utilization_pct=util_pct,
        total_distance_km=opt_dist,
        distance_certainty=calc_result.distance_certainty,
        estimated_transit_hours=opt_duration,
        transit_time_certainty=calc_result.transit_time_certainty,
        comparison_metrics=comparison_metrics,
        waypoints=waypoints,
        feasibility_checks=feasibility_checks,
        warnings=warnings,
        operational_limitations=operational_limitations,
    )

