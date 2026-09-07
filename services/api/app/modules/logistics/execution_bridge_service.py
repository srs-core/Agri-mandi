"""
Phase 2E - Step 6: Logistics Execution Bridge Service.
Bridges the planning layer (ShipmentPlan, PickupStops, Contributors, Vehicle Feasibility, Route Planning)
with operational shipment execution (Shipment, Tracking Events).

Provides:
1. assess_logistics_readiness: Comprehensive multi-point readiness assessment
2. assemble_logistics_cost_summary: Consolidated itemized transport cost breakdown
3. create_shipment_from_plan: Converts a READY_FOR_LOGISTICS plan into an operational Shipment record
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ApiError
from app.models.entities import (
    Commodity,
    Location,
    LogisticsProvider,
    Order,
    Shipment,
    ShipmentEvent,
    ShipmentPlan,
    ShipmentPlanningStatus,
    ShipmentPlanPickupStop,
    ShipmentStatus,
    Vehicle,
)
from app.modules.intelligence.transport_cost import calculate_transport_cost
from app.modules.logistics.route_planning_engine import build_and_evaluate_route_plan
from app.modules.logistics.service import _serialize_shipment
from app.modules.logistics.vehicle_feasibility_engine import evaluate_shipment_plan_vehicle_feasibility
from app.schemas.execution_bridge import (
    CostComponent,
    CreateShipmentFromPlanRequest,
    LogisticsCostSummary,
    LogisticsReadinessAssessment,
    LogisticsReadinessStatus,
    ReadinessCheckResult,
)
from app.schemas.logistics import ShipmentResponse


def assemble_logistics_cost_summary(
    db: Session,
    shipment_plan_id: UUID,
) -> LogisticsCostSummary:
    """
    Assembles a consolidated, itemized logistics cost summary for a shipment plan,
    combining vehicle sizing, road distance, cold-chain requirements, and verified/modeled rate cards.
    """
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

    # 1. Run vehicle feasibility to get candidate and distance
    veh_response = evaluate_shipment_plan_vehicle_feasibility(db, plan.id)
    rec = veh_response.primary_recommendation

    cost_components: List[CostComponent] = []

    if rec is not None:
        rec_vehicle_type = rec.vehicle_type.value if rec.vehicle_type else None
        rec_model = rec.model_name
        veh_certainty = rec.candidate_type
        distance_km = veh_response.estimated_distance_km
        total_cost = rec.estimated_cost
        cost_per_qtl = rec.estimated_cost_per_quintal
        cost_certainty = rec.cost_certainty
        is_verified = rec.is_verified_quote
        disclaimer = "\n".join(rec.disclaimers) if rec.disclaimers else (
            "Transport rate is verified from an active registered provider rate card."
            if is_verified
            else "Transport cost is a modeled regional benchmark estimate. Live transporter quote required prior to dispatch."
        )
        explanation = rec.cost_explanation
        rate_src = "Verified Transporter Rate Card" if is_verified else "Maharashtra Regional Benchmark Rate Card Model"

        # Itemize cost components from deterministic formula if available
        # Base fare + distance charge
        if total_cost is not None and distance_km is not None:
            # Generate breakdown components
            is_perishable = plan.commodity.is_perishable if plan.commodity and plan.commodity.is_perishable is not None else False
            breakdown = calculate_transport_cost(
                distance_km=distance_km,
                quantity_quintals=plan.total_planned_quantity_quintals,
                is_perishable=is_perishable,
            )

            cost_components.append(
                CostComponent(
                    component_name="Base Fare",
                    estimated_amount=breakdown.base_fare,
                    certainty=cost_certainty,
                    notes=f"Fixed terminal and positioning charge for {rec.vehicle_type_label}",
                )
            )
            cost_components.append(
                CostComponent(
                    component_name="Distance Freight",
                    estimated_amount=breakdown.distance_charge,
                    certainty=cost_certainty,
                    notes=f"Modeled road transit across {distance_km} km",
                )
            )
            if breakdown.reefer_surcharge > Decimal("0.00"):
                cost_components.append(
                    CostComponent(
                        component_name="Reefer Cold Chain Surcharge",
                        estimated_amount=breakdown.reefer_surcharge,
                        certainty=cost_certainty,
                        notes="Active refrigeration energy and insulation surcharge",
                    )
                )
            if breakdown.loading_unloading_charge > Decimal("0.00"):
                cost_components.append(
                    CostComponent(
                        component_name="Loading & Handling Charges",
                        estimated_amount=breakdown.loading_unloading_charge,
                        certainty=cost_certainty,
                        notes=f"Handling fee for multi-farm consolidation ({len(plan.pickup_stops)} pickup stops)",
                    )
                )
    else:
        rec_vehicle_type = None
        rec_model = None
        veh_certainty = "UNAVAILABLE"
        distance_km = None
        total_cost = None
        cost_per_qtl = None
        cost_certainty = "UNAVAILABLE"
        is_verified = False
        disclaimer = "Vehicle sizing and transport cost could not be modeled because no suitable vehicle archetype was matched."
        explanation = "Cost unavailable due to capacity or constraint mismatch."
        rate_src = "None"

    return LogisticsCostSummary(
        shipment_plan_id=plan.id,
        plan_code=plan.plan_code,
        recommended_vehicle_type=rec_vehicle_type,
        recommended_vehicle_model=rec_model,
        vehicle_certainty=veh_certainty,
        estimated_distance_km=distance_km,
        distance_certainty="MODELED_GEOGRAPHIC_DISTANCE" if distance_km else "UNAVAILABLE",
        cost_components=cost_components,
        total_estimated_cost=total_cost,
        estimated_cost_per_quintal=cost_per_qtl,
        cost_certainty=cost_certainty,
        is_verified_quote=is_verified,
        rate_source=rate_src,
        disclaimer=disclaimer,
        explanation=explanation,
    )


def assess_logistics_readiness(
    db: Session,
    shipment_plan_id: UUID,
) -> LogisticsReadinessAssessment:
    """
    Evaluates whether a ShipmentPlan is ready for operational logistics execution.
    Combines:
    - Planning lifecycle state
    - Pickup stop data completeness & quantity reconciliation
    - Geographic coordinates precision (EXACT vs ADMINISTRATIVE vs UNAVAILABLE)
    - Vehicle feasibility & capacity satisfaction
    - Route feasibility & time window alignment
    - Existing operational shipment check
    - Consolidated transport cost estimation
    """
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.seller),
            joinedload(ShipmentPlan.shipments),
        )
        .where(ShipmentPlan.id == shipment_plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{shipment_plan_id}' not found.",
        )

    checks: List[ReadinessCheckResult] = []
    blocking_issues: List[str] = []
    advisory_warnings: List[str] = []

    # ---------------------------------------------------------
    # Check 1: Plan Lifecycle Status
    # ---------------------------------------------------------
    if plan.planning_status == ShipmentPlanningStatus.READY_FOR_LOGISTICS:
        checks.append(
            ReadinessCheckResult(
                check_name="plan_status",
                status="passed",
                detail="Shipment plan is in 'ready_for_logistics' status and ready for execution.",
                certainty="verified",
            )
        )
    elif plan.planning_status == ShipmentPlanningStatus.PLANNED:
        msg = "Plan is in 'planned' draft status. Must transition to 'ready_for_logistics' before execution."
        checks.append(
            ReadinessCheckResult(
                check_name="plan_status",
                status="failed",
                detail=msg,
                certainty="verified",
            )
        )
        blocking_issues.append(msg)
    elif plan.planning_status == ShipmentPlanningStatus.CANCELLED:
        msg = "Shipment plan has been cancelled and cannot be executed."
        checks.append(
            ReadinessCheckResult(
                check_name="plan_status",
                status="failed",
                detail=msg,
                certainty="verified",
            )
        )
        blocking_issues.append(msg)

    # ---------------------------------------------------------
    # Check 2: Stops & Cargo Reconciliation
    # ---------------------------------------------------------
    stops = list(plan.pickup_stops)
    if not stops:
        msg = "No pickup stops defined in shipment plan."
        checks.append(
            ReadinessCheckResult(
                check_name="stops_cargo_reconciliation",
                status="failed",
                detail=msg,
                certainty="verified",
            )
        )
        blocking_issues.append(msg)
    else:
        allocated_total = sum(s.allocated_quantity_quintals for s in stops)
        if allocated_total != plan.total_planned_quantity_quintals:
            msg = f"Allocated stops total ({allocated_total} qtl) does not match plan total ({plan.total_planned_quantity_quintals} qtl)."
            checks.append(
                ReadinessCheckResult(
                    check_name="stops_cargo_reconciliation",
                    status="failed",
                    detail=msg,
                    certainty="verified",
                )
            )
            blocking_issues.append(msg)
        else:
            checks.append(
                ReadinessCheckResult(
                    check_name="stops_cargo_reconciliation",
                    status="passed",
                    detail=f"Reconciled {len(stops)} pickup stops totaling {plan.total_planned_quantity_quintals} qtl.",
                    certainty="verified",
                )
            )

    # ---------------------------------------------------------
    # Check 3: Geographic Precision
    # ---------------------------------------------------------
    dest = plan.destination_location
    has_missing_location = dest is None or any(s.pickup_location is None for s in stops)
    all_exact_gps = (
        not has_missing_location
        and dest.latitude is not None
        and dest.longitude is not None
        and all(s.pickup_location.latitude is not None and s.pickup_location.longitude is not None for s in stops)
    )

    if has_missing_location:
        msg = "Missing location entity for destination or one or more pickup stops."
        checks.append(
            ReadinessCheckResult(
                check_name="geographic_precision",
                status="failed",
                detail=msg,
                certainty="unavailable",
            )
        )
        blocking_issues.append(msg)
    elif all_exact_gps:
        checks.append(
            ReadinessCheckResult(
                check_name="geographic_precision",
                status="passed",
                detail="Verified GPS coordinates present for all pickup stops and destination hub.",
                certainty="verified",
            )
        )
    else:
        msg = "Locations rely on administrative boundaries (village/taluka/district); turn-by-turn road precision is modeled."
        checks.append(
            ReadinessCheckResult(
                check_name="geographic_precision",
                status="warning",
                detail=msg,
                certainty="modeled",
            )
        )
        advisory_warnings.append(msg)

    # ---------------------------------------------------------
    # Check 4: Vehicle Feasibility
    # ---------------------------------------------------------
    try:
        veh_eval = evaluate_shipment_plan_vehicle_feasibility(db, plan.id)
        if veh_eval.evaluation_status == "VEHICLE_MATCH_FOUND":
            checks.append(
                ReadinessCheckResult(
                    check_name="vehicle_feasibility",
                    status="passed",
                    detail=f"Feasible vehicle class matched: {veh_eval.recommended_vehicle_class} ({veh_eval.primary_recommendation.model_name if veh_eval.primary_recommendation else ''}).",
                    certainty="verified" if veh_eval.primary_recommendation and veh_eval.primary_recommendation.is_verified_quote else "modeled",
                )
            )
            if veh_eval.primary_recommendation:
                if veh_eval.primary_recommendation.multi_stop_feasibility == "CHALLENGING_NARROW_ACCESS":
                    advisory_warnings.append(
                        f"Multi-stop accessibility note: {veh_eval.primary_recommendation.vehicle_type_label} may encounter access challenges at narrow rural pickup gates."
                    )
        elif veh_eval.evaluation_status == "VEHICLE_CAPACITY_INSUFFICIENT":
            msg = f"Cargo quantity ({plan.total_planned_quantity_quintals} qtl) exceeds maximum single-vehicle payload capacity."
            checks.append(
                ReadinessCheckResult(
                    check_name="vehicle_feasibility",
                    status="failed",
                    detail=msg,
                    certainty="modeled",
                )
            )
            blocking_issues.append(msg)
        else:
            msg = f"Vehicle matching failed with status: {veh_eval.evaluation_status} ({veh_eval.status_summary})."
            checks.append(
                ReadinessCheckResult(
                    check_name="vehicle_feasibility",
                    status="failed",
                    detail=msg,
                    certainty="modeled",
                )
            )
            blocking_issues.append(msg)
    except Exception as e:
        msg = f"Vehicle feasibility evaluation encountered error: {str(e)}"
        checks.append(
            ReadinessCheckResult(
                check_name="vehicle_feasibility",
                status="failed",
                detail=msg,
                certainty="unavailable",
            )
        )
        blocking_issues.append(msg)

    # ---------------------------------------------------------
    # Check 5: Route Feasibility
    # ---------------------------------------------------------
    try:
        route_eval = build_and_evaluate_route_plan(db, plan.id)
        if route_eval.route_status.value == "route_feasible":
            checks.append(
                ReadinessCheckResult(
                    check_name="route_feasibility",
                    status="passed",
                    detail=f"Route is feasible across {len(route_eval.waypoints)} waypoints (estimated distance {route_eval.total_modeled_distance_km} km).",
                    certainty="modeled",
                )
            )
        elif route_eval.route_status.value == "route_feasibility_unknown":
            msg = "Route waypoint sequence generated from administrative boundaries; road navigation precision is estimated."
            checks.append(
                ReadinessCheckResult(
                    check_name="route_feasibility",
                    status="warning",
                    detail=msg,
                    certainty="modeled",
                )
            )
            advisory_warnings.append(msg)
        elif route_eval.route_status.value == "route_infeasible":
            msg = "Route feasibility check failed due to hard scheduling or payload constraint violation."
            checks.append(
                ReadinessCheckResult(
                    check_name="route_feasibility",
                    status="failed",
                    detail=msg,
                    certainty="modeled",
                )
            )
            blocking_issues.append(msg)
        else:
            msg = f"Route planning returned incomplete status: {route_eval.route_status.value}"
            checks.append(
                ReadinessCheckResult(
                    check_name="route_feasibility",
                    status="failed",
                    detail=msg,
                    certainty="unavailable",
                )
            )
            blocking_issues.append(msg)

        if route_eval.warnings:
            for w in route_eval.warnings:
                advisory_warnings.append(f"Route Warning: {w}")
    except Exception as e:
        msg = f"Route feasibility evaluation encountered error: {str(e)}"
        checks.append(
            ReadinessCheckResult(
                check_name="route_feasibility",
                status="failed",
                detail=msg,
                certainty="unavailable",
            )
        )
        blocking_issues.append(msg)

    # ---------------------------------------------------------
    # Check 6: Existing Operational Shipment Check
    # ---------------------------------------------------------
    existing_active_shipments = [
        s for s in plan.shipments if s.status != ShipmentStatus.CANCELLED
    ]
    if existing_active_shipments:
        shipment_id_str = str(existing_active_shipments[0].id)
        msg = f"Operational shipment {shipment_id_str[:8]} already initialized for this plan (status: {existing_active_shipments[0].status.value})."
        checks.append(
            ReadinessCheckResult(
                check_name="existing_shipment",
                status="warning",
                detail=msg,
                certainty="verified",
            )
        )
        advisory_warnings.append(msg)
    else:
        checks.append(
            ReadinessCheckResult(
                check_name="existing_shipment",
                status="passed",
                detail="No prior active operational shipment found for this plan.",
                certainty="verified",
            )
        )

    # ---------------------------------------------------------
    # Cost Summary Assembly
    # ---------------------------------------------------------
    cost_summary: Optional[LogisticsCostSummary] = None
    try:
        cost_summary = assemble_logistics_cost_summary(db, plan.id)
    except Exception:
        pass

    # ---------------------------------------------------------
    # Determine Overall Readiness Status
    # ---------------------------------------------------------
    if blocking_issues:
        overall_status = LogisticsReadinessStatus.NOT_READY
    elif advisory_warnings or not all_exact_gps:
        overall_status = LogisticsReadinessStatus.PARTIALLY_READY
    else:
        overall_status = LogisticsReadinessStatus.READY

    disclaimer = (
        "Logistics readiness is evaluated using verified database records, vehicle sizing archetypes, "
        "and deterministic road distance models. Live transporter quotes, driver assignments, and vehicle "
        "dispatch require explicit confirmation."
    )

    return LogisticsReadinessAssessment(
        shipment_plan_id=plan.id,
        plan_code=plan.plan_code,
        planning_status=plan.planning_status.value,
        overall_status=overall_status,
        checks=checks,
        estimated_cost_summary=cost_summary,
        blocking_issues=blocking_issues,
        advisory_warnings=advisory_warnings,
        disclaimer=disclaimer,
    )


def create_shipment_from_plan(
    db: Session,
    shipment_plan_id: UUID,
    request: CreateShipmentFromPlanRequest,
) -> ShipmentResponse:
    """
    Converts a READY_FOR_LOGISTICS ShipmentPlan into an operational Shipment record.
    Preserves full lineage and links the operational shipment to the shipment plan.
    """
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.shipments),
        )
        .where(ShipmentPlan.id == shipment_plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{shipment_plan_id}' not found.",
        )

    # 1. Enforce planning status requirement
    if plan.planning_status != ShipmentPlanningStatus.READY_FOR_LOGISTICS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Shipment plan must be in 'ready_for_logistics' status to create an operational shipment. "
                f"Current status is '{plan.planning_status.value}'."
            ),
        )

    # 2. Prevent duplicate active shipments for the same plan
    existing_active = [s for s in plan.shipments if s.status != ShipmentStatus.CANCELLED]
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active operational shipment ({existing_active[0].id}) already exists for this shipment plan.",
        )

    # 3. Validate origin and destination
    stops = list(plan.pickup_stops)
    if not stops:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot create shipment from plan with no pickup stops.",
        )

    first_stop = stops[0]
    origin_location_id = first_stop.pickup_location_id
    destination_location_id = plan.destination_location_id

    # 4. Validate optional vehicle and provider if provided
    if request.vehicle_id:
        veh = db.get(Vehicle, request.vehicle_id)
        if not veh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle '{request.vehicle_id}' not found.",
            )

    if request.provider_id:
        prov = db.get(LogisticsProvider, request.provider_id)
        if not prov:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Logistics provider '{request.provider_id}' not found.",
            )

    # 5. Get estimated cost from cost summary
    estimated_cost = None
    try:
        cost_summary = assemble_logistics_cost_summary(db, plan.id)
        estimated_cost = cost_summary.total_estimated_cost
    except Exception:
        pass

    # 6. Schedule pickup and delivery dates
    scheduled_pickup = request.scheduled_pickup_at
    if scheduled_pickup is None:
        scheduled_pickup = datetime.combine(plan.earliest_pickup_date, datetime.min.time(), tzinfo=timezone.utc)

    estimated_arrival = request.estimated_arrival_at
    if estimated_arrival is None and plan.delivery_deadline:
        estimated_arrival = datetime.combine(plan.delivery_deadline, datetime.min.time(), tzinfo=timezone.utc)

    # 7. Create Shipment record
    shipment = Shipment(
        shipment_plan_id=plan.id,
        order_id=plan.order_id,
        vehicle_id=request.vehicle_id,
        provider_id=request.provider_id,
        origin_location_id=origin_location_id,
        destination_location_id=destination_location_id,
        status=ShipmentStatus.SCHEDULED,
        scheduled_pickup_at=scheduled_pickup,
        estimated_arrival_at=estimated_arrival,
        estimated_cost=estimated_cost,
        driver_name=request.driver_name,
        driver_phone=request.driver_phone,
    )
    db.add(shipment)
    db.flush()

    # 8. Record initial milestone event
    notes = f"Operational shipment initialized from plan {plan.plan_code}."
    if request.notes:
        notes += f" Note: {request.notes}"

    event = ShipmentEvent(
        shipment_id=shipment.id,
        event_type="SHIPMENT_INITIALIZED_FROM_PLAN",
        location_name=first_stop.pickup_location.name if first_stop.pickup_location else "Origin Farm Gate",
        geo_point=f"POINT({first_stop.pickup_location.longitude} {first_stop.pickup_location.latitude})"
        if first_stop.pickup_location and first_stop.pickup_location.latitude is not None and first_stop.pickup_location.longitude is not None
        else None,
        notes=notes,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(event)

    db.commit()
    db.refresh(shipment)
    return _serialize_shipment(shipment)
