from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.entities import (
    Commodity,
    CommodityCategory,
    Location,
    LogisticsProvider,
    Notification,
    Role,
    RoleName,
    ShipmentPlan,
    ShipmentPlanPickupStop,
    ShipmentPlanningStatus,
    TransportOpportunity,
    TransportOpportunityStatus,
    TransporterProfile,
    User,
    UserRole,
    UserStatus,
    Vehicle,
    VehicleTypeEnum,
)
from app.modules.logistics.opportunity_engine import generate_opportunities_for_plan
from app.modules.logistics.transporter_service import (
    accept_opportunity_transactional,
    get_opportunity_detail,
)
from app.modules.marketplace.service import list_notifications, mark_notification_read
from app.schemas.transporter import OpportunityAcceptRequest


def _setup_entities(db: Session):
    # 1. Commodity & Locations
    commodity = db.scalar(select(Commodity).where(Commodity.name == "Potato (Jyoti)"))
    if not commodity:
        commodity = Commodity(
            name="Potato (Jyoti)",
            category=CommodityCategory.VEGETABLES,
            default_unit="quintal",
            is_perishable=True,
            is_active=True,
        )
        db.add(commodity)
        db.flush()

    origin_loc = Location(
        name="Manchar APMC Hub",
        district="Pune",
        state="Maharashtra",
        postal_code="410503",
        geo_point="POINT(73.944 19.006)",
    )
    dest_loc = Location(
        name="Vashi APMC Terminal",
        district="Mumbai",
        state="Maharashtra",
        postal_code="400703",
        geo_point="POINT(73.003 19.076)",
    )
    db.add_all([origin_loc, dest_loc])
    db.flush()

    # 2. Transporter A
    t_role = db.scalar(select(Role).where(Role.name == RoleName.TRANSPORTER))
    if not t_role:
        t_role = Role(name=RoleName.TRANSPORTER, description="Transporter")
        db.add(t_role)
        db.flush()
    uid_a = uuid4()
    user_a = User(
        id=uid_a,
        email=f"transporter_a_{uid_a.hex[:6]}@freight.in",
        phone_number=f"+9198{uid_a.hex[:8]}",
        password_hash="mockhash",
        display_name="Kisan Freight Logistics A",
        status=UserStatus.ACTIVE,
    )
    db.add(user_a)
    db.flush()
    db.add(UserRole(user_id=user_a.id, role_id=t_role.id))
    db.flush()

    profile_a = TransporterProfile(
        user_id=user_a.id,
        organization_name="Kisan Freight Logistics A",
        contact_phone="+919822112233",
        contact_email=user_a.email,
        verification_status="verified",
        operational_status="active",
        service_area_districts=["Pune", "Mumbai", "Nashik"],
    )
    db.add(profile_a)
    db.flush()

    provider_a = LogisticsProvider(
        name="Kisan Freight Logistics A",
        registered_transporter_profile_id=profile_a.id,
        is_active=True,
    )
    db.add(provider_a)
    db.flush()

    vehicle_a = Vehicle(
        provider_id=provider_a.id,
        vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
        model_name="Eicher Pro 2049",
        registration_number=f"MH-12-TX-{uid_a.hex[:4].upper()}",
        payload_capacity_kg=Decimal("6000.00"),
        is_refrigerated=False,
        is_available=True,
        operational_status="available",
    )
    db.add(vehicle_a)
    db.flush()

    # 3. Transporter B (for isolation testing)
    uid_b = uuid4()
    user_b = User(
        id=uid_b,
        email=f"transporter_b_{uid_b.hex[:6]}@freight.in",
        phone_number=f"+9199{uid_b.hex[:8]}",
        password_hash="mockhash",
        display_name="Sahyadri Transport B",
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.flush()
    db.add(UserRole(user_id=user_b.id, role_id=t_role.id))
    db.flush()

    profile_b = TransporterProfile(
        user_id=user_b.id,
        organization_name="Sahyadri Transport B",
        contact_phone="+919822998877",
        contact_email=user_b.email,
        verification_status="verified",
        operational_status="active",
        service_area_districts=["Pune", "Mumbai"],
    )
    db.add(profile_b)
    db.flush()

    provider_b = LogisticsProvider(
        name="Sahyadri Transport B",
        registered_transporter_profile_id=profile_b.id,
        is_active=True,
    )
    db.add(provider_b)
    db.flush()

    vehicle_b = Vehicle(
        provider_id=provider_b.id,
        vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
        model_name="Tata 407",
        registration_number=f"MH-14-TY-{uid_b.hex[:4].upper()}",
        payload_capacity_kg=Decimal("5000.00"),
        is_refrigerated=False,
        is_available=True,
        operational_status="available",
    )
    db.add(vehicle_b)
    db.flush()

    # 4. Plan 1
    plan1 = ShipmentPlan(
        plan_code=f"PLAN-NOTIF-1-{uuid4().hex[:6].upper()}",
        commodity_id=commodity.id,
        destination_location_id=dest_loc.id,
        planning_status=ShipmentPlanningStatus.PLANNED,
        earliest_pickup_date=date.today(),
        delivery_deadline=date.today() + timedelta(days=2),
        total_planned_quantity_quintals=Decimal("35.00"),
        estimated_gross_merchandise_value=Decimal("87500.00"),
    )
    db.add(plan1)
    db.flush()

    stop1 = ShipmentPlanPickupStop(
        shipment_plan_id=plan1.id,
        stop_sequence=1,
        seller_user_id=user_a.id,
        seller_name="Manchar Potato Farm",
        pickup_location_id=origin_loc.id,
        allocated_quantity_quintals=Decimal("35.00"),
        earliest_pickup_date=date.today(),
    )
    db.add(stop1)
    db.flush()

    db.commit()

    return {
        "commodity": commodity,
        "origin_loc": origin_loc,
        "dest_loc": dest_loc,
        "user_a": user_a,
        "profile_a": profile_a,
        "vehicle_a": vehicle_a,
        "user_b": user_b,
        "profile_b": profile_b,
        "vehicle_b": vehicle_b,
        "plan1": plan1,
    }


def test_single_opportunity_single_notification(db: Session):
    """Test 1: A generated opportunity creates exactly ONE notification for a transporter."""
    data = _setup_entities(db)
    user_a = data["user_a"]
    plan1 = data["plan1"]

    bcast = generate_opportunities_for_plan(db, plan1.id)
    assert bcast.opportunities_created_count >= 1

    notifs = list_notifications(db, user_a)
    opp_notifs = [n for n in notifs if n.notification_type == "TRANSPORT_OPPORTUNITY_CREATED"]
    assert len(opp_notifs) == 1
    assert opp_notifs[0].data_json is not None
    assert "opportunity_id" in opp_notifs[0].data_json
    assert opp_notifs[0].data_json["plan_code"] == plan1.plan_code


def test_rebroadcast_idempotency(db: Session):
    """Test 2: Repeated broadcast calls do NOT create duplicate notifications."""
    data = _setup_entities(db)
    user_a = data["user_a"]
    plan1 = data["plan1"]

    # Call broadcast 3 times
    generate_opportunities_for_plan(db, plan1.id, force_rebroadcast=True)
    generate_opportunities_for_plan(db, plan1.id, force_rebroadcast=True)
    generate_opportunities_for_plan(db, plan1.id, force_rebroadcast=True)

    notifs = list_notifications(db, user_a)
    opp_notifs = [n for n in notifs if n.notification_type == "TRANSPORT_OPPORTUNITY_CREATED"]
    # Must still be exactly 1 notification for this opportunity
    assert len(opp_notifs) == 1


def test_different_opportunity_creates_new_notification(db: Session):
    """Test 3: Different opportunities create distinct notifications."""
    data = _setup_entities(db)
    user_a = data["user_a"]
    commodity = data["commodity"]
    dest_loc = data["dest_loc"]
    origin_loc = data["origin_loc"]

    # Broadcast Plan 1
    generate_opportunities_for_plan(db, data["plan1"].id)

    # Create Plan 2
    plan2 = ShipmentPlan(
        plan_code=f"PLAN-NOTIF-2-{uuid4().hex[:6].upper()}",
        commodity_id=commodity.id,
        destination_location_id=dest_loc.id,
        planning_status=ShipmentPlanningStatus.PLANNED,
        earliest_pickup_date=date.today(),
        delivery_deadline=date.today() + timedelta(days=2),
        total_planned_quantity_quintals=Decimal("40.00"),
        estimated_gross_merchandise_value=Decimal("100000.00"),
    )
    db.add(plan2)
    db.flush()
    db.add(
        ShipmentPlanPickupStop(
            shipment_plan_id=plan2.id,
            stop_sequence=1,
            seller_user_id=user_a.id,
            seller_name="Khed Farm",
            pickup_location_id=origin_loc.id,
            allocated_quantity_quintals=Decimal("40.00"),
            earliest_pickup_date=date.today(),
        )
    )
    db.commit()

    generate_opportunities_for_plan(db, plan2.id)

    notifs = list_notifications(db, user_a)
    opp_notifs = [n for n in notifs if n.notification_type == "TRANSPORT_OPPORTUNITY_CREATED"]
    assert len(opp_notifs) == 2
    plan_codes = {n.data_json["plan_code"] for n in opp_notifs}
    assert data["plan1"].plan_code in plan_codes
    assert plan2.plan_code in plan_codes


def test_job_assigned_creates_separate_notification(db: Session):
    """Test 4: Accepting a job creates a distinct TRANSPORT_ASSIGNED notification."""
    data = _setup_entities(db)
    user_a = data["user_a"]
    vehicle_a = data["vehicle_a"]
    profile_a = data["profile_a"]
    plan1 = data["plan1"]

    bcast = generate_opportunities_for_plan(db, plan1.id)
    opp = next(o for o in bcast.opportunities if o.transporter_profile_id == profile_a.id)

    accept_opportunity_transactional(
        db,
        user_a.id,
        opp.id,
        OpportunityAcceptRequest(
            vehicle_id=vehicle_a.id,
            driver_name="Raju Shinde",
            driver_phone="+919822334455",
        ),
    )

    notifs = list_notifications(db, user_a)
    assigned_notifs = [n for n in notifs if n.notification_type == "TRANSPORT_ASSIGNED"]
    assert len(assigned_notifs) == 1
    assert assigned_notifs[0].data_json is not None
    assert "shipment_id" in assigned_notifs[0].data_json
    assert assigned_notifs[0].data_json["plan_code"] == plan1.plan_code


def test_notification_linkage_and_isolation(db: Session):
    """Test 5 & 6: Notification payload linkage and user isolation."""
    data = _setup_entities(db)
    user_a = data["user_a"]
    user_b = data["user_b"]
    plan1 = data["plan1"]

    generate_opportunities_for_plan(db, plan1.id)

    notifs_a = list_notifications(db, user_a)
    assert len(notifs_a) >= 1
    notif_a_id = notifs_a[0].id

    # Mark as read works for owner
    read_res = mark_notification_read(db, user_a, notif_a_id)
    assert read_res.read_at is not None

    # User B cannot mark User A's notification as read
    with pytest.raises(ApiError) as exc:
        mark_notification_read(db, user_b, notif_a_id)
    assert exc.value.status_code == 404


def test_transporter_isolation_opportunity(db: Session):
    """Test 7: Transporter A cannot access Transporter B's opportunity."""
    data = _setup_entities(db)
    user_a = data["user_a"]
    plan1 = data["plan1"]

    generate_opportunities_for_plan(db, plan1.id)

    opp_b = db.scalar(
        select(TransportOpportunity).where(
            TransportOpportunity.shipment_plan_id == plan1.id,
            TransportOpportunity.transporter_profile_id == data["profile_b"].id,
        )
    )
    assert opp_b is not None

    # User A tries to get User B's opportunity
    with pytest.raises(ApiError) as exc:
        get_opportunity_detail(db, user_a.id, opp_b.id)
    assert exc.value.status_code == 404


def test_withdrawn_and_expired_opportunity_rejection(db: Session):
    """Test 8: Withdrawn or expired opportunities cannot be accepted."""
    data = _setup_entities(db)
    user_a = data["user_a"]
    vehicle_a = data["vehicle_a"]
    profile_a = data["profile_a"]
    plan1 = data["plan1"]

    bcast = generate_opportunities_for_plan(db, plan1.id)
    opp_item = next(o for o in bcast.opportunities if o.transporter_profile_id == profile_a.id)
    opp = db.scalar(select(TransportOpportunity).where(TransportOpportunity.id == opp_item.id))

    # Mark withdrawn
    opp.status = TransportOpportunityStatus.WITHDRAWN
    db.commit()

    with pytest.raises(ApiError) as exc:
        accept_opportunity_transactional(
            db,
            user_a.id,
            opp.id,
            OpportunityAcceptRequest(vehicle_id=vehicle_a.id),
        )
    assert exc.value.status_code == 400
    assert "opportunity_not_open" in exc.value.code


def test_submit_quote_flow(db: Session):
    """Test 9: Transporter can submit a bid/quote for an open opportunity."""
    from app.modules.logistics.transporter_service import submit_transporter_quote
    from app.schemas.transporter import TransporterQuoteCreate

    data = _setup_entities(db)
    user_a = data["user_a"]
    vehicle_a = data["vehicle_a"]
    profile_a = data["profile_a"]
    plan1 = data["plan1"]

    bcast = generate_opportunities_for_plan(db, plan1.id)
    opp = next(o for o in bcast.opportunities if o.transporter_profile_id == profile_a.id)

    quote_res = submit_transporter_quote(
        db,
        user_a.id,
        opp.id,
        TransporterQuoteCreate(
            vehicle_id=vehicle_a.id,
            quote_amount=Decimal("12500.00"),
            quote_unit="INR_TOTAL",
            notes="Ready for immediate dispatch",
        ),
    )
    assert quote_res.quote_amount == Decimal("12500.00")
    assert quote_res.status == "submitted"


def test_decline_opportunity_flow(db: Session):
    """Test 10: Transporter can decline an opportunity with a reason."""
    from app.modules.logistics.transporter_service import decline_opportunity
    from app.schemas.transporter import OpportunityDeclineRequest

    data = _setup_entities(db)
    user_a = data["user_a"]
    profile_a = data["profile_a"]
    plan1 = data["plan1"]

    bcast = generate_opportunities_for_plan(db, plan1.id)
    opp = next(o for o in bcast.opportunities if o.transporter_profile_id == profile_a.id)

    res = decline_opportunity(
        db,
        user_a.id,
        opp.id,
        OpportunityDeclineRequest(reason="Fleet fully booked for this corridor"),
    )
    assert res.status == TransportOpportunityStatus.DECLINED
    assert res.decline_reason == "Fleet fully booked for this corridor"
