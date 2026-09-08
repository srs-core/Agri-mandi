"""
Tests for Phase 2C - Step 3: Model Training, Evaluation & Backtesting
Validates metric calculations, chronological split integrity, model artifact loading,
and empirical prediction interval bounds.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import xgboost as xgb

from app.modules.intelligence.model_trainer import (
    FEATURE_COLUMNS,
    calculate_regression_metrics,
    prepare_dataset_splits,
)


def test_calculate_regression_metrics():
    """Verifies that MAE, RMSE, MAPE, and R2 are calculated accurately."""
    y_true = np.array([2000.0, 2200.0, 2400.0, 2600.0])
    y_pred = np.array([2100.0, 2150.0, 2450.0, 2500.0])

    metrics = calculate_regression_metrics(y_true, y_pred)
    assert metrics["mae"] == 75.0
    assert metrics["count"] == 4
    assert metrics["rmse"] > 0.0
    assert metrics["mape"] > 0.0
    assert metrics["r2"] > 0.80


def test_chronological_split_integrity():
    """Verifies that train, val, and test splits have ZERO date overlap."""
    feat_csv = Path("data/processed/ml/features/potato_features.csv")
    if not feat_csv.exists():
        pytest.skip("Potato features CSV not found")

    train_df, val_df, test_df, mkt_map = prepare_dataset_splits(feat_csv, "target_price_t1")

    train_dates = set(train_df["price_date"].unique())
    val_dates = set(val_df["price_date"].unique())
    test_dates = set(test_df["price_date"].unique())

    # Assert mutual exclusivity
    assert len(train_dates.intersection(val_dates)) == 0
    assert len(train_dates.intersection(test_dates)) == 0
    assert len(val_dates.intersection(test_dates)) == 0

    # Assert chronological ordering
    assert max(train_dates) < min(val_dates)
    assert max(val_dates) < min(test_dates)


def test_saved_model_artifact_loading():
    """Verifies that trained XGBoost JSON model files can be loaded and used for inference."""
    model_dir = Path("data/processed/ml/models")
    potato_t1_model = model_dir / "potato_t1_xgb.json"
    potato_t1_meta = model_dir / "potato_t1_meta.json"

    if not potato_t1_model.exists() or not potato_t1_meta.exists():
        pytest.skip("Potato t1 model artifact not found")

    # Load model booster
    booster = xgb.Booster()
    booster.load_model(str(potato_t1_model))

    # Load metadata
    with open(potato_t1_meta, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["commodity"] == "Potato (Jyoti)"
    assert meta["horizon"] == "t1"
    assert "uncertainty_parameters" in meta

    # Test dummy inference vector of length 40
    dummy_input = np.ones((1, len(FEATURE_COLUMNS)), dtype=np.float32) * 2000.0
    dmat = xgb.DMatrix(dummy_input)
    pred = booster.predict(dmat)
    assert len(pred) == 1
    assert float(pred[0]) > 0.0


def test_empirical_prediction_intervals():
    """Verifies that empirical prediction intervals are properly bounded."""
    meta_file = Path("data/processed/ml/models/potato_t1_meta.json")
    if not meta_file.exists():
        pytest.skip("Model metadata not found")

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    u_params = meta.get("uncertainty_parameters", {})
    if u_params.get("method") == "empirical_validation_residuals":
        q10 = u_params["residual_q10"]
        q90 = u_params["residual_q90"]
        # q10 is typically negative (over-prediction) and q90 is positive (under-prediction)
        assert q10 <= q90
