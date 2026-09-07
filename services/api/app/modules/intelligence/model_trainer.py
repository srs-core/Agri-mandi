"""
Phase 2C - Step 3: Model Training, Tuning, Backtesting & Evaluation Pipeline
Trains baseline persistence and XGBoost models for multi-horizon price forecasting (t+1, t+3, t+7).
Enforces zero test-set leakage, empirical prediction intervals, and deterministic reproducibility.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb

# Feature columns used for training (Strictly leakage-safe historical signals at time t)
FEATURE_COLUMNS: List[str] = [
    # Observed Price Signals at t
    "modal_price",
    "min_price",
    "max_price",
    "daily_spread_pct",
    "days_since_last_trade",
    
    # Feature Group 1: Trading Lags
    "lag_1",
    "lag_3",
    "lag_7",
    "lag_14",
    "lag_30",
    
    # Feature Group 2: Historical Rolling Windows
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_30",
    "rolling_median_7",
    "rolling_median_30",
    "rolling_std_7",
    "rolling_std_30",
    "rolling_min_7",
    "rolling_max_7",
    "price_momentum_7",
    "price_return_1d",
    "price_volatility_30",
    
    # Feature Group 4: Temporal & Cyclical Signals
    "day_of_week",
    "month",
    "day_of_year",
    "week_of_year",
    "is_monday",
    "is_saturday",
    "season_kharif",
    "season_rabi",
    "season_zaid",
    "sin_day_of_year",
    "cos_day_of_year",
    "sin_month",
    "cos_month",
    
    # Feature Group 5: Spatial Benchmark Features
    "benchmark_price",
    "spread_vs_benchmark",
    "pct_spread_vs_benchmark",
    
    # Market Categorical Code
    "market_code"
]


def calculate_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculates MAE, RMSE, MAPE (safe for non-zeros), and R2."""
    if len(y_true) == 0:
        return {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "r2": 0.0, "count": 0}

    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    errors = y_true - y_pred
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    # Safe MAPE: avoid divide by zero
    safe_true = np.where(np.abs(y_true) < 1.0, 1.0, np.abs(y_true))
    mape = float(np.mean(np.abs(errors) / safe_true) * 100.0)

    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    ss_res = float(np.sum(errors ** 2))
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-6 else 0.0

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "r2": round(r2, 4),
        "count": len(y_true)
    }


def prepare_dataset_splits(
    feature_csv_path: Path,
    target_horizon_col: str = "target_price_t1"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, int]]:
    """
    Loads feature CSV, encodes market names deterministically on TRAIN set,
    and returns (train_df, val_df, test_df, market_to_code).
    """
    df = pd.read_csv(feature_csv_path)

    # Drop rows where target is missing
    df = df.dropna(subset=[target_horizon_col]).copy()

    # Convert numeric fields
    for col in FEATURE_COLUMNS:
        if col in df.columns and col != "market_code":
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Deterministic market encoding fitted ONLY on TRAIN
    train_mask = df["split_set"] == "train"
    train_markets = df.loc[train_mask, "market"].unique()
    market_to_code = {mkt: idx + 1 for idx, mkt in enumerate(sorted(train_markets))}

    df["market_code"] = df["market"].map(market_to_code).fillna(0).astype(int)

    train_df = df[df["split_set"] == "train"].copy()
    val_df = df[df["split_set"] == "val"].copy()
    test_df = df[df["split_set"] == "test"].copy()

    return train_df, val_df, test_df, market_to_code


def train_and_evaluate_commodity_horizon(
    commodity_slug: str,
    commodity_title: str,
    feature_csv_path: Path,
    horizon_name: str,
    target_col: str,
    output_model_dir: Path,
    random_seed: int = 42
) -> Dict[str, Any]:
    """
    Trains baseline, tunes XGBoost on Train + Val, computes empirical prediction intervals,
    and performs final evaluation on Test set.
    """
    train_df, val_df, test_df, market_to_code = prepare_dataset_splits(feature_csv_path, target_horizon_col=target_col)

    if len(train_df) == 0:
        return {"error": f"No training data for {commodity_title} - {horizon_name}"}

    X_train = train_df[FEATURE_COLUMNS].values
    y_train = train_df[target_col].values

    X_val = val_df[FEATURE_COLUMNS].values if len(val_df) > 0 else np.empty((0, len(FEATURE_COLUMNS)))
    y_val = val_df[target_col].values if len(val_df) > 0 else np.empty(0)

    X_test = test_df[FEATURE_COLUMNS].values if len(test_df) > 0 else np.empty((0, len(FEATURE_COLUMNS)))
    y_test = test_df[target_col].values if len(test_df) > 0 else np.empty(0)

    # 1. Naive Persistence Baseline Evaluation (Prediction = modal_price at t)
    y_base_train = train_df["modal_price"].values
    base_train_metrics = calculate_regression_metrics(y_train, y_base_train)

    y_base_val = val_df["modal_price"].values if len(val_df) > 0 else np.empty(0)
    base_val_metrics = calculate_regression_metrics(y_val, y_base_val) if len(val_df) > 0 else {}

    y_base_test = test_df["modal_price"].values if len(test_df) > 0 else np.empty(0)
    base_test_metrics = calculate_regression_metrics(y_test, y_base_test) if len(test_df) > 0 else {}

    # 2. Simple XGBoost Baseline
    simple_xgb = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_seed,
        n_jobs=-1
    )
    simple_xgb.fit(X_train, y_train)

    simple_val_preds = simple_xgb.predict(X_val) if len(X_val) > 0 else np.empty(0)
    simple_val_metrics = calculate_regression_metrics(y_val, simple_val_preds) if len(y_val) > 0 else {}

    # 3. Controlled Hyperparameter Tuning on TRAIN + VAL
    param_grid = [
        {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.03, "subsample": 0.8, "colsample_bytree": 0.8, "reg_alpha": 0.5, "reg_lambda": 1.0},
        {"n_estimators": 150, "max_depth": 5, "learning_rate": 0.05, "subsample": 0.85, "colsample_bytree": 0.85, "reg_alpha": 0.1, "reg_lambda": 1.0},
        {"n_estimators": 200, "max_depth": 6, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.9, "reg_alpha": 1.0, "reg_lambda": 2.0},
        {"n_estimators": 150, "max_depth": 4, "learning_rate": 0.08, "subsample": 0.8, "colsample_bytree": 0.8, "reg_alpha": 0.5, "reg_lambda": 1.5},
        {"n_estimators": 250, "max_depth": 5, "learning_rate": 0.03, "subsample": 0.85, "colsample_bytree": 0.85, "reg_alpha": 0.1, "reg_lambda": 1.0},
    ]

    best_model = simple_xgb
    best_params = {"n_estimators": 100, "max_depth": 5, "learning_rate": 0.05}
    best_val_mae = simple_val_metrics.get("mae", 999999.0)

    if len(X_val) > 0:
        for params in param_grid:
            candidate_model = xgb.XGBRegressor(
                **params,
                random_state=random_seed,
                n_jobs=-1
            )
            candidate_model.fit(X_train, y_train)
            c_val_preds = candidate_model.predict(X_val)
            c_val_metrics = calculate_regression_metrics(y_val, c_val_preds)
            
            if c_val_metrics["mae"] < best_val_mae:
                best_val_mae = c_val_metrics["mae"]
                best_model = candidate_model
                best_params = params

    # 4. Final Evaluation of Best Model across Train, Val, and TEST
    y_pred_train = best_model.predict(X_train)
    final_train_metrics = calculate_regression_metrics(y_train, y_pred_train)

    y_pred_val = best_model.predict(X_val) if len(X_val) > 0 else np.empty(0)
    final_val_metrics = calculate_regression_metrics(y_val, y_pred_val) if len(y_val) > 0 else {}

    y_pred_test = best_model.predict(X_test) if len(X_test) > 0 else np.empty(0)
    final_test_metrics = calculate_regression_metrics(y_test, y_pred_test) if len(y_test) > 0 else {}

    # Calculate Percentage Improvement over Baseline on Test Set
    mae_improvement_pct = 0.0
    rmse_improvement_pct = 0.0
    if len(y_test) > 0 and base_test_metrics.get("mae", 0.0) > 0:
        mae_improvement_pct = round(((base_test_metrics["mae"] - final_test_metrics["mae"]) / base_test_metrics["mae"]) * 100.0, 2)
        rmse_improvement_pct = round(((base_test_metrics["rmse"] - final_test_metrics["rmse"]) / base_test_metrics["rmse"]) * 100.0, 2)

    # 5. Empirical Prediction Intervals (Uncertainty Quantification from Validation Residuals)
    val_residuals = (y_val - y_pred_val) if len(y_val) > 0 else np.empty(0)
    if len(val_residuals) > 0:
        residual_q10 = float(np.percentile(val_residuals, 10))
        residual_q50 = float(np.percentile(val_residuals, 50))
        residual_q90 = float(np.percentile(val_residuals, 90))
        uncertainty_info = {
            "method": "empirical_validation_residuals",
            "confidence_level": "80% empirical prediction interval",
            "residual_q10": round(residual_q10, 2),
            "residual_q50": round(residual_q50, 2),
            "residual_q90": round(residual_q90, 2),
            "formula": "predicted_price + [residual_q10, residual_q90]"
        }
    else:
        uncertainty_info = {"method": "none", "reason": "no_validation_set"}

    # 6. Feature Importance (Gain & Weight)
    importance_gain = best_model.get_booster().get_score(importance_type="gain")
    total_gain = sum(importance_gain.values()) if importance_gain else 1.0

    feature_importance_list = []
    for col_idx, col_name in enumerate(FEATURE_COLUMNS):
        f_key = f"f{col_idx}"
        gain = importance_gain.get(f_key, 0.0)
        norm_gain = (gain / total_gain) if total_gain > 0 else 0.0
        feature_importance_list.append({
            "feature": col_name,
            "raw_gain": round(gain, 2),
            "normalized_gain_pct": round(norm_gain * 100.0, 2)
        })

    feature_importance_list.sort(key=lambda x: x["raw_gain"], reverse=True)

    # 7. Save Trained Model Artifact (.json)
    output_model_dir.mkdir(parents=True, exist_ok=True)
    model_filename = f"{commodity_slug}_{horizon_name}_xgb.json"
    model_filepath = output_model_dir / model_filename
    best_model.save_model(str(model_filepath))

    meta_filename = f"{commodity_slug}_{horizon_name}_meta.json"
    meta_filepath = output_model_dir / meta_filename

    model_metadata = {
        "commodity": commodity_title,
        "commodity_slug": commodity_slug,
        "horizon": horizon_name,
        "target_column": target_col,
        "model_type": "XGBoost Regressor (Tuned)",
        "model_file": model_filename,
        "model_sha256": hashlib.sha256(model_filepath.read_bytes()).hexdigest(),
        "created_at": datetime.now().isoformat(),
        "random_seed": random_seed,
        "best_hyperparameters": best_params,
        "dataset_split_counts": {
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "test_samples": len(test_df)
        },
        "performance_metrics": {
            "baseline": {
                "train": base_train_metrics,
                "val": base_val_metrics,
                "test": base_test_metrics
            },
            "xgboost": {
                "train": final_train_metrics,
                "val": final_val_metrics,
                "test": final_test_metrics
            },
            "test_improvement_over_baseline": {
                "mae_reduction_pct": mae_improvement_pct,
                "rmse_reduction_pct": rmse_improvement_pct
            }
        },
        "uncertainty_parameters": uncertainty_info,
        "top_10_features": feature_importance_list[:10],
        "market_encoding": market_to_code
    }

    meta_filepath.write_text(json.dumps(model_metadata, indent=2), encoding="utf-8")

    return model_metadata


def execute_full_model_training_pipeline(
    features_dir: Path,
    output_model_dir: Path,
    output_reports_dir: Path
) -> Dict[str, Any]:
    """
    Executes training across Tier 1 (Potato, Onion) and Tier 2 (Wheat, Tomato)
    for horizons t+1, t+3, and t+7.
    """
    output_model_dir.mkdir(parents=True, exist_ok=True)
    output_reports_dir.mkdir(parents=True, exist_ok=True)

    commodities_to_train = [
        # Tier 1 Primary
        {"slug": "potato", "title": "Potato (Jyoti)", "file": features_dir / "potato_features.csv", "tier": "TIER_1"},
        {"slug": "onion", "title": "Onion (Nashik Red)", "file": features_dir / "onion_features.csv", "tier": "TIER_1"},
        # Tier 2 Secondary
        {"slug": "wheat", "title": "Wheat (Sharbati)", "file": features_dir / "wheat_features.csv", "tier": "TIER_2"},
        {"slug": "tomato", "title": "Tomato (Hybrid)", "file": features_dir / "tomato_features.csv", "tier": "TIER_2"}
    ]

    horizons = [
        ("t1", "target_price_t1", "Next-Day Price (t+1)"),
        ("t3", "target_price_t3", "3-Day Ahead Price (t+3)"),
        ("t7", "target_price_t7", "7-Day Ahead Price (t+7)")
    ]

    all_model_results: List[Dict[str, Any]] = []
    comparison_rows: List[Dict[str, Any]] = []
    feature_importance_rows: List[Dict[str, Any]] = []

    for comm in commodities_to_train:
        for h_slug, target_col, h_title in horizons:
            res = train_and_evaluate_commodity_horizon(
                commodity_slug=comm["slug"],
                commodity_title=comm["title"],
                feature_csv_path=comm["file"],
                horizon_name=h_slug,
                target_col=target_col,
                output_model_dir=output_model_dir
            )
            all_model_results.append(res)

            # Extract metrics for comparison CSV
            p_base = res["performance_metrics"]["baseline"]
            p_xgb = res["performance_metrics"]["xgboost"]
            p_imp = res["performance_metrics"]["test_improvement_over_baseline"]

            comp_row = {
                "commodity": comm["title"],
                "tier": comm["tier"],
                "horizon": h_title,
                "train_samples": res["dataset_split_counts"]["train_samples"],
                "val_samples": res["dataset_split_counts"]["val_samples"],
                "test_samples": res["dataset_split_counts"]["test_samples"],
                
                # Baseline
                "baseline_val_mae": p_base.get("val", {}).get("mae", ""),
                "baseline_test_mae": p_base.get("test", {}).get("mae", ""),
                "baseline_test_rmse": p_base.get("test", {}).get("rmse", ""),
                "baseline_test_mape": p_base.get("test", {}).get("mape", ""),
                
                # XGBoost
                "xgb_val_mae": p_xgb.get("val", {}).get("mae", ""),
                "xgb_test_mae": p_xgb.get("test", {}).get("mae", ""),
                "xgb_test_rmse": p_xgb.get("test", {}).get("rmse", ""),
                "xgb_test_mape": p_xgb.get("test", {}).get("mape", ""),
                "xgb_test_r2": p_xgb.get("test", {}).get("r2", ""),
                
                # Improvement
                "mae_improvement_pct": f"{p_imp['mae_reduction_pct']}%",
                "rmse_improvement_pct": f"{p_imp['rmse_reduction_pct']}%",
                
                # Model Hyperparameters
                "best_params": json.dumps(res["best_hyperparameters"])
            }
            comparison_rows.append(comp_row)

            # Feature importance entries
            for rank, feat_info in enumerate(res["top_10_features"], 1):
                feature_importance_rows.append({
                    "commodity": comm["title"],
                    "horizon": h_slug,
                    "rank": rank,
                    "feature": feat_info["feature"],
                    "raw_gain": feat_info["raw_gain"],
                    "gain_percentage": f"{feat_info['normalized_gain_pct']}%"
                })

    # Save Comparison CSV
    comp_csv_path = output_reports_dir / "model_comparison.csv"
    if comparison_rows:
        with open(comp_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
            writer.writeheader()
            writer.writerows(comparison_rows)

    # Save Feature Importance CSV
    feat_csv_path = output_reports_dir / "feature_importance.csv"
    if feature_importance_rows:
        with open(feat_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(feature_importance_rows[0].keys()))
            writer.writeheader()
            writer.writerows(feature_importance_rows)

    # Save Model Manifest JSON
    manifest_path = output_reports_dir / "model_manifest.json"
    manifest_data = {
        "pipeline_version": "3.0.0",
        "training_timestamp": datetime.now().isoformat(),
        "total_models_trained": len(all_model_results),
        "primary_crops": ["Potato (Jyoti)", "Onion (Nashik Red)"],
        "secondary_crops": ["Wheat (Sharbati)", "Tomato (Hybrid)"],
        "horizons_supported": ["t+1 (Next Day)", "t+3 (3-Day)", "t+7 (7-Day)"],
        "models_summary": all_model_results
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    return manifest_data


if __name__ == "__main__":
    feat_dir = Path("data/processed/ml/features")
    m_dir = Path("data/processed/ml/models")
    r_dir = Path("data/processed/ml/model_reports")
    
    print("Executing Baseline + XGBoost Model Training Pipeline...")
    res = execute_full_model_training_pipeline(feat_dir, m_dir, r_dir)
    print(f"Training completed! Total models trained: {res['total_models_trained']}")
