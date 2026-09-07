from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.entities import (
    BuyerDirectoryEntry,
    BuyerPreferredCategory,
    BuyerPreferredCommodity,
    Commodity,
    CommodityCategory,
    DataSource,
    Location,
    MarketPriceRecord,
    SourceAttribution,
    SourceType,
    SourceVerificationStatus,
)
from app.modules.marketplace.service import _create_or_get_location, _serialize_location
from app.schemas.intelligence import (
    BuyerDirectoryCreate,
    BuyerDirectoryResponse,
    BuyerPreferredCategoryResponse,
    BuyerPreferredCommodityResponse,
    MarketPriceRecordCreate,
    MarketPriceRecordResponse,
)


# --- Buyer Directory Operations ---

def create_buyer_directory_entry(
    db: Session,
    payload: BuyerDirectoryCreate,
    data_source_id: UUID | None = None,
    confidence_score: float | None = None,
    verification_status: SourceVerificationStatus = SourceVerificationStatus.UNVERIFIED,
) -> BuyerDirectoryResponse:
    location = _create_or_get_location(db, payload.location, payload.location_id)

    # Check for existing external_id
    if payload.external_id:
        existing = db.scalar(select(BuyerDirectoryEntry).where(BuyerDirectoryEntry.external_id == payload.external_id))
        if existing:
            return _serialize_buyer_directory_entry(existing)

    entry = BuyerDirectoryEntry(
        external_id=payload.external_id,
        business_name=payload.business_name,
        buyer_type=payload.buyer_type,
        location_id=location.id,
        contact_person=payload.contact_person,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        procurement_radius_km=payload.procurement_radius_km,
        daily_capacity_mt=payload.daily_capacity_mt,
        typical_payment_terms=payload.typical_payment_terms,
        notes=payload.notes,
        is_active=True,
    )
    db.add(entry)
    db.flush()

    if payload.preferred_commodities:
        for pref in payload.preferred_commodities:
            comm = db.get(Commodity, pref.commodity_id)
            if not comm:
                raise ApiError(404, "commodity_not_found", f"Commodity {pref.commodity_id} not found.")
            p = BuyerPreferredCommodity(
                buyer_entry_id=entry.id,
                commodity_id=comm.id,
                min_quality_grade=pref.min_quality_grade,
                typical_volume_quintals=pref.typical_volume_quintals,
                max_price_per_unit=pref.max_price_per_unit,
            )
            db.add(p)

    if payload.preferred_categories:
        for cat in payload.preferred_categories:
            c = BuyerPreferredCategory(
                buyer_entry_id=entry.id,
                category=cat.category,
                notes=cat.notes,
            )
            db.add(c)

    if data_source_id:
        ds = db.get(DataSource, data_source_id)
        if ds:
            attr = SourceAttribution(
                data_source_id=ds.id,
                entity_type="buyer_directory_entry",
                entity_id=entry.id,
                external_record_id=payload.external_id,
                verification_status=verification_status,
                confidence_score=confidence_score,
            )
            db.add(attr)

    db.commit()
    db.refresh(entry)
    return _serialize_buyer_directory_entry(entry)


def get_buyer_directory_entry(db: Session, entry_id: UUID) -> BuyerDirectoryResponse:
    entry = db.get(BuyerDirectoryEntry, entry_id)
    if not entry:
        raise ApiError(404, "buyer_directory_entry_not_found", "Buyer directory entry not found.")
    return _serialize_buyer_directory_entry(entry)


def list_buyer_directory_entries(
    db: Session,
    commodity_id: UUID | None = None,
    category: CommodityCategory | None = None,
    taluka: str | None = None,
    district: str | None = None,
    is_active: bool = True,
) -> list[BuyerDirectoryResponse]:
    stmt = select(BuyerDirectoryEntry).join(Location, BuyerDirectoryEntry.location_id == Location.id)
    if is_active:
        stmt = stmt.where(BuyerDirectoryEntry.is_active.is_(True))
    if taluka:
        stmt = stmt.where(func.lower(Location.taluka) == taluka.strip().lower())
    if district:
        stmt = stmt.where(func.lower(Location.district) == district.strip().lower())
    if commodity_id:
        stmt = stmt.join(BuyerPreferredCommodity, BuyerDirectoryEntry.id == BuyerPreferredCommodity.buyer_entry_id).where(
            BuyerPreferredCommodity.commodity_id == commodity_id
        )
    elif category:
        # Check both direct category preference AND specific crop category match
        stmt = stmt.outerjoin(BuyerPreferredCategory, BuyerDirectoryEntry.id == BuyerPreferredCategory.buyer_entry_id).outerjoin(
            BuyerPreferredCommodity, BuyerDirectoryEntry.id == BuyerPreferredCommodity.buyer_entry_id
        ).outerjoin(Commodity, BuyerPreferredCommodity.commodity_id == Commodity.id).where(
            (BuyerPreferredCategory.category == category) | (Commodity.category == category)
        )

    stmt = stmt.order_by(BuyerDirectoryEntry.business_name).distinct()
    entries = db.scalars(stmt).all()
    return [_serialize_buyer_directory_entry(e) for e in entries]


def _serialize_buyer_directory_entry(entry: BuyerDirectoryEntry) -> BuyerDirectoryResponse:
    prefs = [
        BuyerPreferredCommodityResponse(
            id=p.id,
            commodity_id=p.commodity_id,
            commodity_name=p.commodity.name,
            commodity_category=p.commodity.category,
            min_quality_grade=p.min_quality_grade,
            typical_volume_quintals=p.typical_volume_quintals,
            max_price_per_unit=p.max_price_per_unit,
        )
        for p in entry.preferred_commodities
    ]
    pref_cats = [
        BuyerPreferredCategoryResponse(
            id=c.id,
            category=c.category,
            notes=c.notes,
        )
        for c in entry.preferred_categories
    ]
    return BuyerDirectoryResponse(
        id=entry.id,
        external_id=entry.external_id,
        business_name=entry.business_name,
        buyer_type=entry.buyer_type,
        location=_serialize_location(entry.location),
        registered_buyer_profile_id=entry.registered_buyer_profile_id,
        contact_person=entry.contact_person,
        contact_phone=entry.contact_phone,
        contact_email=entry.contact_email,
        procurement_radius_km=entry.procurement_radius_km,
        daily_capacity_mt=entry.daily_capacity_mt,
        typical_payment_terms=entry.typical_payment_terms,
        notes=entry.notes,
        is_active=entry.is_active,
        preferred_commodities=prefs,
        preferred_categories=pref_cats,
        created_at=entry.created_at,
    )


# --- Market Price Records ---

def record_market_price(
    db: Session,
    payload: MarketPriceRecordCreate,
    data_source_id: UUID | None = None,
    confidence_score: float | None = None,
    verification_status: SourceVerificationStatus = SourceVerificationStatus.VERIFIED,
) -> MarketPriceRecordResponse:
    comm = db.get(Commodity, payload.commodity_id)
    if not comm:
        raise ApiError(404, "commodity_not_found", "Commodity not found.")

    location = _create_or_get_location(db, payload.market_location, payload.market_location_id)
    effective_ds_id = payload.data_source_id or data_source_id

    # Check for existing observation to guarantee idempotency
    existing = db.scalar(
        select(MarketPriceRecord).where(
            MarketPriceRecord.commodity_id == comm.id,
            MarketPriceRecord.market_location_id == location.id,
            MarketPriceRecord.price_date == payload.price_date,
            MarketPriceRecord.variety == payload.variety,
            MarketPriceRecord.grade == payload.grade,
        )
    )
    if existing:
        existing.min_price = payload.min_price
        existing.max_price = payload.max_price
        existing.modal_price = payload.modal_price
        existing.arrivals_quantity = payload.arrivals_quantity
        if payload.raw_commodity_name:
            existing.raw_commodity_name = payload.raw_commodity_name
        if payload.raw_market_name:
            existing.raw_market_name = payload.raw_market_name
        if effective_ds_id:
            existing.data_source_id = effective_ds_id

        # Update attribution verification status if exists
        attr = db.scalar(
            select(SourceAttribution).where(
                SourceAttribution.entity_type == "market_price_record",
                SourceAttribution.entity_id == existing.id,
            )
        )
        if attr:
            attr.verification_status = verification_status
            if confidence_score is not None:
                attr.confidence_score = Decimal(str(confidence_score))

        db.commit()
        db.refresh(existing)
        return _serialize_market_price_record(existing)

    record = MarketPriceRecord(
        commodity_id=comm.id,
        market_location_id=location.id,
        data_source_id=effective_ds_id,
        price_date=payload.price_date,
        variety=payload.variety,
        grade=payload.grade,
        raw_commodity_name=payload.raw_commodity_name,
        raw_market_name=payload.raw_market_name,
        min_price=payload.min_price,
        max_price=payload.max_price,
        modal_price=payload.modal_price,
        price_unit=payload.price_unit,
        arrivals_quantity=payload.arrivals_quantity,
        arrivals_unit=payload.arrivals_unit,
    )
    db.add(record)
    db.flush()

    if effective_ds_id:
        ds = db.get(DataSource, effective_ds_id)
        if ds:
            attr = SourceAttribution(
                data_source_id=ds.id,
                entity_type="market_price_record",
                entity_id=record.id,
                verification_status=verification_status,
                confidence_score=Decimal(str(confidence_score)) if confidence_score is not None else None,
            )
            db.add(attr)

    db.commit()
    db.refresh(record)
    return _serialize_market_price_record(record)


def list_market_prices(
    db: Session,
    commodity_id: UUID | None = None,
    market_location_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[MarketPriceRecordResponse]:
    stmt = select(MarketPriceRecord)
    if commodity_id:
        stmt = stmt.where(MarketPriceRecord.commodity_id == commodity_id)
    if market_location_id:
        stmt = stmt.where(MarketPriceRecord.market_location_id == market_location_id)
    if start_date:
        stmt = stmt.where(MarketPriceRecord.price_date >= start_date)
    if end_date:
        stmt = stmt.where(MarketPriceRecord.price_date <= end_date)

    stmt = stmt.order_by(MarketPriceRecord.price_date.desc(), MarketPriceRecord.modal_price.desc())
    records = db.scalars(stmt).all()
    return [_serialize_market_price_record(r) for r in records]


def _serialize_market_price_record(record: MarketPriceRecord) -> MarketPriceRecordResponse:
    return MarketPriceRecordResponse(
        id=record.id,
        commodity_id=record.commodity_id,
        commodity_name=record.commodity.name,
        commodity_category=record.commodity.category,
        market_location=_serialize_location(record.market_location),
        data_source_id=record.data_source_id,
        price_date=record.price_date,
        variety=record.variety,
        grade=record.grade,
        raw_commodity_name=record.raw_commodity_name,
        raw_market_name=record.raw_market_name,
        min_price=record.min_price,
        max_price=record.max_price,
        modal_price=record.modal_price,
        price_unit=record.price_unit,
        arrivals_quantity=record.arrivals_quantity,
        arrivals_unit=record.arrivals_unit,
        created_at=record.created_at,
    )
