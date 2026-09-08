"""
Tests for Phase 2C - Step 4: Price Forecasting API Endpoints
Validates Next-Day (t+1) Potato and Onion forecasting, empirical prediction intervals,
Quality Gate restrictions for multi-day horizons/crops, and error handling.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_forecast_models_metadata():
    """Verifies that active and restricted model metadata can be retrieved."""
    response = client.get("/api/v1/intelligence/forecast/models")
    assert response.status_code == 200
    data = response.json()

    assert "production_enabled_crops" in data
    assert "Potato (Jyoti)" in data["production_enabled_crops"]
    assert "Onion (Nashik Red)" in data["production_enabled_crops"]
    assert data["production_enabled_horizons"] == ["t+1"]
    assert "quality_gate_verdict" in data
    assert len(data["offline_restricted_models"]) > 0


def test_post_price_forecast_potato_next_day():
    """Verifies Next-Day (t+1) price forecasting and empirical prediction intervals for Potato."""
    payload = {
        "commodity": "Potato (Jyoti)",
        "market": "Pune APMC (Gultekdi)",
        "horizon": "t+1",
        "reference_date": "2026-08-29",
        "current_modal_price": 1800.00
    }
    response = client.post("/api/v1/intelligence/forecast/price", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["commodity"] == "Potato (Jyoti)"
    assert data["market"] == "Pune APMC (Gultekdi)"
    assert data["horizon"] == "t+1"
    assert float(data["predicted_modal_price"]) > 0
    assert data["price_unit"] == "Rs/quintal"

    # Verify Empirical Prediction Interval
    interval = data["empirical_prediction_interval"]
    assert interval is not None
    assert float(interval["lower_bound"]) <= float(data["predicted_modal_price"])
    assert float(data["predicted_modal_price"]) <= float(interval["upper_bound"])
    assert interval["nominal_coverage_pct"] == 80.0
    assert interval["historical_test_coverage_pct"] >= 80.0


def test_post_price_forecast_onion_next_day():
    """Verifies Next-Day (t+1) price forecasting and empirical prediction intervals for Onion."""
    payload = {
        "commodity": "Onion (Nashik Red)",
        "market": "Lasalgaon APMC",
        "horizon": "t+1",
        "reference_date": "2026-08-29",
        "current_modal_price": 2200.00
    }
    response = client.post("/api/v1/intelligence/forecast/price", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["commodity"] == "Onion (Nashik Red)"
    assert data["market"] == "Lasalgaon APMC"
    assert data["horizon"] == "t+1"
    assert float(data["predicted_modal_price"]) > 0

    interval = data["empirical_prediction_interval"]
    assert interval is not None
    assert float(interval["lower_bound"]) <= float(data["predicted_modal_price"])
    assert float(data["predicted_modal_price"]) <= float(interval["upper_bound"])
    assert interval["nominal_coverage_pct"] == 80.0
    assert interval["historical_test_coverage_pct"] >= 80.0


def test_quality_gate_restriction_unsupported_horizon():
    """Verifies that multi-day horizon requests (t+3, t+7) are restricted by the Quality Gate."""
    payload = {
        "commodity": "Potato (Jyoti)",
        "market": "Pune APMC (Gultekdi)",
        "horizon": "t+7",
        "reference_date": "2026-08-29"
    }
    response = client.post("/api/v1/intelligence/forecast/price", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "RESTRICTED"
    assert "quality_gate_notice" in data
    assert "Next-Day (t+1)" in data["quality_gate_notice"]


def test_quality_gate_restriction_unsupported_crop():
    """Verifies that unapproved crop requests (e.g. Wheat) are restricted by the Quality Gate."""
    payload = {
        "commodity": "Wheat (Sharbati)",
        "market": "Pune APMC (Gultekdi)",
        "horizon": "t+1",
        "reference_date": "2026-08-29"
    }
    response = client.post("/api/v1/intelligence/forecast/price", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "RESTRICTED"
    assert "quality_gate_notice" in data
    assert "Only Potato (Jyoti) and Onion (Nashik Red)" in data["quality_gate_notice"]


def test_forecast_input_validation_errors():
    """Verifies that missing required parameters return validation errors."""
    response = client.post("/api/v1/intelligence/forecast/price", json={})
    assert response.status_code == 422
