from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.entities import (
    BuyerType,
    Commodity,
    CommodityCategory,
    DataSource,
    Location,
    LogisticsProvider,
    Order,
    OrderStatus,
    ProduceLot,
    ProduceLotStatus,
    Role,
    RoleName,
    Shipment,
    ShipmentStatus,
    SourceAttribution,
    SourceType,
    SourceVerificationStatus,
    StorageFacility,
    StorageType,
    User,
    UserRole,
    Vehicle,
    VehicleTypeEnum,
)
from app.modules.ingestion.pipeline import (
    IngestionPipeline,
    ensure_data_source,
    normalize_commodity,
    validate_crop_only,
)
from app.modules.intelligence.service import (
    create_buyer_directory_entry,
    list_buyer_directory_entries,
    list_market_prices,
    record_market_price,
)
from app.modules.logistics.service import (
    create_collection_centre,
    create_logistics_provider,
    create_shipment,
    create_storage_facility,
    list_collection_centres,
    list_logistics_providers,
    list_storage_facilities,
    record_shipment_event,
)
from app.schemas.intelligence import (
    BuyerDirectoryCreate,
    BuyerPreferredCommodityCreate,
    MarketPriceRecordCreate,
)
from app.schemas.logistics import (
    CollectionCentreCreate,
    LogisticsProviderCreate,
    ShipmentCreate,
    ShipmentEventCreate,
    StorageFacilityCreate,
    TransportRateCardCreate,
    VehicleCreate,
)
from app.schemas.marketplace import LocationCreate


def test_zero_dairy_enforcement():
    """Verifies that dairy inputs are strictly rejected across all pipeline interfaces."""
    with pytest.raises(ApiError) as exc:
        validate_crop_only("Pasteurized Cow Milk 1L")
    assert exc.value.code == "disallowed_category"

    with pytest.raises(ApiError) as exc:
        validate_crop_only("Fresh Malai Paneer 500g")
    assert exc.value.code == "disallowed_category"

    with pytest.raises(ApiError) as exc:
        validate_crop_only("Pure Cow Ghee 15kg Tin")
    assert exc.value.code == "disallowed_category"


def test_buyer_directory_creation_and_provenance(db: Session):
    """Tests creating and querying buyer directory entries with crop preferences and source attribution."""
    onion = db.scalar(select(Commodity).where(Commodity.category == CommodityCategory.VEGETABLES))
    assert onion is not None

    ds = ensure_data_source(
        db,
        name="Pune APMC Bulk Buyer Survey 2026",
        source_type=SourceType.BUYER_RESEARCH,
        source_url="https://agri.maharashtra.gov.in/apmc/pune",
        notes="Field verified APMC commission agents and exporters in Gultekdi yard",
        confidence_score=0.92,
    )

    payload = BuyerDirectoryCreate(
        business_name="Maharashtra Agro Exports Ltd",
        buyer_type=BuyerType.EXPORTER,
        location=LocationCreate(
            name="Gultekdi Market Yard Gate 4",
            taluka="Haveli",
            district="Pune",
            state="Maharashtra",
            postal_code="411037",
            latitude=Decimal("18.4901"),
            longitude=Decimal("73.8682"),
        ),
        contact_person="Vikas Deshmukh",
        contact_phone="+91 9822012345",
        procurement_radius_km=Decimal("120.00"),
        daily_capacity_mt=Decimal("45.000"),
        typical_payment_terms="T+2 Days RTGS",
        preferred_commodities=[
            BuyerPreferredCommodityCreate(
                commodity_id=onion.id,
                min_quality_grade="Grade A",
                typical_volume_quintals=Decimal("200.000"),
                max_price_per_unit=Decimal("2600.00"),
            )
        ],
    )

    entry = create_buyer_directory_entry(
        db,
        payload,
        data_source_id=ds.id,
        confidence_score=0.92,
        verification_status=SourceVerificationStatus.VERIFIED,
    )

    assert entry.business_name == "Maharashtra Agro Exports Ltd"
    assert entry.buyer_type == BuyerType.EXPORTER
    assert entry.location.district == "Pune"
    assert len(entry.preferred_commodities) == 1
    assert entry.preferred_commodities[0].commodity_name == onion.name

    # Query attribution
    attr = db.scalar(
        select(SourceAttribution).where(
            SourceAttribution.entity_type == "buyer_directory_entry",
            SourceAttribution.entity_id == entry.id,
        )
    )
    assert attr is not None
    assert attr.data_source_id == ds.id
    assert attr.confidence_score == Decimal("0.920")

    # Filter directory
    results = list_buyer_directory_entries(db, district="Pune", category=CommodityCategory.VEGETABLES)
    assert any(b.id == entry.id for b in results)


def test_logistics_fleet_and_rate_cards(db: Session):
    """Tests creating logistics providers, multi-vehicle fleets with cold-chain specs, and freight rate cards."""
    ds = ensure_data_source(
        db,
        name="Western Maharashtra Agri Logistics Network",
        source_type=SourceType.LOGISTICS_RESEARCH,
        notes="Verified fleet operators across Pune, Nashik, and Ahmednagar",
        confidence_score=0.88,
    )

    payload = LogisticsProviderCreate(
        name="Sahyadri Reefer & Express Logistics",
        operating_scope="interstate",
        has_cold_chain=True,
        contact_phone="+91 9423098765",
        primary_location=LocationCreate(
            name="Hadapsar Transport Hub",
            taluka="Haveli",
            district="Pune",
            state="Maharashtra",
            postal_code="411028",
            latitude=Decimal("18.5089"),
            longitude=Decimal("73.9260"),
        ),
        vehicles=[
            VehicleCreate(
                registration_number=f"MH12AB{uuid.uuid4().hex[:4].upper()}",
                vehicle_type=VehicleTypeEnum.REEFER_VAN,
                model_name="Eicher Pro 2049 Reefer",
                payload_capacity_kg=Decimal("2500.00"),
                volumetric_capacity_cbm=Decimal("14.50"),
                is_refrigerated=True,
                temp_min_celsius=Decimal("2.0"),
                temp_max_celsius=Decimal("12.0"),
            ),
            VehicleCreate(
                registration_number=f"MH12CD{uuid.uuid4().hex[:4].upper()}",
                vehicle_type=VehicleTypeEnum.MINI_TRUCK,
                model_name="Tata Ace Gold",
                payload_capacity_kg=Decimal("750.00"),
                volumetric_capacity_cbm=Decimal("4.50"),
                is_refrigerated=False,
            ),
        ],
        rate_cards=[
            TransportRateCardCreate(
                vehicle_type=VehicleTypeEnum.REEFER_VAN,
                base_fare=Decimal("1500.00"),
                per_km_rate=Decimal("28.50"),
                min_distance_km=Decimal("30.00"),
                reefer_surcharge_per_km=Decimal("6.00"),
                loading_unloading_charge=Decimal("400.00"),
            )
        ],
    )

    provider = create_logistics_provider(db, payload, data_source_id=ds.id, confidence_score=0.88)
    assert provider.name == "Sahyadri Reefer & Express Logistics"
    assert provider.has_cold_chain is True
    assert len(provider.vehicles) == 2
    assert len(provider.rate_cards) == 1
    assert provider.rate_cards[0].per_km_rate == Decimal("28.50")

    providers = list_logistics_providers(db, has_cold_chain=True)
    assert any(p.id == provider.id for p in providers)


def test_storage_facility_and_collection_centres(db: Session):
    """Tests storage facilities (cold stores/dry godowns) and collection packhouses."""
    storage_payload = StorageFacilityCreate(
        name="Baramati Integrated Agri Cold Store",
        facility_type=StorageType.COLD_STORAGE,
        operator_name="Baramati Agro Infrastructure Corp",
        total_capacity_mt=Decimal("5000.000"),
        available_capacity_mt=Decimal("3200.000"),
        is_cold_chain=True,
        temp_min_celsius=Decimal("0.0"),
        temp_max_celsius=Decimal("8.0"),
        humidity_controlled=True,
        daily_rate_per_mt=Decimal("45.00"),
        location=LocationCreate(
            name="MIDC Baramati Agro Zone",
            taluka="Baramati",
            district="Pune",
            state="Maharashtra",
            postal_code="413133",
            latitude=Decimal("18.1500"),
            longitude=Decimal("74.5800"),
        ),
    )
    storage = create_storage_facility(db, storage_payload)
    assert storage.facility_type == StorageType.COLD_STORAGE
    assert storage.total_capacity_mt == Decimal("5000.000")
    assert storage.available_capacity_mt == Decimal("3200.000")

    cc_payload = CollectionCentreCreate(
        name="Junnar Tomato & Veg Aggregation Packhouse",
        operator_name="Junnar Farmer Cooperative Union",
        has_grading_line=True,
        has_precooling=True,
        weighbridge_capacity_mt=Decimal("50.00"),
        max_throughput_mt_day=Decimal("120.00"),
        location=LocationCreate(
            name="Narayangaon Mandi Yard",
            taluka="Junnar",
            district="Pune",
            state="Maharashtra",
            postal_code="410504",
            latitude=Decimal("19.1200"),
            longitude=Decimal("73.9700"),
        ),
    )
    cc = create_collection_centre(db, cc_payload)
    assert cc.has_grading_line is True
    assert cc.has_precooling is True

    # List
    storages = list_storage_facilities(db, is_cold_chain=True, district="Pune")
    assert any(s.id == storage.id for s in storages)
    centres = list_collection_centres(db, district="Pune")
    assert any(c.id == cc.id for c in centres)


def test_market_price_arrivals(db: Session):
    """Tests recording and querying historical APMC market price and arrival metrics."""
    onion = db.scalar(select(Commodity).where(Commodity.name == "Onion (Nashik Red)"))
    assert onion is not None

    price_payload = MarketPriceRecordCreate(
        commodity_id=onion.id,
        price_date=date(2026, 8, 28),
        variety="Nashik Red",
        grade="Grade A",
        min_price=Decimal("1900.00"),
        max_price=Decimal("2650.00"),
        modal_price=Decimal("2400.00"),
        price_unit="Rs/quintal",
        arrivals_quantity=Decimal("3800.000"),
        arrivals_unit="quintal",
        market_location=LocationCreate(
            name="Pune APMC Market Yard",
            taluka="Haveli",
            district="Pune",
            state="Maharashtra",
            postal_code="411037",
        ),
    )

    rec = record_market_price(db, price_payload)
    assert rec.modal_price == Decimal("2400.00")
    assert rec.arrivals_quantity == Decimal("3800.000")

    prices = list_market_prices(db, commodity_id=onion.id)
    assert len(prices) >= 1
    assert prices[0].commodity_name == "Onion (Nashik Red)"


def test_ingestion_pipeline_end_to_end(db: Session):
    """Tests the generic IngestionPipeline normalizing, geocoding, and attributing data."""
    ds = ensure_data_source(
        db,
        name="Ingestion Test Source",
        source_type=SourceType.BUYER_RESEARCH,
        confidence_score=0.95,
    )
    pipeline = IngestionPipeline(db, ds)

    # Ingest Buyer Record with unnormalized commodity input
    buyer = pipeline.ingest_buyer_record(
        business_name="Sahyadri Agro Processing Hub",
        buyer_type=BuyerType.PROCESSOR,
        location_data={
            "name": "Baramati Industrial Area Plot 12",
            "taluka": "Baramati",
            "district": "Pune",
            "state": "Maharashtra",
            "postal_code": "413133",
            "latitude": 18.155,
            "longitude": 74.575,
        },
        commodities=[
            {
                "commodity_name": "Onion",  # Unnormalized: resolves to Onion (Nashik Red)
                "min_quality_grade": "Grade A",
                "typical_volume_quintals": 500,
                "max_price_per_unit": 2500,
            }
        ],
        daily_capacity_mt=50.0,
    )

    assert buyer.business_name == "Sahyadri Agro Processing Hub"
    assert buyer.daily_capacity_mt == Decimal("50.000")
    assert len(buyer.preferred_commodities) == 1
    assert "Onion" in buyer.preferred_commodities[0].commodity_name


def test_api_intelligence_and_logistics_endpoints(client: TestClient, db: Session):
    """Tests the public and operational query endpoints under /api/v1/intelligence and /api/v1/logistics."""
    res = client.get("/api/v1/intelligence/buyers")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/api/v1/intelligence/market-prices")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/api/v1/logistics/providers")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/api/v1/logistics/storage-facilities")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/api/v1/logistics/collection-centres")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_broad_category_preferences_and_filtering(db: Session):
    """Verifies that broad category demands (e.g. Fruits, Vegetables) are preserved separately from specific crops."""
    ds = ensure_data_source(db, name="Category Test Source", source_type=SourceType.BUYER_RESEARCH)
    pipeline = IngestionPipeline(db, ds)

    buyer = pipeline.ingest_buyer_record(
        external_id="B-TEST-CAT-01",
        business_name="Pune Wholesale Fresh Produce Network",
        buyer_type=BuyerType.WHOLESALER,
        location_data={"name": "Gultekdi Market Yard", "district": "Pune"},
        commodities=[
            {"commodity_name": "Fruits"},       # Broad category
            {"commodity_name": "Vegetables"},   # Broad category
            {"commodity_name": "Onion"},        # Specific crop
        ],
    )

    assert buyer.external_id == "B-TEST-CAT-01"
    assert len(buyer.preferred_categories) == 2
    cat_enums = {c.category for c in buyer.preferred_categories}
    assert CommodityCategory.FRUITS in cat_enums
    assert CommodityCategory.VEGETABLES in cat_enums

    assert len(buyer.preferred_commodities) == 1
    assert "Onion" in buyer.preferred_commodities[0].commodity_name

    # Filter directory by category Fruits
    fruit_buyers = list_buyer_directory_entries(db, category=CommodityCategory.FRUITS)
    assert any(b.id == buyer.id for b in fruit_buyers)


def test_historical_infrastructure_isolation(db: Session):
    """Verifies that historical government cold-chain project records are isolated from active logistics providers."""
    ds = ensure_data_source(db, name="MoFPI Cold Chain Survey", source_type=SourceType.LOGISTICS_RESEARCH)
    pipeline = IngestionPipeline(db, ds)

    infra = pipeline.ingest_historical_infrastructure_record(
        external_id="LOG-PUN-001",
        name="Western Hill Foods Ltd",
        lead_type="F&V cold-chain / food-processing lead",
        commodity_sector="F&V",
        district_area="Pune",
        state="Maharashtra",
        evidence_type="Government cold-chain project record",
        government_project_status="Completed",
        evidence_date=date(2012, 7, 31),
        current_service_status="Unknown",
        verification_status="Historical infrastructure evidence",
        location_data={"name": "Pune District Cold Project Area", "district": "Pune"},
        confidence_score=0.85,
    )

    assert infra.external_id == "LOG-PUN-001"
    assert infra.verification_status == "Historical infrastructure evidence"
    assert infra.current_service_status == "Unknown"

    # Verify that active logistics_providers table is NOT contaminated
    active_providers = list_logistics_providers(db)
    assert not any(p.name == "Western Hill Foods Ltd" for p in active_providers)


def test_external_id_idempotent_ingestion(db: Session):
    """Verifies that re-running ingestion with the same external_id performs an idempotent retrieval without duplicate rows."""
    ds = ensure_data_source(db, name="Idempotent Test Source", source_type=SourceType.BUYER_RESEARCH)
    pipeline = IngestionPipeline(db, ds)

    b1 = pipeline.ingest_buyer_record(
        external_id="B-IDEM-001",
        business_name="Unique Buyer Trading Co",
        buyer_type=BuyerType.EXPORTER,
        location_data={"name": "Baramati Mandi", "district": "Pune"},
        commodities=[{"commodity_name": "Tomato"}],
    )
    b2 = pipeline.ingest_buyer_record(
        external_id="B-IDEM-001",
        business_name="Unique Buyer Trading Co (Duplicate Call)",
        buyer_type=BuyerType.EXPORTER,
        location_data={"name": "Baramati Mandi", "district": "Pune"},
        commodities=[{"commodity_name": "Tomato"}],
    )

    assert b1.id == b2.id
    assert b1.business_name == "Unique Buyer Trading Co"


def test_textual_location_without_hallucinated_coordinates(db: Session):
    """Verifies that textual locations with unknown coordinates leave geo_point, latitude, longitude as NULL."""
    ds = ensure_data_source(db, name="Text Loc Test Source", source_type=SourceType.BUYER_RESEARCH)
    pipeline = IngestionPipeline(db, ds)

    buyer = pipeline.ingest_buyer_record(
        external_id="B-TEXT-LOC-01",
        business_name="Rural FPC Procurement Hub",
        buyer_type=BuyerType.WHOLESALER,
        location_data={
            "name": "Darakwadi, Khed, Pune 412402",
            "village": "Darakwadi",
            "taluka": "Khed",
            "district": "Pune",
            "state": "Maharashtra",
            "postal_code": "412402",
            # No latitude or longitude provided
        },
        commodities=[{"commodity_name": "Onion"}],
    )

    assert buyer.location.latitude is None
    assert buyer.location.longitude is None
    loc_entity = db.get(Location, buyer.location.id)
    assert loc_entity is not None
    assert loc_entity.geo_point is None
    assert buyer.location.taluka == "Khed"
    assert buyer.location.postal_code == "412402"

