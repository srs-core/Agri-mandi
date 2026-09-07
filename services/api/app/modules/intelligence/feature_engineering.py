"""
Phase 2C - Step 2: Feature Engineering Engine
Leakage-safe, reproducible time-series feature engineering pipeline for agricultural price forecasting.
Constructs lags, historical rolling statistics, temporal/cyclical features, benchmark spreads, and multi-horizon targets.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Benchmark market mappings by commodity
BENCHMARK_MARKETS_BY_COMMODITY: Dict[str, List[str]] = {
    "Onion (Nashik Red)": ["Lasalgaon APMC", "Solapur APMC", "Pune APMC (Gultekdi)"],
    "Potato (Jyoti)": ["Solapur APMC", "Nashik APMC", "Pune APMC (Gultekdi)"],
    "Wheat (Sharbati)": ["Lasalgaon APMC", "Solapur APMC", "Nagpur APMC"],
    "Tomato (Hybrid)": ["Pimpalgaon Baswant APMC", "Satara APMC", "Manchar APMC"],
    "Rice": ["Nagpur APMC", "Kolhapur APMC"]
}

# Indian Agricultural Crop Seasons
# Kharif: Monsoon sowing/harvest (July - October)
# Rabi: Winter sowing/harvest (November - February)
# Zaid: Summer sowing/harvest (March - June)
def get_agricultural_season(month: int) -> str:
    if 7 <= month <= 10:
        return "kharif"
    elif month in (11, 12, 1, 2):
        return "rabi"
    else:
        return "zaid"


def compute_cyclical_features(dt: date) -> Dict[str, float]:
    """Computes sinusoidal and cosinusoidal cyclical time features."""
    doy = dt.timetuple().tm_yday
    month = dt.month
    
    sin_doy = math.sin(2.0 * math.pi * doy / 365.25)
    cos_doy = math.cos(2.0 * math.pi * doy / 365.25)
    
    sin_month = math.sin(2.0 * math.pi * month / 12.0)
    cos_month = math.cos(2.0 * math.pi * month / 12.0)
    
    return {
        "sin_day_of_year": round(sin_doy, 6),
        "cos_day_of_year": round(cos_doy, 6),
        "sin_month": round(sin_month, 6),
        "cos_month": round(cos_month, 6),
    }


def get_chronological_split(dt: date) -> str:
    """
    Strict chronological dataset split (no future leakage, no random shuffling).
    - Train: June 6, 2023 to December 31, 2024 (~19 months)
    - Validation: January 1, 2025 to March 31, 2025 (Q1 2025)
    - Test: April 1, 2025 to June 11, 2025 (Q2 2025)
    """
    if dt < date(2025, 1, 1):
        return "train"
    elif dt < date(2025, 4, 1):
        return "val"
    else:
        return "test"


def engineer_series_features(
    series_records: List[Dict[str, Any]],
    benchmark_lookup: Optional[Dict[date, float]] = None,
    warmup_window: int = 30
) -> List[Dict[str, Any]]:
    """
    Engineers leakage-safe time-series features for a single (commodity, market, variety) series.
    Assumes series_records are sorted chronologically by price_date ascending.
    """
    if len(series_records) <= warmup_window:
        return []

    # Sort strictly by date
    sorted_records = sorted(series_records, key=lambda x: x["price_date"])
    n = len(sorted_records)
    
    engineered_rows: List[Dict[str, Any]] = []

    # Extract price history array
    prices = [float(r["modal_price"]) for r in sorted_records]
    min_prices = [float(r["min_price"]) for r in sorted_records]
    max_prices = [float(r["max_price"]) for r in sorted_records]
    dates = [datetime.strptime(r["price_date"], "%Y-%m-%d").date() if isinstance(r["price_date"], str) else r["price_date"] for r in sorted_records]

    # Pre-compute running benchmark history (strictly at or before date t)
    latest_benchmark_price: Optional[float] = None
    sorted_benchmark_dates = sorted(benchmark_lookup.keys()) if benchmark_lookup else []

    for i in range(n):
        # We need at least warmup_window historical observations to compute lag_30 and rolling_30
        if i < warmup_window:
            continue

        curr_record = sorted_records[i]
        curr_date = dates[i]
        curr_price = prices[i]
        curr_min = min_prices[i]
        curr_max = max_prices[i]

        # 1. Trading Session Lags (strictly prior trading observations)
        lag_1 = prices[i - 1]
        lag_3 = prices[i - 3]
        lag_7 = prices[i - 7]
        lag_14 = prices[i - 14]
        lag_30 = prices[i - 30]

        days_since_last_trade = (curr_date - dates[i - 1]).days

        # 2. Historical Rolling Windows (over past W trading sessions, including current session t)
        window_7 = prices[i - 6 : i + 1]
        window_14 = prices[i - 13 : i + 1]
        window_30 = prices[i - 29 : i + 1]

        rolling_mean_7 = sum(window_7) / len(window_7)
        rolling_mean_14 = sum(window_14) / len(window_14)
        rolling_mean_30 = sum(window_30) / len(window_30)

        # Medians
        sorted_w7 = sorted(window_7)
        sorted_w30 = sorted(window_30)
        rolling_median_7 = sorted_w7[len(sorted_w7) // 2]
        rolling_median_30 = sorted_w30[len(sorted_w30) // 2]

        # Standard Deviations
        var_7 = sum((x - rolling_mean_7) ** 2 for x in window_7) / len(window_7)
        rolling_std_7 = math.sqrt(var_7)
        var_30 = sum((x - rolling_mean_30) ** 2 for x in window_30) / len(window_30)
        rolling_std_30 = math.sqrt(var_30)

        rolling_min_7 = min(window_7)
        rolling_max_7 = max(window_7)

        # Price Momentum & Returns
        price_momentum_7 = (curr_price - rolling_mean_7) / (rolling_mean_7 + 1e-6)
        price_return_1d = (curr_price - lag_1) / (lag_1 + 1e-6)
        price_volatility_30 = rolling_std_30 / (rolling_mean_30 + 1e-6)
        daily_spread_pct = (curr_max - curr_min) / (curr_price + 1e-6)

        # 3. Temporal & Cyclical Features
        cyclical = compute_cyclical_features(curr_date)
        season = get_agricultural_season(curr_date.month)

        temporal_dict = {
            "day_of_week": curr_date.weekday(),  # 0=Monday, 6=Sunday
            "month": curr_date.month,
            "day_of_year": curr_date.timetuple().tm_yday,
            "week_of_year": curr_date.isocalendar()[1],
            "is_monday": 1 if curr_date.weekday() == 0 else 0,
            "is_saturday": 1 if curr_date.weekday() == 5 else 0,
            "season_kharif": 1 if season == "kharif" else 0,
            "season_rabi": 1 if season == "rabi" else 0,
            "season_zaid": 1 if season == "zaid" else 0,
            **cyclical
        }

        # 4. Cross-Market Benchmark Spatial Spread (Strictly at or prior to date t)
        benchmark_price: Optional[float] = None
        spread_vs_benchmark: Optional[float] = None
        pct_spread_vs_benchmark: Optional[float] = None

        if benchmark_lookup:
            # Update latest known benchmark price up to curr_date
            if curr_date in benchmark_lookup:
                latest_benchmark_price = benchmark_lookup[curr_date]
            else:
                # Find most recent benchmark date <= curr_date
                prior_dates = [bd for bd in sorted_benchmark_dates if bd <= curr_date]
                if prior_dates:
                    latest_benchmark_price = benchmark_lookup[prior_dates[-1]]

            if latest_benchmark_price is not None:
                benchmark_price = round(latest_benchmark_price, 2)
                spread_vs_benchmark = round(curr_price - latest_benchmark_price, 2)
                pct_spread_vs_benchmark = round((curr_price - latest_benchmark_price) / (latest_benchmark_price + 1e-6), 4)

        # 5. Multi-Horizon Forward Target Variables (t+1, t+3, t+7)
        target_price_t1 = prices[i + 1] if (i + 1 < n) else None
        target_price_t3 = prices[i + 3] if (i + 3 < n) else None
        target_price_t7 = prices[i + 7] if (i + 7 < n) else None

        target_return_t1 = round((target_price_t1 - curr_price) / curr_price, 4) if target_price_t1 is not None else None

        # Build feature row
        row = {
            "series_id": f"{curr_record['commodity']}__{curr_record['market']}__{curr_record.get('variety', 'Standard')}",
            "price_date": curr_date.isoformat(),
            "split_set": get_chronological_split(curr_date),
            "state": curr_record.get("state", "Maharashtra"),
            "district": curr_record.get("district", ""),
            "market": curr_record.get("market", ""),
            "market_region": curr_record.get("market_region", ""),
            "commodity": curr_record.get("commodity", ""),
            "variety": curr_record.get("variety", ""),
            "grade": curr_record.get("grade", "FAQ"),
            
            # Current Day Observed Price Features
            "modal_price": curr_price,
            "min_price": curr_min,
            "max_price": curr_max,
            "daily_spread_pct": round(daily_spread_pct, 4),
            "days_since_last_trade": days_since_last_trade,

            # Feature Group 1: Trading Lags
            "lag_1": lag_1,
            "lag_3": lag_3,
            "lag_7": lag_7,
            "lag_14": lag_14,
            "lag_30": lag_30,

            # Feature Group 2: Historical Rolling Windows
            "rolling_mean_7": round(rolling_mean_7, 2),
            "rolling_mean_14": round(rolling_mean_14, 2),
            "rolling_mean_30": round(rolling_mean_30, 2),
            "rolling_median_7": round(rolling_median_7, 2),
            "rolling_median_30": round(rolling_median_30, 2),
            "rolling_std_7": round(rolling_std_7, 2),
            "rolling_std_30": round(rolling_std_30, 2),
            "rolling_min_7": rolling_min_7,
            "rolling_max_7": rolling_max_7,
            "price_momentum_7": round(price_momentum_7, 4),
            "price_return_1d": round(price_return_1d, 4),
            "price_volatility_30": round(price_volatility_30, 4),

            # Feature Group 3: Supply / Arrivals (Documented as unavailable in this source)
            "has_arrivals_data": 0,

            # Feature Group 4: Temporal & Cyclical Features
            **temporal_dict,

            # Feature Group 5: Cross-Market Benchmark Features
            "benchmark_price": benchmark_price if benchmark_price is not None else "",
            "spread_vs_benchmark": spread_vs_benchmark if spread_vs_benchmark is not None else "",
            "pct_spread_vs_benchmark": pct_spread_vs_benchmark if pct_spread_vs_benchmark is not None else "",

            # Target Variables (Multi-horizon forward prices)
            "target_price_t1": target_price_t1 if target_price_t1 is not None else "",
            "target_price_t3": target_price_t3 if target_price_t3 is not None else "",
            "target_price_t7": target_price_t7 if target_price_t7 is not None else "",
            "target_return_t1": target_return_t1 if target_return_t1 is not None else ""
        }

        engineered_rows.append(row)

    return engineered_rows


def generate_commodity_feature_dataset(
    commodity_name: str,
    records: List[Dict[str, Any]],
    output_csv_path: Path,
    target_crop_tier: str = "TIER_1"
) -> Dict[str, Any]:
    """
    Processes all Class A/B series for a specific commodity, builds benchmark price indices,
    computes feature matrices, and writes output CSV.
    """
    # Group records by (market, variety)
    series_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        if r["commodity"] == commodity_name:
            key = (r["market"], r.get("variety", "Standard"))
            series_groups[key].append(r)

    if not series_groups:
        return {"commodity": commodity_name, "total_series": 0, "usable_rows": 0}

    # Identify primary benchmark market for this commodity
    benchmark_candidates = BENCHMARK_MARKETS_BY_COMMODITY.get(commodity_name, [])
    benchmark_lookup: Dict[date, float] = {}

    for cand_mkt in benchmark_candidates:
        cand_records = [r for r in records if r["commodity"] == commodity_name and r["market"] == cand_mkt]
        if len(cand_records) >= 100:
            for cr in cand_records:
                dt = datetime.strptime(cr["price_date"], "%Y-%m-%d").date() if isinstance(cr["price_date"], str) else cr["price_date"]
                benchmark_lookup[dt] = float(cr["modal_price"])
            break

    # Engineer features across all qualifying series
    all_commodity_feature_rows: List[Dict[str, Any]] = []
    series_diagnostics: List[Dict[str, Any]] = []

    for (mkt, var), s_records in series_groups.items():
        # Only process series with sufficient observations (>30 rows to pass warm-up)
        if len(s_records) <= 30:
            continue

        feat_rows = engineer_series_features(s_records, benchmark_lookup=benchmark_lookup)
        if feat_rows:
            all_commodity_feature_rows.extend(feat_rows)
            
            # Diagnostic stats for this series
            s_dates = [r["price_date"] for r in feat_rows]
            s_targets = [r["target_price_t1"] for r in feat_rows if r["target_price_t1"] != ""]
            series_diagnostics.append({
                "market": mkt,
                "variety": var,
                "raw_records": len(s_records),
                "warmup_dropped_records": 30,
                "feature_rows_generated": len(feat_rows),
                "valid_t1_targets": len(s_targets),
                "earliest_feature_date": min(s_dates) if s_dates else None,
                "latest_feature_date": max(s_dates) if s_dates else None,
                "split_counts": dict(Counter(r["split_set"] for r in feat_rows))
            })

    # Write output CSV
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    if all_commodity_feature_rows:
        with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_commodity_feature_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_commodity_feature_rows)

    file_size = output_csv_path.stat().st_size if output_csv_path.exists() else 0
    file_bytes = output_csv_path.read_bytes() if output_csv_path.exists() else b""
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Split breakdown
    split_summary = Counter(r["split_set"] for r in all_commodity_feature_rows)

    return {
        "commodity": commodity_name,
        "crop_tier": target_crop_tier,
        "output_file": str(output_csv_path),
        "file_size_bytes": file_size,
        "sha256": sha256,
        "total_series_processed": len(series_diagnostics),
        "total_feature_rows": len(all_commodity_feature_rows),
        "split_distribution": dict(split_summary),
        "benchmark_market_used": benchmark_candidates[0] if benchmark_candidates else None,
        "series_diagnostics": series_diagnostics
    }


def execute_full_feature_engineering_pipeline(
    input_filtered_csv: Path,
    output_dir: Path
) -> Dict[str, Any]:
    """
    Executes end-to-end reproducible feature engineering pipeline for:
    - Tier 1: Potato (Jyoti), Onion (Nashik Red)
    - Tier 2: Wheat (Sharbati), Tomato (Hybrid)
    Generates CSV feature datasets, feature manifest, and quality report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load validated filtered market data
    records: List[Dict[str, Any]] = []
    with open(input_filtered_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            records.append(r)

    # Output artifact paths
    potato_csv = output_dir / "potato_features.csv"
    onion_csv = output_dir / "onion_features.csv"
    wheat_csv = output_dir / "wheat_features.csv"
    tomato_csv = output_dir / "tomato_features.csv"
    manifest_path = output_dir / "feature_manifest.json"
    quality_report_path = output_dir / "feature_quality_report.json"

    # Execute Tier 1
    potato_res = generate_commodity_feature_dataset("Potato (Jyoti)", records, potato_csv, target_crop_tier="TIER_1")
    onion_res = generate_commodity_feature_dataset("Onion (Nashik Red)", records, onion_csv, target_crop_tier="TIER_1")

    # Execute Tier 2
    wheat_res = generate_commodity_feature_dataset("Wheat (Sharbati)", records, wheat_csv, target_crop_tier="TIER_2")
    tomato_res = generate_commodity_feature_dataset("Tomato (Hybrid)", records, tomato_csv, target_crop_tier="TIER_2")

    commodity_results = [potato_res, onion_res, wheat_res, tomato_res]

    # Feature List Schema Definition
    feature_definitions = {
        "target_variables": {
            "target_price_t1": "Next observed trading day modal price (t+1)",
            "target_price_t3": "3 trading days ahead modal price (t+3)",
            "target_price_t7": "7 trading days ahead modal price (t+7)",
            "target_return_t1": "Percentage price return from t to t+1: (P_{t+1} - P_t) / P_t"
        },
        "lag_features": {
            "lag_1": "Modal price at previous trading session (t-1)",
            "lag_3": "Modal price at 3rd prior trading session (t-3)",
            "lag_7": "Modal price at 7th prior trading session (t-7)",
            "lag_14": "Modal price at 14th prior trading session (t-14)",
            "lag_30": "Modal price at 30th prior trading session (t-30)",
            "days_since_last_trade": "Calendar days elapsed between current session t and prior session t-1"
        },
        "rolling_window_features": {
            "rolling_mean_7": "7-trading-session moving average modal price",
            "rolling_mean_14": "14-trading-session moving average modal price",
            "rolling_mean_30": "30-trading-session moving average modal price",
            "rolling_median_7": "7-trading-session median modal price",
            "rolling_median_30": "30-trading-session median modal price",
            "rolling_std_7": "7-trading-session sample standard deviation",
            "rolling_std_30": "30-trading-session sample standard deviation",
            "rolling_min_7": "7-trading-session minimum modal price",
            "rolling_max_7": "7-trading-session maximum modal price",
            "price_momentum_7": "(P_t - rolling_mean_7) / rolling_mean_7",
            "price_return_1d": "(P_t - lag_1) / lag_1",
            "price_volatility_30": "rolling_std_30 / rolling_mean_30",
            "daily_spread_pct": "(max_price_t - min_price_t) / modal_price_t"
        },
        "temporal_cyclical_features": {
            "day_of_week": "Integer day of week (0=Monday ... 6=Sunday)",
            "month": "Calendar month (1..12)",
            "day_of_year": "Day of calendar year (1..366)",
            "week_of_year": "ISO calendar week (1..53)",
            "sin_day_of_year": "sin(2 * pi * day_of_year / 365.25)",
            "cos_day_of_year": "cos(2 * pi * day_of_year / 365.25)",
            "sin_month": "sin(2 * pi * month / 12)",
            "cos_month": "cos(2 * pi * month / 12)",
            "is_monday": "Binary flag for Monday auction (weekend backlog)",
            "is_saturday": "Binary flag for Saturday auction",
            "season_kharif": "Binary flag for Kharif monsoon harvest (July-October)",
            "season_rabi": "Binary flag for Rabi winter harvest (November-February)",
            "season_zaid": "Binary flag for Zaid summer season (March-June)"
        },
        "spatial_benchmark_features": {
            "benchmark_price": "Modal price at designated primary regional benchmark APMC at date t",
            "spread_vs_benchmark": "Price differential: P_{market, t} - P_{benchmark, t}",
            "pct_spread_vs_benchmark": "(P_{market, t} - P_{benchmark, t}) / P_{benchmark, t}"
        }
    }

    # Manifest creation
    manifest = {
        "pipeline_version": "2.0.0",
        "pipeline_execution_timestamp": datetime.now().isoformat(),
        "input_dataset": {
            "path": str(input_filtered_csv),
            "total_records_loaded": len(records),
            "provenance": "Clean Processed Agmarknet Historical Data (Step 1 Output)"
        },
        "output_feature_datasets": {
            "potato_features": {
                "path": str(potato_csv),
                "file_size_bytes": potato_res["file_size_bytes"],
                "sha256": potato_res["sha256"],
                "feature_rows": potato_res["total_feature_rows"],
                "series_count": potato_res["total_series_processed"],
                "tier": "TIER_1"
            },
            "onion_features": {
                "path": str(onion_csv),
                "file_size_bytes": onion_res["file_size_bytes"],
                "sha256": onion_res["sha256"],
                "feature_rows": onion_res["total_feature_rows"],
                "series_count": onion_res["total_series_processed"],
                "tier": "TIER_1"
            },
            "wheat_features": {
                "path": str(wheat_csv),
                "file_size_bytes": wheat_res["file_size_bytes"],
                "sha256": wheat_res["sha256"],
                "feature_rows": wheat_res["total_feature_rows"],
                "series_count": wheat_res["total_series_processed"],
                "tier": "TIER_2"
            },
            "tomato_features": {
                "path": str(tomato_csv),
                "file_size_bytes": tomato_res["file_size_bytes"],
                "sha256": tomato_res["sha256"],
                "feature_rows": tomato_res["total_feature_rows"],
                "series_count": tomato_res["total_series_processed"],
                "tier": "TIER_2"
            }
        },
        "chronological_split_rules": {
            "train_period": "2023-06-06 to 2024-12-31 (~19 months)",
            "validation_period": "2025-01-01 to 2025-03-31 (Q1 2025)",
            "test_period": "2025-04-01 to 2025-06-11 (Q2 2025)"
        },
        "leakage_safety_rules_enforced": [
            "Lags strictly use prior trading sessions (t-1, t-3, t-7, t-14, t-30)",
            "Rolling statistics strictly use historical observations up to t",
            "Benchmark spatial features strictly use benchmark prices on or before date t",
            "Target variables (t+1, t+3, t+7) are strictly forward-looking and separate from feature columns",
            "Warmup window (30 observations) dropped to ensure 100% complete feature matrices without future back-filling"
        ],
        "feature_definitions": feature_definitions
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Quality Report creation
    total_generated_rows = sum(r["total_feature_rows"] for r in commodity_results)
    quality_report = {
        "report_generated_at": datetime.now().isoformat(),
        "summary": {
            "total_input_records": len(records),
            "total_feature_rows_generated": total_generated_rows,
            "warmup_window_observations_dropped_per_series": 30,
            "commodity_breakdown": {
                "Potato (Jyoti)": potato_res["total_feature_rows"],
                "Onion (Nashik Red)": onion_res["total_feature_rows"],
                "Wheat (Sharbati)": wheat_res["total_feature_rows"],
                "Tomato (Hybrid)": tomato_res["total_feature_rows"]
            },
            "chronological_splits": {
                "Potato": potato_res["split_distribution"],
                "Onion": onion_res["split_distribution"],
                "Wheat": wheat_res["split_distribution"],
                "Tomato": tomato_res["split_distribution"]
            }
        },
        "commodity_details": commodity_results
    }

    quality_report_path.write_text(json.dumps(quality_report, indent=2), encoding="utf-8")

    return {
        "manifest": manifest,
        "quality_report": quality_report
    }


if __name__ == "__main__":
    filtered_csv = Path("data/processed/ml/filtered_market_data.csv")
    feat_dir = Path("data/processed/ml/features")
    print("Executing Feature Engineering Pipeline...")
    res = execute_full_feature_engineering_pipeline(filtered_csv, feat_dir)
    print("Feature Engineering Pipeline Completed Successfully!")
    for c_res in res["quality_report"]["commodity_details"]:
        print(f"  {c_res['commodity']} ({c_res['crop_tier']}): {c_res['total_feature_rows']} feature rows across {c_res['total_series_processed']} series | Splits: {c_res['split_distribution']}")
