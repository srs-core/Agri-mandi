"""
Phase 2E - Step 5: Full Multi-Stop Route Optimization Tests.
Tests Google OR-Tools VRP solver, BaseRouteOptimizer abstractions, capacity tracking,
time-window / deadline conflicts, baseline vs. optimized comparison metrics, and API routes.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
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
    User,
    UserRole,
    UserStatus,
    VerificationStatus,
)
from app.modules.logistics.route_optimizers import (
    BaseRouteOptimizer,
    DeterministicBaselineRouteOptimizer,
    ORToolsVehicleRoutingOptimizer,
    OptimizationExecutionResult,
)
from app.modules.logistics.route_planning_engine import (
    build_and_evaluate_route_plan,
    optimize_shipment_plan_route,
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
from app.schemas.route_optimization import (
    OptimizationComparisonMetrics,
    RouteOptimizationResponse,
    RouteOptimizationStatus,
)
from app.schemas.route_planning import (
    GeographicPrecisionEnum,
    RoutePlanResponse,
    WaypointTypeEnum,
)
from app.schemas.shipment_plan import (
    PlannedLotAllocation,
    ShipmentPlanFromRequirementRequest,
)


@pytest.fixture
def opt_test_data(db: Session) -> Dict:
    """Sets up commodities, buyer hubs, and multiple harvest yards with verified coordinates."""
    unique_suffix = uuid4().hex[:8]

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

    onion = Commodity(
        name=f"Nashik Red Onion {unique_suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=False,
        is_active=True,
    )
    db.add(onion)
    db.commit()

    # Destination: Narayangaon Buyer Hub
    loc_hub = Location(
        name="Pune Narayangaon Buyer Terminal",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("18.5204"),
        longitude=Decimal("73.8567"),
    )
    db.add(loc_hub)
    db.commit()

    buyer_user = User(
        email=f"buyer_opt_{unique_suffix}@agrimandi.com",
        display_name="Apex Agro Processing Ltd",
        password_hash="fake_hash",
        status=UserStatus.ACTIVE,
    )
    db.add(buyer_user)
    db.commit()
    db.add(UserRole(user_id=buyer_user.id, role_id=buyer_role.id))
    db.commit()

    buyer_prof = BuyerProfile(
        user_id=buyer_user.id,
        organization_name="Apex Agro Processing Ltd",
        primary_location_id=loc_hub.id,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(buyer_prof)
    db.commit()

    # 4 distinct harvest yards in Pune/Nashik agricultural belt
    yard_configs = [
        ("Manchar Harvest Yard", Decimal("18.9950"), Decimal("73.9400"), Decimal("8.0")),
        ("Junnar Harvest Yard", Decimal("19.2000"), Decimal("73.8800"), Decimal("12.0")),
        ("Narayangaon Harvest Yard", Decimal("19.1200"), Decimal("73.9800"), Decimal("7.0")),
        ("Alephata Harvest Yard", Decimal("19.1800"), Decimal("74.1000"), Decimal("15.0")),
    ]

    farmer_records = []
    for idx, (yard_name, lat, lon, qtl) in enumerate(yard_configs, start=1):
        f_user = User(
            email=f"farmer_opt_{idx}_{unique_suffix}@agrimandi.com",
            display_name=f"Farmer {chr(64+idx)} Patil",
            password_hash="fake_hash",
            status=UserStatus.ACTIVE,
        )
        db.add(f_user)
        db.commit()
        db.add(UserRole(user_id=f_user.id, role_id=farmer_role.id))
        db.commit()

        f_loc = Location(
            name=yard_name,
            district="Pune",
            taluka="Junnar",
            state="Maharashtra",
            latitude=lat,
            longitude=lon,
        )
        db.add(f_loc)
        db.commit()


        f_prof = FarmerProfile(
            user_id=f_user.id,
            farm_name=f"Farm {chr(64+idx)}",
            primary_location_id=f_loc.id,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(f_prof)
        db.commit()

        f_lot = ProduceLot(
            seller_user_id=f_user.id,
            commodity_id=onion.id,
            pickup_location_id=f_loc.id,
            title=f"{yard_name} Onion Lot",
            available_quantity=qtl,
            unit="quintal",
            available_from=date.today(),
            available_until=date.today() + timedelta(days=5),
            status=ProduceLotStatus.PUBLISHED,
        )
        db.add(f_lot)
        db.commit()

        farmer_records.append((f_user, f_prof, f_loc, f_lot, qtl))

    return {
        "onion": onion,
        "buyer_user": buyer_user,
        "buyer_prof": buyer_prof,
        "loc_hub": loc_hub,

        "farmers": farmer_records,
    }


def test_two_pickup_stops_optimization(db: Session, opt_test_data: dict):
    """
    Test 1: Single vehicle with 2 pickup stops and 1 destination optimizes cleanly.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"][:2]  # Farmer A (8 qtl), Farmer B (12 qtl)

    total_qtl = sum(f[4] for f in farmers)
    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=total_qtl,
        unit="quintal",
        delivery_by=date.today() + timedelta(days=4),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    assert opt_resp.optimization_status == RouteOptimizationStatus.OPTIMIZED_ROUTE_FOUND
    assert opt_resp.routing_strategy == "OR_TOOLS_VRP"
    assert opt_resp.pickup_stops_count == 2
    assert opt_resp.waypoints_count == 3
    assert opt_resp.total_cargo_quantity_quintals == Decimal("20.0")
    assert opt_resp.waypoints[-1].waypoint_type == WaypointTypeEnum.DESTINATION
    assert opt_resp.waypoints[-1].location_name == loc_hub.name
    assert opt_resp.comparison_metrics is not None
    assert opt_resp.comparison_metrics.optimized_distance_km <= opt_resp.comparison_metrics.baseline_distance_km


def test_four_pickup_stops_optimization(db: Session, opt_test_data: dict):
    """
    Test 2: Multi-farmer aggregation with 4 pickup stops (42 qtl) solved by OR-Tools VRP.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]  # 4 farmers (8 + 12 + 7 + 15 = 42 qtl)

    total_qtl = sum(f[4] for f in farmers)
    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=total_qtl,
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    assert opt_resp.optimization_status == RouteOptimizationStatus.OPTIMIZED_ROUTE_FOUND
    assert opt_resp.pickup_stops_count == 4
    assert opt_resp.waypoints_count == 5  # 4 pickups + 1 destination
    assert opt_resp.total_cargo_quantity_quintals == Decimal("42.0")
    assert opt_resp.total_cargo_quantity_tonnes == Decimal("4.2")
    assert opt_resp.total_distance_km is not None
    assert opt_resp.estimated_transit_hours is not None


def test_capacity_constraint_tracking(db: Session, opt_test_data: dict):
    """
    Test 3: Vehicle load is accurately accumulated across all stops and does not exceed vehicle capacity.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    # Assign vehicle with 80 qtl capacity (MCV 8 MT)
    opt_resp = optimize_shipment_plan_route(
        db,
        plan_resp.id,
        assigned_vehicle_capacity_qtl=Decimal("80.0"),
        assigned_vehicle_class="Medium Commercial Vehicle (8 MT)",
    )

    assert opt_resp.optimization_status == RouteOptimizationStatus.OPTIMIZED_ROUTE_FOUND
    assert opt_resp.vehicle_payload_capacity_quintals == Decimal("80.0")
    assert opt_resp.vehicle_payload_utilization_pct == Decimal("52.5")

    # Verify cumulative load increases monotonically and never exceeds 80 qtl
    current_load = Decimal("0.0")
    for wp in opt_resp.waypoints:
        if wp.waypoint_type == WaypointTypeEnum.PICKUP:
            current_load += wp.stop_cargo_quantity_quintals
            assert wp.cumulative_onboard_quantity_quintals == current_load
            assert wp.cumulative_onboard_quantity_quintals <= Decimal("80.0")
        else:
            assert wp.cumulative_onboard_quantity_quintals == Decimal("42.0")


def test_impossible_capacity_failure(db: Session, opt_test_data: dict):
    """
    Test 4: Sizing where total cargo exceeds vehicle capacity produces CAPACITY_CONSTRAINT_FAILURE.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    # Attempt to assign a 15 qtl small mini truck to move 42 qtl
    opt_resp = optimize_shipment_plan_route(
        db,
        plan_resp.id,
        assigned_vehicle_capacity_qtl=Decimal("15.0"),
        assigned_vehicle_class="Mini Truck (1.5 MT)",
    )

    assert opt_resp.optimization_status == RouteOptimizationStatus.CAPACITY_CONSTRAINT_FAILURE
    assert any("FAILED CAPACITY" in c for c in opt_resp.feasibility_checks)
    assert opt_resp.total_distance_km is None


def test_destination_always_final(db: Session, opt_test_data: dict):
    """
    Test 5: Destination waypoint is strictly the terminal stop of the route.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    last_wp = opt_resp.waypoints[-1]
    assert last_wp.waypoint_type == WaypointTypeEnum.DESTINATION
    assert last_wp.location_id == loc_hub.id
    assert last_wp.cumulative_onboard_quantity_quintals == Decimal("42.0")

    # Ensure no pickup stops occur after the destination
    for wp in opt_resp.waypoints[:-1]:
        assert wp.waypoint_type == WaypointTypeEnum.PICKUP


def test_deterministic_identical_inputs(db: Session, opt_test_data: dict):
    """
    Test 6: Identical inputs produce strictly deterministic identical optimization sequences and distances.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    run_1 = optimize_shipment_plan_route(db, plan_resp.id)
    run_2 = optimize_shipment_plan_route(db, plan_resp.id)

    assert run_1.total_distance_km == run_2.total_distance_km
    assert [wp.location_id for wp in run_1.waypoints] == [wp.location_id for wp in run_2.waypoints]


def test_baseline_vs_optimized_comparison_metrics(db: Session, opt_test_data: dict):
    """
    Test 7: Compares baseline heuristic with OR-Tools optimization.
    Verifies that distance_reduction_pct and duration savings are mathematically consistent.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    metrics = opt_resp.comparison_metrics
    assert metrics is not None
    assert metrics.baseline_distance_km >= metrics.optimized_distance_km
    assert metrics.distance_reduction_km == metrics.baseline_distance_km - metrics.optimized_distance_km
    assert metrics.optimized_duration_hours <= metrics.baseline_duration_hours


def test_administrative_precision_handling(db: Session, opt_test_data: dict):
    """
    Test 8: Handles stops with administrative-only precision (no GPS) with proper disclaimer labels.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    farmers = opt_test_data["farmers"]

    # Destination without coordinates
    loc_admin_dest = Location(
        name="Baramati Cooperative Terminal",
        district="Pune",
        taluka="Baramati",
        state="Maharashtra",
        latitude=None,
        longitude=None,
    )

    db.add(loc_admin_dest)
    db.commit()

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_admin_dest.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=4),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=farmers[0][3].id, allocated_quantity=farmers[0][4], unit="quintal"),
        PlannedLotAllocation(produce_lot_id=farmers[1][3].id, allocated_quantity=farmers[1][4], unit="quintal"),
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    assert opt_resp.overall_geographic_precision == GeographicPrecisionEnum.ADMINISTRATIVE_ONLY
    assert any("administrative" in w.lower() for w in opt_resp.warnings)


def test_delivery_deadline_constraint_failure(db: Session, opt_test_data: dict):
    """
    Test 9: Pickup date occurring after delivery deadline triggers TIME_WINDOW_CONFLICT.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmer_a = opt_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("8.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=2),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=farmer_a[3].id, allocated_quantity=Decimal("8.0"), unit="quintal")],
        ),
    )

    # Mutate DB entity to make pickup date after delivery deadline
    plan_entity = db.get(ShipmentPlan, plan_resp.id)
    plan_entity.earliest_pickup_date = date.today() + timedelta(days=10)
    for s in plan_entity.pickup_stops:
        s.earliest_pickup_date = date.today() + timedelta(days=10)
    db.commit()

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    assert opt_resp.optimization_status == RouteOptimizationStatus.TIME_WINDOW_CONFLICT
    assert any("FAILED DEADLINE" in c for c in opt_resp.feasibility_checks)


def test_route_data_incomplete_failure(db: Session, opt_test_data: dict):
    """
    Test 10: Missing destination location triggers ROUTE_DATA_INCOMPLETE.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmer_a = opt_test_data["farmers"][0]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("8.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=4),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=[PlannedLotAllocation(produce_lot_id=farmer_a[3].id, allocated_quantity=Decimal("8.0"), unit="quintal")],
        ),
    )

    # Clear pickup stops on DB entity to create incomplete route data
    plan_entity = db.get(ShipmentPlan, plan_resp.id)
    plan_entity.pickup_stops.clear()
    db.commit()

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    assert opt_resp.optimization_status == RouteOptimizationStatus.ROUTE_DATA_INCOMPLETE
    assert any("FAILED DATA" in c for c in opt_resp.feasibility_checks)



def test_all_pickup_quantities_accounted_and_no_duplicates(db: Session, opt_test_data: dict):
    """
    Test 11: Guarantees that every lot is collected exactly once with zero duplicated or dropped stops.
    """
    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    opt_resp = optimize_shipment_plan_route(db, plan_resp.id)

    pickup_wps = [wp for wp in opt_resp.waypoints if wp.waypoint_type == WaypointTypeEnum.PICKUP]
    assert len(pickup_wps) == 4

    # Verify each seller appears exactly once
    seller_ids = [wp.seller_user_id for wp in pickup_wps]
    assert len(seller_ids) == len(set(seller_ids))

    # Verify total sum matches plan
    sum_collected = sum((wp.stop_cargo_quantity_quintals for wp in pickup_wps), Decimal("0.0"))
    assert sum_collected == Decimal("42.0")


def test_api_route_optimize_endpoint(db: Session, opt_test_data: dict):
    """
    Test 12: End-to-end HTTP API test for POST /api/v1/logistics/shipments/{shipment_id}/route-optimize.
    """
    client = TestClient(app)

    onion = opt_test_data["onion"]
    buyer_prof = opt_test_data["buyer_prof"]
    loc_hub = opt_test_data["loc_hub"]
    farmers = opt_test_data["farmers"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("42.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    allocations = [
        PlannedLotAllocation(produce_lot_id=f[3].id, allocated_quantity=f[4], unit="quintal")
        for f in farmers
    ]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=req.id,
            lot_allocations=allocations,
        ),
    )

    response = client.post(f"/api/v1/logistics/shipments/{plan_resp.id}/route-optimize")
    assert response.status_code == 200

    data = response.json()
    assert data["optimization_status"] == "optimized_route_found"
    assert data["routing_strategy"] == "OR_TOOLS_VRP"
    assert data["pickup_stops_count"] == 4
    assert data["waypoints_count"] == 5
    assert data["comparison_metrics"]["baseline_distance_km"] >= data["comparison_metrics"]["optimized_distance_km"]
