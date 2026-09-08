"""
Phase 2E - Step 2: Shipment Planning Foundation Service.
Generates structured shipment plans from buyer requirements, aggregation opportunities,
or confirmed orders with complete lineage, quantity integrity, and controlled lifecycle.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    BuyerProfile,
    BuyerRequirement,
    BuyerRequirementStatus,
    Commodity,
    Location,
    Order,
    OrderItem,
    OrderStatus,
    ProduceLot,
    ProduceLotStatus,
    ShipmentPlan,
    ShipmentPlanContributor,
    ShipmentPlanPickupStop,
    ShipmentPlanningStatus,
    User,
)
from app.modules.intelligence.aggregation_engine import (
    convert_price_to_per_quintal,
    convert_quantity_to_quintals,
)
from app.modules.intelligence.buyer_matching import evaluate_quality_compatibility
from app.schemas.shipment_plan import (
    PlannedLotAllocation,
    ShipmentPlanContributorResponse,
    ShipmentPlanFromOrderRequest,
    ShipmentPlanFromRequirementRequest,
    ShipmentPlanListResponse,
    ShipmentPlanPickupStopResponse,
    ShipmentPlanResponse,
)


def _generate_plan_code() -> str:
    """Generates a human-readable unique shipment plan code."""
    unique_suffix = str(uuid.uuid4())[:8].upper()
    return f"SHP-PLAN-{datetime.now(timezone.utc).year}-{unique_suffix}"


def _build_shipment_plan_response(plan: ShipmentPlan) -> ShipmentPlanResponse:
    """Converts a database ShipmentPlan entity into its response schema."""
    stops_responses: List[ShipmentPlanPickupStopResponse] = []
    total_contributors = 0

    for stop in plan.pickup_stops:
        contrib_responses: List[ShipmentPlanContributorResponse] = []
        for c in stop.contributors:
            contrib_responses.append(
                ShipmentPlanContributorResponse(
                    id=c.id,
                    produce_lot_id=c.produce_lot_id,
                    seller_user_id=c.seller_user_id,
                    fpo_member_id=c.fpo_member_id,
                    lot_allocated_quantity_quintals=c.lot_allocated_quantity_quintals,
                    asking_price_per_quintal=c.asking_price_per_quintal,
                    quality_grade=c.quality_grade,
                    notes=c.notes,
                )
            )
            total_contributors += 1

        loc = stop.pickup_location
        stops_responses.append(
            ShipmentPlanPickupStopResponse(
                id=stop.id,
                stop_sequence=stop.stop_sequence,
                seller_user_id=stop.seller_user_id,
                seller_name=stop.seller_name,
                seller_role=stop.seller_role,
                pickup_location_id=stop.pickup_location_id,
                pickup_location_name=loc.name if loc else "Farm Gate",
                pickup_district=loc.district if loc else None,
                pickup_state=loc.state if loc else "Maharashtra",
                latitude=float(loc.latitude) if loc and loc.latitude is not None else None,
                longitude=float(loc.longitude) if loc and loc.longitude is not None else None,
                allocated_quantity_quintals=stop.allocated_quantity_quintals,
                earliest_pickup_date=stop.earliest_pickup_date,
                latest_pickup_date=stop.latest_pickup_date,
                is_exact_gps=stop.is_exact_gps,
                contributors=contrib_responses,
            )
        )

    dest = plan.destination_location
    buyer_u = plan.buyer_user

    return ShipmentPlanResponse(
        id=plan.id,
        plan_code=plan.plan_code,
        planning_status=plan.planning_status.value if hasattr(plan.planning_status, "value") else str(plan.planning_status),
        buyer_requirement_id=plan.buyer_requirement_id,
        order_id=plan.order_id,
        aggregation_opportunity_id=plan.aggregation_opportunity_id,
        buyer_user_id=plan.buyer_user_id,
        buyer_name=buyer_u.display_name if buyer_u else None,
        buyer_organization_name=plan.buyer_organization_name,
        commodity_id=plan.commodity_id,
        commodity_name=plan.commodity.name if plan.commodity else None,
        variety=plan.variety,
        quality_grade=plan.quality_grade,
        total_planned_quantity_quintals=plan.total_planned_quantity_quintals,
        destination_location_id=plan.destination_location_id,
        destination_location_name=dest.name if dest else "Delivery Hub",
        destination_district=dest.district if dest else None,
        destination_state=dest.state if dest else "Maharashtra",
        destination_latitude=float(dest.latitude) if dest and dest.latitude is not None else None,
        destination_longitude=float(dest.longitude) if dest and dest.longitude is not None else None,
        earliest_pickup_date=plan.earliest_pickup_date,
        delivery_deadline=plan.delivery_deadline,
        estimated_gross_merchandise_value=plan.estimated_gross_merchandise_value,
        is_geographic_distance_exact=plan.is_geographic_distance_exact,
        geographic_precision_notes=plan.geographic_precision_notes,
        economic_disclaimer=plan.economic_disclaimer,
        pickup_stops=stops_responses,
        total_stops_count=len(stops_responses),
        total_contributors_count=total_contributors,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def create_shipment_plan_from_requirement(
    db: Session,
    request: ShipmentPlanFromRequirementRequest,
) -> ShipmentPlanResponse:
    """
    Creates a structured Shipment Plan to fulfill an active Buyer Requirement from allocated produce lots.
    Enforces quantity reconciliation, date window validity, quality grading, and non-destructive lineage.
    """
    # 1. Fetch & validate Buyer Requirement
    requirement = db.scalar(
        select(BuyerRequirement)
        .options(
            joinedload(BuyerRequirement.buyer_profile).joinedload(BuyerProfile.user),
            joinedload(BuyerRequirement.delivery_location),
            joinedload(BuyerRequirement.commodity),
        )
        .where(BuyerRequirement.id == request.buyer_requirement_id)
    )
    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Buyer requirement '{request.buyer_requirement_id}' not found.",
        )
    if requirement.status != BuyerRequirementStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Buyer requirement status is '{requirement.status.value}'. Must be 'active' for shipment planning.",
        )

    # 2. Validate pickup date against delivery deadline
    earliest_pickup = request.earliest_pickup_date or date.today()
    if requirement.delivery_by and earliest_pickup > requirement.delivery_by:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Earliest pickup date ({earliest_pickup}) cannot be after requirement delivery deadline ({requirement.delivery_by}).",
        )

    # 3. Validate Lot Allocations & Quantity Integrity
    seen_lot_ids: Set[UUID] = set()
    total_allocated_quintals = Decimal("0.0")
    validated_lots: List[Tuple[ProduceLot, Decimal, Decimal]] = []  # (lot, allocated_qtl, asking_price_qtl)

    for alloc in request.lot_allocations:
        if alloc.produce_lot_id in seen_lot_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Duplicate produce lot '{alloc.produce_lot_id}' specified in shipment allocations.",
            )
        seen_lot_ids.add(alloc.produce_lot_id)

        lot = db.scalar(
            select(ProduceLot)
            .options(
                joinedload(ProduceLot.seller),
                joinedload(ProduceLot.pickup_location),
                joinedload(ProduceLot.owner_fpo_profile),
            )
            .where(ProduceLot.id == alloc.produce_lot_id)
        )
        if not lot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produce lot '{alloc.produce_lot_id}' not found.",
            )
        if lot.status != ProduceLotStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Produce lot '{lot.id}' status is '{lot.status.value}'. Must be 'published' to plan shipment.",
            )
        if lot.commodity_id != requirement.commodity_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Produce lot '{lot.id}' commodity does not match requirement commodity '{requirement.commodity.name}'.",
            )

        # Quantity checks
        allocated_qtl = convert_quantity_to_quintals(alloc.allocated_quantity, alloc.unit)
        available_qtl = convert_quantity_to_quintals(lot.available_quantity, lot.unit)

        if allocated_qtl <= Decimal("0.0"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Allocated quantity for lot '{lot.id}' must be greater than zero.",
            )
        if allocated_qtl > available_qtl:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Allocated quantity ({allocated_qtl} qtl) exceeds available quantity ({available_qtl} qtl) for lot '{lot.id}'.",
            )

        # Quality check
        qual_ok, qual_msg = evaluate_quality_compatibility(lot.quality_grade, requirement.minimum_quality_grade)
        if not qual_ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Quality mismatch for lot '{lot.id}': {qual_msg}",
            )

        asking_price_qtl = convert_price_to_per_quintal(lot.asking_price_per_unit, lot.unit)
        validated_lots.append((lot, allocated_qtl, asking_price_qtl or Decimal("0.0")))
        total_allocated_quintals += allocated_qtl

    # 4. Economic Value Calculation
    target_price_qtl = convert_price_to_per_quintal(requirement.target_price_per_unit, requirement.unit)
    total_gross_val = Decimal("0.0")
    for lot, qtl, ask_p in validated_lots:
        price_to_use = target_price_qtl if target_price_qtl is not None else ask_p
        total_gross_val += qtl * price_to_use

    # 5. Geographic precision check
    dest_loc = requirement.delivery_location
    dest_has_gps = dest_loc.latitude is not None and dest_loc.longitude is not None
    all_stops_have_gps = dest_has_gps and all(
        l.pickup_location and l.pickup_location.latitude is not None and l.pickup_location.longitude is not None
        for l, _, _ in validated_lots
    )
    geo_precision_notes = (
        "All pickup stops and destination have verified GPS coordinates."
        if all_stops_have_gps
        else "One or more pickup or delivery locations rely on administrative district definitions without verified coordinates."
    )

    buyer_prof = requirement.buyer_profile
    buyer_u = buyer_prof.user if buyer_prof else None

    # 6. Instantiate ShipmentPlan
    plan = ShipmentPlan(
        plan_code=_generate_plan_code(),
        planning_status=ShipmentPlanningStatus.PLANNED,
        buyer_requirement_id=requirement.id,
        order_id=None,
        aggregation_opportunity_id=request.aggregation_opportunity_id,
        buyer_user_id=buyer_u.id if buyer_u else None,
        buyer_organization_name=buyer_prof.organization_name if buyer_prof else None,
        commodity_id=requirement.commodity_id,
        variety=None,
        quality_grade=requirement.minimum_quality_grade,
        total_planned_quantity_quintals=total_allocated_quintals,
        destination_location_id=requirement.delivery_location_id,
        earliest_pickup_date=earliest_pickup,
        delivery_deadline=requirement.delivery_by,
        estimated_gross_merchandise_value=Decimal(str(round(total_gross_val, 2))),
        is_geographic_distance_exact=all_stops_have_gps,
        geographic_precision_notes=geo_precision_notes,
        economic_disclaimer=(
            "Logistics transportation pricing, carrier dispatch, and route optimization are deferred to subsequent logistics execution."
        ),
        lineage_summary={
            "source_type": "BUYER_REQUIREMENT",
            "buyer_requirement_id": str(requirement.id),
            "aggregation_opportunity_id": request.aggregation_opportunity_id,
            "lots_count": len(validated_lots),
            "total_allocated_quintals": str(total_allocated_quintals),
        },
    )
    db.add(plan)
    db.flush()

    # 7. Group validated lots into Pickup Stops (group by seller and pickup_location)
    stops_map: Dict[Tuple[UUID, UUID], List[Tuple[ProduceLot, Decimal, Decimal]]] = {}
    for lot, alloc_qtl, ask_p in validated_lots:
        key = (lot.seller_user_id, lot.pickup_location_id)
        stops_map.setdefault(key, []).append((lot, alloc_qtl, ask_p))

    sequence = 1
    for (seller_id, loc_id), lot_tuples in stops_map.items():
        first_lot = lot_tuples[0][0]
        seller = first_lot.seller
        stop_total_qtl = sum(q for _, q, _ in lot_tuples)
        loc = first_lot.pickup_location
        stop_has_gps = loc.latitude is not None and loc.longitude is not None if loc else False

        seller_role = "FPO" if (first_lot.is_aggregated or first_lot.owner_fpo_profile_id is not None) else "FARMER"

        stop = ShipmentPlanPickupStop(
            shipment_plan_id=plan.id,
            stop_sequence=sequence,
            seller_user_id=seller_id,
            seller_name=seller.display_name if seller else "Seller",
            seller_role=seller_role,
            pickup_location_id=loc_id,
            allocated_quantity_quintals=stop_total_qtl,
            earliest_pickup_date=earliest_pickup,
            latest_pickup_date=requirement.delivery_by,
            is_exact_gps=stop_has_gps,
        )
        db.add(stop)
        db.flush()

        for lot, alloc_qtl, ask_p in lot_tuples:
            contrib = ShipmentPlanContributor(
                pickup_stop_id=stop.id,
                produce_lot_id=lot.id,
                seller_user_id=seller_id,
                fpo_member_id=None,
                lot_allocated_quantity_quintals=alloc_qtl,
                asking_price_per_quintal=ask_p,
                quality_grade=lot.quality_grade,
                notes=f"Allocated {alloc_qtl} qtl from produce lot '{lot.title}'",
            )
            db.add(contrib)

        sequence += 1

    db.commit()
    db.refresh(plan)

    return _build_shipment_plan_response(plan)


def create_shipment_plan_from_order(
    db: Session,
    request: ShipmentPlanFromOrderRequest,
) -> ShipmentPlanResponse:
    """
    Creates a structured Shipment Plan from an existing confirmed Order.
    """
    order = db.scalar(
        select(Order)
        .options(
            joinedload(Order.buyer),
            joinedload(Order.seller),
            joinedload(Order.delivery_location),
            joinedload(Order.items).joinedload(OrderItem.produce_lot).joinedload(ProduceLot.pickup_location),
            joinedload(Order.items).joinedload(OrderItem.commodity),
        )
        .where(Order.id == request.order_id)
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{request.order_id}' not found.",
        )
    if not order.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Order '{order.id}' has no order items.",
        )
    if not order.delivery_location_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Order '{order.id}' has no designated delivery location.",
        )

    first_item = order.items[0]
    earliest_pickup = request.earliest_pickup_date or date.today()

    total_planned_qtl = Decimal("0.0")
    for item in order.items:
        q_qtl = convert_quantity_to_quintals(item.quantity, item.unit)
        total_planned_qtl += q_qtl

    dest_loc = order.delivery_location
    dest_has_gps = dest_loc.latitude is not None and dest_loc.longitude is not None if dest_loc else False

    plan = ShipmentPlan(
        plan_code=_generate_plan_code(),
        planning_status=ShipmentPlanningStatus.PLANNED,
        buyer_requirement_id=None,
        order_id=order.id,
        aggregation_opportunity_id=None,
        buyer_user_id=order.buyer_user_id,
        buyer_organization_name=order.buyer.display_name if order.buyer else None,
        commodity_id=first_item.commodity_id,
        variety=None,
        quality_grade=first_item.produce_lot.quality_grade if first_item.produce_lot else None,
        total_planned_quantity_quintals=total_planned_qtl,
        destination_location_id=order.delivery_location_id,
        earliest_pickup_date=earliest_pickup,
        delivery_deadline=None,
        estimated_gross_merchandise_value=order.total_amount,
        is_geographic_distance_exact=dest_has_gps,
        geographic_precision_notes="Shipment planned from confirmed commercial marketplace order.",
        economic_disclaimer=(
            "Logistics transportation pricing, carrier dispatch, and route optimization are deferred to subsequent logistics execution."
        ),
        lineage_summary={
            "source_type": "CONFIRMED_ORDER",
            "order_id": str(order.id),
            "items_count": len(order.items),
            "total_planned_quintals": str(total_planned_qtl),
        },
    )
    db.add(plan)
    db.flush()

    # Create stops for order items
    stops_map: Dict[Tuple[UUID, UUID], List[OrderItem]] = {}
    for item in order.items:
        lot = item.produce_lot
        key = (lot.seller_user_id, lot.pickup_location_id)
        stops_map.setdefault(key, []).append(item)

    sequence = 1
    for (seller_id, loc_id), items in stops_map.items():
        first_lot = items[0].produce_lot
        seller = first_lot.seller
        stop_total_qtl = sum(convert_quantity_to_quintals(it.quantity, it.unit) for it in items)
        loc = first_lot.pickup_location
        stop_has_gps = loc.latitude is not None and loc.longitude is not None if loc else False

        seller_role = "FPO" if (first_lot.is_aggregated or first_lot.owner_fpo_profile_id is not None) else "FARMER"

        stop = ShipmentPlanPickupStop(
            shipment_plan_id=plan.id,
            stop_sequence=sequence,
            seller_user_id=seller_id,
            seller_name=seller.display_name if seller else "Seller",
            seller_role=seller_role,
            pickup_location_id=loc_id,
            allocated_quantity_quintals=stop_total_qtl,
            earliest_pickup_date=earliest_pickup,
            latest_pickup_date=None,
            is_exact_gps=stop_has_gps,
        )
        db.add(stop)
        db.flush()

        for item in items:
            lot = item.produce_lot
            item_qtl = convert_quantity_to_quintals(item.quantity, item.unit)
            ask_p = convert_price_to_per_quintal(item.agreed_price_per_unit, item.unit)
            contrib = ShipmentPlanContributor(
                pickup_stop_id=stop.id,
                produce_lot_id=lot.id,
                seller_user_id=seller_id,
                fpo_member_id=None,
                lot_allocated_quantity_quintals=item_qtl,
                asking_price_per_quintal=ask_p,
                quality_grade=lot.quality_grade,
                notes=f"Allocated from Order Item '{item.id}'",
            )
            db.add(contrib)

        sequence += 1

    db.commit()
    db.refresh(plan)

    return _build_shipment_plan_response(plan)


def get_shipment_plan(db: Session, plan_id: UUID) -> ShipmentPlanResponse:
    """Retrieves a specific shipment plan by ID with full stops and contributor lineage."""
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.buyer_user),
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.contributors),
        )
        .where(ShipmentPlan.id == plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{plan_id}' not found.",
        )
    return _build_shipment_plan_response(plan)


def list_shipment_plans(
    db: Session,
    status_filter: Optional[ShipmentPlanningStatus] = None,
    commodity_id: Optional[UUID] = None,
    buyer_requirement_id: Optional[UUID] = None,
    limit: int = 50,
) -> ShipmentPlanListResponse:
    """Lists shipment plans with optional status, commodity, or requirement filters."""
    query = (
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.buyer_user),
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.contributors),
        )
        .order_by(ShipmentPlan.created_at.desc())
        .limit(limit)
    )

    if status_filter:
        query = query.where(ShipmentPlan.planning_status == status_filter)
    if commodity_id:
        query = query.where(ShipmentPlan.commodity_id == commodity_id)
    if buyer_requirement_id:
        query = query.where(ShipmentPlan.buyer_requirement_id == buyer_requirement_id)

    plans = db.scalars(query).unique().all()
    responses = [_build_shipment_plan_response(p) for p in plans]

    return ShipmentPlanListResponse(
        total_count=len(responses),
        plans=responses,
    )


def mark_shipment_plan_ready(db: Session, plan_id: UUID) -> ShipmentPlanResponse:
    """
    Transitions a Shipment Plan from PLANNED to READY_FOR_LOGISTICS.
    Confirms that all supply allocations are locked and ready for future transporter bidding/dispatch.
    """
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.buyer_user),
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.contributors),
        )
        .where(ShipmentPlan.id == plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{plan_id}' not found.",
        )
    if plan.planning_status == ShipmentPlanningStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot mark a cancelled shipment plan as ready for logistics.",
        )

    plan.planning_status = ShipmentPlanningStatus.READY_FOR_LOGISTICS
    db.commit()
    db.refresh(plan)

    return _build_shipment_plan_response(plan)


def cancel_shipment_plan(db: Session, plan_id: UUID, reason: Optional[str] = None) -> ShipmentPlanResponse:
    """
    Cancels a Shipment Plan and releases allocated produce back to available status.
    """
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            joinedload(ShipmentPlan.buyer_user),
            joinedload(ShipmentPlan.commodity),
            joinedload(ShipmentPlan.destination_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.pickup_location),
            joinedload(ShipmentPlan.pickup_stops).joinedload(ShipmentPlanPickupStop.contributors),
        )
        .where(ShipmentPlan.id == plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment plan '{plan_id}' not found.",
        )
    if plan.planning_status == ShipmentPlanningStatus.CANCELLED:
        return _build_shipment_plan_response(plan)

    plan.planning_status = ShipmentPlanningStatus.CANCELLED
    if reason and plan.lineage_summary:
        summary = dict(plan.lineage_summary)
        summary["cancellation_reason"] = reason
        summary["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        plan.lineage_summary = summary

    db.commit()
    db.refresh(plan)

    return _build_shipment_plan_response(plan)
