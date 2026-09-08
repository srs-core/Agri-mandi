"""
Tests for Phase 2C - Step 1: Clean ML Data Preparation Pipeline
Validates deterministic normalization, inversion rejection, non-crop guardian,
time-series calculations, and pipeline reproducibility.
"""
from __future__ import annotations

import csv
import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.modules.intelligence.ml_data_prep import (
    CANONICAL_COMMODITY_MAPPINGS,
    CANONICAL_MARKET_MAPPINGS,
    NON_CROP_EXCLUSIONS,
    compute_series_time_series_metrics,
    execute_ml_data_preparation_pipeline,
    parse_date_deterministic,
    validate_and_normalize_record,
)


def test_parse_date_deterministic():
    """Verifies that date formats are parsed deterministically."""
    assert parse_date_deterministic("6/6/2023") == date(2023, 6, 6)
    assert parse_date_deterministic("12/31/2024") == date(2024, 12, 31)
    assert parse_date_deterministic("2024-08-20") == date(2024, 8, 20)
    assert parse_date_deterministic("20-08-2024") == date(2024, 8, 20)
    assert parse_date_deterministic("") is None
    assert parse_date_deterministic("invalid-date") is None


def test_validate_and_normalize_valid_record():
    """Verifies that a valid Maharashtra record normalizes properly."""
    raw_row = {
        "STATE": "Maharashtra",
        "District Name": "pune",
        "Market Name": "Pune(Manjri)",
        "Commodity": "Potato",
        "Variety": "Jyoti",
        "Grade": "FAQ",
        "Min_Price": "1800",
        "Max_Price": "2400",
        "Modal_Price": "2100",
        "Price Date": "6/6/2023"
    }
    res = validate_and_normalize_record(raw_row)
    assert res.is_valid is True
    assert res.canonical_commodity == "Potato (Jyoti)"
    assert res.canonical_market == "Pune APMC (Manjri Sub-yard)"
    assert res.canonical_district == "Pune"
    assert res.market_region == "Pune Cluster"
    assert res.min_price == 1800.0
    assert res.modal_price == 2100.0
    assert res.max_price == 2400.0
    assert res.parsed_date == date(2023, 6, 6)


def test_price_order_inversion_rejection():
    """Verifies that min > modal or modal > max is strictly rejected without modifying source values."""
    # Min > Modal
    row_inverted_1 = {
        "STATE": "Maharashtra",
        "District Name": "pune",
        "Market Name": "Pune",
        "Commodity": "Onion",
        "Variety": "Nashik Red",
        "Grade": "FAQ",
        "Min_Price": "2500",
        "Max_Price": "2800",
        "Modal_Price": "2200",  # Inversion: Min (2500) > Modal (2200)
        "Price Date": "6/6/2023"
    }
    res1 = validate_and_normalize_record(row_inverted_1)
    assert res1.is_valid is False
    assert res1.rejection_reason == "price_order_inversion"

    # Modal > Max
    row_inverted_2 = {
        "STATE": "Maharashtra",
        "District Name": "pune",
        "Market Name": "Pune",
        "Commodity": "Onion",
        "Variety": "Nashik Red",
        "Grade": "FAQ",
        "Min_Price": "2000",
        "Max_Price": "2400",
        "Modal_Price": "2600",  # Inversion: Modal (2600) > Max (2400)
        "Price Date": "6/6/2023"
    }
    res2 = validate_and_normalize_record(row_inverted_2)
    assert res2.is_valid is False
    assert res2.rejection_reason == "price_order_inversion"


def test_non_crop_and_dairy_rejection():
    """Verifies that dairy and livestock commodities are rejected."""
    for bad_comm in ["Milk", "Cow Milk", "Paneer", "Butter", "Poultry", "Eggs", "Meat"]:
        row = {
            "STATE": "Maharashtra",
            "District Name": "pune",
            "Market Name": "Pune",
            "Commodity": bad_comm,
            "Variety": "Standard",
            "Grade": "FAQ",
            "Min_Price": "50",
            "Max_Price": "70",
            "Modal_Price": "60",
            "Price Date": "6/6/2023"
        }
        res = validate_and_normalize_record(row)
        assert res.is_valid is False
        assert res.rejection_reason == "non_crop_exclusion"


def test_non_positive_and_negative_price_rejection():
    """Verifies that non-positive and negative prices are rejected."""
    row = {
        "STATE": "Maharashtra",
        "District Name": "wardha",
        "Market Name": "Sindi(Selu)",
        "Commodity": "Wheat",
        "Variety": "Other",
        "Grade": "FAQ",
        "Min_Price": "0",
        "Max_Price": "2300",
        "Modal_Price": "0",
        "Price Date": "6/23/2023"
    }
    res = validate_and_normalize_record(row)
    assert res.is_valid is False
    assert res.rejection_reason == "non_positive_price"


def test_time_series_suitability_metric_calculation():
    """Verifies time-series continuity, missing percentage, and classification logic."""
    # Synthetic dense 300-day series
    dense_entries = []
    curr = date(2023, 6, 6)
    for _ in range(350):
        if curr.weekday() != 6:  # Exclude Sundays
            dense_entries.append((curr, 1800.0, 2000.0, 2200.0, {}))
        curr += timedelta(days=1)

    metrics = compute_series_time_series_metrics(dense_entries)
    assert metrics["unique_trading_days"] == 300
    assert metrics["missing_percentage"] == 0.0
    assert metrics["longest_consecutive_gap_days"] == 2  # Sunday gap
    assert metrics["classification"] == "A (Strong)"


def test_pipeline_execution_reproducibility():
    """Verifies that the data preparation pipeline runs cleanly and generates reproducible outputs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        raw_csv = tmp_path / "sample_raw.csv"
        out_dir = tmp_path / "processed"

        # Create small test raw CSV
        sample_rows = [
            {"STATE": "Maharashtra", "District Name": "pune", "Market Name": "Pune(Manjri)", "Commodity": "Potato", "Variety": "Jyoti", "Grade": "FAQ", "Min_Price": "1800", "Max_Price": "2400", "Modal_Price": "2100", "Price Date": "6/6/2023"},
            {"STATE": "Maharashtra", "District Name": "pune", "Market Name": "Pune(Manjri)", "Commodity": "Potato", "Variety": "Jyoti", "Grade": "FAQ", "Min_Price": "2500", "Max_Price": "2400", "Modal_Price": "2100", "Price Date": "6/7/2023"},  # Inversion
            {"STATE": "Gujarat", "District Name": "surat", "Market Name": "Surat", "Commodity": "Potato", "Variety": "Jyoti", "Grade": "FAQ", "Min_Price": "1500", "Max_Price": "2000", "Modal_Price": "1800", "Price Date": "6/6/2023"},  # Out of state
            {"STATE": "Maharashtra", "District Name": "pune", "Market Name": "Pune", "Commodity": "Milk", "Variety": "Cow", "Grade": "FAQ", "Min_Price": "40", "Max_Price": "60", "Modal_Price": "50", "Price Date": "6/6/2023"},  # Dairy
        ]

        with open(raw_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(sample_rows[0].keys()))
            writer.writeheader()
            writer.writerows(sample_rows)

        # Run pipeline
        res = execute_ml_data_preparation_pipeline(raw_csv, out_dir)

        # Assert output artifacts exist
        assert (out_dir / "filtered_market_data.csv").exists()
        assert (out_dir / "rejected_records.csv").exists()
        assert (out_dir / "dataset_manifest.json").exists()
        assert (out_dir / "quality_report.json").exists()

        assert res["manifest"]["output_artifacts"]["filtered_market_data"]["record_count"] == 1
        assert res["manifest"]["output_artifacts"]["rejected_records"]["record_count"] == 3
        assert res["manifest"]["rejection_breakdown"]["price_order_inversion"] == 1
        assert res["manifest"]["rejection_breakdown"]["out_of_state_scope"] == 1
        assert res["manifest"]["rejection_breakdown"]["non_crop_exclusion"] == 1
