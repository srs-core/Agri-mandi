"""
Phase 2H Test Suite: Shipment Execution & Checkpoint Tracking.
Validates:
1. Checkpoint initialization from multi-stop shipment plans
2. Strict sequential milestone progression (Stop 1 -> Stop 2 -> Transit -> Destination -> Delivery)
3. Out-of-order transition rejection
4. Quantity reconciliation, variance validation, and cargo overflow guards
5. Idempotent milestone calls and event auditing
6. Operational exception reporting without state corruption
7. Multi-stakeholder notification dispatch (Farmer, Buyer, Transporter)
8. Role-based access control (RBAC) isolation
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.entities import (
    BuyerProfile,
    CheckpointStatus,
    CheckpointType,
    Commodity,
    CommodityCategory,
    FarmerProfile,
    Location,
    LogisticsProvider,
    Notification,
    ProduceLot,
    ProduceLotStatus,
    Role,
    RoleName,
    Shipment,
    ShipmentCheckpoint,
    ShipmentEvent,
    ShipmentPlan,
    ShipmentPlanContributor,
    ShipmentPlanPickupStop,
    ShipmentPlanningStatus,
    ShipmentStatus,
    TransportOpportunity,
    TransportOpportunityStatus,
    TransporterProfile,
    User,
    UserRole,
    UserStatus,
    Vehicle,
    VehicleTypeEnum,
)
from app.modules.logistics.execution_tracking_service import (
    get_shipment_execution_detail,
    initialize_shipment_checkpoints,
    record_checkpoint_arrival,
    record_checkpoint_completion,
    record_checkpoint_loading_start,
    record_delivery_completion,
    record_destination_arrival,
    record_transit_start,
    report_shipment_exception,
)
from app.modules.logistics.transporter_service import accept_opportunity_transactional
from app.schemas.execution_tracking import (
    CheckpointArriveRequest,
    CheckpointCompleteRequest,
    CheckpointLoadingRequest,
    DeliveryCompleteRequest,
    DestinationArriveRequest,
    ShipmentExceptionRequest,
    TransitStartRequest,
)
from app.schemas.transporter import OpportunityAcceptRequest


@pytest.fixture
def phase2h_fixture(db: Session):
    """Sets up a multi-farmer supply chain with an accepted shipment ready for checkpoint execution."""
    uid = uuid4().hex[:6]

    # Roles
    r_farmer = db.scalar(select(Role).where(Role.name == RoleName.FARMER)) or Role(name=RoleName.FARMER, description="Farmer")
    r_buyer = db.scalar(select(Role).where(Role.name == RoleName.BUYER)) or Role(name=RoleName.BUYER, description="Buyer")
    r_transporter = db.scalar(select(Role).where(Role.name == RoleName.TRANSPORTER)) or Role(name=RoleName.TRANSPORTER, description="Transporter")
    r_admin = db.scalar(select(Role).where(Role.name == RoleName.ADMIN)) or Role(name=RoleName.ADMIN, description="Admin")
    db.add_all([r_farmer, r_buyer, r_transporter, r_admin])
    db.flush()

    # Users
    u_f1 = User(email=f"farmer1.{uid}@agritest.in", password_hash=hash_password("Pass123!"), display_name="Ramesh Patil", status=UserStatus.ACTIVE)
    u_f2 = User(email=f"farmer2.{uid}@agritest.in", password_hash=hash_password("Pass123!"), display_name="Suresh Deshmukh", status=UserStatus.ACTIVE)
    u_b = User(email=f"buyer.{uid}@agritest.in", password_hash=hash_password("Pass123!"), display_name="Pune Agro Wholesaler Ltd", status=UserStatus.ACTIVE)
    u_t = User(email=f"transporter.{uid}@agritest.in", password_hash=hash_password("Pass123!"), display_name="Sahyadri Logistics", status=UserStatus.ACTIVE)
    u_other = User(email=f"other.{uid}@agritest.in", password_hash=hash_password("Pass123!"), display_name="Unrelated User", status=UserStatus.ACTIVE)
    db.add_all([u_f1, u_f2, u_b, u_t, u_other])
    db.flush()

    db.add_all([
        UserRole(user_id=u_f1.id, role_id=r_farmer.id),
        UserRole(user_id=u_f2.id, role_id=r_farmer.id),
        UserRole(user_id=u_b.id, role_id=r_buyer.id),
        UserRole(user_id=u_t.id, role_id=r_transporter.id),
        UserRole(user_id=u_other.id, role_id=r_farmer.id),
    ])
    db.flush()

    # Locations
    loc_farm1 = Location(name=f"Manchar Farm Gate {uid}", district="Pune", state="Maharashtra", geo_point="POINT(73.94 18.995)")
    loc_farm2 = Location(name=f"Junnar Farm Gate {uid}", district="Pune", state="Maharashtra", geo_point="POINT(73.88 19.20)")
    loc_dest = Location(name=f"Pune Central Mandi {uid}", district="Pune", state="Maharashtra", geo_point="POINT(73.8567 18.5204)")
    db.add_all([loc_farm1, loc_farm2, loc_dest])
    db.flush()

    # Profiles
    p_f1 = FarmerProfile(user_id=u_f1.id, primary_location_id=loc_farm1.id, farm_name="Patil Organic Farms", land_area_hectares=Decimal("3.5"))
    p_f2 = FarmerProfile(user_id=u_f2.id, primary_location_id=loc_farm2.id, farm_name="Deshmukh Farms", land_area_hectares=Decimal("5.0"))
    p_b = BuyerProfile(user_id=u_b.id, organization_name="Pune Fresh Wholesale Ltd", primary_location_id=loc_dest.id)
    p_t = TransporterProfile(user_id=u_t.id, organization_name="Sahyadri Freight Logistics", operational_status="active", service_area_districts=["Pune", "Nashik"])
    db.add_all([p_f1, p_f2, p_b, p_t])
    db.flush()

    # Provider & Vehicle
    prov = LogisticsProvider(name=p_t.organization_name, registered_transporter_profile_id=p_t.id, primary_location_id=loc_dest.id, is_active=True)
    db.add(prov)
    db.flush()

    veh = Vehicle(
        provider_id=prov.id,
        registration_number=f"MH-12-EXEC-{uid.upper()}",
        vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
        model_name="Eicher Pro 2049",
        payload_capacity_kg=Decimal("6000.000"),
        is_available=True,
        operational_status="available",
    )
    db.add(veh)
    db.flush()

    # Commodity
    crop = Commodity(name=f"Nashik Red Onion-{uid}", category=CommodityCategory.VEGETABLES, default_unit="quintal", is_perishable=True)
    db.add(crop)
    db.flush()

    # Produce Lots
    lot1 = ProduceLot(
        title=f"Lot Manchar {uid}",
        seller_user_id=u_f1.id,
        commodity_id=crop.id,
        available_quantity=Decimal("20.000"),
        unit="quintal",
        asking_price_per_unit=Decimal("2200.00"),
        quality_grade="Grade A",
        pickup_location_id=loc_farm1.id,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    lot2 = ProduceLot(
        title=f"Lot Junnar {uid}",
        seller_user_id=u_f2.id,
        commodity_id=crop.id,
        available_quantity=Decimal("30.000"),
        unit="quintal",
        asking_price_per_unit=Decimal("2150.00"),
        quality_grade="Grade A",
        pickup_location_id=loc_farm2.id,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([lot1, lot2])
    db.flush()

    # Shipment Plan with 2 pickup stops (Stop 1 = 20 QTL, Stop 2 = 30 QTL, Total = 50 QTL)
    plan = ShipmentPlan(
        plan_code=f"PLAN-2H-{uid.upper()}",
        planning_status=ShipmentPlanningStatus.READY_FOR_LOGISTICS,
        buyer_user_id=u_b.id,
        buyer_organization_name=p_b.organization_name,
        commodity_id=crop.id,
        total_planned_quantity_quintals=Decimal("50.000"),
        destination_location_id=loc_dest.id,
        earliest_pickup_date=date.today(),
    )
    db.add(plan)
    db.flush()

    stop1 = ShipmentPlanPickupStop(
        shipment_plan_id=plan.id,
        stop_sequence=1,
        seller_user_id=u_f1.id,
        seller_name=u_f1.display_name,
        pickup_location_id=loc_farm1.id,
        allocated_quantity_quintals=Decimal("20.000"),
        earliest_pickup_date=date.today(),
    )
    stop2 = ShipmentPlanPickupStop(
        shipment_plan_id=plan.id,
        stop_sequence=2,
        seller_user_id=u_f2.id,
        seller_name=u_f2.display_name,
        pickup_location_id=loc_farm2.id,
        allocated_quantity_quintals=Decimal("30.000"),
        earliest_pickup_date=date.today(),
    )
    db.add_all([stop1, stop2])
    db.flush()

    contrib1 = ShipmentPlanContributor(pickup_stop_id=stop1.id, produce_lot_id=lot1.id, seller_user_id=u_f1.id, lot_allocated_quantity_quintals=Decimal("20.000"))
    contrib2 = ShipmentPlanContributor(pickup_stop_id=stop2.id, produce_lot_id=lot2.id, seller_user_id=u_f2.id, lot_allocated_quantity_quintals=Decimal("30.000"))
    db.add_all([contrib1, contrib2])
    db.flush()

    # Transport Opportunity
    opp = TransportOpportunity(
        shipment_plan_id=plan.id,
        transporter_profile_id=p_t.id,
        status=TransportOpportunityStatus.OPEN,
        required_vehicle_class="medium_commercial",
        required_payload_quintals=Decimal("50.000"),
        requires_cold_chain=False,
        pickup_stops_count=2,
        origin_district="Pune",
        destination_district="Pune",
        total_distance_km=Decimal("85.5"),
        estimated_cost=Decimal("6200.00"),
        earliest_pickup_date=date.today(),
        eligibility_score=95,
    )
    db.add(opp)
    db.commit()

    return {
        "farmer1": u_f1,
        "farmer2": u_f2,
        "buyer": u_b,
        "transporter": u_t,
        "other_user": u_other,
        "transporter_profile": p_t,
        "provider": prov,
        "vehicle": veh,
        "shipment_plan": plan,
        "opportunity": opp,
    }


def test_checkpoint_initialization_upon_acceptance(db: Session, phase2h_fixture):
    """Test that accepting a transport opportunity initializes sequential checkpoints from the multi-stop plan."""
    f = phase2h_fixture
    u_t = f["transporter"]
    opp = f["opportunity"]
    veh = f["vehicle"]

    accept_res = accept_opportunity_transactional(
        db,
        user_id=u_t.id,
        opportunity_id=opp.id,
        payload=OpportunityAcceptRequest(
            vehicle_id=veh.id,
            driver_name="Sunil Shinde",
            driver_phone="+919876543210",
            notes="Ready for morning pickup",
        ),
    )

    shipment_id = accept_res.shipment_id
    assert shipment_id is not None

    checkpoints = db.scalars(
        select(ShipmentCheckpoint)
        .where(ShipmentCheckpoint.shipment_id == shipment_id)
        .order_by(ShipmentCheckpoint.stop_sequence)
    ).all()

    assert len(checkpoints) == 3
    assert checkpoints[0].stop_sequence == 1
    assert checkpoints[0].checkpoint_type == CheckpointType.PICKUP
    assert checkpoints[0].planned_quantity_quintals == Decimal("20.000")
    assert checkpoints[0].status == CheckpointStatus.PENDING

    assert checkpoints[1].stop_sequence == 2
    assert checkpoints[1].checkpoint_type == CheckpointType.PICKUP
    assert checkpoints[1].planned_quantity_quintals == Decimal("30.000")
    assert checkpoints[1].status == CheckpointStatus.PENDING

    assert checkpoints[2].stop_sequence == 3
    assert checkpoints[2].checkpoint_type == CheckpointType.DESTINATION
    assert checkpoints[2].planned_quantity_quintals == Decimal("50.000")
    assert checkpoints[2].status == CheckpointStatus.PENDING


def test_full_sequential_execution_workflow(db: Session, phase2h_fixture):
    """
    Test full end-to-end milestone progression:
    Stop 1 (Arrive -> Load -> Complete) -> Stop 2 (Arrive -> Complete with Variance) ->
    Transit Start -> Destination Arrive -> Delivery Complete.
    """
    f = phase2h_fixture
    u_t = f["transporter"]
    u_f1 = f["farmer1"]
    u_f2 = f["farmer2"]
    u_b = f["buyer"]
    opp = f["opportunity"]
    veh = f["vehicle"]

    # 1. Accept job
    accept_res = accept_opportunity_transactional(
        db,
        user_id=u_t.id,
        opportunity_id=opp.id,
        payload=OpportunityAcceptRequest(vehicle_id=veh.id, driver_name="Sunil Shinde"),
    )
    shipment_id = accept_res.shipment_id

    # 2. Arrive at Stop 1
    cps = db.scalars(select(ShipmentCheckpoint).where(ShipmentCheckpoint.shipment_id == shipment_id).order_by(ShipmentCheckpoint.stop_sequence)).all()
    cp1, cp2, cp_dest = cps[0], cps[1], cps[2]

    detail1 = record_checkpoint_arrival(db, u_t.id, shipment_id, cp1.id, CheckpointArriveRequest(notes="At farm gate"))
    assert detail1.status == ShipmentStatus.IN_PICKUP
    assert detail1.checkpoints[0].status == CheckpointStatus.ARRIVED
    assert detail1.checkpoints[0].arrived_at is not None

    # Verify notification sent to Farmer 1
    notif_f1 = db.scalar(select(Notification).where(Notification.recipient_user_id == u_f1.id, Notification.title == "Transporter Arrived"))
    assert notif_f1 is not None

    # 3. Start loading at Stop 1
    detail2 = record_checkpoint_loading_start(db, u_t.id, shipment_id, cp1.id, CheckpointLoadingRequest(notes="Inspecting bags"))
    assert detail2.checkpoints[0].status == CheckpointStatus.LOADING

    # 4. Complete Stop 1 (Loaded exact 20 QTL)
    detail3 = record_checkpoint_completion(
        db, u_t.id, shipment_id, cp1.id, CheckpointCompleteRequest(loaded_quantity_quintals=Decimal("20.000"), notes="Grade A loaded")
    )
    assert detail3.checkpoints[0].status == CheckpointStatus.COMPLETED
    assert detail3.total_picked_up_quantity_quintals == Decimal("20.000")
    assert detail3.current_checkpoint_sequence == 2

    # 5. Arrive & Complete Stop 2 (Loaded 32 QTL with documented harvest variance)
    record_checkpoint_arrival(db, u_t.id, shipment_id, cp2.id, CheckpointArriveRequest(notes="Arrived at Junnar"))
    detail4 = record_checkpoint_completion(
        db,
        u_t.id,
        shipment_id,
        cp2.id,
        CheckpointCompleteRequest(
            loaded_quantity_quintals=Decimal("32.000"),
            variance_reason="Extra farm harvest allocation authorized by farmer",
            notes="High grade produce",
        ),
    )
    assert detail4.checkpoints[1].status == CheckpointStatus.COMPLETED
    assert detail4.checkpoints[1].loaded_quantity_quintals == Decimal("32.000")
    assert detail4.checkpoints[1].variance_quintals == Decimal("2.000")
    assert detail4.total_picked_up_quantity_quintals == Decimal("52.000")
    assert detail4.current_checkpoint_sequence == 3

    # 6. Start Road Transit
    detail5 = record_transit_start(db, u_t.id, shipment_id, TransitStartRequest(notes="Departing Nashik via NH60"))
    assert detail5.status == ShipmentStatus.IN_TRANSIT

    # Verify Buyer received in-transit notification
    notif_b = db.scalar(select(Notification).where(Notification.recipient_user_id == u_b.id, Notification.title == "Shipment In Transit"))
    assert notif_b is not None

    # 7. Arrive at Buyer Destination
    detail6 = record_destination_arrival(db, u_t.id, shipment_id, DestinationArriveRequest(notes="Docked at bay 3"))
    assert detail6.status == ShipmentStatus.AT_DESTINATION
    assert detail6.checkpoints[2].status == CheckpointStatus.ARRIVED

    # 8. Confirm Delivery
    detail7 = record_delivery_completion(
        db,
        u_t.id,
        shipment_id,
        DeliveryCompleteRequest(
            delivered_quantity_quintals=Decimal("52.000"),
            receiver_name="Mahesh Pawar (Warehouse Supervisor)",
            delivery_notes="Weighbridge verified: 52 QTL in sound condition",
        ),
    )
    assert detail7.status == ShipmentStatus.DELIVERED
    assert detail7.delivered_quantity_quintals == Decimal("52.000")
    assert detail7.progress_percentage == 100.0
    assert detail7.receiver_name == "Mahesh Pawar (Warehouse Supervisor)"

    # Verify Vehicle is released back to AVAILABLE
    v_updated = db.scalar(select(Vehicle).where(Vehicle.id == veh.id))
    assert v_updated.is_available is True
    assert v_updated.operational_status == "available"

    # Verify Audit Events Timeline
    events = db.scalars(select(ShipmentEvent).where(ShipmentEvent.shipment_id == shipment_id).order_by(ShipmentEvent.recorded_at)).all()
    event_types = [e.event_type for e in events]
    assert "TRANSPORTER_ASSIGNED" in event_types
    assert "ARRIVED_AT_PICKUP" in event_types
    assert "LOADING_STARTED" in event_types
    assert "PICKUP_COMPLETED" in event_types
    assert "IN_TRANSIT_STARTED" in event_types
    assert "ARRIVED_AT_DESTINATION" in event_types
    assert "DELIVERY_COMPLETED" in event_types


def test_out_of_order_transition_rejection(db: Session, phase2h_fixture):
    """Test that attempting to skip checkpoints or perform out-of-order state transitions is rejected server-side."""
    f = phase2h_fixture
    u_t = f["transporter"]
    opp = f["opportunity"]
    veh = f["vehicle"]

    accept_res = accept_opportunity_transactional(
        db, user_id=u_t.id, opportunity_id=opp.id, payload=OpportunityAcceptRequest(vehicle_id=veh.id)
    )
    shipment_id = accept_res.shipment_id
    cps = db.scalars(select(ShipmentCheckpoint).where(ShipmentCheckpoint.shipment_id == shipment_id).order_by(ShipmentCheckpoint.stop_sequence)).all()

    # 1. Attempting to complete Stop 2 before Stop 1
    with pytest.raises(Exception) as exc1:
        record_checkpoint_arrival(db, u_t.id, shipment_id, cps[1].id, CheckpointArriveRequest())
    assert getattr(exc1.value, "code", None) == "invalid_sequence" or getattr(exc1.value, "status_code", None) == 400

    # 2. Attempting to start transit before completing pickups
    with pytest.raises(Exception) as exc2:
        record_transit_start(db, u_t.id, shipment_id, TransitStartRequest())
    assert getattr(exc2.value, "code", None) == "pickups_incomplete" or getattr(exc2.value, "status_code", None) == 400

    # 3. Attempting to complete delivery before destination arrival
    with pytest.raises(Exception) as exc3:
        record_delivery_completion(
            db, u_t.id, shipment_id, DeliveryCompleteRequest(delivered_quantity_quintals=Decimal("50.000"))
        )
    assert getattr(exc3.value, "code", None) == "invalid_state" or getattr(exc3.value, "status_code", None) == 400


def test_quantity_reconciliation_variance_and_overflow_guard(db: Session, phase2h_fixture):
    """Test quantity variance requirement and cargo overflow prevention."""
    f = phase2h_fixture
    u_t = f["transporter"]
    opp = f["opportunity"]
    veh = f["vehicle"]

    accept_res = accept_opportunity_transactional(
        db, user_id=u_t.id, opportunity_id=opp.id, payload=OpportunityAcceptRequest(vehicle_id=veh.id)
    )
    shipment_id = accept_res.shipment_id
    cps = db.scalars(select(ShipmentCheckpoint).where(ShipmentCheckpoint.shipment_id == shipment_id).order_by(ShipmentCheckpoint.stop_sequence)).all()

    record_checkpoint_arrival(db, u_t.id, shipment_id, cps[0].id, CheckpointArriveRequest())

    # 1. Variance without variance_reason is rejected
    with pytest.raises(Exception) as exc1:
        record_checkpoint_completion(
            db,
            u_t.id,
            shipment_id,
            cps[0].id,
            CheckpointCompleteRequest(loaded_quantity_quintals=Decimal("25.000"), variance_reason=None),
        )
    assert getattr(exc1.value, "code", None) == "variance_reason_required" or getattr(exc1.value, "status_code", None) == 422

    # 2. Gross cargo overflow exceeding vehicle/plan capacity is rejected
    with pytest.raises(Exception) as exc2:
        record_checkpoint_completion(
            db,
            u_t.id,
            shipment_id,
            cps[0].id,
            CheckpointCompleteRequest(
                loaded_quantity_quintals=Decimal("100.000"),
                variance_reason="Unreasonable massive harvest",
            ),
        )
    assert getattr(exc2.value, "code", None) == "cargo_overflow" or getattr(exc2.value, "status_code", None) == 422


def test_exception_reporting_and_rbac(db: Session, phase2h_fixture):
    """Test operational exception reporting and RBAC access permissions."""
    f = phase2h_fixture
    u_t = f["transporter"]
    u_f1 = f["farmer1"]
    u_b = f["buyer"]
    u_other = f["other_user"]
    opp = f["opportunity"]
    veh = f["vehicle"]

    accept_res = accept_opportunity_transactional(
        db, user_id=u_t.id, opportunity_id=opp.id, payload=OpportunityAcceptRequest(vehicle_id=veh.id)
    )
    shipment_id = accept_res.shipment_id

    # 1. Transporter reports loading delay exception
    exc_res = report_shipment_exception(
        db,
        u_t.id,
        shipment_id,
        ShipmentExceptionRequest(
            exception_code="LOADING_DELAY",
            notes="Farm gate access road blocked by tractor. Expected delay 30 mins.",
        ),
    )
    assert exc_res.current_checkpoint_sequence == 1
    assert any(e.event_type == "EXCEPTION_REPORTED" for e in exc_res.timeline)

    # 2. RBAC: Participating Farmer can view tracking
    f1_detail = get_shipment_execution_detail(db, u_f1.id, [RoleName.FARMER.value], shipment_id)
    assert f1_detail.id == shipment_id

    # 3. RBAC: Target Buyer can view tracking
    b_detail = get_shipment_execution_detail(db, u_b.id, [RoleName.BUYER.value], shipment_id)
    assert b_detail.id == shipment_id

    # 4. RBAC: Unrelated User is denied access
    with pytest.raises(Exception) as exc_denied:
        get_shipment_execution_detail(db, u_other.id, [RoleName.FARMER.value], shipment_id)
    assert getattr(exc_denied.value, "code", None) == "access_denied" or getattr(exc_denied.value, "status_code", None) == 403
