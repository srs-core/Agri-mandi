from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.entities import (
    CollectionCentre,
    DataSource,
    HistoricalInfrastructureRecord,
    Location,
    LogisticsProvider,
    Order,
    Shipment,
    ShipmentEvent,
    ShipmentPlan,
    ShipmentStatus,
    SourceAttribution,
    SourceVerificationStatus,
    StorageFacility,
    StorageType,
    TransportRateCard,
    Vehicle,
    VehicleTypeEnum,
)
from app.modules.marketplace.service import _create_or_get_location, _serialize_location
from app.schemas.logistics import (
    CollectionCentreCreate,
    CollectionCentreResponse,
    HistoricalInfrastructureRecordCreate,
    HistoricalInfrastructureRecordResponse,
    LogisticsProviderCreate,
    LogisticsProviderResponse,
    ShipmentCreate,
    ShipmentEventCreate,
    ShipmentEventResponse,
    ShipmentResponse,
    StorageFacilityCreate,
    StorageFacilityResponse,
    TransportRateCardCreate,
    TransportRateCardResponse,
    VehicleCreate,
    VehicleResponse,
)


# --- Logistics Providers & Fleets ---

def create_logistics_provider(
    db: Session,
    payload: LogisticsProviderCreate,
    data_source_id: UUID | None = None,
    confidence_score: float | None = None,
) -> LogisticsProviderResponse:
    primary_location = None
    if payload.primary_location or payload.primary_location_id:
        primary_location = _create_or_get_location(db, payload.primary_location, payload.primary_location_id)

    provider = LogisticsProvider(
        name=payload.name,
        registered_transporter_profile_id=payload.registered_transporter_profile_id,
        primary_location_id=primary_location.id if primary_location else None,
        operating_scope=payload.operating_scope,
        has_cold_chain=payload.has_cold_chain,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        is_active=True,
    )
    db.add(provider)
    db.flush()

    if payload.vehicles:
        for v in payload.vehicles:
            veh = Vehicle(
                provider_id=provider.id,
                registration_number=v.registration_number,
                vehicle_type=v.vehicle_type,
                model_name=v.model_name,
                payload_capacity_kg=v.payload_capacity_kg,
                volumetric_capacity_cbm=v.volumetric_capacity_cbm,
                is_refrigerated=v.is_refrigerated,
                temp_min_celsius=v.temp_min_celsius,
                temp_max_celsius=v.temp_max_celsius,
                is_available=v.is_available,
            )
            db.add(veh)

    if payload.rate_cards:
        for rc in payload.rate_cards:
            card = TransportRateCard(
                provider_id=provider.id,
                vehicle_type=rc.vehicle_type,
                base_fare=rc.base_fare,
                per_km_rate=rc.per_km_rate,
                min_distance_km=rc.min_distance_km,
                reefer_surcharge_per_km=rc.reefer_surcharge_per_km,
                loading_unloading_charge=rc.loading_unloading_charge,
                valid_from=rc.valid_from,
                valid_to=rc.valid_to,
                is_active=True,
            )
            db.add(card)

    if data_source_id:
        ds = db.get(DataSource, data_source_id)
        if ds:
            attr = SourceAttribution(
                data_source_id=ds.id,
                entity_type="logistics_provider",
                entity_id=provider.id,
                verification_status=SourceVerificationStatus.UNVERIFIED,
                confidence_score=confidence_score,
            )
            db.add(attr)

    db.commit()
    db.refresh(provider)
    return _serialize_logistics_provider(provider)


def list_logistics_providers(
    db: Session,
    has_cold_chain: bool | None = None,
    operating_scope: str | None = None,
) -> list[LogisticsProviderResponse]:
    stmt = select(LogisticsProvider).where(LogisticsProvider.is_active.is_(True))
    if has_cold_chain is not None:
        stmt = stmt.where(LogisticsProvider.has_cold_chain == has_cold_chain)
    if operating_scope:
        stmt = stmt.where(LogisticsProvider.operating_scope == operating_scope)

    stmt = stmt.order_by(LogisticsProvider.name)
    providers = db.scalars(stmt).all()
    return [_serialize_logistics_provider(p) for p in providers]


def _serialize_logistics_provider(provider: LogisticsProvider) -> LogisticsProviderResponse:
    vehicles = [
        VehicleResponse(
            id=v.id,
            provider_id=v.provider_id,
            registration_number=v.registration_number,
            vehicle_type=v.vehicle_type,
            model_name=v.model_name,
            payload_capacity_kg=v.payload_capacity_kg,
            volumetric_capacity_cbm=v.volumetric_capacity_cbm,
            is_refrigerated=v.is_refrigerated,
            temp_min_celsius=v.temp_min_celsius,
            temp_max_celsius=v.temp_max_celsius,
            is_available=v.is_available,
            created_at=v.created_at,
        )
        for v in provider.vehicles
    ]
    rate_cards = [
        TransportRateCardResponse(
            id=rc.id,
            provider_id=rc.provider_id,
            vehicle_type=rc.vehicle_type,
            base_fare=rc.base_fare,
            per_km_rate=rc.per_km_rate,
            min_distance_km=rc.min_distance_km,
            reefer_surcharge_per_km=rc.reefer_surcharge_per_km,
            loading_unloading_charge=rc.loading_unloading_charge,
            valid_from=rc.valid_from,
            valid_to=rc.valid_to,
            is_active=rc.is_active,
            created_at=rc.created_at,
        )
        for rc in provider.rate_cards
    ]
    return LogisticsProviderResponse(
        id=provider.id,
        name=provider.name,
        registered_transporter_profile_id=provider.registered_transporter_profile_id,
        primary_location=_serialize_location(provider.primary_location),
        operating_scope=provider.operating_scope,
        has_cold_chain=provider.has_cold_chain,
        contact_phone=provider.contact_phone,
        contact_email=provider.contact_email,
        is_active=provider.is_active,
        vehicles=vehicles,
        rate_cards=rate_cards,
        created_at=provider.created_at,
    )


# --- Storage Facilities ---

def create_storage_facility(
    db: Session,
    payload: StorageFacilityCreate,
    data_source_id: UUID | None = None,
    confidence_score: float | None = None,
) -> StorageFacilityResponse:
    location = _create_or_get_location(db, payload.location, payload.location_id)

    facility = StorageFacility(
        name=payload.name,
        facility_type=payload.facility_type,
        location_id=location.id,
        operator_name=payload.operator_name,
        total_capacity_mt=payload.total_capacity_mt,
        available_capacity_mt=payload.available_capacity_mt,
        is_cold_chain=payload.is_cold_chain,
        temp_min_celsius=payload.temp_min_celsius,
        temp_max_celsius=payload.temp_max_celsius,
        humidity_controlled=payload.humidity_controlled,
        daily_rate_per_mt=payload.daily_rate_per_mt,
        is_active=True,
    )
    db.add(facility)
    db.flush()

    if data_source_id:
        ds = db.get(DataSource, data_source_id)
        if ds:
            attr = SourceAttribution(
                data_source_id=ds.id,
                entity_type="storage_facility",
                entity_id=facility.id,
                verification_status=SourceVerificationStatus.UNVERIFIED,
                confidence_score=confidence_score,
            )
            db.add(attr)

    db.commit()
    db.refresh(facility)
    return _serialize_storage_facility(facility)


def list_storage_facilities(
    db: Session,
    is_cold_chain: bool | None = None,
    facility_type: StorageType | None = None,
    district: str | None = None,
    taluka: str | None = None,
) -> list[StorageFacilityResponse]:
    stmt = select(StorageFacility).join(Location, StorageFacility.location_id == Location.id).where(StorageFacility.is_active.is_(True))
    if is_cold_chain is not None:
        stmt = stmt.where(StorageFacility.is_cold_chain == is_cold_chain)
    if facility_type:
        stmt = stmt.where(StorageFacility.facility_type == facility_type)
    if district:
        stmt = stmt.where(func.lower(Location.district) == district.strip().lower())
    if taluka:
        stmt = stmt.where(func.lower(Location.taluka) == taluka.strip().lower())

    stmt = stmt.order_by(StorageFacility.name)
    facilities = db.scalars(stmt).all()
    return [_serialize_storage_facility(f) for f in facilities]


def _serialize_storage_facility(facility: StorageFacility) -> StorageFacilityResponse:
    return StorageFacilityResponse(
        id=facility.id,
        name=facility.name,
        facility_type=facility.facility_type,
        location=_serialize_location(facility.location),
        operator_name=facility.operator_name,
        total_capacity_mt=facility.total_capacity_mt,
        available_capacity_mt=facility.available_capacity_mt,
        is_cold_chain=facility.is_cold_chain,
        temp_min_celsius=facility.temp_min_celsius,
        temp_max_celsius=facility.temp_max_celsius,
        humidity_controlled=facility.humidity_controlled,
        daily_rate_per_mt=facility.daily_rate_per_mt,
        is_active=facility.is_active,
        created_at=facility.created_at,
    )


# --- Collection Centres ---

def create_collection_centre(
    db: Session,
    payload: CollectionCentreCreate,
    data_source_id: UUID | None = None,
    confidence_score: float | None = None,
) -> CollectionCentreResponse:
    location = _create_or_get_location(db, payload.location, payload.location_id)

    centre = CollectionCentre(
        name=payload.name,
        location_id=location.id,
        operator_name=payload.operator_name,
        has_grading_line=payload.has_grading_line,
        has_precooling=payload.has_precooling,
        weighbridge_capacity_mt=payload.weighbridge_capacity_mt,
        max_throughput_mt_day=payload.max_throughput_mt_day,
        is_active=True,
    )
    db.add(centre)
    db.flush()

    if data_source_id:
        ds = db.get(DataSource, data_source_id)
        if ds:
            attr = SourceAttribution(
                data_source_id=ds.id,
                entity_type="collection_centre",
                entity_id=centre.id,
                verification_status=SourceVerificationStatus.UNVERIFIED,
                confidence_score=confidence_score,
            )
            db.add(attr)

    db.commit()
    db.refresh(centre)
    return _serialize_collection_centre(centre)


def list_collection_centres(
    db: Session,
    district: str | None = None,
    taluka: str | None = None,
) -> list[CollectionCentreResponse]:
    stmt = select(CollectionCentre).join(Location, CollectionCentre.location_id == Location.id).where(CollectionCentre.is_active.is_(True))
    if district:
        stmt = stmt.where(func.lower(Location.district) == district.strip().lower())
    if taluka:
        stmt = stmt.where(func.lower(Location.taluka) == taluka.strip().lower())

    stmt = stmt.order_by(CollectionCentre.name)
    centres = db.scalars(stmt).all()
    return [_serialize_collection_centre(c) for c in centres]


def _serialize_collection_centre(centre: CollectionCentre) -> CollectionCentreResponse:
    return CollectionCentreResponse(
        id=centre.id,
        name=centre.name,
        location=_serialize_location(centre.location),
        operator_name=centre.operator_name,
        has_grading_line=centre.has_grading_line,
        has_precooling=centre.has_precooling,
        weighbridge_capacity_mt=centre.weighbridge_capacity_mt,
        max_throughput_mt_day=centre.max_throughput_mt_day,
        is_active=centre.is_active,
        created_at=centre.created_at,
    )


# --- Shipments & Tracking ---

def create_shipment(db: Session, payload: ShipmentCreate) -> ShipmentResponse:
    order = None
    if payload.order_id:
        order = db.get(Order, payload.order_id)
        if not order:
            raise ApiError(404, "order_not_found", "Order not found.")

    shipment_plan = None
    if payload.shipment_plan_id:
        shipment_plan = db.get(ShipmentPlan, payload.shipment_plan_id)
        if not shipment_plan:
            raise ApiError(404, "shipment_plan_not_found", "Shipment plan not found.")

    if not order and not shipment_plan:
        raise ApiError(422, "missing_source", "Either order_id or shipment_plan_id must be provided.")

    origin = _create_or_get_location(db, payload.origin_location, payload.origin_location_id)
    destination = _create_or_get_location(db, payload.destination_location, payload.destination_location_id)

    shipment = Shipment(
        order_id=order.id if order else None,
        shipment_plan_id=shipment_plan.id if shipment_plan else None,
        vehicle_id=payload.vehicle_id,
        provider_id=payload.provider_id,
        origin_location_id=origin.id,
        destination_location_id=destination.id,
        storage_facility_id=payload.storage_facility_id,
        collection_centre_id=payload.collection_centre_id,
        status=ShipmentStatus.SCHEDULED,
        scheduled_pickup_at=payload.scheduled_pickup_at,
        estimated_arrival_at=payload.estimated_arrival_at,
        estimated_cost=payload.estimated_cost,
        driver_name=payload.driver_name,
        driver_phone=payload.driver_phone,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return _serialize_shipment(shipment)


def record_shipment_event(db: Session, shipment_id: UUID, payload: ShipmentEventCreate) -> ShipmentEventResponse:
    shipment = db.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError(404, "shipment_not_found", "Shipment not found.")

    geo_point = None
    if payload.latitude is not None and payload.longitude is not None:
        geo_point = f"POINT({payload.longitude} {payload.latitude})"

    event = ShipmentEvent(
        shipment_id=shipment.id,
        event_type=payload.event_type,
        location_name=payload.location_name,
        geo_point=geo_point,
        notes=payload.notes,
        recorded_at=payload.recorded_at,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return ShipmentEventResponse(
        id=event.id,
        shipment_id=event.shipment_id,
        event_type=event.event_type,
        location_name=event.location_name,
        notes=event.notes,
        recorded_at=event.recorded_at,
    )


def _serialize_shipment(shipment: Shipment) -> ShipmentResponse:
    events = [
        ShipmentEventResponse(
            id=e.id,
            shipment_id=e.shipment_id,
            event_type=e.event_type,
            location_name=e.location_name,
            notes=e.notes,
            recorded_at=e.recorded_at,
        )
        for e in shipment.events
    ]
    return ShipmentResponse(
        id=shipment.id,
        order_id=shipment.order_id,
        shipment_plan_id=shipment.shipment_plan_id,
        vehicle_id=shipment.vehicle_id,
        provider_id=shipment.provider_id,
        origin_location=_serialize_location(shipment.origin_location),
        destination_location=_serialize_location(shipment.destination_location),
        storage_facility_id=shipment.storage_facility_id,
        collection_centre_id=shipment.collection_centre_id,
        status=shipment.status,
        scheduled_pickup_at=shipment.scheduled_pickup_at,
        actual_pickup_at=shipment.actual_pickup_at,
        estimated_arrival_at=shipment.estimated_arrival_at,
        actual_arrival_at=shipment.actual_arrival_at,
        estimated_cost=shipment.estimated_cost,
        actual_cost=shipment.actual_cost,
        driver_name=shipment.driver_name,
        driver_phone=shipment.driver_phone,
        events=events,
        created_at=shipment.created_at,
    )


# --- Historical Infrastructure Records (Research Evidence) ---

def create_historical_infrastructure_record(
    db: Session,
    payload: HistoricalInfrastructureRecordCreate,
    data_source_id: UUID | None = None,
    confidence_score: float | None = None,
) -> HistoricalInfrastructureRecordResponse:
    # Check for existing external_id
    existing = db.scalar(select(HistoricalInfrastructureRecord).where(HistoricalInfrastructureRecord.external_id == payload.external_id))
    if existing:
        return _serialize_historical_infrastructure_record(existing)

    location = None
    if payload.location or payload.location_id:
        location = _create_or_get_location(db, payload.location, payload.location_id)

    record = HistoricalInfrastructureRecord(
        external_id=payload.external_id,
        name=payload.name,
        lead_type=payload.lead_type,
        commodity_sector=payload.commodity_sector,
        district_area=payload.district_area,
        state=payload.state,
        coverage_label=payload.coverage_label,
        location_granularity=payload.location_granularity,
        evidence_type=payload.evidence_type,
        government_project_status=payload.government_project_status,
        evidence_date=payload.evidence_date,
        current_service_status=payload.current_service_status,
        verification_status=payload.verification_status,
        location_id=location.id if location else None,
        notes=payload.notes,
    )
    db.add(record)
    db.flush()

    if data_source_id:
        ds = db.get(DataSource, data_source_id)
        if ds:
            attr = SourceAttribution(
                data_source_id=ds.id,
                entity_type="historical_infrastructure_record",
                entity_id=record.id,
                external_record_id=payload.external_id,
                verification_status=SourceVerificationStatus.UNVERIFIED,
                confidence_score=confidence_score,
            )
            db.add(attr)

    db.commit()
    db.refresh(record)
    return _serialize_historical_infrastructure_record(record)


def list_historical_infrastructure_records(
    db: Session,
    commodity_sector: str | None = None,
    district_area: str | None = None,
) -> list[HistoricalInfrastructureRecordResponse]:
    stmt = select(HistoricalInfrastructureRecord)
    if commodity_sector:
        stmt = stmt.where(func.lower(HistoricalInfrastructureRecord.commodity_sector) == commodity_sector.strip().lower())
    if district_area:
        stmt = stmt.where(func.lower(HistoricalInfrastructureRecord.district_area) == district_area.strip().lower())

    stmt = stmt.order_by(HistoricalInfrastructureRecord.name)
    records = db.scalars(stmt).all()
    return [_serialize_historical_infrastructure_record(r) for r in records]


def _serialize_historical_infrastructure_record(record: HistoricalInfrastructureRecord) -> HistoricalInfrastructureRecordResponse:
    return HistoricalInfrastructureRecordResponse(
        id=record.id,
        external_id=record.external_id,
        name=record.name,
        lead_type=record.lead_type,
        commodity_sector=record.commodity_sector,
        district_area=record.district_area,
        state=record.state,
        coverage_label=record.coverage_label,
        location_granularity=record.location_granularity,
        evidence_type=record.evidence_type,
        government_project_status=record.government_project_status,
        evidence_date=record.evidence_date,
        current_service_status=record.current_service_status,
        verification_status=record.verification_status,
        location=_serialize_location(record.location) if record.location else None,
        notes=record.notes,
        created_at=record.created_at,
    )

