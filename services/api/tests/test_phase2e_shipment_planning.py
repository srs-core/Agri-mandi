"""
Phase 2E - Step 2: Shipment Planning Foundation Tests.
Tests single-lot and multi-lot shipment plans, quantity reconciliation, duplicate rejection,
over-allocation prevention, lifecycle states (PLANNED -> READY_FOR_LOGISTICS -> CANCELLED),
lineage preservation, and HTTP endpoints.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import (
    BuyerProfile,
    BuyerRequirement,
    BuyerRequirementStatus,
    Commodity,
    CommodityCategory,
    FarmerProfile,
    Location,
    Order,
    OrderItem,
    OrderStatus,
    ProduceLot,
    ProduceLotStatus,
    Role,
    RoleName,
    ShipmentPlan,
    ShipmentPlanningStatus,
    User,
    UserRole,
    UserStatus,
    VerificationStatus,
)
from app.modules.logistics.shipment_planning_service import (
    cancel_shipment_plan,
    create_shipment_plan_from_order,
    create_shipment_plan_from_requirement,
    get_shipment_plan,
    list_shipment_plans,
    mark_shipment_plan_ready,
)
from app.schemas.shipment_plan import (
    PlannedLotAllocation,
    ShipmentPlanFromOrderRequest,
    ShipmentPlanFromRequirementRequest,
)


@pytest.fixture
def shipment_test_data(db: Session):
    """Creates isolated test users, locations, commodities, and profiles for shipment planning."""
    suffix = str(uuid.uuid4())[:8]

    # Roles
    farmer_role = db.query(Role).filter(Role.name == RoleName.FARMER).first()
    if not farmer_role:
        farmer_role = Role(name=RoleName.FARMER, description="Farmer")
        db.add(farmer_role)
    buyer_role = db.query(Role).filter(Role.name == RoleName.BUYER).first()
    if not buyer_role:
        buyer_role = Role(name=RoleName.BUYER, description="Buyer")
        db.add(buyer_role)
    db.commit()

    # Commodity
    onion = Commodity(
        name=f"Nashik Red Onion {suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=True,
        is_active=True,
    )
    potato = Commodity(
        name=f"Jyoti Potato {suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=True,
        is_active=True,
    )
    db.add_all([onion, potato])
    db.commit()

    # Locations
    loc_buyer = Location(
        name="Pune Narayangaon Buyer Hub",
        district="Pune",
        state="Maharashtra",
        latitude=Decimal("18.5204"),
        longitude=Decimal("73.8567"),
    )
    loc_farm_a = Location(
        name="Manchar Yard",
        district="Pune",
        taluka="Ambegaon",
        state="Maharashtra",
        latitude=Decimal("18.9950"),
        longitude=Decimal("73.9400"),
    )
    loc_farm_b = Location(
        name="Junnar Yard",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.2000"),
        longitude=Decimal("73.8800"),
    )
    loc_farm_c = Location(
        name="Narayangaon Yard",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.1200"),
        longitude=Decimal("73.9800"),
    )
    loc_farm_d = Location(
        name="Alephata Yard",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.1800"),
        longitude=Decimal("74.1000"),
    )
    loc_textual = Location(
        name="Baramati Textual Yard",
        district="Pune",
        taluka="Baramati",
        state="Maharashtra",
        latitude=None,
        longitude=None,
    )
    db.add_all([loc_buyer, loc_farm_a, loc_farm_b, loc_farm_c, loc_farm_d, loc_textual])
    db.commit()

    # Buyer User & Profile
    buyer_user = User(
        email=f"buyer_{suffix}@agrimandi.test",
        display_name="Metro Fresh Wholesale Ltd",
        password_hash="mock_hash",
        status=UserStatus.ACTIVE,
    )
    db.add(buyer_user)
    db.commit()
    db.add(UserRole(user_id=buyer_user.id, role_id=buyer_role.id))
    buyer_profile = BuyerProfile(
        user_id=buyer_user.id,
        organization_name="Metro Fresh Wholesale Ltd",
        primary_location_id=loc_buyer.id,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(buyer_profile)
    db.commit()

    # 4 Farmer Users & Profiles
    farmers = []
    for i, loc in enumerate([loc_farm_a, loc_farm_b, loc_farm_c, loc_farm_d]):
        f_user = User(
            email=f"farmer_{chr(65+i)}_{suffix}@agrimandi.test",
            display_name=f"Farmer {chr(65+i)} Patil",
            password_hash="mock_hash",
            status=UserStatus.ACTIVE,
        )
        db.add(f_user)
        db.commit()
        db.add(UserRole(user_id=f_user.id, role_id=farmer_role.id))
        f_prof = FarmerProfile(
            user_id=f_user.id,
            farm_name=f"Farm {chr(65+i)}",
            primary_location_id=loc.id,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(f_prof)
        db.commit()
        farmers.append((f_user, f_prof, loc))

    return {
        "suffix": suffix,
        "onion": onion,
        "potato": potato,
        "loc_buyer": loc_buyer,
        "farmers": farmers,
        "loc_textual": loc_textual,
        "buyer_user": buyer_user,
        "buyer_profile": buyer_profile,
    }


def test_single_lot_shipment_plan_creation(db: Session, shipment_test_data: dict):
    """
    Verifies that a single-lot fulfillment opportunity creates a 1-stop shipment plan
    with exact quantity, lineage, and PLANNED status.
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]

    # Buyer requirement: 25 quintals
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("25.0"),
        unit="quintal",
        minimum_quality_grade="Grade A",
        target_price_per_unit=Decimal("2600.00"),
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    # Produce Lot: 30 quintals
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Single Harvest Lot",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        quality_grade="Grade A",
        asking_price_per_unit=Decimal("2550.00"),
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        lot_allocations=[
            PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("25.0"), unit="quintal")
        ],
        earliest_pickup_date=date.today(),
    )

    plan = create_shipment_plan_from_requirement(db, request_payload)

    assert plan.planning_status == "planned"
    assert plan.total_planned_quantity_quintals == Decimal("25.0")
    assert plan.total_stops_count == 1
    assert plan.total_contributors_count == 1
    assert plan.pickup_stops[0].seller_user_id == farmer_a_user.id
    assert plan.pickup_stops[0].allocated_quantity_quintals == Decimal("25.0")
    assert plan.pickup_stops[0].contributors[0].produce_lot_id == lot.id
    assert plan.estimated_gross_merchandise_value == Decimal("65000.00")  # 25 qtl * ₹2600
    assert plan.is_geographic_distance_exact is True


def test_multi_farmer_aggregated_shipment_plan(db: Session, shipment_test_data: dict):
    """
    Verifies multi-farmer aggregation:
    4 farmers (800kg + 1200kg + 700kg + 1500kg = 4.2 tonnes = 42 qtl)
    creates a 4-stop shipment plan with exact contributor lineage.
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmers = shipment_test_data["farmers"]

    # Requirement: 4 tonnes (40 quintals)
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("4.0"),
        unit="tonnes",
        minimum_quality_grade="Grade B",
        target_price_per_unit=Decimal("25000.00"),  # ₹25,000 / tonne = ₹2,500 / quintal
        delivery_by=date.today() + timedelta(days=7),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    quantities_kg = [Decimal("800.0"), Decimal("1200.0"), Decimal("700.0"), Decimal("1500.0")]
    lots = []
    allocations = []

    for i, (f_user, _, loc) in enumerate(farmers):
        lot = ProduceLot(
            seller_user_id=f_user.id,
            commodity_id=onion.id,
            pickup_location_id=loc.id,
            title=f"Multi Lot Farmer {chr(65+i)}",
            available_quantity=quantities_kg[i],
            unit="kg",
            quality_grade="Grade A",
            asking_price_per_unit=Decimal("24.50"),
            available_from=date.today(),
            status=ProduceLotStatus.PUBLISHED,
        )
        db.add(lot)
        lots.append(lot)
    db.commit()

    for i, lot in enumerate(lots):
        allocations.append(
            PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=quantities_kg[i], unit="kg")
        )


    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        aggregation_opportunity_id="AGG-OPP-ONION-4P",
        lot_allocations=allocations,
        earliest_pickup_date=date.today(),
    )

    plan = create_shipment_plan_from_requirement(db, request_payload)

    assert plan.planning_status == "planned"
    assert plan.total_planned_quantity_quintals == Decimal("42.0")  # 8 + 12 + 7 + 15 qtl
    assert plan.total_stops_count == 4
    assert plan.total_contributors_count == 4
    assert plan.aggregation_opportunity_id == "AGG-OPP-ONION-4P"
    assert plan.is_geographic_distance_exact is True

    # Check that each stop sequence is 1..4
    sequences = [s.stop_sequence for s in plan.pickup_stops]
    assert sequences == [1, 2, 3, 4]


def test_quantity_reconciliation_exact_sum(db: Session, shipment_test_data: dict):
    """
    Confirms sum(stop allocated quantities) == total_planned_quantity_quintals.
    """
    potato = shipment_test_data["potato"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]
    farmer_b_user, _, loc_b = shipment_test_data["farmers"][1]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=potato.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("50.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    lot_a = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=potato.id,
        pickup_location_id=loc_a.id,
        title="Potato A",
        available_quantity=Decimal("20.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    lot_b = ProduceLot(
        seller_user_id=farmer_b_user.id,
        commodity_id=potato.id,
        pickup_location_id=loc_b.id,
        title="Potato B",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([lot_a, lot_b])
    db.commit()

    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        lot_allocations=[
            PlannedLotAllocation(produce_lot_id=lot_a.id, allocated_quantity=Decimal("15.5"), unit="quintal"),
            PlannedLotAllocation(produce_lot_id=lot_b.id, allocated_quantity=Decimal("24.5"), unit="quintal"),
        ],
    )

    plan = create_shipment_plan_from_requirement(db, request_payload)

    stops_sum = sum(s.allocated_quantity_quintals for s in plan.pickup_stops)
    assert stops_sum == Decimal("40.0")
    assert plan.total_planned_quantity_quintals == Decimal("40.0")


def test_duplicate_produce_lot_rejection(db: Session, shipment_test_data: dict):
    """
    Prevents duplicate produce lots in allocations list.
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Duplicated Lot",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        lot_allocations=[
            PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("10.0"), unit="quintal"),
            PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("10.0"), unit="quintal"),
        ],
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_shipment_plan_from_requirement(db, request_payload)

    assert exc_info.value.status_code == 422
    assert "Duplicate produce lot" in exc_info.value.detail


def test_inactive_produce_lot_rejection(db: Session, shipment_test_data: dict):
    """
    Rejects draft/sold/cancelled produce lots.
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    draft_lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Draft Lot",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.DRAFT,
    )
    db.add(draft_lot)
    db.commit()

    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        lot_allocations=[
            PlannedLotAllocation(produce_lot_id=draft_lot.id, allocated_quantity=Decimal("20.0"), unit="quintal")
        ],
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_shipment_plan_from_requirement(db, request_payload)

    assert exc_info.value.status_code == 422
    assert "Must be 'published'" in exc_info.value.detail


def test_over_allocation_rejection(db: Session, shipment_test_data: dict):
    """
    Rejects allocations where requested quantity exceeds available lot quantity.
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("50.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Small Lot 10qtl",
        available_quantity=Decimal("10.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    # Attempt to allocate 25 quintals from a 10-quintal lot
    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        lot_allocations=[
            PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("25.0"), unit="quintal")
        ],
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_shipment_plan_from_requirement(db, request_payload)

    assert exc_info.value.status_code == 422
    assert "exceeds available quantity" in exc_info.value.detail


def test_invalid_delivery_window_rejection(db: Session, shipment_test_data: dict):
    """
    Rejects plans where earliest pickup date is after the buyer delivery deadline.
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=2),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Available Lot",
        available_quantity=Decimal("20.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    # Requested pickup date is in 10 days, but deadline is in 2 days
    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        lot_allocations=[
            PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("20.0"), unit="quintal")
        ],
        earliest_pickup_date=date.today() + timedelta(days=10),
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_shipment_plan_from_requirement(db, request_payload)

    assert exc_info.value.status_code == 422
    assert "cannot be after requirement delivery deadline" in exc_info.value.detail


def test_missing_gps_coordinates_fallback(db: Session, shipment_test_data: dict):
    """
    Verifies that textual locations without GPS coordinates set is_geographic_distance_exact = False
    with descriptive geographic precision notes.
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user = shipment_test_data["farmers"][0][0]
    loc_textual = shipment_test_data["loc_textual"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_textual.id,
        title="Textual Location Lot",
        available_quantity=Decimal("20.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    request_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=req.id,
        lot_allocations=[
            PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("20.0"), unit="quintal")
        ],
    )

    plan = create_shipment_plan_from_requirement(db, request_payload)

    assert plan.is_geographic_distance_exact is False
    assert "rely on administrative district definitions" in plan.geographic_precision_notes
    assert plan.pickup_stops[0].is_exact_gps is False


def test_shipment_plan_from_order(db: Session, shipment_test_data: dict):
    """
    Verifies creating a shipment plan from an existing confirmed Order.
    """
    onion = shipment_test_data["onion"]
    buyer_user = shipment_test_data["buyer_user"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]
    loc_buyer = shipment_test_data["loc_buyer"]

    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Order Lot",
        available_quantity=Decimal("50.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    order = Order(
        buyer_user_id=buyer_user.id,
        seller_user_id=farmer_a_user.id,
        delivery_location_id=loc_buyer.id,
        status=OrderStatus.CONFIRMED,
        total_amount=Decimal("75000.00"),
    )
    db.add(order)
    db.commit()

    item = OrderItem(
        order_id=order.id,
        produce_lot_id=lot.id,
        commodity_id=onion.id,
        quantity=Decimal("30.0"),
        unit="quintal",
        agreed_price_per_unit=Decimal("2500.00"),
    )
    db.add(item)
    db.commit()

    plan = create_shipment_plan_from_order(db, ShipmentPlanFromOrderRequest(order_id=order.id))

    assert plan.planning_status == "planned"
    assert plan.order_id == order.id
    assert plan.total_planned_quantity_quintals == Decimal("30.0")
    assert plan.total_stops_count == 1
    assert plan.estimated_gross_merchandise_value == Decimal("75000.00")


def test_shipment_plan_lifecycle_transitions(db: Session, shipment_test_data: dict):
    """
    Tests transitions:
    PLANNED -> READY_FOR_LOGISTICS
    PLANNED -> CANCELLED
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Lifecycle Lot",
        available_quantity=Decimal("25.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    # 1. Create plan
    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("20.0"), unit="quintal")],
        ),
    )
    assert plan.planning_status == "planned"

    # 2. Mark READY_FOR_LOGISTICS
    ready_plan = mark_shipment_plan_ready(db, plan.id)
    assert ready_plan.planning_status == "ready_for_logistics"

    # 3. Cancel plan
    cancelled_plan = cancel_shipment_plan(db, plan.id, reason="Buyer requested quantity modification")
    assert cancelled_plan.planning_status == "cancelled"


def test_api_shipment_planning_endpoints(client: TestClient, db: Session, shipment_test_data: dict):
    """
    Tests FastAPI HTTP routes:
    - POST /api/v1/logistics/shipments/plan/from-requirement
    - GET /api/v1/logistics/shipments/plans
    - GET /api/v1/logistics/shipments/plans/{id}
    - POST /api/v1/logistics/shipments/plans/{id}/ready
    - POST /api/v1/logistics/shipments/plans/{id}/cancel
    """
    onion = shipment_test_data["onion"]
    buyer_profile = shipment_test_data["buyer_profile"]
    loc_buyer = shipment_test_data["loc_buyer"]
    farmer_a_user, _, loc_a = shipment_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("15.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="HTTP API Lot",
        available_quantity=Decimal("20.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()


    # 1. POST /from-requirement
    res_create = client.post(
        "/api/v1/logistics/shipments/plan/from-requirement",
        json={
            "buyer_requirement_id": str(req.id),
            "lot_allocations": [
                {"produce_lot_id": str(lot.id), "allocated_quantity": 15.0, "unit": "quintal"}
            ],
        },
    )
    assert res_create.status_code == 200
    plan_data = res_create.json()
    plan_id = plan_data["id"]
    assert plan_data["planning_status"] == "planned"
    assert plan_data["total_stops_count"] == 1

    # 2. GET /plans
    res_list = client.get("/api/v1/logistics/shipments/plans")
    assert res_list.status_code == 200
    assert res_list.json()["total_count"] >= 1

    # 3. GET /plans/{id}
    res_get = client.get(f"/api/v1/logistics/shipments/plans/{plan_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == plan_id

    # 4. POST /plans/{id}/ready
    res_ready = client.post(f"/api/v1/logistics/shipments/plans/{plan_id}/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["planning_status"] == "ready_for_logistics"

    # 5. POST /plans/{id}/cancel
    res_cancel = client.post(f"/api/v1/logistics/shipments/plans/{plan_id}/cancel?reason=TestCancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["planning_status"] == "cancelled"
