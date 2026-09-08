"""
Phase 2E - Step 1: Automated Supply Aggregation Tests.
Tests multi-farmer aggregation, hard constraint filtering, clustering, traceability, and output states.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

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
    User,
    UserRole,
    UserStatus,
    VerificationStatus,
)
from app.modules.intelligence.aggregation_engine import (
    convert_price_to_per_quintal,
    convert_quantity_to_quintals,
    evaluate_single_requirement_aggregation,
    scan_aggregation_opportunities,
)
from app.schemas.aggregation import AggregationScanRequest


@pytest.fixture
def test_data(db: Session):
    """Creates isolated test users, locations, commodities, and profiles."""
    unique_suffix = str(uuid.uuid4())[:8]

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
        name=f"Nashik Red Onion {unique_suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=True,
        is_active=True,
    )
    potato = Commodity(
        name=f"Jyoti Potato {unique_suffix}",
        category=CommodityCategory.VEGETABLES,
        default_unit="kg",
        is_perishable=True,
        is_active=True,
    )
    db.add_all([onion, potato])
    db.commit()

    # Locations
    loc_buyer = Location(
        name="Pune Central Mandi Hub",
        district="Pune",
        state="Maharashtra",
        latitude=Decimal("18.5204"),
        longitude=Decimal("73.8567"),
    )
    loc_farm_a = Location(
        name="Manchar Farm Yard",
        district="Pune",
        taluka="Ambegaon",
        state="Maharashtra",
        latitude=Decimal("18.9950"),
        longitude=Decimal("73.9400"),
    )
    loc_farm_b = Location(
        name="Junnar Farm Gate",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.2000"),
        longitude=Decimal("73.8800"),
    )
    loc_farm_c = Location(
        name="Narayangaon Depot",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.1200"),
        longitude=Decimal("73.9800"),
    )
    loc_farm_d = Location(
        name="Alephata Farm Store",
        district="Pune",
        taluka="Junnar",
        state="Maharashtra",
        latitude=Decimal("19.1800"),
        longitude=Decimal("74.1000"),
    )
    loc_distant = Location(
        name="Nagpur Orange Yard",
        district="Nagpur",
        state="Maharashtra",
        latitude=Decimal("21.1458"),
        longitude=Decimal("79.0882"),  # ~700 km away
    )
    loc_textual = Location(
        name="Baramati Farm Gate (Textual)",
        district="Pune",
        taluka="Baramati",
        state="Maharashtra",
        latitude=None,
        longitude=None,
    )
    db.add_all([loc_buyer, loc_farm_a, loc_farm_b, loc_farm_c, loc_farm_d, loc_distant, loc_textual])
    db.commit()

    # Buyer User & Profile
    buyer_user = User(
        email=f"buyer_{unique_suffix}@agrimandi.test",
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
            email=f"farmer_{chr(65+i)}_{unique_suffix}@agrimandi.test",
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
        "suffix": unique_suffix,
        "onion": onion,
        "potato": potato,
        "loc_buyer": loc_buyer,
        "farmers": farmers,
        "loc_distant": loc_distant,
        "loc_textual": loc_textual,
        "buyer_user": buyer_user,
        "buyer_profile": buyer_profile,
    }


def test_unit_and_price_conversions():
    """Verifies standard unit and price conversions into quintals."""
    assert convert_quantity_to_quintals(Decimal("800.0"), "kg") == Decimal("8.0")
    assert convert_quantity_to_quintals(Decimal("4.2"), "tonnes") == Decimal("42.0")
    assert convert_quantity_to_quintals(Decimal("50.0"), "quintal") == Decimal("50.0")

    assert convert_price_to_per_quintal(Decimal("25.0"), "kg") == Decimal("2500.00")
    assert convert_price_to_per_quintal(Decimal("24000.0"), "tonne") == Decimal("2400.00")
    assert convert_price_to_per_quintal(Decimal("2200.0"), "quintal") == Decimal("2200.00")


def test_single_lot_satisfies_requirement_no_aggregation_needed(db: Session, test_data: dict):
    """
    When a single produce lot has enough quantity to satisfy the buyer requirement independently,
    status must be NO_AGGREGATION_NEEDED with 1 contributor.
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]

    # Buyer requirement: 20 quintals (2,000 kg)
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        minimum_quality_grade="Grade B",
        target_price_per_unit=Decimal("2500.00"),
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    # Single farmer lot: 30 quintals (3,000 kg) -> exceeds 20 quintals
    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Large Onion Harvest 30qtl",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        quality_grade="Grade A",
        asking_price_per_unit=Decimal("2400.00"),
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "NO_AGGREGATION_NEEDED"
    assert opp.contributor_count == 1
    assert opp.candidate_supply_quintals == Decimal("30.0")
    assert opp.economics.coverage_ratio_pct == Decimal("150.0")
    assert opp.contributing_lots[0].produce_lot_id == lot.id
    assert opp.contributing_lots[0].seller_user_id == farmer_a_user.id


def test_multiple_farmers_aggregate_possible_105_pct_coverage(db: Session, test_data: dict):
    """
    Tests prompt's exact scenario:
    Farmer A -> 800 kg (8 qtl)
    Farmer B -> 1,200 kg (12 qtl)
    Farmer C -> 700 kg (7 qtl)
    Farmer D -> 1,500 kg (15 qtl)
    Total: 4.2 tonnes (42 qtl)
    Buyer requirement: 4 tonnes (40 qtl)
    Coverage: 105% (42 / 40)
    Status: AGGREGATION_POSSIBLE
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmers = test_data["farmers"]

    # Buyer requirement: 4 tonnes (40 quintals = 4,000 kg)
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("4.0"),
        unit="tonnes",  # 4 tonnes = 40 quintals
        minimum_quality_grade="Grade B",
        target_price_per_unit=Decimal("26000.00"),  # ₹26,000 / tonne = ₹2,600 / quintal
        delivery_by=date.today() + timedelta(days=7),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    # 4 distinct farmer lots
    quantities_kg = [Decimal("800.0"), Decimal("1200.0"), Decimal("700.0"), Decimal("1500.0")]
    asking_prices_kg = [Decimal("24.0"), Decimal("25.0"), Decimal("24.5"), Decimal("25.5")]
    lots = []

    for i, (f_user, _, loc) in enumerate(farmers):
        lot = ProduceLot(
            seller_user_id=f_user.id,
            commodity_id=onion.id,
            pickup_location_id=loc.id,
            title=f"Fresh Onion Harvest Farmer {chr(65+i)}",
            available_quantity=quantities_kg[i],
            unit="kg",
            quality_grade="Grade A",
            asking_price_per_unit=asking_prices_kg[i],
            available_from=date.today(),
            status=ProduceLotStatus.PUBLISHED,
        )
        db.add(lot)
        lots.append(lot)
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "AGGREGATION_POSSIBLE"
    assert opp.contributor_count == 4
    assert opp.required_quantity_quintals == Decimal("40.0")
    assert opp.candidate_supply_quintals == Decimal("42.0")
    assert opp.economics.coverage_ratio_pct == Decimal("105.0")

    # Verify full contributor traceability
    contrib_ids = [c.produce_lot_id for c in opp.contributing_lots]
    for lot in lots:
        assert lot.id in contrib_ids

    # Traceability checks
    assert len(opp.contributing_lots) == 4
    assert opp.contributing_lots[0].seller_name is not None
    assert opp.cluster_info is not None
    assert opp.cluster_info.is_geographic_distance_exact is True
    assert opp.economics.is_economic_estimate_complete is False


def test_partial_aggregation_insufficient_supply(db: Session, test_data: dict):
    """
    When available compatible lots provide only part of the requirement (<100%),
    status must be AGGREGATION_PARTIAL.
    """
    potato = test_data["potato"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]
    farmer_b_user, _, loc_b = test_data["farmers"][1]

    # Buyer requirement: 100 quintals
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=potato.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("100.0"),
        unit="quintal",
        minimum_quality_grade="Grade B",
        delivery_by=date.today() + timedelta(days=5),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    # Supply: Lot A (15 qtl) + Lot B (20 qtl) = 35 qtl (35% coverage)
    lot1 = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=potato.id,
        pickup_location_id=loc_a.id,
        title="Potato Lot 1",
        available_quantity=Decimal("15.0"),
        unit="quintal",
        quality_grade="Grade A",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    lot2 = ProduceLot(
        seller_user_id=farmer_b_user.id,
        commodity_id=potato.id,
        pickup_location_id=loc_b.id,
        title="Potato Lot 2",
        available_quantity=Decimal("20.0"),
        unit="quintal",
        quality_grade="Grade B",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add_all([lot1, lot2])
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "AGGREGATION_PARTIAL"
    assert opp.contributor_count == 2
    assert opp.candidate_supply_quintals == Decimal("35.0")
    assert opp.economics.coverage_ratio_pct == Decimal("35.0")


def test_no_compatible_supply_state(db: Session, test_data: dict):
    """
    When zero published produce lots match the commodity, status is NO_COMPATIBLE_SUPPLY.
    """
    potato = test_data["potato"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=potato.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("50.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "NO_COMPATIBLE_SUPPLY"
    assert opp.contributor_count == 0
    assert len(opp.contributing_lots) == 0
    assert opp.candidate_supply_quintals == Decimal("0.0")


def test_commodity_mismatch_rejection(db: Session, test_data: dict):
    """
    Ensures produce lots of a different commodity are strictly excluded from aggregation.
    """
    onion = test_data["onion"]
    potato = test_data["potato"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]

    # Requirement for Onion
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("30.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    # Produce lot of Potato
    potato_lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=potato.id,
        pickup_location_id=loc_a.id,
        title="Big Potato Lot",
        available_quantity=Decimal("50.0"),
        unit="quintal",
        status=ProduceLotStatus.PUBLISHED,
        available_from=date.today(),
    )
    db.add(potato_lot)
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "NO_COMPATIBLE_SUPPLY"
    assert opp.contributor_count == 0


def test_quality_grade_mismatch_rejection(db: Session, test_data: dict):
    """
    Ensures lots with quality grades below buyer minimum are rejected by the hard constraint.
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]

    # Buyer requires Grade A
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        minimum_quality_grade="Grade A",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    # Farmer offers Grade C (inferior)
    low_grade_lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Lower Quality Onion",
        available_quantity=Decimal("25.0"),
        unit="quintal",
        quality_grade="Grade C",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(low_grade_lot)
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "NO_COMPATIBLE_SUPPLY"


def test_availability_date_mismatch_rejection(db: Session, test_data: dict):
    """
    Ensures lots available only after the buyer delivery deadline are rejected.
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]

    # Buyer needs delivery by tomorrow
    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        delivery_by=date.today() + timedelta(days=1),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    # Farmer lot will only be harvested in 15 days
    late_lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Late Harvest Onion",
        available_quantity=Decimal("25.0"),
        unit="quintal",
        available_from=date.today() + timedelta(days=15),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(late_lot)
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "NO_COMPATIBLE_SUPPLY"


def test_inactive_produce_lots_ignored(db: Session, test_data: dict):
    """
    Draft, sold, or cancelled produce lots are ignored.
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]

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
        title="Draft Produce",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.DRAFT,
    )
    sold_lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Sold Produce",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.SOLD,
    )
    db.add_all([draft_lot, sold_lot])
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "NO_COMPATIBLE_SUPPLY"


def test_geographic_distance_exceeded_rejection(db: Session, test_data: dict):
    """
    Lots located beyond regional radius (>300 km from buyer delivery location) are excluded.
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user = test_data["farmers"][0][0]
    loc_distant = test_data["loc_distant"]  # Nagpur ~700 km away

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("20.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)

    distant_lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_distant.id,
        title="Distant Onion Harvest",
        available_quantity=Decimal("50.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(distant_lot)
    db.commit()

    opp = evaluate_single_requirement_aggregation(db, req)

    assert opp.status == "NO_COMPATIBLE_SUPPLY"


def test_scan_aggregation_opportunities_batch(db: Session, test_data: dict):
    """
    Tests scanning across multiple active requirements.
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]

    # Active requirement
    req_active = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("25.0"),
        unit="quintal",
        status=BuyerRequirementStatus.ACTIVE,
    )
    # Cancelled requirement
    req_cancelled = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=onion.id,
        delivery_location_id=loc_buyer.id,
        required_quantity=Decimal("50.0"),
        unit="quintal",
        status=BuyerRequirementStatus.CANCELLED,
    )
    db.add_all([req_active, req_cancelled])

    lot = ProduceLot(
        seller_user_id=farmer_a_user.id,
        commodity_id=onion.id,
        pickup_location_id=loc_a.id,
        title="Published Lot",
        available_quantity=Decimal("30.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    batch = scan_aggregation_opportunities(db, AggregationScanRequest(commodity_id=onion.id))

    # Cancelled requirement should be omitted
    assert batch.total_requirements_evaluated == 1
    assert batch.total_opportunities_found == 1
    assert batch.opportunities[0].buyer_requirement_id == req_active.id


def test_api_aggregation_endpoints(client: TestClient, db: Session, test_data: dict):
    """
    Tests FastAPI HTTP endpoints:
    - POST /api/v1/intelligence/aggregation/opportunities
    - GET /api/v1/intelligence/aggregation/requirements/{requirement_id}
    """
    onion = test_data["onion"]
    buyer_profile = test_data["buyer_profile"]
    loc_buyer = test_data["loc_buyer"]
    farmer_a_user, _, loc_a = test_data["farmers"][0]

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
        title="API Test Lot",
        available_quantity=Decimal("25.0"),
        unit="quintal",
        available_from=date.today(),
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.commit()

    # 1. Test POST /api/v1/intelligence/aggregation/opportunities
    res_post = client.post(
        "/api/v1/intelligence/aggregation/opportunities",
        json={"commodity_id": str(onion.id), "max_cluster_radius_km": 50.0},
    )
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["total_requirements_evaluated"] >= 1
    assert len(data_post["opportunities"]) >= 1

    # 2. Test GET /api/v1/intelligence/aggregation/requirements/{id}
    res_get = client.get(f"/api/v1/intelligence/aggregation/requirements/{req.id}")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["buyer_requirement_id"] == str(req.id)
    assert data_get["status"] in ("NO_AGGREGATION_NEEDED", "AGGREGATION_POSSIBLE")
    assert len(data_get["contributing_lots"]) >= 1
    assert float(data_get["economics"]["coverage_ratio_pct"]) >= 100.0

    # 3. Test 404 for nonexistent requirement
    fake_id = uuid.uuid4()
    res_404 = client.get(f"/api/v1/intelligence/aggregation/requirements/{fake_id}")
    assert res_404.status_code == 404
