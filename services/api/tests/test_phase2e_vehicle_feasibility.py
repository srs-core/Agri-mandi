"""
Phase 2E - Step 3: Vehicle Feasibility & Selection Engine Tests.
Tests vehicle sizing, configurable maximum capacity, cold-chain suitability (REQUIRED/NOT_REQUIRED/UNKNOWN),
multi-stop compatibility, archetype vs live availability, cost certainty tiers, deficit handling, and HTTP APIs.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
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
    LogisticsProvider,
    ProduceLot,
    ProduceLotStatus,
    Role,
    RoleName,
    ShipmentPlan,
    ShipmentPlanningStatus,
    TransportRateCard,
    User,
    UserRole,
    UserStatus,
    Vehicle,
    VehicleTypeEnum,
    VerificationStatus,
)
from app.modules.logistics.shipment_planning_service import (
    create_shipment_plan_from_requirement,
)
from app.modules.logistics.vehicle_feasibility_engine import (
    evaluate_direct_vehicle_feasibility,
    evaluate_shipment_plan_vehicle_feasibility,
)
from app.schemas.shipment_plan import (
    PlannedLotAllocation,
    ShipmentPlanFromRequirementRequest,
)
from app.schemas.vehicle_feasibility import DirectVehicleFeasibilityRequest


@pytest.fixture
def vehicle_test_data(db: Session):
    """Creates isolated commodities, locations, users, and logistics provider test fixtures."""
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

    # Commodities
    onion = Commodity(
        name=f"Nashik Red Onion {suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=False,
        is_active=True,
    )
    tomato = Commodity(
        name=f"Hybrid Tomato {suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=True,
        is_active=True,
    )
    wheat = Commodity(
        name=f"Sharbati Wheat {suffix}",
        category=CommodityCategory.GRAINS,
        default_unit="quintal",
        is_perishable=False,
        is_active=True,
    )
    unclassified_crop = Commodity(
        name=f"Specialty Herb {suffix}",
        category=CommodityCategory.SPICES,
        default_unit="kg",
        is_perishable=None,  # Unknown perishability
        is_active=True,
    )
    db.add_all([onion, tomato, wheat, unclassified_crop])
    db.commit()

    # Locations
    loc_hub = Location(
        name="Pune Narayangaon Buyer Hub",
        district="Pune",
        state="Maharashtra",
        latitude=Decimal("18.5204"),
        longitude=Decimal("73.8567"),
    )
    loc_farm = Location(
        name="Manchar Harvest Yard",
        district="Pune",
        taluka="Ambegaon",
        state="Maharashtra",
        latitude=Decimal("18.9950"),
        longitude=Decimal("73.9400"),
    )
    db.add_all([loc_hub, loc_farm])
    db.commit()

    # Buyer User & Profile
    buyer_u = User(
        email=f"buyer_veh_{suffix}@agrimandi.test",
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

    # Farmer User & Profile
    farmer_u = User(
        email=f"farmer_veh_{suffix}@agrimandi.test",
        display_name="Suresh Patil",
        password_hash="mock_hash",
        status=UserStatus.ACTIVE,
    )
    db.add(farmer_u)
    db.commit()
    db.add(UserRole(user_id=farmer_u.id, role_id=farmer_role.id))
    farmer_prof = FarmerProfile(
        user_id=farmer_u.id,
        farm_name="Patil Agro Farm",
        primary_location_id=loc_farm.id,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(farmer_prof)
    db.commit()

    return {
        "suffix": suffix,
        "onion": onion,
        "tomato": tomato,
        "wheat": wheat,
        "unclassified_crop": unclassified_crop,
        "loc_hub": loc_hub,
        "loc_farm": loc_farm,
        "buyer_prof": buyer_prof,
        "farmer_u": farmer_u,
    }


def test_sufficient_capacity_selection(db: Session, vehicle_test_data: dict):
    """
    Test 1: Sizing selection.
    For a 25 quintal (2.5 MT) Onion shipment, the engine selects the Pickup Truck (3.0 MT)
    with 83.33% payload utilization as the primary recommendation.
    """
    onion = vehicle_test_data["onion"]
    buyer_prof = vehicle_test_data["buyer_prof"]
    farmer_u = vehicle_test_data["farmer_u"]
    loc_farm = vehicle_test_data["loc_farm"]
    loc_hub = vehicle_test_data["loc_hub"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("25.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_u.id,
        commodity_id=onion.id,
        pickup_location_id=loc_farm.id,
        title="25qtl Onion Harvest",
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

    feasibility = evaluate_shipment_plan_vehicle_feasibility(db, plan.id)

    assert feasibility.evaluation_status == "VEHICLE_MATCH_FOUND"
    assert feasibility.planned_quantity_quintals == Decimal("25.0")
    assert feasibility.primary_recommendation is not None
    assert feasibility.primary_recommendation.vehicle_type == VehicleTypeEnum.PICKUP
    assert feasibility.primary_recommendation.max_payload_quintals == Decimal("30.0")
    assert feasibility.primary_recommendation.payload_utilization_pct == Decimal("83.33")
    assert feasibility.primary_recommendation.is_capacity_sufficient is True


def test_insufficient_capacity_state(db: Session, vehicle_test_data: dict):
    """
    Test 2: Insufficient Capacity.
    When shipment payload exceeds maximum single-vehicle capacity (> 250 quintals / 25 MT),
    the engine returns VEHICLE_CAPACITY_INSUFFICIENT and explains the deficit against configured capacity.
    """
    onion = vehicle_test_data["onion"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("320.0"),  # 32 Metric Tonnes
        commodity_id=onion.id,
        stops_count=1,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    assert feasibility.evaluation_status == "VEHICLE_CAPACITY_INSUFFICIENT"
    assert "exceeds the maximum capacity of any currently configured" in feasibility.status_summary
    assert "by 70.0 quintals" in feasibility.status_summary
    assert feasibility.primary_recommendation is None


def test_configurable_maximum_capacity(db: Session, vehicle_test_data: dict):
    """
    Test 3: Configurable maximum vehicle capacity.
    Verifies that when custom fleet archetypes are provided (e.g. limiting fleet to 50 qtl / 5 MT max),
    the deficit is dynamically calculated against the configured maximum rather than hard-coded limits.
    """
    onion = vehicle_test_data["onion"]

    custom_archetypes = {
        VehicleTypeEnum.MINI_TRUCK: {
            "label": "Mini Truck",
            "models": "Tata Ace",
            "max_payload_quintals": Decimal("10.0"),
            "is_refrigerated": False,
            "multi_stop_rating": "FEASIBLE_AGILE",
        },
        VehicleTypeEnum.PICKUP: {
            "label": "Custom Light Pickup Fleet",
            "models": "Bolero Pickup",
            "max_payload_quintals": Decimal("50.0"),
            "is_refrigerated": False,
            "multi_stop_rating": "FEASIBLE_AGILE",
        },
    }

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("65.0"),  # 65 quintals vs 50 qtl max
        commodity_id=onion.id,
        stops_count=1,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req, configured_archetypes=custom_archetypes)

    assert feasibility.evaluation_status == "VEHICLE_CAPACITY_INSUFFICIENT"
    assert "50.0 qtl = 5.0 MT" in feasibility.status_summary
    assert "by 15.0 quintals" in feasibility.status_summary


def test_exact_capacity_match(db: Session, vehicle_test_data: dict):
    """
    Test 4: Exact 100% capacity match.
    A 10 quintal (1.0 MT) cargo exactly matches a Mini Truck (1.0 MT) with 100% utilization.
    """
    wheat = vehicle_test_data["wheat"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("10.0"),
        commodity_id=wheat.id,
        stops_count=1,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    assert feasibility.evaluation_status == "VEHICLE_MATCH_FOUND"
    assert feasibility.primary_recommendation is not None
    assert feasibility.primary_recommendation.vehicle_type == VehicleTypeEnum.MINI_TRUCK
    assert feasibility.primary_recommendation.payload_utilization_pct == Decimal("100.00")
    assert feasibility.primary_recommendation.is_capacity_sufficient is True


def test_commodity_suitability_dry_grains(db: Session, vehicle_test_data: dict):
    """
    Test 5: Commodity suitability for dry grains.
    Dry commodities (Wheat) should select standard dry cargo trucks and avoid reefer surcharges.
    """
    wheat = vehicle_test_data["wheat"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("50.0"),
        commodity_id=wheat.id,
        stops_count=1,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    assert feasibility.evaluation_status == "VEHICLE_MATCH_FOUND"
    assert feasibility.cold_chain_requirement == "NOT_REQUIRED"
    assert feasibility.primary_recommendation is not None
    assert feasibility.primary_recommendation.vehicle_type == VehicleTypeEnum.MEDIUM_COMMERCIAL
    assert feasibility.primary_recommendation.cold_chain_status == "NOT_REQUIRED_DRY"

    # Reefer candidate should be flagged with excess surcharge
    reefer_candidate = next(
        (c for c in feasibility.ranked_options if c.vehicle_type == VehicleTypeEnum.REEFER_VAN),
        None,
    )
    if reefer_candidate:
        assert reefer_candidate.cold_chain_status == "REEFER_EXCESS_SURCHARGE"


def test_cold_chain_required_perishable(db: Session, vehicle_test_data: dict):
    """
    Test 6: Perishable commodity cold-chain selection.
    For a 20 quintal Tomato shipment (perishable), the engine requires refrigeration.
    Reefer Van passes hard feasibility; non-refrigerated vehicles fail hard feasibility.
    """
    tomato = vehicle_test_data["tomato"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("20.0"),
        commodity_id=tomato.id,
        is_perishable=True,
        stops_count=1,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    assert feasibility.evaluation_status == "VEHICLE_MATCH_FOUND"
    assert feasibility.cold_chain_requirement == "REQUIRED"
    assert feasibility.primary_recommendation is not None
    assert feasibility.primary_recommendation.vehicle_type == VehicleTypeEnum.REEFER_VAN
    assert feasibility.primary_recommendation.cold_chain_status == "SATISFIES_PERISHABLE"
    assert feasibility.primary_recommendation.is_cold_chain_compatible is True

    # Check that non-reefer pickup failed hard feasibility because cold-chain is required
    pickup_opt = next(c for c in feasibility.ranked_options if c.vehicle_type == VehicleTypeEnum.PICKUP)
    assert pickup_opt.hard_feasibility_passed is False
    assert pickup_opt.cold_chain_status == "COLD_CHAIN_REQUIRED_BUT_MISSING"


def test_cold_chain_unknown_not_falsely_assumed(db: Session, vehicle_test_data: dict):
    """
    Test 7: Unknown cold chain state.
    When commodity is unclassified/unknown, the engine sets cold_chain_requirement = UNKNOWN
    and does NOT falsely assume cold chain is required (standard dry trucks pass hard feasibility).
    """
    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("20.0"),
        commodity_id=None,
        commodity_name="Unlisted Rare Crop",
        is_perishable=None,
        stops_count=1,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    assert feasibility.cold_chain_requirement == "UNKNOWN"
    assert feasibility.primary_recommendation is not None
    assert feasibility.primary_recommendation.hard_feasibility_passed is True



def test_cold_chain_unavailable_handling(db: Session, vehicle_test_data: dict):
    """
    Test 8: Missing cold chain for perishables.
    Non-refrigerated vehicles evaluating perishable cargo are flagged with COLD_CHAIN_REQUIRED_BUT_MISSING.
    """
    tomato = vehicle_test_data["tomato"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("20.0"),
        commodity_id=tomato.id,
        is_perishable=True,
        stops_count=1,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    pickup_opt = next(c for c in feasibility.ranked_options if c.vehicle_type == VehicleTypeEnum.PICKUP)
    assert pickup_opt.cold_chain_status == "COLD_CHAIN_REQUIRED_BUT_MISSING"
    assert pickup_opt.is_cold_chain_compatible is False
    assert any("accelerated product decay" in d for d in pickup_opt.disclaimers)


def test_multiple_pickup_stops_compatibility(db: Session, vehicle_test_data: dict):
    """
    Test 9: Multi-stop compatibility.
    Light/medium vehicles are flagged as FEASIBLE_AGILE for 4 stops,
    while heavy trucks are flagged with CHALLENGING_NARROW_ACCESS.
    """
    onion = vehicle_test_data["onion"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("60.0"),
        commodity_id=onion.id,
        stops_count=4,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    med_opt = next(c for c in feasibility.ranked_options if c.vehicle_type == VehicleTypeEnum.MEDIUM_COMMERCIAL)
    assert med_opt.multi_stop_feasibility == "FEASIBLE_AGILE"

    heavy_opt = next(c for c in feasibility.ranked_options if c.vehicle_type == VehicleTypeEnum.HEAVY_TRUCK)
    assert heavy_opt.multi_stop_feasibility == "CHALLENGING_NARROW_ACCESS"
    assert any("narrow turning" in d for d in heavy_opt.disclaimers)


def test_unknown_vehicle_availability_disclaimer(db: Session, vehicle_test_data: dict):
    """
    Test 10: Availability transparency.
    Reference archetypes are explicitly marked UNKNOWN_ARCHETYPE_ONLY with disclaimer.
    """
    onion = vehicle_test_data["onion"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("25.0"),
        commodity_id=onion.id,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    assert feasibility.primary_recommendation is not None
    assert feasibility.primary_recommendation.operational_availability == "UNKNOWN_ARCHETYPE_ONLY"
    assert feasibility.primary_recommendation.candidate_type == "REFERENCE_ARCHETYPE"
    assert any("Reference vehicle archetype" in d for d in feasibility.primary_recommendation.disclaimers)


def test_modeled_cost_handling(db: Session, vehicle_test_data: dict):
    """
    Test 11: Cost certainty modeling.
    When no live provider rate card exists, the cost certainty is MODELED_REGIONAL_ESTIMATE.
    """
    onion = vehicle_test_data["onion"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("25.0"),
        commodity_id=onion.id,
        distance_km=Decimal("40.0"),
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    primary = feasibility.primary_recommendation
    assert primary is not None
    assert primary.cost_certainty == "MODELED_REGIONAL_ESTIMATE"
    assert primary.is_verified_quote is False
    assert primary.estimated_cost is not None
    assert primary.estimated_cost > Decimal("0.0")


def test_verified_cost_when_rate_card_present(db: Session, vehicle_test_data: dict):
    """
    Test 12: Verified transporter rate card extraction.
    When an active LogisticsProvider with a Vehicle and RateCard is registered,
    the candidate is marked VERIFIED_TRANSPORTER_QUOTE with is_verified_quote = True.
    """
    onion = vehicle_test_data["onion"]
    loc_farm = vehicle_test_data["loc_farm"]

    # Register live provider with vehicle and active rate card
    provider = LogisticsProvider(
        name="Sahyadri Express Freight Services",
        primary_location_id=loc_farm.id,
        has_cold_chain=False,
        is_active=True,
    )
    db.add(provider)
    db.flush()

    live_veh = Vehicle(
        provider_id=provider.id,
        registration_number="MH12AB9999",
        vehicle_type=VehicleTypeEnum.PICKUP,
        model_name="Mahindra Bolero Maxi Truck HD",
        payload_capacity_kg=Decimal("3000.00"),  # 30 qtl
        volumetric_capacity_cbm=Decimal("8.50"),
        is_refrigerated=False,
        is_available=True,
    )
    rate_card = TransportRateCard(
        provider_id=provider.id,
        vehicle_type=VehicleTypeEnum.PICKUP,
        base_fare=Decimal("1200.00"),
        per_km_rate=Decimal("26.00"),
        min_distance_km=Decimal("15.00"),
        loading_unloading_charge=Decimal("450.00"),
        valid_from=date.today(),
        is_active=True,
    )
    db.add_all([live_veh, rate_card])
    db.commit()

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("25.0"),
        commodity_id=onion.id,
        distance_km=Decimal("40.0"),
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    live_candidate = next(
        (c for c in feasibility.ranked_options if c.registration_number == "MH12AB9999"),
        None,
    )
    assert live_candidate is not None
    assert live_candidate.candidate_type == "VERIFIED_OPERATIONAL_VEHICLE"
    assert live_candidate.operational_availability == "VERIFIED_AVAILABLE"
    assert live_candidate.cost_certainty == "VERIFIED_TRANSPORTER_QUOTE"
    assert live_candidate.is_verified_quote is True
    assert live_candidate.provider_name == "Sahyadri Express Freight Services"


def test_no_fabricated_availability(db: Session, vehicle_test_data: dict):
    """
    Test 13: No fabricated availability.
    Reference archetypes must never claim VERIFIED_AVAILABLE or provide synthetic registration numbers.
    """
    wheat = vehicle_test_data["wheat"]

    req = DirectVehicleFeasibilityRequest(
        quantity_quintals=Decimal("40.0"),
        commodity_id=wheat.id,
    )

    feasibility = evaluate_direct_vehicle_feasibility(db, req)

    archetype_options = [c for c in feasibility.ranked_options if c.candidate_type == "REFERENCE_ARCHETYPE"]
    for arch in archetype_options:
        assert arch.operational_availability != "VERIFIED_AVAILABLE"
        assert arch.registration_number is None
        assert arch.is_verified_quote is False


def test_api_vehicle_options_endpoint(client: TestClient, db: Session, vehicle_test_data: dict):
    """
    Test 14: HTTP API integration tests:
    - POST /api/v1/logistics/shipments/{shipment_id}/vehicle-options
    - POST /api/v1/logistics/vehicles/evaluate-feasibility
    """
    onion = vehicle_test_data["onion"]
    buyer_prof = vehicle_test_data["buyer_prof"]
    farmer_u = vehicle_test_data["farmer_u"]
    loc_farm = vehicle_test_data["loc_farm"]
    loc_hub = vehicle_test_data["loc_hub"]

    # 1. Setup shipment plan
    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=onion.id,
        delivery_location_id=loc_hub.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    lot = ProduceLot(
        seller_user_id=farmer_u.id,
        commodity_id=onion.id,
        pickup_location_id=loc_farm.id,
        title="API Vehicle Test Lot",
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

    # 2. Call POST /shipments/{id}/vehicle-options
    res_plan = client.post(f"/api/v1/logistics/shipments/{plan.id}/vehicle-options")
    assert res_plan.status_code == 200
    plan_feasibility = res_plan.json()
    assert plan_feasibility["evaluation_status"] == "VEHICLE_MATCH_FOUND"
    assert float(plan_feasibility["planned_quantity_quintals"]) == 20.0
    assert plan_feasibility["primary_recommendation"]["vehicle_type"] == "pickup"

    # 3. Call POST /vehicles/evaluate-feasibility
    res_direct = client.post(
        "/api/v1/logistics/vehicles/evaluate-feasibility",
        json={
            "quantity_quintals": 75.0,
            "commodity_id": str(onion.id),
            "stops_count": 2,
            "distance_km": 50.0,
        },
    )
    assert res_direct.status_code == 200
    direct_feasibility = res_direct.json()
    assert direct_feasibility["evaluation_status"] == "VEHICLE_MATCH_FOUND"
    assert float(direct_feasibility["planned_quantity_quintals"]) == 75.0
    assert direct_feasibility["primary_recommendation"]["vehicle_type"] == "medium_commercial"
