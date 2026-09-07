"""
Phase 2H: Shipment Execution & Checkpoint Tracking Service.
Provides server-side sequential milestone progression, quantity reconciliation,
event auditing, in-app notifications, and RBAC protection for executing freight shipments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.entities import (
    CheckpointStatus,
    CheckpointType,
    Notification,
    Role,
    RoleName,
    Shipment,
    ShipmentCheckpoint,
    ShipmentEvent,
    ShipmentPlan,
    ShipmentPlanPickupStop,
    ShipmentStatus,
    TransporterProfile,
    User,
    UserRole,
    Vehicle,
)
from app.schemas.execution_tracking import (
    CheckpointArriveRequest,
    CheckpointCompleteRequest,
    CheckpointLoadingRequest,
    DeliveryCompleteRequest,
    DestinationArriveRequest,
    ShipmentCheckpointResponse,
    ShipmentExceptionRequest,
    ShipmentExecutionDetailResponse,
    TransitStartRequest,
)
from app.schemas.logistics import ShipmentEventResponse


def initialize_shipment_checkpoints(db: Session, shipment: Shipment) -> list[ShipmentCheckpoint]:
    """
    Initializes sequential ShipmentCheckpoint records from the associated ShipmentPlan.
    Creates 1 checkpoint per pickup stop + 1 destination checkpoint.
    """
    existing = db.scalars(
        select(ShipmentCheckpoint)
        .where(ShipmentCheckpoint.shipment_id == shipment.id)
        .order_by(ShipmentCheckpoint.stop_sequence)
    ).all()
    if existing:
        return list(existing)

    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            selectinload(ShipmentPlan.pickup_stops).selectinload(ShipmentPlanPickupStop.pickup_location),
            selectinload(ShipmentPlan.destination_location),
            selectinload(ShipmentPlan.commodity),
        )
        .where(ShipmentPlan.id == shipment.shipment_plan_id)
    )

    checkpoints: list[ShipmentCheckpoint] = []
    total_planned = Decimal("0.000")

    if plan and plan.pickup_stops:
        sorted_stops = sorted(plan.pickup_stops, key=lambda s: s.stop_sequence)
        for stop in sorted_stops:
            district_str = stop.pickup_location.district or stop.pickup_location.name
            loc_name = f"{stop.seller_name} ({district_str})"
            cp = ShipmentCheckpoint(
                shipment_id=shipment.id,
                checkpoint_type=CheckpointType.PICKUP,
                stop_sequence=stop.stop_sequence,
                pickup_stop_id=stop.id,
                location_id=stop.pickup_location_id,
                location_name=loc_name,
                seller_user_id=stop.seller_user_id,
                seller_name=stop.seller_name,
                status=CheckpointStatus.PENDING,
                planned_quantity_quintals=stop.allocated_quantity_quintals,
            )
            checkpoints.append(cp)
            total_planned += stop.allocated_quantity_quintals

        # Add destination checkpoint
        dest_seq = len(sorted_stops) + 1
        dest_loc = plan.destination_location
        dest_name = f"{dest_loc.name} ({dest_loc.district or 'Destination'})"
        dest_cp = ShipmentCheckpoint(
            shipment_id=shipment.id,
            checkpoint_type=CheckpointType.DESTINATION,
            stop_sequence=dest_seq,
            pickup_stop_id=None,
            location_id=plan.destination_location_id,
            location_name=dest_name,
            seller_user_id=None,
            seller_name=None,
            status=CheckpointStatus.PENDING,
            planned_quantity_quintals=plan.total_planned_quantity_quintals,
        )
        checkpoints.append(dest_cp)
    else:
        # Fallback for direct single-leg shipments without plan
        total_planned = shipment.total_planned_quantity_quintals or Decimal("10.000")
        cp_origin = ShipmentCheckpoint(
            shipment_id=shipment.id,
            checkpoint_type=CheckpointType.PICKUP,
            stop_sequence=1,
            pickup_stop_id=None,
            location_id=shipment.origin_location_id,
            location_name="Origin Farm Gate",
            seller_user_id=None,
            seller_name="Origin Seller",
            status=CheckpointStatus.PENDING,
            planned_quantity_quintals=total_planned,
        )
        cp_dest = ShipmentCheckpoint(
            shipment_id=shipment.id,
            checkpoint_type=CheckpointType.DESTINATION,
            stop_sequence=2,
            pickup_stop_id=None,
            location_id=shipment.destination_location_id,
            location_name="Destination Terminal",
            seller_user_id=None,
            seller_name=None,
            status=CheckpointStatus.PENDING,
            planned_quantity_quintals=total_planned,
        )
        checkpoints.extend([cp_origin, cp_dest])

    db.add_all(checkpoints)
    shipment.total_planned_quantity_quintals = total_planned
    shipment.total_picked_up_quantity_quintals = Decimal("0.000")
    shipment.current_checkpoint_sequence = 1
    db.flush()
    return checkpoints


def _load_shipment_with_relations(db: Session, shipment_id: UUID, for_update: bool = False) -> Shipment:
    stmt = (
        select(Shipment)
        .options(
            selectinload(Shipment.checkpoints),
            selectinload(Shipment.events),
            selectinload(Shipment.shipment_plan).selectinload(ShipmentPlan.commodity),
            selectinload(Shipment.shipment_plan).selectinload(ShipmentPlan.pickup_stops),
            selectinload(Shipment.vehicle),
            selectinload(Shipment.provider),
            selectinload(Shipment.origin_location),
            selectinload(Shipment.destination_location),
        )
        .where(Shipment.id == shipment_id)
    )
    if for_update:
        stmt = stmt.with_for_update()
    shipment = db.scalar(stmt)
    if not shipment:
        raise ApiError(404, "shipment_not_found", f"Shipment {shipment_id} not found.")

    if not shipment.checkpoints:
        initialize_shipment_checkpoints(db, shipment)
        # re-query checkpoints
        shipment.checkpoints = list(
            db.scalars(
                select(ShipmentCheckpoint)
                .where(ShipmentCheckpoint.shipment_id == shipment.id)
                .order_by(ShipmentCheckpoint.stop_sequence)
            ).all()
        )
    return shipment


def _verify_transporter_actor(db: Session, user_id: UUID, shipment: Shipment) -> TransporterProfile:
    """Verifies that the actor is the assigned transporter or system admin."""
    user = db.scalar(select(User).options(selectinload(User.user_roles).selectinload(UserRole.role)).where(User.id == user_id))
    if not user:
        raise ApiError(404, "user_not_found", "User not found.")

    role_names = {ur.role.name for ur in user.user_roles if ur.role}
    if RoleName.ADMIN in role_names:
        prof = db.scalar(select(TransporterProfile).where(TransporterProfile.user_id == user_id))
        return prof or TransporterProfile(user_id=user_id, organization_name="Admin Dispatch")

    profile = db.scalar(select(TransporterProfile).where(TransporterProfile.user_id == user_id))
    if not profile:
        raise ApiError(403, "not_a_transporter", "User does not have an active transporter profile.")

    # Check if this transporter is assigned to the shipment
    if shipment.provider and shipment.provider.registered_transporter_profile_id == profile.id:
        return profile

    raise ApiError(403, "unauthorized_transporter", "You are not the assigned transporter for this shipment.")


def _create_notification(db: Session, user_id: UUID, title: str, message: str, notification_type: str = "SHIPMENT_MILESTONE", payload: dict[str, Any] | None = None) -> None:
    notif = Notification(
        recipient_user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=message,
        data_json=payload,
        read_at=None,
    )
    db.add(notif)


def get_shipment_execution_detail(
    db: Session, user_id: UUID, user_roles: list[str], shipment_id: UUID
) -> ShipmentExecutionDetailResponse:
    """Retrieves full shipment execution detail with RBAC visibility filtering."""
    shipment = _load_shipment_with_relations(db, shipment_id)

    # RBAC check
    is_admin = RoleName.ADMIN.value in user_roles or "admin" in user_roles
    is_transporter = RoleName.TRANSPORTER.value in user_roles or "transporter" in user_roles
    is_buyer = RoleName.BUYER.value in user_roles or "buyer" in user_roles
    is_farmer = RoleName.FARMER.value in user_roles or "farmer" in user_roles or "fpo" in user_roles

    allowed = False
    if is_admin:
        allowed = True
    elif is_transporter and shipment.provider:
        trans_prof = db.scalar(select(TransporterProfile).where(TransporterProfile.user_id == user_id))
        if trans_prof and shipment.provider.registered_transporter_profile_id == trans_prof.id:
            allowed = True
    elif is_buyer and shipment.shipment_plan and shipment.shipment_plan.buyer_user_id == user_id:
        allowed = True
    elif is_farmer:
        seller_ids = {cp.seller_user_id for cp in shipment.checkpoints if cp.seller_user_id}
        if user_id in seller_ids:
            allowed = True

    if not allowed:
        raise ApiError(403, "access_denied", "You are not authorized to view tracking for this shipment.")

    total_cps = len(shipment.checkpoints)
    completed_cps = sum(1 for cp in shipment.checkpoints if cp.status == CheckpointStatus.COMPLETED)
    if shipment.status == ShipmentStatus.DELIVERED:
        progress_pct = 100.0
    elif total_cps > 0:
        progress_pct = round((completed_cps / total_cps) * 100.0, 1)
    else:
        progress_pct = 0.0

    commodity_name = shipment.shipment_plan.commodity.name if shipment.shipment_plan and shipment.shipment_plan.commodity else "Agricultural Produce"

    return ShipmentExecutionDetailResponse(
        id=shipment.id,
        plan_id=shipment.shipment_plan_id,
        plan_code=shipment.shipment_plan.plan_code if shipment.shipment_plan else None,
        order_id=shipment.order_id,
        status=shipment.status,
        commodity_name=commodity_name,
        total_planned_quantity_quintals=shipment.total_planned_quantity_quintals or Decimal("0.000"),
        total_picked_up_quantity_quintals=shipment.total_picked_up_quantity_quintals or Decimal("0.000"),
        delivered_quantity_quintals=shipment.delivered_quantity_quintals,
        progress_percentage=progress_pct,
        current_checkpoint_sequence=shipment.current_checkpoint_sequence,
        total_checkpoints_count=total_cps,
        completed_checkpoints_count=completed_cps,
        vehicle_id=shipment.vehicle_id,
        vehicle_model=shipment.vehicle.model_name if shipment.vehicle else None,
        vehicle_reg_number=shipment.vehicle.registration_number if shipment.vehicle else None,
        transporter_name=shipment.provider.name if shipment.provider else None,
        driver_name=shipment.driver_name,
        driver_phone=shipment.driver_phone,
        origin_location_name=shipment.origin_location.name if shipment.origin_location else None,
        destination_location_name=shipment.destination_location.name if shipment.destination_location else None,
        delivery_variance_reason=shipment.delivery_variance_reason,
        receiver_name=shipment.receiver_name,
        delivery_notes=shipment.delivery_notes,
        checkpoints=[
            ShipmentCheckpointResponse.model_validate(cp)
            for cp in sorted(shipment.checkpoints, key=lambda x: x.stop_sequence)
        ],
        timeline=[
            ShipmentEventResponse.model_validate(e)
            for e in sorted(shipment.events, key=lambda x: x.recorded_at)
        ],
        created_at=shipment.created_at,
        updated_at=shipment.updated_at,
    )


def record_checkpoint_arrival(
    db: Session, user_id: UUID, shipment_id: UUID, checkpoint_id: UUID, payload: CheckpointArriveRequest
) -> ShipmentExecutionDetailResponse:
    """Transporter confirms arrival at a pickup or destination checkpoint."""
    shipment = _load_shipment_with_relations(db, shipment_id, for_update=True)
    _verify_transporter_actor(db, user_id, shipment)

    cp = db.scalar(select(ShipmentCheckpoint).where(ShipmentCheckpoint.id == checkpoint_id, ShipmentCheckpoint.shipment_id == shipment.id).with_for_update())
    if not cp:
        raise ApiError(404, "checkpoint_not_found", f"Checkpoint {checkpoint_id} not found on shipment.")

    # Validate sequence
    if cp.stop_sequence != shipment.current_checkpoint_sequence:
        raise ApiError(400, "invalid_sequence", f"Cannot arrive at stop #{cp.stop_sequence}. Current active stop is #{shipment.current_checkpoint_sequence}.")

    # Idempotent arrival
    now = datetime.now(timezone.utc)
    if cp.status == CheckpointStatus.ARRIVED:
        return get_shipment_execution_detail(db, user_id, [RoleName.TRANSPORTER.value], shipment_id)

    if cp.status == CheckpointStatus.COMPLETED:
        raise ApiError(400, "checkpoint_already_completed", "This checkpoint has already been completed.")

    cp.status = CheckpointStatus.ARRIVED
    cp.arrived_at = now
    if payload.notes:
        cp.notes = f"{cp.notes or ''} | Arrival notes: {payload.notes}".strip(" |")

    if cp.checkpoint_type == CheckpointType.PICKUP:
        if shipment.status in [ShipmentStatus.SCHEDULED, ShipmentStatus.ASSIGNED]:
            shipment.status = ShipmentStatus.IN_PICKUP
        event_type = "ARRIVED_AT_PICKUP"
    else:
        shipment.status = ShipmentStatus.AT_DESTINATION
        event_type = "ARRIVED_AT_DESTINATION"

    # Audit event
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            event_type=event_type,
            location_name=cp.location_name,
            notes=payload.notes or f"Arrived at checkpoint #{cp.stop_sequence} ({cp.location_name})",
            recorded_at=now,
        )
    )

    # Notify Seller if pickup
    if cp.seller_user_id:
        _create_notification(
            db,
            cp.seller_user_id,
            title="Transporter Arrived",
            message=f"Transporter has arrived at your farm gate ({cp.location_name}) for pickup.",
            payload={"shipment_id": str(shipment.id), "checkpoint_id": str(cp.id)},
        )

    db.commit()
    return get_shipment_execution_detail(db, user_id, [RoleName.TRANSPORTER.value], shipment_id)


def record_checkpoint_loading_start(
    db: Session, user_id: UUID, shipment_id: UUID, checkpoint_id: UUID, payload: CheckpointLoadingRequest
) -> ShipmentExecutionDetailResponse:
    """Transporter confirms that crop loading has commenced at a pickup checkpoint."""
    shipment = _load_shipment_with_relations(db, shipment_id, for_update=True)
    _verify_transporter_actor(db, user_id, shipment)

    cp = db.scalar(select(ShipmentCheckpoint).where(ShipmentCheckpoint.id == checkpoint_id, ShipmentCheckpoint.shipment_id == shipment.id).with_for_update())
    if not cp:
        raise ApiError(404, "checkpoint_not_found", f"Checkpoint {checkpoint_id} not found on shipment.")

    if cp.checkpoint_type != CheckpointType.PICKUP:
        raise ApiError(400, "invalid_checkpoint_type", "Loading action is only valid for pickup checkpoints.")

    if cp.stop_sequence != shipment.current_checkpoint_sequence:
        raise ApiError(400, "invalid_sequence", f"Cannot load at stop #{cp.stop_sequence}. Current active stop is #{shipment.current_checkpoint_sequence}.")

    if cp.status == CheckpointStatus.COMPLETED:
        raise ApiError(400, "checkpoint_already_completed", "This checkpoint has already been completed.")

    now = datetime.now(timezone.utc)
    if cp.status != CheckpointStatus.ARRIVED:
        cp.arrived_at = cp.arrived_at or now

    cp.status = CheckpointStatus.LOADING
    cp.loading_started_at = now
    if payload.notes:
        cp.notes = f"{cp.notes or ''} | Loading start notes: {payload.notes}".strip(" |")

    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            event_type="LOADING_STARTED",
            location_name=cp.location_name,
            notes=payload.notes or f"Commenced produce loading at stop #{cp.stop_sequence}",
            recorded_at=now,
        )
    )

    db.commit()
    return get_shipment_execution_detail(db, user_id, [RoleName.TRANSPORTER.value], shipment_id)


def record_checkpoint_completion(
    db: Session, user_id: UUID, shipment_id: UUID, checkpoint_id: UUID, payload: CheckpointCompleteRequest
) -> ShipmentExecutionDetailResponse:
    """Transporter confirms pickup completion and records verified loaded quantity with variance tracking."""
    shipment = _load_shipment_with_relations(db, shipment_id, for_update=True)
    _verify_transporter_actor(db, user_id, shipment)

    cp = db.scalar(select(ShipmentCheckpoint).where(ShipmentCheckpoint.id == checkpoint_id, ShipmentCheckpoint.shipment_id == shipment.id).with_for_update())
    if not cp:
        raise ApiError(404, "checkpoint_not_found", f"Checkpoint {checkpoint_id} not found on shipment.")

    if cp.checkpoint_type != CheckpointType.PICKUP:
        raise ApiError(400, "invalid_checkpoint_type", "Pickup completion is only applicable to pickup checkpoints.")

    if cp.stop_sequence != shipment.current_checkpoint_sequence:
        raise ApiError(400, "invalid_sequence", f"Cannot complete stop #{cp.stop_sequence}. Current active stop is #{shipment.current_checkpoint_sequence}.")

    if cp.status == CheckpointStatus.COMPLETED:
        raise ApiError(400, "checkpoint_already_completed", "This checkpoint has already been completed.")

    loaded_qty = payload.loaded_quantity_quintals
    planned_qty = cp.planned_quantity_quintals
    variance = loaded_qty - planned_qty

    # Strict variance reason check
    if variance != Decimal("0") and not payload.variance_reason:
        raise ApiError(
            422,
            "variance_reason_required",
            f"Loaded quantity ({loaded_qty} QTL) differs from planned ({planned_qty} QTL). An explicit variance reason is required.",
        )

    # Cargo overflow guard: total picked up cannot exceed total planned shipment capacity
    other_loaded = db.scalar(
        select(ShipmentCheckpoint)
        .where(
            ShipmentCheckpoint.shipment_id == shipment.id,
            ShipmentCheckpoint.checkpoint_type == CheckpointType.PICKUP,
            ShipmentCheckpoint.id != cp.id,
            ShipmentCheckpoint.status == CheckpointStatus.COMPLETED,
        )
    )
    all_pickups = db.scalars(
        select(ShipmentCheckpoint).where(
            ShipmentCheckpoint.shipment_id == shipment.id,
            ShipmentCheckpoint.checkpoint_type == CheckpointType.PICKUP,
        )
    ).all()
    sum_other_pickups = sum((p.loaded_quantity_quintals or Decimal("0")) for p in all_pickups if p.id != cp.id and p.status == CheckpointStatus.COMPLETED)
    new_total_picked_up = sum_other_pickups + loaded_qty

    if shipment.total_planned_quantity_quintals and new_total_picked_up > shipment.total_planned_quantity_quintals * Decimal("1.20"):
        # Allow up to 20% aggregate harvest overfill with variance reason, but block gross overflow
        raise ApiError(
            422,
            "cargo_overflow",
            f"Total picked up quantity ({new_total_picked_up} QTL) exceeds the maximum allowed shipment allocation ({shipment.total_planned_quantity_quintals} QTL).",
        )

    now = datetime.now(timezone.utc)
    cp.status = CheckpointStatus.COMPLETED
    cp.loaded_quantity_quintals = loaded_qty
    cp.variance_quintals = variance
    cp.variance_reason = payload.variance_reason
    cp.loading_completed_at = now
    cp.completed_at = now
    if payload.notes:
        cp.notes = f"{cp.notes or ''} | Pickup complete: {payload.notes}".strip(" |")

    shipment.total_picked_up_quantity_quintals = new_total_picked_up
    shipment.current_checkpoint_sequence += 1

    # Audit event
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            event_type="PICKUP_COMPLETED",
            location_name=cp.location_name,
            notes=f"Pickup #{cp.stop_sequence} completed: Loaded {loaded_qty} QTL (Variance: {variance:+} QTL). Notes: {payload.notes or 'None'}",
            recorded_at=now,
        )
    )

    # Notifications
    if cp.seller_user_id:
        _create_notification(
            db,
            cp.seller_user_id,
            title="Pickup Completed",
            message=f"Pickup Stop #{cp.stop_sequence} completed: {loaded_qty} QTL collected from your lot.",
            payload={"shipment_id": str(shipment.id), "loaded_quantity": str(loaded_qty)},
        )

    if shipment.shipment_plan and shipment.shipment_plan.buyer_user_id:
        total_pickups = len([p for p in all_pickups])
        _create_notification(
            db,
            shipment.shipment_plan.buyer_user_id,
            title="Pickup Milestone Update",
            message=f"Pickup stop {cp.stop_sequence} of {total_pickups} completed ({loaded_qty} QTL loaded).",
            payload={"shipment_id": str(shipment.id), "completed_sequence": cp.stop_sequence},
        )

    db.commit()
    return get_shipment_execution_detail(db, user_id, [RoleName.TRANSPORTER.value], shipment_id)


def record_transit_start(
    db: Session, user_id: UUID, shipment_id: UUID, payload: TransitStartRequest
) -> ShipmentExecutionDetailResponse:
    """Transporter departs final pickup stop and starts linehaul road transit."""
    shipment = _load_shipment_with_relations(db, shipment_id, for_update=True)
    _verify_transporter_actor(db, user_id, shipment)

    # Ensure all pickup stops are COMPLETED
    pickups = db.scalars(
        select(ShipmentCheckpoint).where(
            ShipmentCheckpoint.shipment_id == shipment.id,
            ShipmentCheckpoint.checkpoint_type == CheckpointType.PICKUP,
        )
    ).all()

    incomplete = [p for p in pickups if p.status != CheckpointStatus.COMPLETED]
    if incomplete:
        raise ApiError(
            400,
            "pickups_incomplete",
            f"Cannot start road transit. {len(incomplete)} pickup stop(s) are still pending completion.",
        )

    now = datetime.now(timezone.utc)
    shipment.status = ShipmentStatus.IN_TRANSIT
    shipment.actual_pickup_at = shipment.actual_pickup_at or now

    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            event_type="IN_TRANSIT_STARTED",
            location_name="Departed Final Pickup Point",
            notes=payload.notes or f"Shipment is in transit with {shipment.total_picked_up_quantity_quintals} QTL total cargo.",
            recorded_at=now,
        )
    )

    if shipment.shipment_plan and shipment.shipment_plan.buyer_user_id:
        _create_notification(
            db,
            shipment.shipment_plan.buyer_user_id,
            title="Shipment In Transit",
            message=f"Consolidated shipment of {shipment.total_picked_up_quantity_quintals} QTL is now in transit to your delivery destination.",
            payload={"shipment_id": str(shipment.id)},
        )

    db.commit()
    return get_shipment_execution_detail(db, user_id, [RoleName.TRANSPORTER.value], shipment_id)


def record_destination_arrival(
    db: Session, user_id: UUID, shipment_id: UUID, payload: DestinationArriveRequest
) -> ShipmentExecutionDetailResponse:
    """Transporter confirms arrival at buyer destination hub."""
    shipment = _load_shipment_with_relations(db, shipment_id, for_update=True)
    _verify_transporter_actor(db, user_id, shipment)

    if shipment.status != ShipmentStatus.IN_TRANSIT:
        raise ApiError(400, "invalid_state", f"Shipment must be 'in_transit' before arriving at destination. Current status: '{shipment.status.value}'.")

    dest_cp = db.scalar(
        select(ShipmentCheckpoint).where(
            ShipmentCheckpoint.shipment_id == shipment.id,
            ShipmentCheckpoint.checkpoint_type == CheckpointType.DESTINATION,
        ).with_for_update()
    )
    if not dest_cp:
        raise ApiError(404, "destination_checkpoint_not_found", "Destination checkpoint not found.")

    now = datetime.now(timezone.utc)
    shipment.status = ShipmentStatus.AT_DESTINATION
    dest_cp.status = CheckpointStatus.ARRIVED
    dest_cp.arrived_at = now
    if payload.notes:
        dest_cp.notes = f"{dest_cp.notes or ''} | Destination arrival: {payload.notes}".strip(" |")

    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            event_type="ARRIVED_AT_DESTINATION",
            location_name=dest_cp.location_name,
            notes=payload.notes or f"Arrived at destination hub ({dest_cp.location_name})",
            recorded_at=now,
        )
    )

    if shipment.shipment_plan and shipment.shipment_plan.buyer_user_id:
        _create_notification(
            db,
            shipment.shipment_plan.buyer_user_id,
            title="Shipment Arrived at Destination",
            message=f"Shipment has arrived at destination {dest_cp.location_name}. Ready for unloading and inspection.",
            payload={"shipment_id": str(shipment.id)},
        )

    db.commit()
    return get_shipment_execution_detail(db, user_id, [RoleName.TRANSPORTER.value], shipment_id)


def record_delivery_completion(
    db: Session, user_id: UUID, shipment_id: UUID, payload: DeliveryCompleteRequest
) -> ShipmentExecutionDetailResponse:
    """Transporter and buyer confirm delivery completion, recording delivered quantity and releasing vehicle."""
    shipment = _load_shipment_with_relations(db, shipment_id, for_update=True)
    _verify_transporter_actor(db, user_id, shipment)

    if shipment.status != ShipmentStatus.AT_DESTINATION:
        raise ApiError(400, "invalid_state", f"Shipment must be 'at_destination' before completing delivery. Current status: '{shipment.status.value}'.")

    dest_cp = db.scalar(
        select(ShipmentCheckpoint).where(
            ShipmentCheckpoint.shipment_id == shipment.id,
            ShipmentCheckpoint.checkpoint_type == CheckpointType.DESTINATION,
        ).with_for_update()
    )
    if not dest_cp:
        raise ApiError(404, "destination_checkpoint_not_found", "Destination checkpoint not found.")

    del_qty = payload.delivered_quantity_quintals
    picked_up_qty = shipment.total_picked_up_quantity_quintals
    delivery_var = del_qty - picked_up_qty

    if delivery_var != Decimal("0") and not payload.variance_reason:
        raise ApiError(
            422,
            "variance_reason_required",
            f"Delivered quantity ({del_qty} QTL) differs from picked up total ({picked_up_qty} QTL). An explicit variance reason is required.",
        )

    now = datetime.now(timezone.utc)
    shipment.status = ShipmentStatus.DELIVERED
    shipment.delivered_quantity_quintals = del_qty
    shipment.delivery_variance_reason = payload.variance_reason
    shipment.receiver_name = payload.receiver_name
    shipment.delivery_notes = payload.delivery_notes
    shipment.actual_arrival_at = now

    dest_cp.status = CheckpointStatus.COMPLETED
    dest_cp.loaded_quantity_quintals = del_qty
    dest_cp.variance_quintals = delivery_var
    dest_cp.variance_reason = payload.variance_reason
    dest_cp.completed_at = now

    # Release vehicle to available status
    if shipment.vehicle_id:
        veh = db.scalar(select(Vehicle).where(Vehicle.id == shipment.vehicle_id).with_for_update())
        if veh:
            veh.is_available = True
            veh.operational_status = "available"

    # Audit event
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            event_type="DELIVERY_COMPLETED",
            location_name=dest_cp.location_name,
            notes=f"Delivery confirmed: {del_qty} QTL received by {payload.receiver_name or 'Authorized Receiver'}. Notes: {payload.delivery_notes or 'None'}",
            recorded_at=now,
        )
    )

    # Notify Buyer & Sellers
    if shipment.shipment_plan and shipment.shipment_plan.buyer_user_id:
        _create_notification(
            db,
            shipment.shipment_plan.buyer_user_id,
            title="Shipment Delivered",
            message=f"Shipment delivery confirmed: {del_qty} QTL successfully received.",
            payload={"shipment_id": str(shipment.id), "delivered_quantity": str(del_qty)},
        )

    sellers = db.scalars(
        select(ShipmentCheckpoint.seller_user_id)
        .where(
            ShipmentCheckpoint.shipment_id == shipment.id,
            ShipmentCheckpoint.seller_user_id.is_not(None),
        )
        .distinct()
    ).all()
    for s_id in sellers:
        if s_id:
            _create_notification(
                db,
                s_id,
                title="Shipment Delivered to Buyer",
                message="Your crop lot was delivered to the buyer destination.",
                payload={"shipment_id": str(shipment.id)},
            )

    db.commit()
    return get_shipment_execution_detail(db, user_id, [RoleName.TRANSPORTER.value], shipment_id)


def report_shipment_exception(
    db: Session, user_id: UUID, shipment_id: UUID, payload: ShipmentExceptionRequest
) -> ShipmentExecutionDetailResponse:
    """Records an operational exception/issue on a shipment without advancing checkpoints."""
    shipment = _load_shipment_with_relations(db, shipment_id, for_update=True)
    user = db.scalar(select(User).options(selectinload(User.user_roles).selectinload(UserRole.role)).where(User.id == user_id))
    if not user:
        raise ApiError(404, "user_not_found", "User not found.")

    loc_name = "En Route"
    if payload.checkpoint_id:
        cp = db.scalar(select(ShipmentCheckpoint).where(ShipmentCheckpoint.id == payload.checkpoint_id, ShipmentCheckpoint.shipment_id == shipment.id))
        if cp:
            loc_name = cp.location_name

    now = datetime.now(timezone.utc)
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            event_type="EXCEPTION_REPORTED",
            location_name=loc_name,
            notes=f"[{payload.exception_code}] Reported by {user.display_name}: {payload.notes}",
            recorded_at=now,
        )
    )

    # Notify counterparty
    if shipment.shipment_plan and shipment.shipment_plan.buyer_user_id and shipment.shipment_plan.buyer_user_id != user_id:
        _create_notification(
            db,
            shipment.shipment_plan.buyer_user_id,
            title="Logistics Exception Alert",
            message=f"Exception on shipment: [{payload.exception_code}] {payload.notes}",
            payload={"shipment_id": str(shipment.id), "exception_code": payload.exception_code},
        )

    db.commit()
    user_roles = [ur.role.name.value for ur in user.user_roles if ur.role]
    return get_shipment_execution_detail(db, user_id, user_roles, shipment_id)
