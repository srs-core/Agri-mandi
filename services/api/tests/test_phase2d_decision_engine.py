"""
Comprehensive test suite for Phase 2D: Intelligent Decision Engine.
Tests Transport Cost Engine, Buyer Matching Service, Net Realization Deductions,
Phase 2C Forecast Integration, Explainable Checklists, and Safe Fallbacks.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.entities import (
    BuyerDirectoryEntry,
    BuyerPreferredCategory,
    BuyerPreferredCommodity,
    BuyerProfile,
    BuyerRequirement,
    BuyerRequirementStatus,
    BuyerType,
    Commodity,
    CommodityCategory,
    Location,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    VehicleTypeEnum,
)
from app.modules.intelligence.buyer_matching import (
    evaluate_quality_compatibility,
    match_buyers_for_produce,
)
from app.modules.intelligence.transport_cost import (
    calculate_haversine_road_distance,
    calculate_transport_cost,
    select_optimal_vehicle_type,
)

client = TestClient(app)


# ==========================================
# STEP 3: TRANSPORT COST ENGINE TESTS
# ==========================================

def test_haversine_road_distance():
    """Validates road distance calculation between Pune and Mumbai coordinates."""
    # Pune (Gultekdi): 18.4975, 73.8643 | Mumbai (Vashi APMC): 19.0760, 72.9977 (~130 km road)
    dist = calculate_haversine_road_distance(18.4975, 73.8643, 19.0760, 72.9977)
    assert dist > Decimal("100.0")
    assert dist < Decimal("200.0")


def test_vehicle_payload_selection():
    """Validates vehicle type selection based on load capacity."""
    assert select_optimal_vehicle_type(Decimal("8.0")) == VehicleTypeEnum.MINI_TRUCK
    assert select_optimal_vehicle_type(Decimal("25.0")) == VehicleTypeEnum.PICKUP
    assert select_optimal_vehicle_type(Decimal("60.0")) == VehicleTypeEnum.MEDIUM_COMMERCIAL
    assert select_optimal_vehicle_type(Decimal("150.0")) == VehicleTypeEnum.HEAVY_TRUCK
    assert select_optimal_vehicle_type(Decimal("20.0"), is_perishable=True) == VehicleTypeEnum.REEFER_VAN


def test_deterministic_transport_cost_breakdown():
    """Verifies itemized transport deductions and formulas."""
    # 50 km distance with 20 quintals (PICKUP)
    # PICKUP: base=1000, per_km=25, min_dist=15, handling=400
    # Expected: 1000 + (50 * 25) + 400 = 2650.00
    breakdown = calculate_transport_cost(
        distance_km=Decimal("50.0"),
        quantity_quintals=Decimal("20.0"),
        is_perishable=False,
        origin_name="Manchar",
        destination_name="Pune APMC",
    )
    assert breakdown.total_transport_cost == Decimal("2650.00")
    assert breakdown.cost_per_quintal == Decimal("132.50")
    assert breakdown.vehicle_type == VehicleTypeEnum.PICKUP
    assert breakdown.base_fare == Decimal("1000.00")
    assert breakdown.distance_charge == Decimal("1250.00")
    assert breakdown.loading_unloading_charge == Decimal("400.00")
    assert "Transport by Pickup over 50.0 km" in breakdown.explanation


# ==========================================
# STEP 1: BUYER MATCHING SERVICE TESTS
# ==========================================

def test_quality_compatibility_evaluation():
    """Tests grade matching rules."""
    ok, reason = evaluate_quality_compatibility("Grade A", "FAQ")
    assert ok is True
    assert "satisfies" in reason

    ok, reason = evaluate_quality_compatibility("Grade C", "Grade A")
    assert ok is False
    assert "below" in reason


def test_buyer_matching_exact_and_category(db: Session):
    """Tests buyer matching against directory records and requirements."""
    # 1. Ensure test location & commodity
    loc_pune = Location(
        name="Pune Central Hub",
        district="Pune",
        state="Maharashtra",
        latitude=Decimal("18.5204"),
        longitude=Decimal("73.8567"),
    )
    db.add(loc_pune)
    db.flush()

    onion = db.query(Commodity).filter(Commodity.name == "Onion").first()
    if not onion:
        onion = Commodity(
            name="Onion",
            category=CommodityCategory.VEGETABLES,
            default_unit="kg",
            is_perishable=False,
            is_active=True,
        )
        db.add(onion)
        db.flush()

    # 2. Add Directory Buyer with Exact Preference
    buyer_exact = BuyerDirectoryEntry(
        business_name="Sahyadri Onion Traders",
        buyer_type=BuyerType.WHOLESALER,
        location_id=loc_pune.id,
        procurement_radius_km=Decimal("100.0"),
        daily_capacity_mt=Decimal("20.0"),
        is_active=True,
    )
    db.add(buyer_exact)
    db.flush()

    pref_comm = BuyerPreferredCommodity(
        buyer_entry_id=buyer_exact.id,
        commodity_id=onion.id,
        min_quality_grade="FAQ",
        typical_volume_quintals=Decimal("50.0"),
        max_price_per_unit=Decimal("2300.00"),
    )
    db.add(pref_comm)
    db.commit()

    # Match offering
    candidates = match_buyers_for_produce(
        db=db,
        commodity_id=onion.id,
        quantity_quintals=Decimal("30.0"),
        quality_grade="FAQ",
        pickup_location=loc_pune,
    )

    assert len(candidates) >= 1
    exact_cand = next((c for c in candidates if c.business_name == "Sahyadri Onion Traders"), None)
    assert exact_cand is not None
    assert exact_cand.match_type == "EXACT_COMMODITY"
    assert exact_cand.quantity_compatibility is True
    assert exact_cand.quality_compatibility is True
    assert exact_cand.geographic_compatibility is True
    assert exact_cand.is_eligible is True


# ==========================================
# STEP 4, 5, 6, 7 & 8: DECISION ENGINE API TESTS
# ==========================================

def test_decision_engine_potato_next_day_forecast():
    """Verifies decision recommendation for Potato using Phase 2C Next-Day XGBoost forecast."""
    payload = {
        "commodity_name": "Potato (Jyoti)",
        "quantity_quintals": 25.0,
        "quality_grade": "Grade A",
        "pickup_location_name": "Manchar, Pune",
    }
    response = client.post("/api/v1/intelligence/recommendation", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ["SUCCESS", "NO_ELIGIBLE_BUYER_MATCH"]
    assert data["commodity_name"] == "Potato (Jyoti)"
    assert float(data["quantity_quintals"]) == 25.0

    # Forecast reference must be active
    f_ref = data["forecast_reference"]
    assert f_ref["is_forecast_available"] is True
    assert "t+1" in f_ref["forecast_horizon"]
    assert float(f_ref["predicted_price_per_quintal"]) > 0
    assert f_ref["interval_lower_bound"] is not None
    assert f_ref["interval_upper_bound"] is not None

    if data["status"] == "SUCCESS":
        rec = data["recommended_option"]
        assert rec is not None
        assert float(rec["gross_selling_value"]) > 0
        assert float(rec["logistics_deduction"]["total_transport_cost"]) > 0
        # Formula Check: Net = Gross - Transport
        gross = Decimal(str(rec["gross_selling_value"]))
        trans = Decimal(str(rec["logistics_deduction"]["total_transport_cost"]))
        net = Decimal(str(rec["expected_net_realization"]))
        assert net == gross - trans

        # Explainability checklist must be present
        assert len(rec["reasoning_checklist"]) >= 4
        assert any("HIGHEST NET REALIZATION" in r or "BEST ECONOMIC OPTION" in r for r in rec["reasoning_checklist"])


def test_decision_engine_onion_next_day_forecast():
    """Verifies decision recommendation for Onion using Phase 2C Next-Day XGBoost forecast."""
    payload = {
        "commodity_name": "Onion (Nashik Red)",
        "quantity_quintals": 50.0,
        "quality_grade": "FAQ",
        "pickup_location_name": "Lasalgaon, Nashik",
    }
    response = client.post("/api/v1/intelligence/recommendation", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["forecast_reference"]["is_forecast_available"] is True
    assert "t+1" in data["forecast_reference"]["forecast_horizon"]


def test_decision_engine_unsupported_crop_no_fabricated_forecast():
    """Verifies that non-approved crops (e.g. Soybean) do NOT fabricate forecasts and use market prices."""
    payload = {
        "commodity_name": "Soybean",
        "quantity_quintals": 40.0,
        "quality_grade": "Standard",
        "pickup_location_name": "Latur",
    }
    response = client.post("/api/v1/intelligence/recommendation", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Forecast must be explicitly UNAVAILABLE
    f_ref = data["forecast_reference"]
    assert f_ref["is_forecast_available"] is False
    assert f_ref["forecast_horizon"] is None
    assert f_ref["predicted_price_per_quintal"] is None


def test_decision_engine_fallback_for_unknown_crop():
    """Verifies safe fallback when crop is unknown or not in catalog."""
    payload = {
        "commodity_name": "ExoticDragonFruit999",
        "quantity_quintals": 10.0,
    }
    response = client.post("/api/v1/intelligence/recommendation", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "NO_ELIGIBLE_BUYER_MATCH"
    assert data["recommended_option"] is None
    assert "Commodity not recognized" in data["fallback_reason"]
    assert len(data["explanation"]) > 0


# ==========================================
# DATA TRUST & ECONOMIC REALISM AUDIT TESTS
# ==========================================

def test_transport_realism_and_disclaimer():
    """Verifies that unverified transport costs are explicitly marked as modeled estimates with disclaimers."""
    breakdown = calculate_transport_cost(
        distance_km=Decimal("45.0"),
        quantity_quintals=Decimal("15.0"),
        is_perishable=False,
    )
    assert breakdown.cost_certainty == "MODELED_REGIONAL_ESTIMATE"
    assert breakdown.is_verified_quote is False
    assert breakdown.provider_name is None
    assert "No active verified transporter quote" in breakdown.disclaimer
    assert "Maharashtra Regional Benchmark" in breakdown.rate_source


def test_buyer_provenance_and_trust_categorization():
    """Verifies that recommendations categorize facts, estimates, and cautions explicitly."""
    payload = {
        "commodity_name": "Potato (Jyoti)",
        "quantity_quintals": 25.0,
        "quality_grade": "Grade A",
        "pickup_location_name": "Manchar, Pune",
    }
    response = client.post("/api/v1/intelligence/recommendation", json=payload)
    assert response.status_code == 200
    data = response.json()

    if data["status"] == "SUCCESS":
        rec = data["recommended_option"]
        assert rec["buyer_provenance"] in ["REGISTERED_VERIFIED_BUYER", "RESEARCHED_DIRECTORY_RECORD"]
        assert rec["net_realization_certainty"] in ["VERIFIED_QUOTE", "CONDITIONAL_ESTIMATE"]
        
        # Check structured lists
        assert isinstance(rec["verified_facts"], list)
        assert len(rec["verified_facts"]) > 0
        assert any("✓" in f for f in rec["verified_facts"])

        assert isinstance(rec["modeled_estimates"], list)
        assert len(rec["modeled_estimates"]) > 0
        assert any("ℹ" in e for e in rec["modeled_estimates"])

        assert isinstance(rec["uncertainties_and_cautions"], list)
        assert len(rec["uncertainties_and_cautions"]) > 0
        assert any("⚠" in c for c in rec["uncertainties_and_cautions"])


def test_live_registered_buyer_provenance(db: Session):
    """Verifies that live requirements from registered buyers are classified as REGISTERED_VERIFIED_BUYER."""
    # 1. Create registered user & buyer profile
    user = User(
        email=f"buyer_reg_{uuid4().hex[:6]}@example.com",
        password_hash="fakehash",
        display_name="Kisan Fresh Procurement Ltd",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    loc = Location(
        name="Vashi Mandi Hub, Navi Mumbai",
        district="Thane",
        state="Maharashtra",
        latitude=Decimal("19.0760"),
        longitude=Decimal("72.9977"),
    )
    db.add(loc)
    db.flush()

    buyer_prof = BuyerProfile(
        user_id=user.id,
        primary_location_id=loc.id,
        organization_name="Kisan Fresh Procurement Ltd",
        gstin="27AAACK1234F1Z5",
    )
    db.add(buyer_prof)
    db.flush()

    potato = db.query(Commodity).filter(Commodity.name == "Potato (Jyoti)").first()
    if not potato:
        potato = Commodity(
            name="Potato (Jyoti)",
            category=CommodityCategory.VEGETABLES,
            default_unit="kg",
            is_perishable=True,
            is_active=True,
        )
        db.add(potato)
        db.flush()

    # 2. Add Live Active Requirement
    req = BuyerRequirement(
        buyer_profile_id=buyer_prof.id,
        commodity_id=potato.id,
        delivery_location_id=loc.id,
        required_quantity=Decimal("50.0"),
        unit="quintal",
        minimum_quality_grade="Grade A",
        target_price_per_unit=Decimal("2100.00"),
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()

    # Match offering
    candidates = match_buyers_for_produce(
        db=db,
        commodity_id=potato.id,
        quantity_quintals=Decimal("40.0"),
        quality_grade="Grade A",
        pickup_location=loc,
    )

    live_cand = next((c for c in candidates if c.buyer_id == buyer_prof.id), None)
    assert live_cand is not None
    assert live_cand.buyer_provenance == "REGISTERED_VERIFIED_BUYER"
    assert live_cand.is_platform_registered is True
    assert live_cand.verification_status == "VERIFIED_PLATFORM_BUYER"

