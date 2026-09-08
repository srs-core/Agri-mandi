"""
Phase 2E - Step 6: Logistics Execution Bridge Tests.
Tests readiness assessment, consolidated cost summary assembly, shipment creation from plan,
state transitions, lineage tracking, and API endpoints.
"""
from datetime import date, datetime, timedelta, timezone
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
    LogisticsProvider,
    ProduceLot,
    ProduceLotStatus,
    Role,
    RoleName,
    Shipment,
    ShipmentPlan,
    ShipmentPlanningStatus,
    ShipmentStatus,
    TransportRateCard,
    User,
    UserRole,
    UserStatus,
    Vehicle,
    VehicleTypeEnum,
    VerificationStatus,
)
from app.modules.logistics.execution_bridge_service import (
    assemble_logistics_cost_summary,
    assess_logistics_readiness,
    create_shipment_from_plan,
)
from app.modules.logistics.shipment_planning_service import (
    create_shipment_plan_from_requirement,
    mark_shipment_plan_ready,
)
from app.schemas.execution_bridge import (
    CreateShipmentFromPlanRequest,
    LogisticsCostSummary,
    LogisticsReadinessAssessment,
    LogisticsReadinessStatus,
)
from app.schemas.shipment_plan import (
    PlannedLotAllocation,
    ShipmentPlanFromRequirementRequest,
)


@pytest.fixture
def bridge_test_data(db: Session) -> Dict:
    """Sets up commodities, buyer hub, farmers, produce lots, and active buyer requirement."""
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

    # Dry Commodity
    onion = Commodity(
        name=f"Nashik Red Onion {unique_suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=False,
        is_active=True,
    )
    # Perishable Commodity
    tomato = Commodity(
        name=f"Hybrid Tomato {unique_suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=True,
        is_active=True,
    )
    db.add(onion)
    db.add(tomato)
    db.commit()

    # Destination Location (Exact GPS)
    dest_loc = Location(
        name="Pune Narayangaon Buyer Hub",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("18.5204"),
        longitude=Decimal("73.8567"),
    )
    db.add(dest_loc)
    db.commit()

    # Buyer User & Profile
    buyer_user = User(
        email=f"buyer_bridge_{unique_suffix}@agrimandi.com",
        display_name="Maharashtra Agro Terminal Ltd",
        password_hash="fake_hash",
        status=UserStatus.ACTIVE,
    )
    db.add(buyer_user)
    db.commit()
    db.add(UserRole(user_id=buyer_user.id, role_id=buyer_role.id))
    db.commit()

    buyer_prof = BuyerProfile(
        user_id=buyer_user.id,
        organization_name="Maharashtra Agro Terminal Ltd",
        primary_location_id=dest_loc.id,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(buyer_prof)
    db.commit()

    # 3 Farmer Locations with exact GPS
    yard_coords = [
        ("Manchar Harvest Yard", Decimal("18.9950"), Decimal("73.9400"), Decimal("10.0")),
        ("Junnar Harvest Yard", Decimal("19.2000"), Decimal("73.8800"), Decimal("15.0")),
        ("Alephata Harvest Yard", Decimal("19.1800"), Decimal("74.1000"), Decimal("15.0")),
    ]

    farmers = []
    for idx, (yard_name, lat, lon, qtl) in enumerate(yard_coords, start=1):
        f_user = User(
            email=f"farmer_bridge_{idx}_{unique_suffix}@agrimandi.com",
            display_name=f"Farmer {chr(64+idx)} Gaikwad",
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
            farm_name=f"Gaikwad Farm {idx}",
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

        farmers.append({"user": f_user, "loc": f_loc, "lot": f_lot, "qty": qtl})

    # Buyer Requirement for 40 quintals Onion
    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        required_quantity=Decimal("40.0"),
        unit="quintal",
        delivery_location_id=dest_loc.id,
        delivery_by=date.today() + timedelta(days=7),
        target_price_per_unit=Decimal("2500.00"),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    return {
        "onion": onion,
        "tomato": tomato,
        "buyer_user": buyer_user,
        "buyer_prof": buyer_prof,
        "dest_loc": dest_loc,
        "farmers": farmers,
        "req": req,
    }


def _create_standard_plan(db: Session, data: Dict) -> ShipmentPlan:
    """Helper to create a standard 40 qtl ShipmentPlan across 3 pickup stops."""
    allocations = [
        PlannedLotAllocation(
            produce_lot_id=f["lot"].id,
            allocated_quantity=f["qty"],
            unit="quintal",
        )
        for f in data["farmers"]
    ]
    req_payload = ShipmentPlanFromRequirementRequest(
        buyer_requirement_id=data["req"].id,
        lot_allocations=allocations,
        earliest_pickup_date=date.today(),
        planning_notes="Standard multi-farmer consolidation",
    )
    resp = create_shipment_plan_from_requirement(db, req_payload)
    return db.get(ShipmentPlan, resp.id)


# ============================================================================
# READINESS ASSESSMENT TESTS
# ============================================================================

def test_readiness_planned_status_blocks_execution(db: Session, bridge_test_data: Dict):
    """A ShipmentPlan in 'PLANNED' status is NOT_READY for operational execution."""
    plan = _create_standard_plan(db, bridge_test_data)
    assert plan.planning_status == ShipmentPlanningStatus.PLANNED

    assessment = assess_logistics_readiness(db, plan.id)
    assert assessment.overall_status == LogisticsReadinessStatus.NOT_READY
    assert any("must transition to 'ready_for_logistics'" in issue.lower() for issue in assessment.blocking_issues)
    plan_check = next(c for c in assessment.checks if c.check_name == "plan_status")
    assert plan_check.status == "failed"


def test_readiness_ready_for_logistics_with_exact_gps(db: Session, bridge_test_data: Dict):
    """A ShipmentPlan in 'READY_FOR_LOGISTICS' with exact GPS and feasible vehicle is READY."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    assessment = assess_logistics_readiness(db, plan.id)
    assert assessment.overall_status == LogisticsReadinessStatus.READY
    assert len(assessment.blocking_issues) == 0

    status_check = next(c for c in assessment.checks if c.check_name == "plan_status")
    assert status_check.status == "passed"

    gps_check = next(c for c in assessment.checks if c.check_name == "geographic_precision")
    assert gps_check.status == "passed"
    assert gps_check.certainty == "verified"

    veh_check = next(c for c in assessment.checks if c.check_name == "vehicle_feasibility")
    assert veh_check.status == "passed"

    route_check = next(c for c in assessment.checks if c.check_name == "route_feasibility")
    assert route_check.status == "passed"


def test_readiness_cancelled_plan_blocks_execution(db: Session, bridge_test_data: Dict):
    """A cancelled ShipmentPlan is NOT_READY."""
    plan = _create_standard_plan(db, bridge_test_data)
    plan.planning_status = ShipmentPlanningStatus.CANCELLED
    db.commit()

    assessment = assess_logistics_readiness(db, plan.id)
    assert assessment.overall_status == LogisticsReadinessStatus.NOT_READY
    assert any("cancelled" in issue.lower() for issue in assessment.blocking_issues)


def test_readiness_administrative_coordinates_partially_ready(db: Session, bridge_test_data: Dict):
    """When coordinates are administrative (no exact lat/lon), readiness is PARTIALLY_READY with advisory warning."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    # Clear GPS coordinates on destination to make it administrative
    dest = plan.destination_location
    dest.latitude = None
    dest.longitude = None
    db.commit()

    assessment = assess_logistics_readiness(db, plan.id)
    assert assessment.overall_status == LogisticsReadinessStatus.PARTIALLY_READY
    assert len(assessment.blocking_issues) == 0
    assert any("administrative" in w.lower() for w in assessment.advisory_warnings)

    gps_check = next(c for c in assessment.checks if c.check_name == "geographic_precision")
    assert gps_check.status == "warning"
    assert gps_check.certainty == "modeled"


def test_readiness_vehicle_capacity_insufficient(db: Session, bridge_test_data: Dict):
    """When cargo exceeds maximum single-vehicle capacity, readiness is NOT_READY."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    # Set planned quantity to 300 quintals (exceeds standard 250 qtl Taurus maximum)
    plan.total_planned_quantity_quintals = Decimal("300.0")
    for s in plan.pickup_stops:
        s.allocated_quantity_quintals = Decimal("100.0")
    db.commit()

    assessment = assess_logistics_readiness(db, plan.id)
    assert assessment.overall_status == LogisticsReadinessStatus.NOT_READY
    assert any("exceeds maximum" in issue.lower() for issue in assessment.blocking_issues)


def test_readiness_existing_shipment_flagged_as_warning(db: Session, bridge_test_data: Dict):
    """When an operational shipment is already created for a plan, readiness flags an advisory warning."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    # Create shipment from plan
    req = CreateShipmentFromPlanRequest(driver_name="Ramesh Shinde", driver_phone="9876543210")
    create_shipment_from_plan(db, plan.id, req)

    assessment = assess_logistics_readiness(db, plan.id)
    assert assessment.overall_status == LogisticsReadinessStatus.PARTIALLY_READY
    existing_check = next(c for c in assessment.checks if c.check_name == "existing_shipment")
    assert existing_check.status == "warning"
    assert any("already initialized" in w.lower() for w in assessment.advisory_warnings)


# ============================================================================
# COST SUMMARY ASSEMBLY TESTS
# ============================================================================

def test_cost_summary_assembly_modeled_estimate(db: Session, bridge_test_data: Dict):
    """Consolidated cost summary returns itemized breakdown with MODELED_REGIONAL_ESTIMATE."""
    plan = _create_standard_plan(db, bridge_test_data)
    cost_summary = assemble_logistics_cost_summary(db, plan.id)

    assert cost_summary.shipment_plan_id == plan.id
    assert cost_summary.plan_code == plan.plan_code
    assert cost_summary.cost_certainty == "MODELED_REGIONAL_ESTIMATE"
    assert cost_summary.is_verified_quote is False
    assert cost_summary.total_estimated_cost is not None
    assert cost_summary.total_estimated_cost > Decimal("0.00")
    assert cost_summary.estimated_distance_km is not None
    assert len(cost_summary.cost_components) >= 3  # Base fare, Distance, Loading

    base_comp = next(c for c in cost_summary.cost_components if c.component_name == "Base Fare")
    assert base_comp.estimated_amount > Decimal("0.00")

    dist_comp = next(c for c in cost_summary.cost_components if c.component_name == "Distance Freight")
    assert dist_comp.estimated_amount > Decimal("0.00")


def test_cost_summary_perishable_includes_reefer_surcharge(db: Session, bridge_test_data: Dict):
    """Perishable tomato shipment includes Reefer Cold Chain Surcharge in cost summary."""
    data = bridge_test_data
    tomato = data["tomato"]
    dest_loc = data["dest_loc"]

    # Setup tomato lot for farmer 1
    f1 = data["farmers"][0]
    t_lot = ProduceLot(
        seller_user_id=f1["user"].id,
        commodity_id=tomato.id,
        pickup_location_id=f1["loc"].id,
        title="Fresh Hybrid Tomato",
        available_quantity=Decimal("35.0"),
        unit="quintal",
        available_from=date.today(),
        available_until=date.today() + timedelta(days=3),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(t_lot)
    db.commit()

    t_req = BuyerRequirement(
        buyer_profile_id=data["buyer_prof"].id,
        commodity_id=tomato.id,
        required_quantity=Decimal("35.0"),
        unit="quintal",
        delivery_location_id=dest_loc.id,
        delivery_by=date.today() + timedelta(days=4),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(t_req)
    db.commit()

    allocations = [PlannedLotAllocation(produce_lot_id=t_lot.id, allocated_quantity=Decimal("35.0"), unit="quintal")]
    plan_resp = create_shipment_plan_from_requirement(
        db,
        ShipmentPlanFromRequirementRequest(
            buyer_requirement_id=t_req.id,
            lot_allocations=allocations,
            earliest_pickup_date=date.today(),
        ),
    )

    cost_summary = assemble_logistics_cost_summary(db, plan_resp.id)
    assert cost_summary.recommended_vehicle_type == "reefer_van"
    reefer_comp = next((c for c in cost_summary.cost_components if "Reefer" in c.component_name), None)
    assert reefer_comp is not None
    assert reefer_comp.estimated_amount > Decimal("0.00")


def test_cost_summary_verified_quote_when_live_rate_card_present(db: Session, bridge_test_data: Dict):
    """When a verified LogisticsProvider and TransportRateCard exist for the route, cost is VERIFIED_TRANSPORTER_QUOTE."""
    data = bridge_test_data
    dest_loc = data["dest_loc"]

    # Register a LogisticsProvider with Medium Commercial rate card
    provider = LogisticsProvider(
        name="MahaFast Agri Logistics",
        operating_scope="regional",
        has_cold_chain=False,
        primary_location_id=dest_loc.id,
        is_active=True,
    )
    db.add(provider)
    db.flush()

    vehicle = Vehicle(
        provider_id=provider.id,
        registration_number=f"MH14-BT-{uuid4().hex[:4].upper()}",
        vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
        model_name="Eicher Pro 6049",
        payload_capacity_kg=Decimal("8000.0"),  # 80 qtl
        is_refrigerated=False,
        is_available=True,
    )
    db.add(vehicle)

    rate_card = TransportRateCard(
        provider_id=provider.id,
        vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
        base_fare=Decimal("2000.00"),
        per_km_rate=Decimal("40.00"),
        min_distance_km=Decimal("20.0"),
        reefer_surcharge_per_km=Decimal("0.00"),
        loading_unloading_charge=Decimal("700.00"),
        valid_from=date.today() - timedelta(days=10),
        valid_to=date.today() + timedelta(days=30),
        is_active=True,
    )
    db.add(rate_card)
    db.commit()

    plan = _create_standard_plan(db, bridge_test_data)
    cost_summary = assemble_logistics_cost_summary(db, plan.id)

    assert cost_summary.cost_certainty == "VERIFIED_TRANSPORTER_QUOTE"
    assert cost_summary.is_verified_quote is True
    assert "Verified Transporter Rate Card" in cost_summary.rate_source


# ============================================================================
# SHIPMENT CREATION FROM PLAN TESTS
# ============================================================================

def test_create_shipment_from_plan_success(db: Session, bridge_test_data: Dict):
    """Converts a READY_FOR_LOGISTICS ShipmentPlan into an operational Shipment record."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    req = CreateShipmentFromPlanRequest(
        driver_name="Pandurang Kadam",
        driver_phone="9822012345",
        notes="Handle with care - fresh harvest consolidation",
    )
    shipment_resp = create_shipment_from_plan(db, plan.id, req)

    assert shipment_resp.id is not None
    assert shipment_resp.shipment_plan_id == plan.id
    assert shipment_resp.status == ShipmentStatus.SCHEDULED
    assert shipment_resp.driver_name == "Pandurang Kadam"
    assert shipment_resp.driver_phone == "9822012345"
    assert shipment_resp.origin_location.id == plan.pickup_stops[0].pickup_location_id
    assert shipment_resp.destination_location.id == plan.destination_location_id
    assert shipment_resp.estimated_cost is not None
    assert len(shipment_resp.events) >= 1
    assert shipment_resp.events[0].event_type == "SHIPMENT_INITIALIZED_FROM_PLAN"


def test_create_shipment_from_plan_fails_when_not_ready(db: Session, bridge_test_data: Dict):
    """Attempting to create shipment from a 'PLANNED' status plan raises 409 Conflict."""
    plan = _create_standard_plan(db, bridge_test_data)
    assert plan.planning_status == ShipmentPlanningStatus.PLANNED

    req = CreateShipmentFromPlanRequest()
    with pytest.raises(Exception) as exc_info:
        create_shipment_from_plan(db, plan.id, req)
    assert "ready_for_logistics" in str(exc_info.value)


def test_create_shipment_from_plan_duplicate_rejection(db: Session, bridge_test_data: Dict):
    """Cannot create two active operational shipments for the same shipment plan."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    req = CreateShipmentFromPlanRequest(driver_name="Driver A")
    create_shipment_from_plan(db, plan.id, req)

    # Second creation attempt should fail
    with pytest.raises(Exception) as exc_info:
        create_shipment_from_plan(db, plan.id, req)
    assert "already exists" in str(exc_info.value).lower()


def test_create_shipment_with_vehicle_and_provider_assignment(db: Session, bridge_test_data: Dict):
    """Creating shipment with explicit vehicle_id and provider_id links them correctly."""
    data = bridge_test_data
    dest_loc = data["dest_loc"]

    provider = LogisticsProvider(
        name="Kisan Express Logistics",
        operating_scope="regional",
        primary_location_id=dest_loc.id,
        is_active=True,
    )
    db.add(provider)
    db.flush()

    vehicle = Vehicle(
        provider_id=provider.id,
        registration_number=f"MH12-QK-{uuid4().hex[:4].upper()}",
        vehicle_type=VehicleTypeEnum.MEDIUM_COMMERCIAL,
        model_name="Tata 1109",
        payload_capacity_kg=Decimal("8000.0"),
        is_available=True,
    )
    db.add(vehicle)
    db.commit()

    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    req = CreateShipmentFromPlanRequest(
        vehicle_id=vehicle.id,
        provider_id=provider.id,
        driver_name="Sunil Jadhav",
        driver_phone="9890123456",
    )
    shipment = create_shipment_from_plan(db, plan.id, req)

    assert shipment.vehicle_id == vehicle.id
    assert shipment.provider_id == provider.id
    assert shipment.driver_name == "Sunil Jadhav"


# ============================================================================
# API ENDPOINT HTTP INTEGRATION TESTS
# ============================================================================

def test_api_get_readiness_endpoint(db: Session, bridge_test_data: Dict):
    """GET /api/v1/logistics/shipments/plans/{id}/readiness returns HTTP 200 with complete assessment."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    client = TestClient(app)
    resp = client.get(f"/api/v1/logistics/shipments/plans/{plan.id}/readiness")
    assert resp.status_code == 200

    data = resp.json()
    assert data["shipment_plan_id"] == str(plan.id)
    assert data["overall_status"] == "ready"
    assert "checks" in data
    assert len(data["checks"]) >= 5
    assert "disclaimer" in data


def test_api_get_cost_summary_endpoint(db: Session, bridge_test_data: Dict):
    """GET /api/v1/logistics/shipments/plans/{id}/cost-summary returns HTTP 200 with itemized cost summary."""
    plan = _create_standard_plan(db, bridge_test_data)

    client = TestClient(app)
    resp = client.get(f"/api/v1/logistics/shipments/plans/{plan.id}/cost-summary")
    assert resp.status_code == 200

    data = resp.json()
    assert data["shipment_plan_id"] == str(plan.id)
    assert data["cost_certainty"] in ["MODELED_REGIONAL_ESTIMATE", "VERIFIED_TRANSPORTER_QUOTE"]
    assert "cost_components" in data
    assert len(data["cost_components"]) > 0


def test_api_post_create_shipment_from_plan_endpoint(db: Session, bridge_test_data: Dict):
    """POST /api/v1/logistics/shipments/plans/{id}/create-shipment returns HTTP 201 with operational shipment."""
    plan = _create_standard_plan(db, bridge_test_data)
    mark_shipment_plan_ready(db, plan.id)

    client = TestClient(app)
    payload = {
        "driver_name": "Balasaheb Thorat",
        "driver_phone": "9922334455",
        "notes": "API test shipment creation",
    }
    resp = client.post(f"/api/v1/logistics/shipments/plans/{plan.id}/create-shipment", json=payload)
    assert resp.status_code == 201

    data = resp.json()
    assert data["shipment_plan_id"] == str(plan.id)
    assert data["driver_name"] == "Balasaheb Thorat"
    assert data["status"] == "scheduled"
    assert len(data["events"]) >= 1
