from __future__ import annotations

import abc
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
from app.modules.ingestion.pipeline import (
    COMMODITY_EXACT_ALIASES,
    DISALLOWED_DAIRY_KEYWORDS,
    DISALLOWED_NON_CROP_KEYWORDS,
    ensure_data_source,
    validate_crop_only,
)
from app.modules.intelligence.service import record_market_price
from app.schemas.intelligence import MarketPriceRecordCreate, MarketPriceRecordResponse
from app.schemas.marketplace import LocationCreate

logger = logging.getLogger("agrimandi.market_intelligence")


# =====================================================================
# DATA CLASSES & REJECTION REPORTS
# =====================================================================

@dataclass
class RawMarketPriceObservation:
    """Intermediate parsed representation of a market observation from any adapter."""
    raw_commodity: str
    raw_market: str
    state: str
    district: str
    price_date: date
    modal_price: Decimal
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    variety: str | None = None
    grade: str | None = None
    price_unit: str = "Rs/quintal"
    arrivals_quantity: Decimal | None = None
    arrivals_unit: str = "quintal"
    external_record_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RejectedMarketRecord:
    raw_data: dict[str, Any]
    reason: str
    rejection_category: str  # "scope_violation", "price_inconsistency", "invalid_date", "missing_required_field"


@dataclass
class MarketIngestionReport:
    data_source_name: str
    total_processed: int = 0
    imported_count: int = 0
    updated_count: int = 0
    outliers_flagged: int = 0
    rejected_records: list[RejectedMarketRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# =====================================================================
# DETERMINISTIC NORMALIZERS
# =====================================================================

# Pune & Western Maharashtra APMC Market Aliases
MARKET_EXACT_ALIASES: dict[str, dict[str, str]] = {
    "pune": {"name": "Pune APMC (Gultekdi)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune apmc": {"name": "Pune APMC (Gultekdi)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(gultekdi)": {"name": "Pune APMC (Gultekdi)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(gultekdi) apmc": {"name": "Pune APMC (Gultekdi)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune (gultekdi)": {"name": "Pune APMC (Gultekdi)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(market yard)": {"name": "Pune APMC (Gultekdi)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune (market yard)": {"name": "Pune APMC (Gultekdi)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(khadki)": {"name": "Pune APMC (Khadki Sub-Yard)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(khadki) apmc": {"name": "Pune APMC (Khadki Sub-Yard)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(khadiki)": {"name": "Pune APMC (Khadki Sub-Yard)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(khadiki) apmc": {"name": "Pune APMC (Khadki Sub-Yard)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(pimpri)": {"name": "Pune APMC (Pimpri Sub-Yard)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(pimpri) apmc": {"name": "Pune APMC (Pimpri Sub-Yard)", "taluka": "Haveli", "district": "Pune", "state": "Maharashtra"},
    "pune(manchar)": {"name": "Manchar APMC", "taluka": "Ambegaon", "district": "Pune", "state": "Maharashtra"},
    "pune(manchar) apmc": {"name": "Manchar APMC", "taluka": "Ambegaon", "district": "Pune", "state": "Maharashtra"},
    "manchar": {"name": "Manchar APMC", "taluka": "Ambegaon", "district": "Pune", "state": "Maharashtra"},
    "manchar apmc": {"name": "Manchar APMC", "taluka": "Ambegaon", "district": "Pune", "state": "Maharashtra"},
    "pune(khed)": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "pune(khed) apmc": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "pune(chakan)": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "pune(chakan) apmc": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "khed(chakan)": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "khed(chakan) apmc": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "chakan": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "chakan apmc": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "khed": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "khed apmc": {"name": "Khed APMC (Chakan)", "taluka": "Khed", "district": "Pune", "state": "Maharashtra"},
    "pune(junnar)": {"name": "Junnar APMC (Narayangaon)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "pune(junnar) apmc": {"name": "Junnar APMC (Narayangaon)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "pune(narayangaon)": {"name": "Junnar APMC (Narayangaon)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "pune(narayangaon) apmc": {"name": "Junnar APMC (Narayangaon)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "pune(alephata)": {"name": "Junnar APMC (Alephata)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "pune(alephata) apmc": {"name": "Junnar APMC (Alephata)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "junnar": {"name": "Junnar APMC (Narayangaon)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "junnar apmc": {"name": "Junnar APMC (Narayangaon)", "taluka": "Junnar", "district": "Pune", "state": "Maharashtra"},
    "baramati": {"name": "Baramati APMC", "taluka": "Baramati", "district": "Pune", "state": "Maharashtra"},
    "baramati apmc": {"name": "Baramati APMC", "taluka": "Baramati", "district": "Pune", "state": "Maharashtra"},
    "pune(baramati)": {"name": "Baramati APMC", "taluka": "Baramati", "district": "Pune", "state": "Maharashtra"},
    "pune(baramati) apmc": {"name": "Baramati APMC", "taluka": "Baramati", "district": "Pune", "state": "Maharashtra"},
    "shirur": {"name": "Shirur APMC", "taluka": "Shirur", "district": "Pune", "state": "Maharashtra"},
    "shirur apmc": {"name": "Shirur APMC", "taluka": "Shirur", "district": "Pune", "state": "Maharashtra"},
    "pune(shirur)": {"name": "Shirur APMC", "taluka": "Shirur", "district": "Pune", "state": "Maharashtra"},
    "pune(shirur) apmc": {"name": "Shirur APMC", "taluka": "Shirur", "district": "Pune", "state": "Maharashtra"},
    "indapur": {"name": "Indapur APMC", "taluka": "Indapur", "district": "Pune", "state": "Maharashtra"},
    "indapur apmc": {"name": "Indapur APMC", "taluka": "Indapur", "district": "Pune", "state": "Maharashtra"},
    "daund": {"name": "Daund APMC", "taluka": "Daund", "district": "Pune", "state": "Maharashtra"},
    "daund apmc": {"name": "Daund APMC", "taluka": "Daund", "district": "Pune", "state": "Maharashtra"},
    "lasalgaon": {"name": "Lasalgaon APMC", "taluka": "Niphad", "district": "Nashik", "state": "Maharashtra"},
    "lasalgaon apmc": {"name": "Lasalgaon APMC", "taluka": "Niphad", "district": "Nashik", "state": "Maharashtra"},
    "pimpalgaon": {"name": "Pimpalgaon Baswant APMC", "taluka": "Niphad", "district": "Nashik", "state": "Maharashtra"},
    "pimpalgaon baswant": {"name": "Pimpalgaon Baswant APMC", "taluka": "Niphad", "district": "Nashik", "state": "Maharashtra"},
    "pimpalgaon apmc": {"name": "Pimpalgaon Baswant APMC", "taluka": "Niphad", "district": "Nashik", "state": "Maharashtra"},
    "pimpalgaon baswant apmc": {"name": "Pimpalgaon Baswant APMC", "taluka": "Niphad", "district": "Nashik", "state": "Maharashtra"},
    "nashik": {"name": "Nashik APMC", "taluka": "Nashik", "district": "Nashik", "state": "Maharashtra"},
    "nashik apmc": {"name": "Nashik APMC", "taluka": "Nashik", "district": "Nashik", "state": "Maharashtra"},
    "solapur": {"name": "Solapur APMC", "taluka": "Solapur North", "district": "Solapur", "state": "Maharashtra"},
    "solapur apmc": {"name": "Solapur APMC", "taluka": "Solapur North", "district": "Solapur", "state": "Maharashtra"},
    "ahmednagar": {"name": "Ahmednagar APMC", "taluka": "Nagar", "district": "Ahmednagar", "state": "Maharashtra"},
    "ahmednagar apmc": {"name": "Ahmednagar APMC", "taluka": "Nagar", "district": "Ahmednagar", "state": "Maharashtra"},
    "sangamner": {"name": "Sangamner APMC", "taluka": "Sangamner", "district": "Ahmednagar", "state": "Maharashtra"},
    "sangamner apmc": {"name": "Sangamner APMC", "taluka": "Sangamner", "district": "Ahmednagar", "state": "Maharashtra"},
    "rahata": {"name": "Rahata APMC", "taluka": "Rahata", "district": "Ahmednagar", "state": "Maharashtra"},
    "rahata apmc": {"name": "Rahata APMC", "taluka": "Rahata", "district": "Ahmednagar", "state": "Maharashtra"},
}


def normalize_commodity_deterministic(db: Session, raw_commodity_name: str) -> Commodity | None:
    """Deterministically resolves commodity name via exact dictionary and exact DB match. Never uses unsafe loose substrings."""
    validate_crop_only(raw_commodity_name)
    cleaned = raw_commodity_name.strip().lower()

    # 1. Exact alias match
    if cleaned in COMMODITY_EXACT_ALIASES:
        canonical_name = COMMODITY_EXACT_ALIASES[cleaned]
        return db.scalar(select(Commodity).where(func.lower(Commodity.name) == canonical_name.lower()))

    # 2. Exact database match (case-insensitive)
    comm = db.scalar(select(Commodity).where(func.lower(Commodity.name) == cleaned))
    if comm:
        return comm

    return None


def normalize_market_location_deterministic(db: Session, raw_market: str, district: str, state: str) -> Location:
    """Resolves or creates Location entity for market yard without inventing coordinates."""
    cleaned_market = raw_market.strip().lower()

    if cleaned_market in MARKET_EXACT_ALIASES:
        spec = MARKET_EXACT_ALIASES[cleaned_market]
        canonical_name = spec["name"]
        taluka = spec.get("taluka")
        dist = spec.get("district", district.strip().title())
        st = spec.get("state", state.strip().title())
    else:
        canonical_name = f"{raw_market.strip().title()} APMC"
        taluka = None
        dist = district.strip().title()
        st = state.strip().title()

    # Query existing location
    loc = db.scalar(
        select(Location).where(
            func.lower(Location.name) == canonical_name.lower(),
            Location.district == dist,
            Location.state == st,
        )
    )
    if not loc:
        loc = Location(
            name=canonical_name,
            taluka=taluka,
            district=dist,
            state=st,
            country_code="IN",
            latitude=None,   # Coordinates left NULL unless independently verified
            longitude=None,
            geo_point=None,
        )
        db.add(loc)
        db.flush()

    return loc


# =====================================================================
# ABSTRACT ADAPTER & CONCRETE ADAPTERS
# =====================================================================

class BaseMarketDataAdapter(abc.ABC):
    """Abstract interface for all market-data sources (OGD API, MSAMB, CSV Archives)."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def source_type(self) -> SourceType:
        pass

    @property
    def default_source_url(self) -> str | None:
        return None

    @abc.abstractmethod
    def parse_record(self, raw_record: dict[str, Any]) -> RawMarketPriceObservation:
        """Parses raw adapter dictionary into structured RawMarketPriceObservation."""
        pass


class AgmarknetOGDAdapter(BaseMarketDataAdapter):
    """Adapter for data.gov.in / OGD Agmarknet Daily API feeds."""

    @property
    def source_name(self) -> str:
        return "Agmarknet via OGD India (data.gov.in)"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GOVERNMENT

    @property
    def default_source_url(self) -> str | None:
        return "https://api.data.gov.in/resource"

    def parse_record(self, raw_record: dict[str, Any]) -> RawMarketPriceObservation:
        # Standard OGD field naming
        raw_comm = raw_record.get("Commodity") or raw_record.get("commodity") or ""
        raw_market = raw_record.get("Market") or raw_record.get("market") or ""
        state = raw_record.get("State") or raw_record.get("state") or "Maharashtra"
        district = raw_record.get("District") or raw_record.get("district") or "Pune"
        arrival_date_str = raw_record.get("Arrival_Date") or raw_record.get("arrival_date") or raw_record.get("date")

        if not arrival_date_str:
            raise ValueError("Missing Arrival_Date in record")

        # Parse date formats: YYYY-MM-DD, DD/MM/YYYY, or DD-MM-YYYY
        p_date = self._parse_date(str(arrival_date_str))

        modal_val = Decimal(str(raw_record.get("Modal_Price") or raw_record.get("modal_price") or "0"))
        min_raw = raw_record.get("Min_Price") or raw_record.get("min_price")
        max_raw = raw_record.get("Max_Price") or raw_record.get("max_price")
        min_val = Decimal(str(min_raw)) if min_raw is not None and str(min_raw).strip() != "" else None
        max_val = Decimal(str(max_raw)) if max_raw is not None and str(max_raw).strip() != "" else None

        variety = raw_record.get("Variety") or raw_record.get("variety")
        grade = raw_record.get("Grade") or raw_record.get("grade")
        arr_raw = raw_record.get("Arrivals") or raw_record.get("arrivals_quantity")
        arrivals_qty = Decimal(str(arr_raw)) if arr_raw is not None and str(arr_raw).strip() != "" else None

        ext_id = f"OGD:{state}:{district}:{raw_market}:{raw_comm}:{p_date.isoformat()}:{variety or 'NA'}"

        return RawMarketPriceObservation(
            raw_commodity=str(raw_comm).strip(),
            raw_market=str(raw_market).strip(),
            state=str(state).strip(),
            district=str(district).strip(),
            price_date=p_date,
            modal_price=modal_val,
            min_price=min_val,
            max_price=max_val,
            variety=str(variety).strip() if variety else None,
            grade=str(grade).strip() if grade else None,
            price_unit="Rs/quintal",
            arrivals_quantity=arrivals_qty,
            arrivals_unit="quintal",
            external_record_id=ext_id,
            metadata=raw_record,
        )

    def _parse_date(self, date_str: str) -> date:
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unsupported date format '{date_str}'")


class MSAMBMarketDataAdapter(BaseMarketDataAdapter):
    """Adapter for Maharashtra State Agricultural Marketing Board daily arrival and price reports."""

    @property
    def source_name(self) -> str:
        return "MSAMB Maharashtra APMC Market Reports"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GOVERNMENT

    @property
    def default_source_url(self) -> str | None:
        return "https://www.msamb.com"

    def parse_record(self, raw_record: dict[str, Any]) -> RawMarketPriceObservation:
        raw_comm = raw_record.get("commodity") or raw_record.get("Commodity") or ""
        raw_market = raw_record.get("apmc") or raw_record.get("market") or ""
        district = raw_record.get("district") or "Pune"
        state = raw_record.get("state") or "Maharashtra"
        date_str = raw_record.get("date") or raw_record.get("Date")

        if not date_str:
            raise ValueError("Missing date in MSAMB record")

        p_date = self._parse_date(str(date_str))
        modal_val = Decimal(str(raw_record.get("modal_price") or raw_record.get("Modal_Price") or "0"))
        min_raw = raw_record.get("min_price") or raw_record.get("Min_Price")
        max_raw = raw_record.get("max_price") or raw_record.get("Max_Price")
        min_val = Decimal(str(min_raw)) if min_raw is not None and str(min_raw).strip() != "" else None
        max_val = Decimal(str(max_raw)) if max_raw is not None and str(max_raw).strip() != "" else None

        arr_raw = raw_record.get("arrivals_quantity") or raw_record.get("Arrival_Quantity")
        arrivals_qty = Decimal(str(arr_raw)) if arr_raw is not None and str(arr_raw).strip() != "" else None
        variety = raw_record.get("variety") or raw_record.get("Variety")
        grade = raw_record.get("grade") or raw_record.get("Grade")

        ext_id = f"MSAMB:{district}:{raw_market}:{raw_comm}:{p_date.isoformat()}:{variety or 'NA'}"

        return RawMarketPriceObservation(
            raw_commodity=str(raw_comm).strip(),
            raw_market=str(raw_market).strip(),
            state=str(state).strip(),
            district=str(district).strip(),
            price_date=p_date,
            modal_price=modal_val,
            min_price=min_val,
            max_price=max_val,
            variety=str(variety).strip() if variety else None,
            grade=str(grade).strip() if grade else None,
            price_unit="Rs/quintal",
            arrivals_quantity=arrivals_qty,
            arrivals_unit="quintal",
            external_record_id=ext_id,
            metadata=raw_record,
        )

    def _parse_date(self, date_str: str) -> date:
        date_str = date_str.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unsupported MSAMB date format '{date_str}'")


# =====================================================================
# INGESTION SERVICE WITH VALIDATION ENGINE
# =====================================================================

class MarketDataIngestionService:
    """Production ingestion service for agricultural market price and arrival observations."""

    def __init__(self, db: Session, outlier_ratio_threshold: float | None = None):
        self.db = db
        settings = get_settings()
        self.outlier_ratio_threshold = (
            outlier_ratio_threshold if outlier_ratio_threshold is not None else settings.market_data_outlier_ratio_threshold
        )

    def ingest_observations(
        self,
        adapter: BaseMarketDataAdapter,
        raw_records: list[dict[str, Any]],
        custom_data_source_id: UUID | None = None,
    ) -> MarketIngestionReport:
        report = MarketIngestionReport(data_source_name=adapter.source_name)

        if not raw_records:
            return report

        # 1. Resolve or ensure DataSource
        if custom_data_source_id:
            ds = self.db.get(DataSource, custom_data_source_id)
            if not ds:
                raise ApiError(404, "data_source_not_found", "Custom data source not found.")
        else:
            ds = ensure_data_source(
                self.db,
                name=adapter.source_name,
                source_type=adapter.source_type,
                source_url=adapter.default_source_url,
                notes="Automated market price & arrival ingestion pipeline",
                is_mock=False,
                confidence_score=0.95,
            )

        today = date.today()

        for raw in raw_records:
            report.total_processed += 1

            # Step A: Adapter Parse
            try:
                obs = adapter.parse_record(raw)
            except Exception as e:
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Failed to parse raw record: {str(e)}",
                        rejection_category="missing_required_field",
                    )
                )
                continue

            # Step B: Zero-Dairy & Non-Crop Scope Guardian
            try:
                validate_crop_only(obs.raw_commodity)
            except ApiError as e:
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=e.message,
                        rejection_category="scope_violation",
                    )
                )
                continue

            # Step C: Date Sanity
            if obs.price_date > today:
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Future price date '{obs.price_date}' is invalid. Max allowed is today ({today}).",
                        rejection_category="invalid_date",
                    )
                )
                continue

            if obs.price_date < date(2000, 1, 1):
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Historical price date '{obs.price_date}' exceeds minimum boundary (2000-01-01).",
                        rejection_category="invalid_date",
                    )
                )
                continue

            # Step D: Price Non-Negative & Boundary Sanity
            if obs.modal_price <= Decimal("0"):
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Modal price must be greater than 0 (got {obs.modal_price}).",
                        rejection_category="price_inconsistency",
                    )
                )
                continue

            if obs.min_price is not None and obs.min_price < Decimal("0"):
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Minimum price cannot be negative (got {obs.min_price}).",
                        rejection_category="price_inconsistency",
                    )
                )
                continue

            if obs.max_price is not None and obs.max_price < Decimal("0"):
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Maximum price cannot be negative (got {obs.max_price}).",
                        rejection_category="price_inconsistency",
                    )
                )
                continue

            # Step E: Min <= Modal <= Max Consistency
            if obs.min_price is not None and obs.min_price > obs.modal_price:
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Price inconsistency: Min price ({obs.min_price}) > Modal price ({obs.modal_price}).",
                        rejection_category="price_inconsistency",
                    )
                )
                continue

            if obs.max_price is not None and obs.modal_price > obs.max_price:
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Price inconsistency: Modal price ({obs.modal_price}) > Max price ({obs.max_price}).",
                        rejection_category="price_inconsistency",
                    )
                )
                continue

            if obs.arrivals_quantity is not None and obs.arrivals_quantity < Decimal("0"):
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Arrivals quantity cannot be negative (got {obs.arrivals_quantity}).",
                        rejection_category="price_inconsistency",
                    )
                )
                continue

            # Step F: Deterministic Commodity & Market Resolution
            comm = normalize_commodity_deterministic(self.db, obs.raw_commodity)
            if not comm:
                report.rejected_records.append(
                    RejectedMarketRecord(
                        raw_data=raw,
                        reason=f"Could not map commodity '{obs.raw_commodity}' to canonical catalog.",
                        rejection_category="scope_violation",
                    )
                )
                continue

            loc = normalize_market_location_deterministic(self.db, obs.raw_market, obs.district, obs.state)

            # Step G: Configurable Outlier Check (Flag without deleting)
            is_outlier = self._check_outlier(comm.id, loc.id, obs.modal_price)
            verification_status = SourceVerificationStatus.VERIFIED
            if is_outlier:
                report.outliers_flagged += 1
                verification_status = SourceVerificationStatus.UNVERIFIED
                logger.warning(
                    f"Outlier detected for {comm.name} at {loc.name} on {obs.price_date}: {obs.modal_price} Rs/quintal"
                )

            # Step H: Idempotent Insertion / Update
            payload = MarketPriceRecordCreate(
                commodity_id=comm.id,
                market_location_id=loc.id,
                data_source_id=ds.id,
                price_date=obs.price_date,
                variety=obs.variety,
                grade=obs.grade,
                raw_commodity_name=obs.raw_commodity,
                raw_market_name=obs.raw_market,
                min_price=obs.min_price,
                max_price=obs.max_price,
                modal_price=obs.modal_price,
                price_unit=obs.price_unit,
                arrivals_quantity=obs.arrivals_quantity,
                arrivals_unit=obs.arrivals_unit,
            )

            # Check if this is an update vs new insert
            existing = self.db.scalar(
                select(MarketPriceRecord).where(
                    MarketPriceRecord.commodity_id == comm.id,
                    MarketPriceRecord.market_location_id == loc.id,
                    MarketPriceRecord.price_date == obs.price_date,
                    MarketPriceRecord.variety == obs.variety,
                    MarketPriceRecord.grade == obs.grade,
                )
            )

            if existing:
                report.updated_count += 1
            else:
                report.imported_count += 1

            record_market_price(
                self.db,
                payload,
                data_source_id=ds.id,
                confidence_score=0.95 if verification_status == SourceVerificationStatus.VERIFIED else 0.70,
                verification_status=verification_status,
            )

        self.db.commit()
        return report

    def _check_outlier(self, commodity_id: UUID, market_location_id: UUID, current_modal: Decimal) -> bool:
        """Checks if current modal price deviates by > threshold ratio from recent 14-day median."""
        recent_prices = self.db.scalars(
            select(MarketPriceRecord.modal_price)
            .where(
                MarketPriceRecord.commodity_id == commodity_id,
                MarketPriceRecord.market_location_id == market_location_id,
            )
            .order_by(MarketPriceRecord.price_date.desc())
            .limit(14)
        ).all()

        if len(recent_prices) < 3:
            return False

        sorted_prices = sorted([float(p) for p in recent_prices])
        median_price = sorted_prices[len(sorted_prices) // 2]

        if median_price <= 0:
            return False

        ratio = float(current_modal) / median_price
        return ratio > self.outlier_ratio_threshold or ratio < (1.0 / self.outlier_ratio_threshold)
