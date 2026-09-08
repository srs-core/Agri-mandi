from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.entities import (
    Commodity,
    CommodityCategory,
    DataSource,
    Location,
    MarketPriceRecord,
    SourceAttribution,
    SourceType,
    SourceVerificationStatus,
)
from app.modules.intelligence.market_ingestion import (
    AgmarknetOGDAdapter,
    MarketDataIngestionService,
    MSAMBMarketDataAdapter,
    normalize_commodity_deterministic,
    normalize_market_location_deterministic,
)


def test_deterministic_commodity_and_market_normalization(db: Session):
    """Verifies that commodity names and market APMC locations are resolved deterministically."""
    # Commodity exact aliases
    onion = normalize_commodity_deterministic(db, "Onion")
    assert onion is not None
    assert onion.name == "Onion (Nashik Red)"

    tomato = normalize_commodity_deterministic(db, "Tomato (Hybrid)")
    assert tomato is not None
    assert tomato.name == "Tomato (Hybrid)"

    chilli = normalize_commodity_deterministic(db, "Green Chilli")
    assert chilli is not None
    assert chilli.name == "Green Chilli"

    # Market exact aliases (Pune region)
    pune_loc = normalize_market_location_deterministic(db, "Pune(Gultekdi)", "Pune", "Maharashtra")
    assert pune_loc.name == "Pune APMC (Gultekdi)"
    assert pune_loc.taluka == "Haveli"
    assert pune_loc.district == "Pune"
    assert pune_loc.latitude is None  # No fabricated coordinates

    manchar_loc = normalize_market_location_deterministic(db, "Manchar", "Pune", "Maharashtra")
    assert manchar_loc.name == "Manchar APMC"
    assert manchar_loc.taluka == "Ambegaon"


def test_agmarknet_ogd_adapter_ingestion(db: Session):
    """Tests Agmarknet / data.gov.in adapter parsing, validation, and database storage."""
    adapter = AgmarknetOGDAdapter()
    service = MarketDataIngestionService(db)

    raw_data = [
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune(Gultekdi)",
            "Commodity": "Onion",
            "Variety": "Nashik Red",
            "Grade": "Grade A",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "2100",
            "Max_Price": "2800",
            "Modal_Price": "2500",
            "Arrivals": "4500",
        },
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Manchar",
            "Commodity": "Tomato",
            "Variety": "Hybrid",
            "Grade": "FAQ",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "1400",
            "Max_Price": "1900",
            "Modal_Price": "1700",
            "Arrivals": "2200",
        },
    ]

    report = service.ingest_observations(adapter, raw_data)

    assert report.total_processed == 2
    assert report.imported_count == 2
    assert len(report.rejected_records) == 0

    # Verify in database
    records = db.scalars(select(MarketPriceRecord).where(MarketPriceRecord.price_date == date(2026, 8, 28))).all()
    assert len(records) >= 2

    onion_rec = next(
        r for r in records if r.commodity.name == "Onion (Nashik Red)" and r.market_location.name == "Pune APMC (Gultekdi)"
    )
    assert onion_rec.modal_price == Decimal("2500.00")
    assert onion_rec.min_price == Decimal("2100.00")
    assert onion_rec.max_price == Decimal("2800.00")
    assert onion_rec.arrivals_quantity == Decimal("4500.000")
    assert onion_rec.raw_commodity_name == "Onion"
    assert onion_rec.raw_market_name == "Pune(Gultekdi)"
    assert onion_rec.data_source is not None
    assert onion_rec.data_source.name == adapter.source_name


def test_msamb_adapter_ingestion(db: Session):
    """Tests MSAMB adapter format ingestion."""
    adapter = MSAMBMarketDataAdapter()
    service = MarketDataIngestionService(db)

    raw_data = [
        {
            "state": "Maharashtra",
            "district": "Pune",
            "apmc": "Pune(Junnar)",
            "commodity": "Pomegranate arils",
            "variety": "Bhagwa",
            "grade": "Export",
            "date": "28/08/2026",
            "min_price": "8000",
            "max_price": "12000",
            "modal_price": "10500",
            "arrivals_quantity": "350",
        }
    ]

    report = service.ingest_observations(adapter, raw_data)

    assert report.total_processed == 1
    assert report.imported_count == 1
    assert len(report.rejected_records) == 0

    rec = db.scalar(
        select(MarketPriceRecord)
        .join(Commodity, MarketPriceRecord.commodity_id == Commodity.id)
        .where(Commodity.name == "Pomegranate (Bhagwa)")
    )
    assert rec is not None
    assert rec.modal_price == Decimal("10500.00")
    assert rec.raw_market_name == "Pune(Junnar)"


def test_price_inconsistency_validation(db: Session):
    """Verifies that invalid prices (min > modal, modal > max, negative prices) are rejected."""
    adapter = AgmarknetOGDAdapter()
    service = MarketDataIngestionService(db)

    bad_records = [
        # min > modal
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune(Gultekdi)",
            "Commodity": "Onion",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "3000",  # > modal 2500
            "Max_Price": "3500",
            "Modal_Price": "2500",
        },
        # modal > max
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune(Gultekdi)",
            "Commodity": "Tomato",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "1000",
            "Max_Price": "1500",  # < modal 2000
            "Modal_Price": "2000",
        },
        # negative price
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Baramati",
            "Commodity": "Potato",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "-500",
            "Max_Price": "1500",
            "Modal_Price": "1000",
        },
    ]

    report = service.ingest_observations(adapter, bad_records)

    assert report.total_processed == 3
    assert report.imported_count == 0
    assert len(report.rejected_records) == 3
    for rej in report.rejected_records:
        assert rej.rejection_category == "price_inconsistency"


def test_date_and_arrival_validation(db: Session):
    """Verifies that future dates and negative arrivals are rejected."""
    adapter = AgmarknetOGDAdapter()
    service = MarketDataIngestionService(db)

    future_date = (date.today() + timedelta(days=2)).isoformat()
    bad_records = [
        # Future date
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune(Gultekdi)",
            "Commodity": "Onion",
            "Arrival_Date": future_date,
            "Min_Price": "2000",
            "Max_Price": "2500",
            "Modal_Price": "2200",
        },
        # Negative arrivals
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune(Gultekdi)",
            "Commodity": "Onion",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "2000",
            "Max_Price": "2500",
            "Modal_Price": "2200",
            "Arrivals": "-50",
        },
    ]

    report = service.ingest_observations(adapter, bad_records)

    assert report.total_processed == 2
    assert report.imported_count == 0
    assert len(report.rejected_records) == 2


def test_zero_dairy_and_non_crop_rejection(db: Session):
    """Verifies that dairy and livestock commodities are strictly rejected by the scope guardian."""
    adapter = AgmarknetOGDAdapter()
    service = MarketDataIngestionService(db)

    non_crop_records = [
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune(Gultekdi)",
            "Commodity": "Buffalo Milk",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "5000",
            "Max_Price": "6000",
            "Modal_Price": "5500",
        },
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune(Gultekdi)",
            "Commodity": "Poultry Broiler",
            "Arrival_Date": "2026-08-28",
            "Min_Price": "8000",
            "Max_Price": "9000",
            "Modal_Price": "8500",
        },
    ]

    report = service.ingest_observations(adapter, non_crop_records)

    assert report.total_processed == 2
    assert report.imported_count == 0
    assert len(report.rejected_records) == 2
    for rej in report.rejected_records:
        assert rej.rejection_category == "scope_violation"


def test_idempotent_ingestion_and_updates(db: Session):
    """Verifies that re-ingesting observations for the same commodity/market/date updates existing rows cleanly."""
    adapter = AgmarknetOGDAdapter()
    service = MarketDataIngestionService(db)

    record_v1 = [
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Baramati",
            "Commodity": "Wheat",
            "Variety": "Sharbati",
            "Grade": "FAQ",
            "Arrival_Date": "2026-08-25",
            "Min_Price": "2400",
            "Max_Price": "2800",
            "Modal_Price": "2600",
            "Arrivals": "800",
        }
    ]

    report1 = service.ingest_observations(adapter, record_v1)
    assert report1.imported_count == 1
    assert report1.updated_count == 0

    # Re-ingest with updated closing price
    record_v2 = [
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Baramati",
            "Commodity": "Wheat",
            "Variety": "Sharbati",
            "Grade": "FAQ",
            "Arrival_Date": "2026-08-25",
            "Min_Price": "2450",
            "Max_Price": "2900",
            "Modal_Price": "2700",  # Updated modal price
            "Arrivals": "950",      # Updated arrivals
        }
    ]

    report2 = service.ingest_observations(adapter, record_v2)
    assert report2.imported_count == 0
    assert report2.updated_count == 1

    # Verify only 1 record exists in DB with updated values
    records = db.scalars(
        select(MarketPriceRecord)
        .join(Commodity, MarketPriceRecord.commodity_id == Commodity.id)
        .join(Location, MarketPriceRecord.market_location_id == Location.id)
        .where(
            Commodity.name == "Wheat (Sharbati)",
            Location.name == "Baramati APMC",
            MarketPriceRecord.price_date == date(2026, 8, 25),
        )
    ).all()

    assert len(records) == 1
    assert records[0].modal_price == Decimal("2700.00")
    assert records[0].arrivals_quantity == Decimal("950.000")


def test_configurable_outlier_detection_flagging(db: Session):
    """Verifies that price anomalies are flagged as outliers with UNVERIFIED status without being deleted."""
    adapter = AgmarknetOGDAdapter()
    service = MarketDataIngestionService(db, outlier_ratio_threshold=2.5)

    # Establish 4 baseline historical prices (~2500 Rs/quintal)
    for day in range(1, 5):
        service.ingest_observations(
            adapter,
            [
                {
                    "State": "Maharashtra",
                    "District": "Pune",
                    "Market": "Lasalgaon",
                    "Commodity": "Onion",
                    "Variety": "Nashik Red",
                    "Grade": "FAQ",
                    "Arrival_Date": f"2026-08-0{day}",
                    "Min_Price": "2300",
                    "Max_Price": "2700",
                    "Modal_Price": "2500",
                }
            ],
        )

    # Ingest sudden extreme spike price (9000 Rs/quintal > 2.5x baseline)
    spike_record = [
        {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Lasalgaon",
            "Commodity": "Onion",
            "Variety": "Nashik Red",
            "Grade": "FAQ",
            "Arrival_Date": "2026-08-06",
            "Min_Price": "8500",
            "Max_Price": "9500",
            "Modal_Price": "9000",
        }
    ]

    report = service.ingest_observations(adapter, spike_record)
    assert report.outliers_flagged == 1
    assert report.imported_count == 1

    # Verify outlier was stored in DB but attribution carries UNVERIFIED status
    spike_db = db.scalar(
        select(MarketPriceRecord)
        .join(Commodity, MarketPriceRecord.commodity_id == Commodity.id)
        .where(
            Commodity.name == "Onion (Nashik Red)",
            MarketPriceRecord.price_date == date(2026, 8, 6),
        )
    )
    assert spike_db is not None
    assert spike_db.modal_price == Decimal("9000.00")

    attr = db.scalar(
        select(SourceAttribution).where(
            SourceAttribution.entity_type == "market_price_record",
            SourceAttribution.entity_id == spike_db.id,
        )
    )
    assert attr is not None
    assert attr.verification_status == SourceVerificationStatus.UNVERIFIED
