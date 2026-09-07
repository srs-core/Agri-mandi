"""
Tests for Phase 2C - Step 2: Feature Engineering Engine
Validates lag correctness, historical rolling statistics, leakage safety,
cyclical time encodings, benchmark alignment, and chronological splits.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.modules.intelligence.feature_engineering import (
    compute_cyclical_features,
    engineer_series_features,
    get_agricultural_season,
    get_chronological_split,
)


def test_cyclical_and_temporal_features():
    """Verifies that cyclical day-of-year and month encodings produce correct bounded trigonometric values."""
    dt_mid_year = date(2024, 7, 2)  # ~Mid year
    cyclical = compute_cyclical_features(dt_mid_year)
    
    # Values must be strictly bounded in [-1.0, 1.0]
    for k, v in cyclical.items():
        assert -1.0 <= v <= 1.0

    # Verify agricultural seasons
    assert get_agricultural_season(7) == "kharif"  # July
    assert get_agricultural_season(12) == "rabi"   # December
    assert get_agricultural_season(4) == "zaid"    # April


def test_chronological_split_boundaries():
    """Verifies that dataset splits are assigned strictly by date thresholds without random shuffling."""
    assert get_chronological_split(date(2023, 6, 6)) == "train"
    assert get_chronological_split(date(2024, 12, 31)) == "train"
    assert get_chronological_split(date(2025, 1, 1)) == "val"
    assert get_chronological_split(date(2025, 3, 31)) == "val"
    assert get_chronological_split(date(2025, 4, 1)) == "test"
    assert get_chronological_split(date(2025, 6, 11)) == "test"


def test_lag_and_rolling_calculations():
    """Verifies that lags and rolling window statistics are computed accurately from historical observations."""
    records: List[Dict[str, Any]] = []
    base_date = date(2023, 6, 6)
    
    # Generate 50 consecutive trading records with known prices
    for i in range(50):
        d = base_date + timedelta(days=i)
        p = 1000.0 + (i * 10.0)  # Price: 1000, 1010, 1020, ...
        records.append({
            "price_date": d.isoformat(),
            "state": "Maharashtra",
            "district": "Pune",
            "market": "Pune APMC (Manjri Sub-yard)",
            "commodity": "Potato (Jyoti)",
            "variety": "Jyoti",
            "grade": "FAQ",
            "min_price": p - 100.0,
            "modal_price": p,
            "max_price": p + 100.0
        })

    feat_rows = engineer_series_features(records, warmup_window=30)
    assert len(feat_rows) == 20  # 50 - 30 warmup

    first_row = feat_rows[0]
    # Index 30 in records corresponds to price 1300.0
    assert first_row["modal_price"] == 1300.0
    assert first_row["lag_1"] == 1290.0
    assert first_row["lag_3"] == 1270.0
    assert first_row["lag_7"] == 1230.0
    assert first_row["lag_14"] == 1160.0
    assert first_row["lag_30"] == 1000.0

    # Check 7-day rolling window at index 30: [1240, 1250, 1260, 1270, 1280, 1290, 1300]
    expected_w7_mean = sum([1240, 1250, 1260, 1270, 1280, 1290, 1300]) / 7.0
    assert abs(first_row["rolling_mean_7"] - expected_w7_mean) < 1e-2
    assert first_row["rolling_min_7"] == 1240.0
    assert first_row["rolling_max_7"] == 1300.0


def test_leakage_safety_guarantee():
    """
    STRICT LEAKAGE TEST:
    Verifies that future targets (t+1, t+3, t+7) NEVER leak into features at time t.
    """
    records: List[Dict[str, Any]] = []
    base_date = date(2023, 6, 6)
    
    # Generate 45 records with an extreme future price shock at t=40
    for i in range(45):
        d = base_date + timedelta(days=i)
        # Extreme sudden price spike at t=40
        p = 5000.0 if i >= 40 else 1000.0
        records.append({
            "price_date": d.isoformat(),
            "state": "Maharashtra",
            "district": "Pune",
            "market": "Pune APMC (Manjri Sub-yard)",
            "commodity": "Potato (Jyoti)",
            "variety": "Jyoti",
            "grade": "FAQ",
            "min_price": p - 50.0,
            "modal_price": p,
            "max_price": p + 50.0
        })

    feat_rows = engineer_series_features(records, warmup_window=30)
    
    # For row at t=35 (index 5 in feat_rows), the extreme spike at t=40 must NOT be in any feature!
    row_t35 = feat_rows[5]  # Index 35 in original records
    assert row_t35["modal_price"] == 1000.0
    assert row_t35["rolling_mean_7"] == 1000.0
    assert row_t35["rolling_mean_30"] == 1000.0
    assert row_t35["rolling_max_7"] == 1000.0
    assert row_t35["lag_1"] == 1000.0

    # The forward target at t=35 for t+7 (index 42) DOES capture the spike in target_price_t7
    assert row_t35["target_price_t7"] == 5000.0
    # But target_price_t1 and target_price_t3 (t=36 and t=38) are still 1000.0
    assert row_t35["target_price_t1"] == 1000.0
    assert row_t35["target_price_t3"] == 1000.0


def test_cross_market_benchmark_spread_alignment():
    """Verifies that benchmark prices and spreads are aligned without future leakage."""
    base_date = date(2023, 6, 6)
    records: List[Dict[str, Any]] = []
    
    for i in range(40):
        d = base_date + timedelta(days=i)
        records.append({
            "price_date": d.isoformat(),
            "state": "Maharashtra",
            "district": "Pune",
            "market": "Pune APMC (Gultekdi)",
            "commodity": "Onion (Nashik Red)",
            "variety": "Nashik Red",
            "grade": "FAQ",
            "min_price": 2000.0,
            "modal_price": 2200.0,
            "max_price": 2400.0
        })

    # Benchmark lookup table (e.g. Lasalgaon at 2000.0 Rs/qtl)
    benchmark_lookup = {base_date + timedelta(days=i): 2000.0 for i in range(40)}

    feat_rows = engineer_series_features(records, benchmark_lookup=benchmark_lookup, warmup_window=30)
    assert len(feat_rows) == 10
    
    first_row = feat_rows[0]
    assert first_row["benchmark_price"] == 2000.0
    assert first_row["spread_vs_benchmark"] == 200.0  # 2200 - 2000
    assert abs(first_row["pct_spread_vs_benchmark"] - 0.10) < 1e-3  # +10% spread
