from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.entities import (
    BuyerType,
    Commodity,
    CommodityCategory,
    DataSource,
    HistoricalInfrastructureRecord,
    Location,
    SourceAttribution,
    SourceType,
    SourceVerificationStatus,
    StorageType,
    VehicleTypeEnum,
)
from app.modules.intelligence.service import create_buyer_directory_entry, record_market_price
from app.modules.logistics.service import (
    create_collection_centre,
    create_historical_infrastructure_record,
    create_logistics_provider,
    create_storage_facility,
)
from app.schemas.intelligence import (
    BuyerDirectoryCreate,
    BuyerPreferredCategoryCreate,
    BuyerPreferredCommodityCreate,
    MarketPriceRecordCreate,
)
from app.schemas.logistics import (
    CollectionCentreCreate,
    HistoricalInfrastructureRecordCreate,
    LogisticsProviderCreate,
    StorageFacilityCreate,
    TransportRateCardCreate,
    VehicleCreate,
)
from app.schemas.marketplace import LocationCreate


# Known Talukas in Pune & Western Maharashtra region
PUNE_TALUKAS = {
    "haveli", "baramati", "junnar", "khed", "shirur", "indapur",
    "daund", "ambegaon", "purandar", "maval", "mulshi", "velhe", "bhor", "pune city"
}

DISALLOWED_DAIRY_KEYWORDS = ["milk", "dairy", "paneer", "ghee", "butter", "cheese", "curd", "khoya", "lassi"]
DISALLOWED_NON_CROP_KEYWORDS = ["poultry", "meat", "fish", "egg", "leather"]

CATEGORY_ALIASES: dict[str, CommodityCategory] = {
    "fruits": CommodityCategory.FRUITS,
    "fresh fruits": CommodityCategory.FRUITS,
    "fruit pulps": CommodityCategory.FRUITS,
    "juices": CommodityCategory.FRUITS,
    "guava": CommodityCategory.FRUITS,
    "vegetables": CommodityCategory.VEGETABLES,
    "mixed vegetables": CommodityCategory.VEGETABLES,
    "fruits & vegetables": CommodityCategory.VEGETABLES,
    "grains": CommodityCategory.GRAINS,
    "food grains": CommodityCategory.GRAINS,
    "pulses": CommodityCategory.PULSES,
    "spices": CommodityCategory.SPICES,
    "coconut": CommodityCategory.OTHER_CROPS,
    "other crops": CommodityCategory.OTHER_CROPS,
    "agri commodities": CommodityCategory.OTHER_CROPS,
    "food commodities": CommodityCategory.OTHER_CROPS,
    "food ingredients": CommodityCategory.OTHER_CROPS,
    "processed agri-products": CommodityCategory.OTHER_CROPS,
    "fresh/frozen/dehydrated products": CommodityCategory.OTHER_CROPS,
    "beverages": CommodityCategory.OTHER_CROPS,
}

COMMODITY_EXACT_ALIASES: dict[str, str] = {
    "onion": "Onion (Nashik Red)",
    "tomato": "Tomato (Hybrid)",
    "green chilli": "Green Chilli",
    "chilly capsicum": "Green Chilli",
    "capsicum": "Green Chilli",
    "brinjal": "Brinjal (Round Green)",
    "potato": "Potato (Jyoti)",
    "alphonso mango": "Mango (Alphonso)",
    "mango": "Mango (Alphonso)",
    "banana": "Banana (Robusta)",
    "grapes": "Grapes (Thompson Seedless)",
    "oranges": "Orange (Nagpur)",
    "orange": "Orange (Nagpur)",
    "pomegranate": "Pomegranate (Bhagwa)",
    "pomegranate arils": "Pomegranate (Bhagwa)",
    "apples": "Apple (Royal Delicious)",
    "apple": "Apple (Royal Delicious)",
    "rice": "Rice (Sona Masoori)",
    "sweet corn": "Maize (Yellow Dent)",
    "maize": "Maize (Yellow Dent)",
    "turmeric": "Turmeric (Salem)",
    "chana": "Chana (Desi Chickpea)",
    "bengal gram(gram)(whole)": "Chana (Desi Chickpea)",
    "gram raw(chholia)": "Chana (Desi Chickpea)",
    "moong": "Moong (Green Gram)",
    "green gram(moong)(whole)": "Moong (Green Gram)",
    "urad": "Urad (Black Gram)",
    "black gram (urad)(whole)": "Urad (Black Gram)",
    "black gram(urd beans)(whole)": "Urad (Black Gram)",
    "lentil(masur)(whole)": "Masoor (Red Lentil)",
    "masoor": "Masoor (Red Lentil)",
    "arhar (tur/red gram)(whole)": "Tur / Arhar (Pigeon Pea)",
    "red gram/arhar/tur(whole)": "Tur / Arhar (Pigeon Pea)",
    "pigeon pea (arhar/tur)(whole)": "Tur / Arhar (Pigeon Pea)",
    "tur / arhar": "Tur / Arhar (Pigeon Pea)",
    "bajra(pearl millet/cumbu)": "Bajra (Pearl Millet)",
    "bajra": "Bajra (Pearl Millet)",
    "jowar(sorghum)": "Jowar (Sorghum)",
    "jowar": "Jowar (Sorghum)",
    "wheat": "Wheat (Sharbati)",
    "flour": "Wheat (Sharbati)",
    "sugar": "Sugarcane",
    "sugarcane": "Sugarcane",
    "cabbage": "Cabbage",
    "cauliflower": "Cauliflower",
    "soybean": "Soybean (Yellow)",
    "soyabean": "Soybean (Yellow)",
    "cotton": "Cotton (Medium Staple)",
    "groundnut": "Groundnut (Bold)",
    "mustard": "Mustard (Black)",
    "coriander(leaves)": "Coriander / Dhania",
    "coriander / dhania": "Coriander / Dhania",
    "corriander seed": "Coriander / Dhania",
    "coriander seed": "Coriander / Dhania",
    "cumin seed(jeera)": "Cumin / Jeera (Unjha)",
    "black pepper": "Black Pepper (Malabar)",
}


def validate_crop_only(name_or_text: str) -> None:
    """Strictly enforces zero dairy and zero non-crop produce across all inputs."""
    text_lower = name_or_text.lower()
    for kw in DISALLOWED_DAIRY_KEYWORDS:
        if kw in text_lower:
            raise ApiError(
                400,
                "disallowed_category",
                f"Dairy product '{name_or_text}' is strictly forbidden. AgriMandi supports agricultural crops only.",
            )
    for kw in DISALLOWED_NON_CROP_KEYWORDS:
        if kw in text_lower:
            raise ApiError(
                400,
                "disallowed_category",
                f"Non-crop entity '{name_or_text}' is strictly forbidden. AgriMandi supports agricultural crops only.",
            )


def ensure_data_source(
    db: Session,
    name: str,
    source_type: SourceType,
    source_url: str | None = None,
    notes: str | None = None,
    is_mock: bool = False,
    confidence_score: float | None = 0.85,
) -> DataSource:
    ds = db.scalar(select(DataSource).where(DataSource.name == name))
    if not ds:
        ds = DataSource(
            name=name,
            source_type=source_type,
            source_url=source_url,
            checked_at=datetime.now(timezone.utc),
            verification_status=SourceVerificationStatus.VERIFIED if not is_mock else SourceVerificationStatus.UNVERIFIED,
            confidence_score=Decimal(str(confidence_score)) if confidence_score is not None else None,
            is_mock=is_mock,
            notes=notes,
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
    return ds


def resolve_commodity_or_category(db: Session, raw_name: str) -> tuple[Commodity | None, CommodityCategory | None]:
    """Deterministically resolves raw name into either a canonical Commodity or a broad CommodityCategory."""
    validate_crop_only(raw_name)
    cleaned = raw_name.strip().lower()

    # 1. Check broad category alias
    if cleaned in CATEGORY_ALIASES:
        return None, CATEGORY_ALIASES[cleaned]

    # 2. Check exact alias dictionary
    if cleaned in COMMODITY_EXACT_ALIASES:
        target_name = COMMODITY_EXACT_ALIASES[cleaned]
        comm = db.scalar(select(Commodity).where(func.lower(Commodity.name) == target_name.lower()))
        if comm:
            return comm, None

    # 3. Direct match in DB
    comm = db.scalar(select(Commodity).where(func.lower(Commodity.name) == cleaned))
    if comm:
        return comm, None

    # 4. Fallback search (exact substring match)
    comm = db.scalar(select(Commodity).where(func.lower(Commodity.name).like(f"%{cleaned}%")))
    if comm:
        return comm, None

    raise ApiError(404, "commodity_not_found", f"Could not map commodity/category '{raw_name}' to crop catalog.")


def normalize_commodity(db: Session, raw_name: str) -> Commodity:
    comm, _ = resolve_commodity_or_category(db, raw_name)
    if not comm:
        raise ApiError(400, "expected_commodity_got_category", f"'{raw_name}' is a broad category, not a specific crop.")
    return comm


class IngestionPipeline:
    """Idempotent ingestion and normalization pipeline for research datasets."""

    def __init__(self, db: Session, data_source: DataSource):
        self.db = db
        self.data_source = data_source

    def ingest_buyer_record(
        self,
        business_name: str,
        buyer_type: BuyerType,
        location_data: dict[str, Any],
        commodities: list[dict[str, Any]],
        external_id: str | None = None,
        contact_person: str | None = None,
        contact_phone: str | None = None,
        contact_email: str | None = None,
        procurement_radius_km: float | None = None,
        daily_capacity_mt: float | None = None,
        typical_payment_terms: str | None = None,
        notes: str | None = None,
        confidence_score: float = 0.90,
    ) -> Any:
        validate_crop_only(business_name)

        pref_creates: list[BuyerPreferredCommodityCreate] = []
        pref_cats: list[BuyerPreferredCategoryCreate] = []

        for c in commodities:
            raw_comm = c["commodity_name"]
            comm, cat = resolve_commodity_or_category(self.db, raw_comm)
            if comm:
                pref_creates.append(
                    BuyerPreferredCommodityCreate(
                        commodity_id=comm.id,
                        min_quality_grade=c.get("min_quality_grade"),
                        typical_volume_quintals=Decimal(str(c["typical_volume_quintals"])) if "typical_volume_quintals" in c and c["typical_volume_quintals"] else None,
                        max_price_per_unit=Decimal(str(c["max_price_per_unit"])) if "max_price_per_unit" in c and c["max_price_per_unit"] else None,
                    )
                )
            elif cat:
                pref_cats.append(
                    BuyerPreferredCategoryCreate(
                        category=cat,
                        notes=f"Broad category demand: {raw_comm}",
                    )
                )

        # Do NOT invent coordinates if lat/lng are unverified/missing
        has_coords = (
            "latitude" in location_data
            and location_data["latitude"] is not None
            and "longitude" in location_data
            and location_data["longitude"] is not None
        )

        loc_create = LocationCreate(
            name=location_data["name"],
            village=location_data.get("village"),
            taluka=location_data.get("taluka"),
            district=location_data.get("district", "Pune"),
            state=location_data.get("state", "Maharashtra"),
            postal_code=location_data.get("postal_code"),
            latitude=Decimal(str(location_data["latitude"])) if has_coords else None,
            longitude=Decimal(str(location_data["longitude"])) if has_coords else None,
        )

        entry_payload = BuyerDirectoryCreate(
            external_id=external_id,
            business_name=business_name.strip(),
            buyer_type=buyer_type,
            location=loc_create,
            contact_person=contact_person,
            contact_phone=contact_phone,
            contact_email=contact_email,
            procurement_radius_km=Decimal(str(procurement_radius_km)) if procurement_radius_km is not None else None,
            daily_capacity_mt=Decimal(str(daily_capacity_mt)) if daily_capacity_mt is not None else None,
            typical_payment_terms=typical_payment_terms,
            notes=notes,
            preferred_commodities=pref_creates,
            preferred_categories=pref_cats,
        )

        return create_buyer_directory_entry(
            self.db,
            entry_payload,
            data_source_id=self.data_source.id,
            confidence_score=confidence_score,
            verification_status=self.data_source.verification_status,
        )

    def ingest_historical_infrastructure_record(
        self,
        external_id: str,
        name: str,
        lead_type: str,
        commodity_sector: str,
        district_area: str | None = None,
        state: str = "Maharashtra",
        coverage_label: str | None = None,
        location_granularity: str | None = None,
        evidence_type: str = "Government cold-chain project record",
        government_project_status: str | None = None,
        evidence_date: date | None = None,
        current_service_status: str = "Unknown",
        verification_status: str = "Historical infrastructure evidence",
        location_data: dict[str, Any] | None = None,
        notes: str | None = None,
        confidence_score: float = 0.85,
    ) -> Any:
        loc_create = None
        if location_data:
            has_coords = (
                "latitude" in location_data
                and location_data["latitude"] is not None
                and "longitude" in location_data
                and location_data["longitude"] is not None
            )
            loc_create = LocationCreate(
                name=location_data["name"],
                village=location_data.get("village"),
                taluka=location_data.get("taluka"),
                district=location_data.get("district", "Pune"),
                state=location_data.get("state", "Maharashtra"),
                postal_code=location_data.get("postal_code"),
                latitude=Decimal(str(location_data["latitude"])) if has_coords else None,
                longitude=Decimal(str(location_data["longitude"])) if has_coords else None,
            )

        payload = HistoricalInfrastructureRecordCreate(
            external_id=external_id,
            name=name.strip(),
            lead_type=lead_type,
            commodity_sector=commodity_sector,
            district_area=district_area,
            state=state,
            coverage_label=coverage_label,
            location_granularity=location_granularity,
            evidence_type=evidence_type,
            government_project_status=government_project_status,
            evidence_date=evidence_date,
            current_service_status=current_service_status,
            verification_status=verification_status,
            location=loc_create,
            notes=notes,
        )

        return create_historical_infrastructure_record(
            self.db,
            payload,
            data_source_id=self.data_source.id,
            confidence_score=confidence_score,
        )
