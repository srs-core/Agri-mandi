"""
Phase 2C - Step 1: Clean ML Data Preparation & Feature-Pipeline Foundation
Reproducible filtering, validation, normalization, and auditing pipeline for historical market data.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Canonical commodity mappings (Deterministic)
CANONICAL_COMMODITY_MAPPINGS: Dict[str, str] = {
    "potato": "Potato (Jyoti)",
    "onion": "Onion (Nashik Red)",
    "tomato": "Tomato (Hybrid)",
    "wheat": "Wheat (Sharbati)",
    "rice": "Rice",  # Preserved as generic Rice (not auto-mapped to Sona Masoori)
}

# Strict non-crop exclusions (Zero-Dairy & Livestock policy)
NON_CROP_EXCLUSIONS: Set[str] = {
    "milk", "dairy", "paneer", "ghee", "butter", "curd", "cream",
    "poultry", "chicken", "egg", "eggs", "meat", "mutton", "fish", "prawn"
}

# Priority Maharashtra APMC Market mappings (Deterministic)
CANONICAL_MARKET_MAPPINGS: Dict[str, Dict[str, str]] = {
    "pune(manjri)": {"canonical": "Pune APMC (Manjri Sub-yard)", "district": "Pune", "region": "Pune Cluster"},
    "pune(moshi)": {"canonical": "Pune APMC (Moshi Sub-yard)", "district": "Pune", "region": "Pune Cluster"},
    "pune": {"canonical": "Pune APMC (Gultekdi)", "district": "Pune", "region": "Pune Cluster"},
    "pune(gultekdi)": {"canonical": "Pune APMC (Gultekdi)", "district": "Pune", "region": "Pune Cluster"},
    "pune(khadiki)": {"canonical": "Pune APMC (Khadki Sub-yard)", "district": "Pune", "region": "Pune Cluster"},
    "pune(pimpri)": {"canonical": "Pune APMC (Pimpri Sub-yard)", "district": "Pune", "region": "Pune Cluster"},
    "khed(chakan)": {"canonical": "Khed APMC (Chakan Yard)", "district": "Pune", "region": "Pune Cluster"},
    "chakan": {"canonical": "Khed APMC (Chakan Yard)", "district": "Pune", "region": "Pune Cluster"},
    "manchar": {"canonical": "Manchar APMC", "district": "Pune", "region": "Pune Cluster"},
    "junnar(narayangaon)": {"canonical": "Junnar APMC (Narayangaon Sub-yard)", "district": "Pune", "region": "Pune Cluster"},
    "junnar(alephata)": {"canonical": "Junnar APMC (Alephata Sub-yard)", "district": "Pune", "region": "Pune Cluster"},
    "junnar(otur)": {"canonical": "Junnar APMC (Otur Sub-yard)", "district": "Pune", "region": "Pune Cluster"},
    "junnar": {"canonical": "Junnar APMC", "district": "Pune", "region": "Pune Cluster"},
    "baramati": {"canonical": "Baramati APMC", "district": "Pune", "region": "Pune Cluster"},
    "shirur": {"canonical": "Shirur APMC", "district": "Pune", "region": "Pune Cluster"},
    "dound": {"canonical": "Daund APMC", "district": "Pune", "region": "Pune Cluster"},
    "indapur": {"canonical": "Indapur APMC", "district": "Pune", "region": "Pune Cluster"},
    "solapur": {"canonical": "Solapur APMC", "district": "Solapur", "region": "Benchmark"},
    "lasalgaon(niphad)": {"canonical": "Lasalgaon APMC", "district": "Nashik", "region": "Benchmark"},
    "lasalgaon": {"canonical": "Lasalgaon APMC", "district": "Nashik", "region": "Benchmark"},
    "nasik": {"canonical": "Nashik APMC", "district": "Nashik", "region": "Benchmark"},
    "nashik": {"canonical": "Nashik APMC", "district": "Nashik", "region": "Benchmark"},
    "pimpalgaon": {"canonical": "Pimpalgaon Baswant APMC", "district": "Nashik", "region": "Benchmark"},
    "pimpalgaon baswant": {"canonical": "Pimpalgaon Baswant APMC", "district": "Nashik", "region": "Benchmark"},
    "rahata": {"canonical": "Rahata APMC", "district": "Ahmednagar", "region": "Benchmark"},
    "shrirampur": {"canonical": "Shrirampur APMC", "district": "Ahmednagar", "region": "Benchmark"},
    "vashi new mumbai": {"canonical": "Vashi APMC (Mumbai)", "district": "Mumbai", "region": "Benchmark"},
    "amrawati(frui & veg. market)": {"canonical": "Amravati APMC", "district": "Amravati", "region": "Benchmark"},
    "amrawati": {"canonical": "Amravati APMC", "district": "Amravati", "region": "Benchmark"},
    "akola": {"canonical": "Akola APMC", "district": "Akola", "region": "Benchmark"},
    "jalgaon": {"canonical": "Jalgaon APMC", "district": "Jalgaon", "region": "Benchmark"},
    "sangli": {"canonical": "Sangli APMC", "district": "Sangli", "region": "Benchmark"},
    "kolhapur": {"canonical": "Kolhapur APMC", "district": "Kolhapur", "region": "Benchmark"},
    "nagpur": {"canonical": "Nagpur APMC", "district": "Nagpur", "region": "Benchmark"},
}


@dataclass
class RecordValidationResult:
    is_valid: bool
    rejection_reason: Optional[str] = None
    parsed_date: Optional[date] = None
    min_price: Optional[float] = None
    modal_price: Optional[float] = None
    max_price: Optional[float] = None
    canonical_commodity: Optional[str] = None
    canonical_market: Optional[str] = None
    canonical_district: Optional[str] = None
    market_region: Optional[str] = None


def parse_date_deterministic(d_str: str) -> Optional[date]:
    """Parses date string deterministically with explicit format order."""
    d_str = d_str.strip()
    if not d_str:
        return None
    for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(d_str, fmt).date()
        except ValueError:
            pass
    return None


def validate_and_normalize_record(row: Dict[str, str], target_scope_state: str = "maharashtra") -> RecordValidationResult:
    """
    Validates and normalizes a single raw record from Kaggle Agmarknet dataset.
    Enforces non-crop rejection, price inversion checks, date boundaries, and deterministic mappings.
    """
    # 1. State filter
    state = row.get("STATE", "").strip()
    if state.lower() != target_scope_state.lower():
        return RecordValidationResult(is_valid=False, rejection_reason="out_of_state_scope")

    # 2. Required fields presence
    required_cols = ["Commodity", "Market Name", "District Name", "Price Date", "Min_Price", "Max_Price", "Modal_Price"]
    for col in required_cols:
        if not row.get(col, "").strip():
            return RecordValidationResult(is_valid=False, rejection_reason=f"missing_required_field_{col}")

    # 3. Commodity scope and non-crop guardian
    raw_comm = row.get("Commodity", "").strip()
    raw_comm_lower = raw_comm.lower()

    if any(nc in raw_comm_lower for nc in NON_CROP_EXCLUSIONS):
        return RecordValidationResult(is_valid=False, rejection_reason="non_crop_exclusion")

    if raw_comm_lower not in CANONICAL_COMMODITY_MAPPINGS:
        return RecordValidationResult(is_valid=False, rejection_reason=f"out_of_commodity_scope_{raw_comm}")

    canonical_comm = CANONICAL_COMMODITY_MAPPINGS[raw_comm_lower]

    # 4. Date validation
    d_str = row.get("Price Date", "").strip()
    parsed_d = parse_date_deterministic(d_str)
    if not parsed_d:
        return RecordValidationResult(is_valid=False, rejection_reason="invalid_date_format")

    if parsed_d > date.today():
        return RecordValidationResult(is_valid=False, rejection_reason="future_date")

    if parsed_d < date(2020, 1, 1):
        return RecordValidationResult(is_valid=False, rejection_reason="date_prior_to_boundary")

    # 5. Price parsing and sanity
    try:
        min_p = float(row.get("Min_Price", "0").strip())
        mod_p = float(row.get("Modal_Price", "0").strip())
        max_p = float(row.get("Max_Price", "0").strip())
    except ValueError:
        return RecordValidationResult(is_valid=False, rejection_reason="non_numeric_price")

    if min_p <= 0 or mod_p <= 0 or max_p <= 0:
        return RecordValidationResult(is_valid=False, rejection_reason="non_positive_price")

    # 6. Price order inversion check (Do NOT mutate source - reject with audit reason)
    if min_p > mod_p or mod_p > max_p:
        return RecordValidationResult(is_valid=False, rejection_reason="price_order_inversion")

    # 7. Market normalization
    raw_mkt = row.get("Market Name", "").strip()
    raw_mkt_lower = raw_mkt.lower()
    raw_dist = row.get("District Name", "").strip()

    if raw_mkt_lower in CANONICAL_MARKET_MAPPINGS:
        mkt_info = CANONICAL_MARKET_MAPPINGS[raw_mkt_lower]
        canonical_mkt = mkt_info["canonical"]
        canonical_dist = mkt_info["district"]
        region = mkt_info["region"]
    else:
        # Form canonical market name from raw text without fabricating coordinates
        canonical_mkt = f"{raw_mkt.title()} APMC"
        canonical_dist = raw_dist.title()
        region = "Other Maharashtra"

    return RecordValidationResult(
        is_valid=True,
        parsed_date=parsed_d,
        min_price=min_p,
        modal_price=mod_p,
        max_price=max_p,
        canonical_commodity=canonical_comm,
        canonical_market=canonical_mkt,
        canonical_district=canonical_dist,
        market_region=region
    )


def compute_series_time_series_metrics(entries: List[Tuple[date, float, float, float, Dict[str, Any]]]) -> Dict[str, Any]:
    """Calculates time series continuity, missingness, and suitability metrics for a crop-market series."""
    if not entries:
        return {}

    entries.sort(key=lambda x: x[0])
    d_list = [e[0] for e in entries]
    mod_list = [e[2] for e in entries]

    first_d = d_list[0]
    last_d = d_list[-1]
    n_obs = len(d_list)

    # Expected trading days (Mon-Sat, excluding Sundays)
    expected_td = 0
    curr = first_d
    while curr <= last_d:
        if curr.weekday() != 6:
            expected_td += 1
        curr += timedelta(days=1)

    unique_obs = len(set(d_list))
    dup_count = n_obs - unique_obs
    missing_td = max(0, expected_td - unique_obs)
    missing_pct = (missing_td / expected_td * 100) if expected_td > 0 else 0.0

    gaps = [(d_list[i] - d_list[i-1]).days for i in range(1, len(d_list))]
    longest_gap = max(gaps) if gaps else 1

    # Suitability classification
    # A = Strong (>= 300 unique trading days, < 45% missing, max gap <= 14)
    # B = Usable (>= 150 unique trading days, < 65% missing, max gap <= 30)
    # C = Sparse (50 to 149 observations)
    # D = Insufficient (< 50 observations)
    if unique_obs >= 300 and missing_pct < 45.0 and longest_gap <= 14:
        classification = "A (Strong)"
    elif unique_obs >= 150 and missing_pct < 65.0 and longest_gap <= 30:
        classification = "B (Usable)"
    elif unique_obs >= 50:
        classification = "C (Sparse)"
    else:
        classification = "D (Insufficient)"

    return {
        "first_date": first_d.isoformat(),
        "last_date": last_d.isoformat(),
        "total_records": n_obs,
        "unique_trading_days": unique_obs,
        "expected_trading_days": expected_td,
        "missing_trading_days": missing_td,
        "missing_percentage": round(missing_pct, 2),
        "longest_consecutive_gap_days": longest_gap,
        "duplicate_observations": dup_count,
        "avg_modal_price": round(sum(mod_list) / len(mod_list), 2),
        "min_modal_price": min(mod_list),
        "max_modal_price": max(mod_list),
        "classification": classification
    }


def execute_ml_data_preparation_pipeline(
    raw_input_csv: Path,
    output_dir: Path,
    target_scope_state: str = "maharashtra"
) -> Dict[str, Any]:
    """
    Executes full reproducible ML data preparation pipeline.
    Generates:
    - filtered_market_data.csv
    - rejected_records.csv
    - dataset_manifest.json
    - quality_report.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filtered_csv_path = output_dir / "filtered_market_data.csv"
    rejected_csv_path = output_dir / "rejected_records.csv"
    manifest_path = output_dir / "dataset_manifest.json"
    quality_report_path = output_dir / "quality_report.json"

    # Compute raw input checksum
    raw_bytes = raw_input_csv.read_bytes()
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    raw_file_size = len(raw_bytes)

    valid_records: List[Dict[str, Any]] = []
    rejected_records: List[Dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()

    # Track series for time-series metrics
    series_map: Dict[Tuple[str, str], List[Tuple[date, float, float, float, Dict[str, Any]]]] = defaultdict(list)

    with open(raw_input_csv, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        total_input_rows = 0

        for row in reader:
            total_input_rows += 1
            val_res = validate_and_normalize_record(row, target_scope_state=target_scope_state)

            if val_res.is_valid:
                valid_row = {
                    "price_date": val_res.parsed_date.isoformat(),
                    "state": "Maharashtra",
                    "district": val_res.canonical_district,
                    "market": val_res.canonical_market,
                    "market_region": val_res.market_region,
                    "commodity": val_res.canonical_commodity,
                    "raw_commodity": row.get("Commodity", "").strip(),
                    "raw_market": row.get("Market Name", "").strip(),
                    "variety": row.get("Variety", "").strip(),
                    "grade": row.get("Grade", "").strip(),
                    "min_price": val_res.min_price,
                    "modal_price": val_res.modal_price,
                    "max_price": val_res.max_price,
                    "price_unit": "Rs/quintal",
                    "has_arrivals": "false",
                    "source": "Agmarknet Historical (Kaggle CC0-1.0 Processed)"
                }
                valid_records.append(valid_row)

                # Append to series tracking
                s_key = (val_res.canonical_commodity, val_res.canonical_market)
                series_map[s_key].append((val_res.parsed_date, val_res.min_price, val_res.modal_price, val_res.max_price, valid_row))
            else:
                rejection_reasons[val_res.rejection_reason] += 1
                rejected_row = {
                    "raw_row_index": total_input_rows,
                    "rejection_reason": val_res.rejection_reason,
                    "state": row.get("STATE", ""),
                    "district": row.get("District Name", ""),
                    "market": row.get("Market Name", ""),
                    "commodity": row.get("Commodity", ""),
                    "variety": row.get("Variety", ""),
                    "grade": row.get("Grade", ""),
                    "min_price": row.get("Min_Price", ""),
                    "modal_price": row.get("Modal_Price", ""),
                    "max_price": row.get("Max_Price", ""),
                    "price_date": row.get("Price Date", "")
                }
                rejected_records.append(rejected_row)

    # Write filtered valid dataset
    if valid_records:
        with open(filtered_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(valid_records[0].keys()))
            writer.writeheader()
            writer.writerows(valid_records)

    # Write rejected dataset
    if rejected_records:
        with open(rejected_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rejected_records[0].keys()))
            writer.writeheader()
            writer.writerows(rejected_records)

    # Calculate filtered and rejected checksums
    filtered_bytes = filtered_csv_path.read_bytes() if filtered_csv_path.exists() else b""
    filtered_sha256 = hashlib.sha256(filtered_bytes).hexdigest()

    rejected_bytes = rejected_csv_path.read_bytes() if rejected_csv_path.exists() else b""
    rejected_sha256 = hashlib.sha256(rejected_bytes).hexdigest()

    # Calculate series time-series metrics
    series_quality_list = []
    for (comm, mkt), entries in series_map.items():
        metrics = compute_series_time_series_metrics(entries)
        metrics["commodity"] = comm
        metrics["market"] = mkt
        series_quality_list.append(metrics)

    series_quality_list.sort(key=lambda x: x["unique_trading_days"], reverse=True)
    classification_summary = Counter(s["classification"] for s in series_quality_list)

    # Commodity and market distributions in filtered data
    filtered_commodities = Counter(r["commodity"] for r in valid_records)
    filtered_markets = Counter(r["market"] for r in valid_records)
    filtered_regions = Counter(r["market_region"] for r in valid_records)

    # Manifest creation
    manifest = {
        "pipeline_version": "1.0.0",
        "pipeline_execution_timestamp": datetime.now().isoformat(),
        "input_dataset": {
            "source_path": str(raw_input_csv),
            "file_size_bytes": raw_file_size,
            "sha256": raw_sha256,
            "total_records": total_input_rows,
            "provenance": "C. Third-Party Processed / Agmarknet-Derived Dataset",
            "license": "CC0-1.0 (Public Domain Dedication)"
        },
        "output_artifacts": {
            "filtered_market_data": {
                "path": str(filtered_csv_path),
                "file_size_bytes": len(filtered_bytes),
                "sha256": filtered_sha256,
                "record_count": len(valid_records)
            },
            "rejected_records": {
                "path": str(rejected_csv_path),
                "file_size_bytes": len(rejected_bytes),
                "sha256": rejected_sha256,
                "record_count": len(rejected_records)
            },
            "quality_report": {
                "path": str(quality_report_path)
            }
        },
        "filtering_rules": {
            "state_scope": "Maharashtra",
            "target_commodities": ["Potato", "Onion", "Tomato", "Wheat", "Rice"],
            "non_crop_exclusions_enforced": list(NON_CROP_EXCLUSIONS),
            "price_inversion_rejection_enforced": True,
            "date_range_observed": {
                "start": min(r["price_date"] for r in valid_records) if valid_records else None,
                "end": max(r["price_date"] for r in valid_records) if valid_records else None
            }
        },
        "rejection_breakdown": dict(rejection_reasons),
        "series_summary": {
            "total_series": len(series_quality_list),
            "class_a_strong_series": classification_summary.get("A (Strong)", 0),
            "class_b_usable_series": classification_summary.get("B (Usable)", 0),
            "class_c_sparse_series": classification_summary.get("C (Sparse)", 0),
            "class_d_insufficient_series": classification_summary.get("D (Insufficient)", 0),
            "ml_ready_series_count": classification_summary.get("A (Strong)", 0) + classification_summary.get("B (Usable)", 0)
        }
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Quality report creation
    quality_report = {
        "report_generated_at": datetime.now().isoformat(),
        "summary": {
            "total_input_records": total_input_rows,
            "total_filtered_records": len(valid_records),
            "total_rejected_records": len(rejected_records),
            "retention_rate_pct": round(len(valid_records) / total_input_rows * 100, 2),
            "maharashtra_records_in_raw": sum(rejection_reasons[k] for k in rejection_reasons if "scope" not in k and k != "out_of_state_scope") + len(valid_records),
            "commodity_distribution": dict(filtered_commodities),
            "regional_distribution": dict(filtered_regions),
            "classification_counts": dict(classification_summary)
        },
        "rejection_details": dict(rejection_reasons),
        "series_evaluations": series_quality_list
    }

    quality_report_path.write_text(json.dumps(quality_report, indent=2), encoding="utf-8")

    return {
        "manifest": manifest,
        "quality_report": quality_report
    }


if __name__ == "__main__":
    raw_csv = Path("data/historical/raw/kaggle/Agriculture_price_dataset.csv")
    out_dir = Path("data/processed/ml")
    print("Executing ML Data Preparation Pipeline...")
    res = execute_ml_data_preparation_pipeline(raw_csv, out_dir)
    print("Done! Valid rows:", res["manifest"]["output_artifacts"]["filtered_market_data"]["record_count"])
    print("Rejected rows:", res["manifest"]["output_artifacts"]["rejected_records"]["record_count"])
    print("Rejection breakdown:", res["manifest"]["rejection_breakdown"])
    print("Series classification:", res["manifest"]["series_summary"])
