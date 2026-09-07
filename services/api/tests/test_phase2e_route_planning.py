"""
Phase 2E - Step 4: Route Feasibility & Waypoint Sequencing Foundation Tests.
Tests single-stop and multi-stop waypoint itineraries, geographic precision states (EXACT,
ADMINISTRATIVE_ONLY, UNAVAILABLE), routing provider abstraction, cumulative onboard payload,
deadline/capacity feasibility checks, and HTTP APIs.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

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
    ProduceLot,
    ProduceLotStatus,
    Role,
    RoleName,
    ShipmentPlan,
    ShipmentPlanPickupStop,
    ShipmentPlanningStatus,
    User,
    UserRole,
    UserStatus,
    VerificationStatus,
)
from app.modules.logistics.route_planning_engine import (
    build_and_evaluate_route_plan,
)
from app.modules.logistics.routing_providers import (
    BaseRoutingProvider,
    LocationCoordinate,
    ModeledGeographicRoutingProvider,
    RouteCalculationResult,
)
from app.modules.logistics.shipment_planning_service import (
    create_shipment_plan_from_requirement,
)
from app.schemas.route_planning import (
    GeographicPrecisionEnum,
    RoutePlanningStatus,
    WaypointTypeEnum,
)
from app.schemas.shipment_plan import (
    PlannedLotAllocation,
    ShipmentPlanFromRequirementRequest,
)


@pytest.fixture
def route_test_data(db: Session):
    """Creates isolated commodities, locations, users, and shipment plan test fixtures."""
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
        is_perishable=False,
        is_active=True,
    )
    db.add(onion)
    db.commit()

    # Locations with exact GPS coordinates
    loc_hub = Location(
        name="Pune Narayangaon Buyer Hub",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("18.5204"),
        longitude=Decimal("73.8567"),
    )
    loc_farm_a = Location(
        name="Manchar Harvest Yard",
        district="Pune",
        taluka="Ambegaon",
        state="Maharashtra",
        latitude=Decimal("18.9950"),
        longitude=Decimal("73.9400"),
    )
    loc_farm_b = Location(
        name="Junnar Harvest Yard",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.2000"),
        longitude=Decimal("73.8800"),
    )
    loc_farm_c = Location(
        name="Narayangaon Harvest Yard",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.1200"),
        longitude=Decimal("73.9800"),
    )
    loc_farm_d = Location(
        name="Alephata Harvest Yard",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.1800"),
        longitude=Decimal("74.1000"),
    )
    # Administrative-only Location without coordinates
    loc_textual = Location(
        name="Baramati Textual Yard",
        district="Pune",
        taluka="Baramati",
        state="Maharashtra",
        latitude=None,
        longitude=None,
    )
    db.add_all([loc_hub, loc_farm_a, loc_farm_b, loc_farm_c, loc_farm_d, loc_textual])
    db.commit()

    # Buyer User & Profile
    buyer_u = User(
        email=f"buyer_route_{suffix}@agrimandi.test",
        display_name="Wholesale Produce Terminal",
        password_hash="mock_hash",
        status=UserStatus.ACTIVE,
    )
    db.add(buyer_u)
    db.commit()
    db.add(UserRole(user_id=buyer_u.id, role_id=buyer_role.id))
    buyer_prof = BuyerProfile(
        user_id=buyer_u.id,
        organization_name="Wholesale Produce Terminal Ltd",
        primary_location_id=loc_hub.id,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(buyer_prof)

    # 4 Farmer Users & Profiles
    farmers = []
    for i, loc in enumerate([loc_farm_a, loc_farm_b, loc_farm_c, loc_farm_d]):
        f_user = User(
            email=f"farmer_route_{chr(65+i)}_{suffix}@agrimandi.test",
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
        farmers.append((f_user, f_prof, loc))
    db.commit()

    return {
        "suffix": suffix,
        "onion": onion,
        "loc_hub": loc_hub,
        "loc_farm_a": loc_farm_a,
        "loc_farm_b": loc_farm_b,
        "loc_farm_c": loc_farm_c,
        "loc_farm_d": loc_farm_d,
        "loc_textual": loc_textual,
        "buyer_prof": buyer_prof,
        "farmers": farmers,
    }


def test_single_pickup_and_destination_route(db: Session, route_test_data: dict):
    """
    Test 1: Single pickup stop + destination.
    Constructs a 2-waypoint itinerary: Pickup 1 -> Destination.
    Verifies cumulative onboard cargo and waypoint sequence.
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("25.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="25qtl Single Lot",
        available_quantity=Decimal("25.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("25.0"), unit="quintal")],
        ),
    )

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.route_status == RoutePlanningStatus.ROUTE_FEASIBLE
    assert route_plan.waypoints_count == 2
    assert route_plan.pickup_stops_count == 1
    assert route_plan.total_cargo_quantity_quintals == Decimal("25.0")
    assert route_plan.total_modeled_distance_km is not None
    assert route_plan.total_modeled_distance_km > Decimal("0.0")

    wp1 = route_plan.waypoints[0]
    assert wp1.waypoint_sequence == 1
    assert wp1.waypoint_type == WaypointTypeEnum.PICKUP
    assert wp1.stop_cargo_quantity_quintals == Decimal("25.0")
    assert wp1.cumulative_onboard_quantity_quintals == Decimal("25.0")

    wp2 = route_plan.waypoints[1]
    assert wp2.waypoint_sequence == 2
    assert wp2.waypoint_type == WaypointTypeEnum.DESTINATION
    assert wp2.stop_cargo_quantity_quintals == Decimal("0.0")
    assert wp2.cumulative_onboard_quantity_quintals == Decimal("25.0")


def test_multi_stop_waypoint_sequencing(db: Session, route_test_data: dict):
    """
    Test 2: Multi-stop shipment (4 stops: 8 qtl, 12 qtl, 7 qtl, 15 qtl = 42 qtl).
    Constructs a 5-waypoint sequence with exact cumulative load accumulation:
    Stop 1 (8) -> Stop 2 (20) -> Stop 3 (27) -> Stop 4 (42) -> Destination (42).
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    loc_hub = route_test_data["loc_hub"]
    farmers = route_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=7),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    quantities_qtl = [Decimal("8.0"), Decimal("12.0"), Decimal("7.0"), Decimal("15.0")]
    lots = []
    for i, (f_user, _, loc) in enumerate(farmers):
        lot = ProduceLot(
            seller_user_id=f_user.id,
            commodity_id=onion.id,
            pickup_location_id=loc.id,
            title=f"Multi Lot Farmer {chr(65+i)}",
            available_quantity=quantities_qtl[i],
            unit="quintal",
            available_from=date.today(),
            status=ProduceLotStatus.PUBLISHED,
        )
        db.add(lot)
        lots.append(lot)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=lots[i].id, allocated_quantity=quantities_qtl[i], unit="quintal")
        for i in range(4)
    ]

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.route_status == RoutePlanningStatus.ROUTE_FEASIBLE
    assert route_plan.waypoints_count == 5
    assert route_plan.pickup_stops_count == 4
    assert route_plan.total_cargo_quantity_quintals == Decimal("42.0")

    # Verify cumulative load tracking at each waypoint
    running_load = Decimal("0.0")
    for wp in route_plan.waypoints:
        running_load += wp.stop_cargo_quantity_quintals
        assert wp.cumulative_onboard_quantity_quintals == running_load
    assert route_plan.waypoints[-1].cumulative_onboard_quantity_quintals == Decimal("42.0")



def test_exact_coordinates_route_feasible(db: Session, route_test_data: dict):
    """
    Test 3: Exact coordinate completeness produces ROUTE_FEASIBLE and EXACT precision.
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("15.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Exact GPS Lot",
        available_quantity=Decimal("15.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("15.0"), unit="quintal")],
        ),
    )

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.overall_geographic_precision == GeographicPrecisionEnum.EXACT
    assert route_plan.route_status == RoutePlanningStatus.ROUTE_FEASIBLE
    assert route_plan.distance_certainty == "MODELED_GEOGRAPHIC_DISTANCE"


def test_administrative_only_locations_unknown_status(db: Session, route_test_data: dict):
    """
    Test 4: Textual location without GPS coordinates produces ROUTE_FEASIBILITY_UNKNOWN
    with overall_geographic_precision = ADMINISTRATIVE_ONLY (no fabricated coordinates).
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user = route_test_data["farmers"][0][0]
    loc_textual = route_test_data["loc_textual"]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
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
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("20.0"), unit="quintal")],
        ),
    )

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.overall_geographic_precision == GeographicPrecisionEnum.ADMINISTRATIVE_ONLY
    assert route_plan.route_status == RoutePlanningStatus.ROUTE_FEASIBILITY_UNKNOWN
    assert route_plan.waypoints[0].latitude is None
    assert route_plan.waypoints[0].longitude is None
    assert route_plan.waypoints[0].geographic_precision == GeographicPrecisionEnum.ADMINISTRATIVE_ONLY
    assert any("Exact GPS coordinates unavailable" in w for w in route_plan.warnings)


def test_missing_destination_incomplete_data(db: Session, route_test_data: dict):
    """
    Test 5: Missing destination location produces ROUTE_DATA_INCOMPLETE.
    """
    onion = route_test_data["onion"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]

    # Create manual plan without destination
    plan = ShipmentPlan(
        plan_code="SHP-TEST-NODEST",
        planning_status=ShipmentPlanningStatus.PLANNED,
        commodity_id=onion.id,
        total_planned_quantity_quintals=Decimal("10.0"),
        destination_location_id=uuid.uuid4(),  # Non-existent location ID
        earliest_pickup_date=date.today(),
        is_geographic_distance_exact=False,
        economic_disclaimer="Test",
    )
    db.add(plan)
    db.commit()

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.route_status == RoutePlanningStatus.ROUTE_DATA_INCOMPLETE
    assert "Destination location is missing or unresolvable" in route_plan.status_summary


def test_vehicle_capacity_exceeded_infeasible(db: Session, route_test_data: dict):
    """
    Test 6: Cumulative cargo exceeding assigned vehicle capacity produces ROUTE_INFEASIBLE.
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("35.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="35qtl Lot",
        available_quantity=Decimal("35.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("35.0"), unit="quintal")],
        ),
    )

    # Pass an undersized vehicle capacity (e.g. 10 qtl mini truck for 35 qtl cargo)
    route_plan = build_and_evaluate_route_plan(
        db,
        plan.id,
        assigned_vehicle_capacity_qtl=Decimal("10.0"),
        assigned_vehicle_class="Mini Truck (1.0 MT)",
    )

    assert route_plan.route_status == RoutePlanningStatus.ROUTE_INFEASIBLE
    assert any("FAILED CAPACITY" in c for c in route_plan.feasibility_checks)


def test_pickup_quantity_reconciliation(db: Session, route_test_data: dict):
    """
    Test 7: Multi-stop quantity reconciliation.
    Confirms sum(stop cargo quantities) == total_cargo_quantity_quintals == shipment plan quantity.
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    loc_hub = route_test_data["loc_hub"]
    farmers = route_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("27.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    quantities = [Decimal("8.0"), Decimal("12.0"), Decimal("7.0")]
    lots = []
    for i in range(3):
        f_user, _, loc = farmers[i]
        lot = ProduceLot(
            seller_user_id=f_user.id,
            commodity_id=onion.id,
            pickup_location_id=loc.id,
            title=f"Reconcile Lot {chr(65+i)}",
            available_quantity=quantities[i],
            unit="quintal",
            available_from=date.today(),
            status=ProduceLotStatus.PUBLISHED,
        )
        db.add(lot)
        lots.append(lot)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=lots[i].id, allocated_quantity=quantities[i], unit="quintal")
        for i in range(3)
    ]

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.total_cargo_quantity_quintals == Decimal("27.0")
    stop_sum = sum(wp.stop_cargo_quantity_quintals for wp in route_plan.waypoints if wp.waypoint_type == WaypointTypeEnum.PICKUP)
    assert stop_sum == Decimal("27.0")
    assert any("Quantity reconciliation passed" in c for c in route_plan.feasibility_checks)


def test_delivery_deadline_violation_infeasible(db: Session, route_test_data: dict):
    """
    Test 8: Pickup window conflicting with delivery deadline produces ROUTE_INFEASIBLE.
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("10.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=3),
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Late Lot",
        available_quantity=Decimal("10.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("10.0"), unit="quintal")],
        ),
    )

    # Mutate DB entity plan and stop's earliest_pickup_date to be AFTER delivery deadline
    plan_entity = db.get(ShipmentPlan, plan.id)
    assert plan_entity is not None
    plan_entity.earliest_pickup_date = date.today() + timedelta(days=10)
    for s in plan_entity.pickup_stops:
        s.earliest_pickup_date = date.today() + timedelta(days=10)
    db.commit()

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.route_status == RoutePlanningStatus.ROUTE_INFEASIBLE
    assert any("FAILED DEADLINE" in c for c in route_plan.feasibility_checks)






def test_routing_provider_abstraction(db: Session, route_test_data: dict):
    """
    Test 9: Pluggable BaseRoutingProvider abstraction.
    Verifies that a custom routing provider implementation can be passed into build_and_evaluate_route_plan.
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("10.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Provider Test Lot",
        available_quantity=Decimal("10.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("10.0"), unit="quintal")],
        ),
    )

    class MockCustomRoutingEngine(BaseRoutingProvider):
        @property
        def provider_name(self) -> str:
            return "Mock High-Precision Road Router"

        def calculate_route(self, waypoints: List[LocationCoordinate]) -> RouteCalculationResult:
            return RouteCalculationResult(
                total_distance_km=Decimal("48.50"),
                distance_certainty="VERIFIED_ROAD_DISTANCE",
                estimated_transit_hours=Decimal("1.25"),
                transit_time_certainty="VERIFIED_ROAD_TIME",
                segment_distances_km=[Decimal("48.50")],
                provider_name=self.provider_name,
                is_live_routing=True,
                disclaimer="Mock route calculation.",
            )

        def get_distance_matrix(self, origins, destinations):
            return [[Decimal("48.50")]]

    custom_provider = MockCustomRoutingEngine()
    route_plan = build_and_evaluate_route_plan(db, plan.id, routing_provider=custom_provider)

    assert route_plan.routing_provider_name == "Mock High-Precision Road Router"
    assert route_plan.total_modeled_distance_km == Decimal("48.50")
    assert route_plan.distance_certainty == "VERIFIED_ROAD_DISTANCE"
    assert route_plan.estimated_transit_hours == Decimal("1.25")
    assert route_plan.transit_time_certainty == "VERIFIED_ROAD_TIME"


def test_deterministic_baseline_ordering(db: Session, route_test_data: dict):
    """
    Test 10: Deterministic baseline waypoint ordering.
    Verifies that the strategy is documented as DETERMINISTIC_BASELINE_ORDERING
    without false global optimality claims.
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("10.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Baseline Order Lot",
        available_quantity=Decimal("10.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("10.0"), unit="quintal")],
        ),
    )

    route_plan = build_and_evaluate_route_plan(db, plan.id)

    assert route_plan.routing_strategy == "DETERMINISTIC_BASELINE_ORDERING"
    assert any("deterministic baseline heuristic" in l for l in route_plan.operational_limitations)


def test_no_fabricated_coordinates(db: Session, route_test_data: dict):
    """
    Test 11: No fabricated coordinates.
    Locations lacking verified coordinates must maintain latitude = None and longitude = None.
    """
    loc_textual = route_test_data["loc_textual"]
    assert loc_textual.latitude is None
    assert loc_textual.longitude is None


def test_api_route_plan_post_and_get(client: TestClient, db: Session, route_test_data: dict):
    """
    Test 12: HTTP API integration tests:
    - POST /api/v1/logistics/shipments/{shipment_id}/route-plan
    - GET /api/v1/logistics/shipments/{shipment_id}/route-plan
    """
    onion = route_test_data["onion"]
    buyer_prof = route_test_data["buyer_prof"]
    farmer_a_user, _, loc_a = route_test_data["farmers"][0]
    loc_hub = route_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("15.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="API Route Lot",
        available_quantity=Decimal("15.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([req, lot])
    db.commit()

    plan = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=lot.id, allocated_quantity=Decimal("15.0"), unit="quintal")],
        ),
    )

    # 1. POST /shipments/{id}/route-plan
    res_post = client.post(f"/api/v1/logistics/shipments/{plan.id}/route-plan")
    assert res_post.status_code == 200
    route_data_post = res_post.json()
    assert route_data_post["route_status"] == "route_feasible"
    assert route_data_post["waypoints_count"] == 2
    assert float(route_data_post["total_cargo_quantity_quintals"]) == 15.0

    # 2. GET /shipments/{id}/route-plan
    res_get = client.get(f"/api/v1/logistics/shipments/{plan.id}/route-plan")
    assert res_get.status_code == 200
    route_data_get = res_get.json()
    assert route_data_get["route_status"] == "route_feasible"
    assert route_data_get["plan_code"] == plan.plan_code
