import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.entities import (
    Commodity,
    CommodityCategory,
    Location,
    LogisticsProvider,
    Notification,
    ProduceLot,
    ProduceLotStatus,
    QuoteStatus,
    Role,
    RoleName,
    Shipment,
    ShipmentEvent,
    ShipmentPlan,
    ShipmentPlanContributor,
    ShipmentPlanPickupStop,
    ShipmentPlanningStatus,
    ShipmentStatus,
    TransportOpportunity,
    TransportOpportunityStatus,
    TransporterProfile,
    TransporterQuote,
    User,
    UserRole,
    UserStatus,
    Vehicle,
    VehicleTypeEnum,
    VerificationStatus,
)
from app.modules.logistics.opportunity_engine import generate_opportunities_for_plan
from app.modules.logistics.transporter_service import (
    accept_opportunity_transactional,
    decline_opportunity,
    get_opportunity_detail,
    get_transporter_me,
    list_opportunities_for_transporter,
    list_transporter_shipments,
    list_transporter_vehicles,
    register_transporter_vehicle,
    submit_transporter_quote,
    update_transporter_profile,
    update_transporter_vehicle,
)
from app.schemas.transporter import (
    OpportunityAcceptRequest,
    OpportunityDeclineRequest,
    TransporterProfileUpdate,
    TransporterQuoteCreate,
    TransporterVehicleCreate,
    TransporterVehicleUpdate,
)


@pytest.fixture
def test_data(db: Session):
    """Setup verified entities for Phase 2G testing."""
    transporter_role = db.scalar(select(Role).where(Role.name == RoleName.TRANSPORTER))
    if not transporter_role:
        transporter_role = Role(name=RoleName.TRANSPORTER, description="Commercial Freight Carrier")
        db.add(transporter_role)

    farmer_role = db.scalar(select(Role).where(Role.name == RoleName.FARMER))
    if not farmer_role:
        farmer_role = Role(name=RoleName.FARMER, description="Agricultural Producer")
        db.add(farmer_role)

    buyer_role = db.scalar(select(Role).where(Role.name == RoleName.BUYER))
    if not buyer_role:
        buyer_role = Role(name=RoleName.BUYER, description="Commercial Buyer")
        db.add(buyer_role)

    db.flush()

    uid = uuid.uuid4().hex[:8]

    # Transporter 1: Sahyadri Logistics
    t1_user = User(
        email=f"sahyadri.{uid}@example.com",
        password_hash="fake_hash",
        display_name="Sahyadri Freight & Logistics",
        status=UserStatus.ACTIVE,
    )
    db.add(t1_user)
    db.flush()
    db.add(UserRole(user_id=t1_user.id, role_id=transporter_role.id))

    t1_profile = TransporterProfile(
        user_id=t1_user.id,
        organization_name=f"Sahyadri Freight & Logistics {uid}",
        verification_status=VerificationStatus.VERIFIED,
        operational_status="active",
        service_area_districts=["Pune", "Nashik", "Ahmednagar"],
        contact_phone="+919876543210",
        contact_email=f"dispatch.{uid}@sahyadrilogistics.com",
    )
    db.add(t1_profile)
    db.flush()

    t1_provider = LogisticsProvider(
        name=f"Sahyadri Freight & Logistics {uid}",
        registered_transporter_profile_id=t1_profile.id,
        operating_scope="regional",
        has_cold_chain=False,
        contact_phone="+919876543210",
        contact_email=f"dispatch.{uid}@sahyadrilogistics.com",
        is_active=True,
    )
    db.add(t1_provider)
    db.flush()

    # Transporter 2: Deccan Swift Transport
    t2_user = User(
        email=f"deccan.{uid}@example.com",
        password_hash="fake_hash",
        display_name="Deccan Swift Transport",
        status=UserStatus.ACTIVE,
    )
    db.add(t2_user)
    db.flush()
    db.add(UserRole(user_id=t2_user.id, role_id=transporter_role.id))

    t2_profile = TransporterProfile(
        user_id=t2_user.id,
        organization_name=f"Deccan Swift Transport {uid}",
        verification_status=VerificationStatus.VERIFIED,
        operational_status="active",
        service_area_districts=["Pune", "Satara", "Solapur"],
        contact_phone="+919876543211",
        contact_email=f"ops.{uid}@deccanswift.com",
    )
    db.add(t2_profile)
    db.flush()

    t2_provider = LogisticsProvider(
        name=f"Deccan Swift Transport {uid}",
        registered_transporter_profile_id=t2_profile.id,
        operating_scope="regional",
        has_cold_chain=True,
        contact_phone="+919876543211",
        contact_email=f"ops.{uid}@deccanswift.com",
        is_active=True,
    )
    db.add(t2_provider)
    db.flush()

    # Farmer & Buyer
    farmer_user = User(
        email=f"farmer.{uid}@example.com",
        password_hash="fake_hash",
        display_name="Anand Patil (Farmer)",
        status=UserStatus.ACTIVE,
    )
    db.add(farmer_user)
    db.flush()
    db.add(UserRole(user_id=farmer_user.id, role_id=farmer_role.id))

    buyer_user = User(
        email=f"apex.{uid}@example.com",
        password_hash="fake_hash",
        display_name="Apex Agro Processing Ltd",
        status=UserStatus.ACTIVE,
    )
    db.add(buyer_user)
    db.flush()
    db.add(UserRole(user_id=buyer_user.id, role_id=buyer_role.id))

    # Locations
    loc_manchar = Location(name=f"Manchar Harvest Yard {uid}", district="Pune", state="Maharashtra", geo_point="POINT(73.94 18.995)")
    loc_junnar = Location(name=f"Junnar Collection Gate {uid}", district="Pune", state="Maharashtra", geo_point="POINT(73.88 19.20)")
    loc_terminal = Location(name=f"Apex Terminal Pune {uid}", district="Pune", state="Maharashtra", geo_point="POINT(73.8567 18.5204)")
    db.add_all([loc_manchar, loc_junnar, loc_terminal])
    db.flush()

    # Commodity
    commodity = db.scalar(select(Commodity).where(Commodity.name == "Onion"))
    if not commodity:
        commodity = Commodity(
            name=f"Onion-{uid}",
            category=CommodityCategory.VEGETABLES,
            default_unit="quintal",
            is_perishable=True,
        )
        db.add(commodity)
        db.flush()

    # Produce Lots
    lot1 = ProduceLot(
        title=f"Red Onion Lot Manchar {uid}",
        seller_user_id=farmer_user.id,
        commodity_id=commodity.id,
        available_quantity=Decimal("20.000"),
        unit="quintal",
        asking_price_per_unit=Decimal("2200.00"),
        quality_grade="Grade A",
        pickup_location_id=loc_manchar.id,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    lot2 = ProduceLot(
        title=f"Red Onion Lot Junnar {uid}",
        seller_user_id=farmer_user.id,
        commodity_id=commodity.id,
        available_quantity=Decimal("20.000"),
        unit="quintal",
        asking_price_per_unit=Decimal("2150.00"),
        quality_grade="Grade A",
        pickup_location_id=loc_junnar.id,
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([lot1, lot2])
    db.flush()

    # Structured Shipment Plan
    plan = ShipmentPlan(
        plan_code=f"PLAN-TEST-2G-{uid}",
        planning_status=ShipmentPlanningStatus.READY_FOR_LOGISTICS,
        buyer_user_id=buyer_user.id,
        buyer_organization_name="Apex Agro Processing Ltd",
        commodity_id=commodity.id,
        total_planned_quantity_quintals=Decimal("40.000"),
        destination_location_id=loc_terminal.id,
        earliest_pickup_date=date.today() + timedelta(days=1),
        delivery_deadline=date.today() + timedelta(days=5),
        estimated_gross_merchandise_value=Decimal("87000.00"),
        is_geographic_distance_exact=True,
    )
    db.add(plan)
    db.flush()

    stop1 = ShipmentPlanPickupStop(
        shipment_plan_id=plan.id,
        stop_sequence=1,
        seller_user_id=farmer_user.id,
        seller_name="Anand Patil",
        seller_role="FARMER",
        pickup_location_id=loc_manchar.id,
        allocated_quantity_quintals=Decimal("20.000"),
        earliest_pickup_date=date.today() + timedelta(days=1),
        is_exact_gps=True,
    )
    stop2 = ShipmentPlanPickupStop(
        shipment_plan_id=plan.id,
        stop_sequence=2,
        seller_user_id=farmer_user.id,
        seller_name="Anand Patil",
        seller_role="FARMER",
        pickup_location_id=loc_junnar.id,
        allocated_quantity_quintals=Decimal("20.000"),
        earliest_pickup_date=date.today() + timedelta(days=1),
        is_exact_gps=True,
    )
    db.add_all([stop1, stop2])
    db.flush()

    contrib1 = ShipmentPlanContributor(
        pickup_stop_id=stop1.id,
        produce_lot_id=lot1.id,
        seller_user_id=farmer_user.id,
        lot_allocated_quantity_quintals=Decimal("20.000"),
        asking_price_per_quintal=Decimal("2200.00"),
        quality_grade="Grade A",
    )
    contrib2 = ShipmentPlanContributor(
        pickup_stop_id=stop2.id,
        produce_lot_id=lot2.id,
        seller_user_id=farmer_user.id,
        lot_allocated_quantity_quintals=Decimal("20.000"),
        asking_price_per_quintal=Decimal("2150.00"),
        quality_grade="Grade A",
    )
    db.add_all([contrib1, contrib2])
    db.commit()

    return {
        "t1_user": t1_user,
        "t1_profile": t1_profile,
        "t1_provider": t1_provider,
        "t2_user": t2_user,
        "t2_profile": t2_profile,
        "t2_provider": t2_provider,
        "farmer_user": farmer_user,
        "buyer_user": buyer_user,
        "plan": plan,
    }


def test_transporter_profile_and_vehicle_lifecycle(db: Session, test_data):
    """Test 2G-1: Transporter profile update and fleet vehicle registration."""
    t1_user = test_data["t1_user"]
    uid = uuid.uuid4().hex[:6].upper()

    # 1. Get transporter dashboard summary
    summary = get_transporter_me(db, t1_user.id)
    assert "Sahyadri Freight & Logistics" in summary.profile.organization_name
    assert summary.total_vehicles_count == 0

    # 2. Update transporter profile
    updated = update_transporter_profile(
        db,
        t1_user.id,
        TransporterProfileUpdate(
            contact_phone="+919988776655",
            service_area_districts=["Pune", "Nashik", "Ahmednagar", "Solapur"],
        ),
    )
    assert updated.contact_phone == "+919988776655"
    assert "Solapur" in updated.service_area_districts

    # 3. Register vehicle 1: Medium Commercial (8 MT / 80 qtl)
    v1 = register_transporter_vehicle(
        db,
        t1_user.id,
        TransporterVehicleCreate(
            registration_number=f"MH-12-AB-{uid}",
            vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
            model_name="Tata 1109 LPT (8.0 MT)",
            payload_capacity_kg=Decimal("8000.00"),
            is_refrigerated=False,
            is_available=True,
            operational_status="available",
        ),
    )
    assert v1.registration_number == f"MH-12-AB-{uid}"
    assert v1.payload_capacity_quintals == Decimal("80.00")
    assert v1.is_available is True

    # 4. List vehicles
    fleet = list_transporter_vehicles(db, t1_user.id)
    assert len(fleet) == 1
    assert fleet[0].id == v1.id

    # 5. Update vehicle status
    v1_updated = update_transporter_vehicle(
        db,
        t1_user.id,
        v1.id,
        TransporterVehicleUpdate(operational_status="maintenance", is_available=False),
    )
    assert v1_updated.operational_status == "maintenance"
    assert v1_updated.is_available is False

    # Restore to available
    update_transporter_vehicle(
        db,
        t1_user.id,
        v1.id,
        TransporterVehicleUpdate(operational_status="available", is_available=True),
    )


def test_opportunity_generation_and_matching(db: Session, test_data):
    """Test 2G-2 & 2G-3: Generate transport opportunities with deterministic eligibility scoring."""
    t1_user = test_data["t1_user"]
    t2_user = test_data["t2_user"]
    plan = test_data["plan"]
    uid = uuid.uuid4().hex[:6].upper()

    # Register vehicles for both transporters
    register_transporter_vehicle(
        db,
        t1_user.id,
        TransporterVehicleCreate(
            registration_number=f"MH-14-XY-{uid}",
            vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
            model_name="Eicher Pro 2049",
            payload_capacity_kg=Decimal("6000.00"),
            is_available=True,
        ),
    )

    register_transporter_vehicle(
        db,
        t2_user.id,
        TransporterVehicleCreate(
            registration_number=f"MH-12-TR-{uid}",
            vehicle_type=VehicleTypeEnum.HEAVY_TRUCK,
            model_name="Ashok Leyland Ecomet",
            payload_capacity_kg=Decimal("10000.00"),
            is_refrigerated=True,
            is_available=True,
        ),
    )

    # Broadcast opportunities for the plan
    broadcast_res = generate_opportunities_for_plan(db, plan.id)
    assert broadcast_res.opportunities_created_count >= 2
    assert broadcast_res.plan_code == plan.plan_code

    # Check T1 opportunity visibility
    t1_opps = list_opportunities_for_transporter(db, t1_user.id)
    assert len(t1_opps) >= 1
    t1_opp = t1_opps[0]
    assert t1_opp.status == TransportOpportunityStatus.OPEN
    assert t1_opp.required_payload_quintals == Decimal("40.000")
    assert t1_opp.distance_certainty == "MODELED_GEOGRAPHIC_DISTANCE"
    assert t1_opp.cost_certainty == "MODELED_REGIONAL_ESTIMATE"
    assert t1_opp.pickup_stops_count == 2

    # Check Opportunity Detail includes waypoints and vehicles
    opp_detail = get_opportunity_detail(db, t1_user.id, t1_opp.id)
    assert len(opp_detail.waypoints) == 3
    assert len(opp_detail.vehicle_options) >= 1

    # Check that in-app notification was recorded
    notif = db.scalar(
        select(Notification).where(
            Notification.recipient_user_id == t1_user.id,
            Notification.notification_type == "TRANSPORT_OPPORTUNITY_CREATED",
        )
    )
    assert notif is not None
    assert "Onion" in notif.title


def test_quote_submission_and_decline_workflow(db: Session, test_data):
    """Test 2G-5 & 2G-6: Transporter can submit a freight bid or decline an opportunity."""
    t2_user = test_data["t2_user"]
    plan = test_data["plan"]
    uid = uuid.uuid4().hex[:6].upper()

    register_transporter_vehicle(
        db,
        t2_user.id,
        TransporterVehicleCreate(
            registration_number=f"MH-20-QT-{uid}",
            vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
            model_name="Tata Ultra (8.0 MT)",
            payload_capacity_kg=Decimal("8000.00"),
            is_available=True,
        ),
    )

    generate_opportunities_for_plan(db, plan.id)

    t2_opps = list_opportunities_for_transporter(db, t2_user.id)
    assert len(t2_opps) >= 1
    opp = t2_opps[0]

    # Transporter 2 submits commercial quote of Rs. 4800
    quote_res = submit_transporter_quote(
        db,
        t2_user.id,
        opp.id,
        TransporterQuoteCreate(
            quote_amount=Decimal("4800.00"),
            quote_unit="INR_TOTAL",
            notes="Ready for morning pickup at Manchar",
        ),
    )
    assert quote_res.quote_amount == Decimal("4800.00")
    assert quote_res.status == QuoteStatus.SUBMITTED
    assert quote_res.quote_certainty == "VERIFIED_TRANSPORTER_QUOTE"

    # Refresh opportunity status -> OFFERED
    opp_detail = get_opportunity_detail(db, t2_user.id, opp.id)
    assert opp_detail.status == TransportOpportunityStatus.OFFERED
    assert len(opp_detail.my_quotes) == 1

    # Decline opportunity
    decline_res = decline_opportunity(
        db,
        t2_user.id,
        opp.id,
        OpportunityDeclineRequest(reason="Truck committed to another route"),
    )
    assert decline_res.status == TransportOpportunityStatus.DECLINED
    assert decline_res.decline_reason == "Truck committed to another route"


def test_transactional_acceptance_and_race_condition_protection(db: Session, test_data):
    """
    Test 2G-7 & 2G-21: Concurrency Protection.
    When Transporter A accepts an opportunity, vehicle is assigned and locked,
    competing opportunities are withdrawn, and Transporter B's subsequent accept
    is rejected with 409 Conflict.
    """
    t1_user = test_data["t1_user"]
    t2_user = test_data["t2_user"]
    plan = test_data["plan"]
    uid = uuid.uuid4().hex[:6].upper()

    t1_veh = register_transporter_vehicle(
        db,
        t1_user.id,
        TransporterVehicleCreate(
            registration_number=f"MH-12-T1-{uid}",
            vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
            model_name="Tata 1109 LPT",
            payload_capacity_kg=Decimal("8000.00"),
            is_available=True,
        ),
    )

    t2_veh = register_transporter_vehicle(
        db,
        t2_user.id,
        TransporterVehicleCreate(
            registration_number=f"MH-12-T2-{uid}",
            vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
            model_name="Eicher 2049",
            payload_capacity_kg=Decimal("8000.00"),
            is_available=True,
        ),
    )

    generate_opportunities_for_plan(db, plan.id)

    # Fetch opportunities for both transporters
    t1_opp = db.scalar(
        select(TransportOpportunity).where(
            TransportOpportunity.shipment_plan_id == plan.id,
            TransportOpportunity.transporter_profile_id == test_data["t1_profile"].id,
        )
    )
    t1_opp.status = TransportOpportunityStatus.OPEN

    t2_opp = db.scalar(
        select(TransportOpportunity).where(
            TransportOpportunity.shipment_plan_id == plan.id,
            TransportOpportunity.transporter_profile_id == test_data["t2_profile"].id,
        )
    )
    t2_opp.status = TransportOpportunityStatus.OPEN
    db.commit()

    # 1. Transporter A accepts first
    accepted_detail = accept_opportunity_transactional(
        db,
        t1_user.id,
        t1_opp.id,
        OpportunityAcceptRequest(
            vehicle_id=t1_veh.id,
            driver_name="Suresh Shinde",
            driver_phone="+919876543299",
            notes="Will arrive at 07:00 AM",
        ),
    )
    assert accepted_detail.status == TransportOpportunityStatus.ACCEPTED
    assert accepted_detail.shipment_id is not None

    # Verify vehicle 1 is now busy
    v1_db = db.scalar(select(Vehicle).where(Vehicle.id == t1_veh.id))
    assert v1_db.is_available is False
    assert v1_db.operational_status == "busy"

    # Verify shipment created and assigned
    shipment = db.scalar(select(Shipment).where(Shipment.shipment_plan_id == plan.id))
    assert shipment is not None
    assert shipment.status == ShipmentStatus.SCHEDULED
    assert shipment.provider_id == test_data["t1_provider"].id
    assert shipment.vehicle_id == t1_veh.id
    assert shipment.driver_name == "Suresh Shinde"

    # Verify ShipmentEvent recorded
    event = db.scalar(select(ShipmentEvent).where(ShipmentEvent.shipment_id == shipment.id))
    assert event is not None
    assert event.event_type == "TRANSPORTER_ASSIGNED"

    # Verify Transporter B's opportunity was WITHDRAWN
    t2_opp_refreshed = db.scalar(select(TransportOpportunity).where(TransportOpportunity.id == t2_opp.id))
    assert t2_opp_refreshed.status == TransportOpportunityStatus.WITHDRAWN

    # 2. Transporter B attempts to accept the same job -> REJECTED with 400/409 error
    with pytest.raises(Exception) as exc_info:
        accept_opportunity_transactional(
            db,
            t2_user.id,
            t2_opp.id,
            OpportunityAcceptRequest(vehicle_id=t2_veh.id),
        )
    assert "opportunity_not_open" in str(getattr(exc_info.value, "code", "")) or "withdrawn" in str(exc_info.value).lower() or "assigned" in str(exc_info.value).lower()

    # Verify active shipments list for Transporter A
    t1_shipments = list_transporter_shipments(db, t1_user.id)
    assert len(t1_shipments) == 1
    assert t1_shipments[0]["plan_code"] == plan.plan_code
    assert t1_shipments[0]["driver_name"] == "Suresh Shinde"
