from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import (
    BuyerDirectoryEntry,
    BuyerPreferredCategory,
    BuyerPreferredCommodity,
    Commodity,
    DataSource,
    HistoricalInfrastructureRecord,
    Location,
    LogisticsProvider,
    MarketPriceRecord,
    Role,
    SourceAttribution,
    User,
)
from app.modules.intelligence.market_ingestion import (
    AgmarknetOGDAdapter,
    MarketDataIngestionService,
    MarketIngestionReport,
)

logger = logging.getLogger("agrimandi.market_import")

# Staged current market data paths
CANDIDATE_PATHS = [
    Path("data/staging/agmarknet_current_batch.json"),
    Path("/app/data/staging/agmarknet_current_batch.json"),
    Path(__file__).parent.parent.parent.parent.parent / "data" / "staging" / "agmarknet_current_batch.json",
]


def load_or_fetch_current_batch() -> list[dict[str, Any]]:
    """Loads staged current batch from candidate paths or fetches from OGD API."""
    for p in CANDIDATE_PATHS:
        if p.exists():
            print(f"[1/3] Loading verified real current market batch from {p}...")
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                recs = data.get("records", [])
                print(f"[OK] Loaded {len(recs)} staged records.")
                return recs

    # If not already staged, build the verified current batch
    import urllib.request
    import time

    districts = [
        "Pune", "Nashik", "Solapur", "Ahmednagar", "Sangli", "Satara", "Kolhapur", "Nagpur"
    ]
    all_records: list[dict[str, Any]] = []

    print("[1/3] Retrieving real daily market data from Agmarknet OGD feed...")
    for dist in districts:
        url = (
            "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
            f"?api-key=579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
            f"&format=json&limit=10&filters%5Bdistrict%5D={dist}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "AgriMandi-Research/1.0"})
        for attempt in range(3):
            try:
                time.sleep(1.5)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    recs = payload.get("records", [])
                    all_records.extend(recs)
                    print(f"  -> {dist}: {len(recs)} records")
                    break
            except Exception as e:
                print(f"  -> {dist} attempt {attempt+1} warning: {e}")
                time.sleep(3.0)

    # Save to staging
    STAGED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STAGED_FILE, "w", encoding="utf-8") as f:
        json.dump({"total": len(all_records), "records": all_records}, f, indent=2)

    print(f"[OK] Staged {len(all_records)} records to {STAGED_FILE}")
    return all_records


def execute_current_market_ingestion(db: Session, records: list[dict[str, Any]]) -> MarketIngestionReport:
    """Executes controlled ingestion through the MarketDataIngestionService pipeline."""
    adapter = AgmarknetOGDAdapter()
    service = MarketDataIngestionService(db)

    print("\n[2/3] Processing observations through validation & normalization engine...")
    report = service.ingest_observations(adapter, records)
    return report


def generate_ingestion_summary(db: Session, report: MarketIngestionReport) -> dict[str, Any]:
    """Generates detailed verification and breakdown metrics."""
    # 1. Total Market Price Records in DB
    total_prices = db.scalar(select(func.count(MarketPriceRecord.id))) or 0
    total_sources = db.scalar(select(func.count(DataSource.id))) or 0
    total_attributions = db.scalar(
        select(func.count(SourceAttribution.id)).where(SourceAttribution.entity_type == "market_price_record")
    ) or 0

    # 2. Pune District Observations
    pune_count = db.scalar(
        select(func.count(MarketPriceRecord.id))
        .join(Location, MarketPriceRecord.market_location_id == Location.id)
        .where(Location.district == "Pune")
    ) or 0

    # 3. Benchmark Market Observations
    benchmark_markets = ["Nashik APMC", "Lasalgaon APMC", "Solapur APMC", "Ahmednagar APMC", "Sangli APMC", "Nagpur APMC"]
    benchmark_counts = {}
    for bm in benchmark_markets:
        cnt = db.scalar(
            select(func.count(MarketPriceRecord.id))
            .join(Location, MarketPriceRecord.market_location_id == Location.id)
            .where(Location.name.ilike(f"%{bm}%"))
        ) or 0
        if cnt > 0:
            benchmark_counts[bm] = cnt

    # 4. Usable Observations by Canonical Commodity
    commodity_rows = db.execute(
        select(Commodity.name, Commodity.category, func.count(MarketPriceRecord.id))
        .join(MarketPriceRecord, MarketPriceRecord.commodity_id == Commodity.id)
        .group_by(Commodity.name, Commodity.category)
        .order_by(Commodity.category, Commodity.name)
    ).all()

    commodity_breakdown = {row[0]: {"category": row[1].value, "count": row[2]} for row in commodity_rows}

    # 5. Phase 1 & 2A Integrity Verification
    phase1_users = db.scalar(select(func.count(User.id)))
    phase1_roles = db.scalar(select(func.count(Role.id)))
    phase1_commodities = db.scalar(select(func.count(Commodity.id)))
    phase2a_buyers = db.scalar(select(func.count(BuyerDirectoryEntry.id)))
    phase2a_pref_comm = db.scalar(select(func.count(BuyerPreferredCommodity.id)))
    phase2a_pref_cat = db.scalar(select(func.count(BuyerPreferredCategory.id)))
    phase2a_hist_infra = db.scalar(select(func.count(HistoricalInfrastructureRecord.id)))
    active_logistics = db.scalar(select(func.count(LogisticsProvider.id)))

    return {
        "report": {
            "total_processed": report.total_processed,
            "imported_count": report.imported_count,
            "updated_count": report.updated_count,
            "outliers_flagged": report.outliers_flagged,
            "rejected_count": len(report.rejected_records),
            "rejection_reasons": Counter(r.reason for r in report.rejected_records),
        },
        "database_state": {
            "total_market_price_records": total_prices,
            "total_price_attributions": total_attributions,
            "total_data_sources": total_sources,
        },
        "geography": {
            "pune_district_observations": pune_count,
            "benchmark_market_observations": benchmark_counts,
        },
        "commodity_coverage": commodity_breakdown,
        "integrity": {
            "phase1_users": phase1_users,
            "phase1_roles": phase1_roles,
            "phase1_commodities": phase1_commodities,
            "phase2a_buyers": phase2a_buyers,
            "phase2a_pref_comm": phase2a_pref_comm,
            "phase2a_pref_cat": phase2a_pref_cat,
            "phase2a_hist_infra": phase2a_hist_infra,
            "active_logistics_providers": active_logistics,
        },
    }


def main():
    records = load_or_fetch_current_batch()
    db = SessionLocal()
    try:
        report = execute_current_market_ingestion(db, records)
        summary = generate_ingestion_summary(db, report)
        print("\n" + "=" * 80)
        print("PHASE 2B CONTROLLED CURRENT MARKET INGESTION COMPLETE")
        print("=" * 80)
        print(json.dumps(summary, indent=2, default=str))

        # Test Idempotency (2nd run)
        print("\n[3/3] Testing idempotency with second execution...")
        report2 = execute_current_market_ingestion(db, records)
        print(f"Second Run: {report2.imported_count} imported, {report2.updated_count} updated, {len(report2.rejected_records)} rejected.")
        assert report2.imported_count == 0, "Idempotency failed: imported > 0 on second run"
        print("[OK] Idempotency verified: 0 duplicates created.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
