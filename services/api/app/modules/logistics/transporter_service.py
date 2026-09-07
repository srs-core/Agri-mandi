from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.entities import (
    Location,
    LogisticsProvider,
    Notification,
    QuoteStatus,
    Shipment,
    ShipmentEvent,
    ShipmentPlan,
    ShipmentStatus,
    TransportOpportunity,
    TransportOpportunityStatus,
    TransporterProfile,
    TransporterQuote,
    User,
    UserStatus,
    Vehicle,
    VehicleTypeEnum,
    VerificationStatus,
)
from app.modules.logistics.route_planning_engine import build_and_evaluate_route_plan
from app.modules.logistics.execution_tracking_service import initialize_shipment_checkpoints
from app.schemas.route_planning import RouteWaypoint
from app.schemas.transporter import (
    OpportunityAcceptRequest,
    OpportunityDeclineRequest,
    TransporterMeResponse,
    TransporterProfileResponse,
    TransporterProfileUpdate,
    TransporterQuoteCreate,
    TransporterQuoteResponse,
    TransporterVehicleCreate,
    TransporterVehicleResponse,
    TransporterVehicleUpdate,
    TransportOpportunityDetailResponse,
    TransportOpportunityResponse,
)


def _get_transporter_profile(db: Session, user_id: UUID) -> TransporterProfile:
    profile = db.scalar(
        select(TransporterProfile).where(TransporterProfile.user_id == user_id)
    )
    if not profile:
        # Auto-create profile if user exists with transporter role
        user = db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise ApiError(404, "user_not_found", "User not found.")
        profile = TransporterProfile(
            user_id=user_id,
            organization_name=user.display_name,
            operational_status="active",
            verification_status=VerificationStatus.PENDING,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _get_or_create_provider(db: Session, profile: TransporterProfile) -> LogisticsProvider:
    provider = db.scalar(
        select(LogisticsProvider).where(
            LogisticsProvider.registered_transporter_profile_id == profile.id
        )
    )
    if not provider:
        provider = LogisticsProvider(
            name=profile.organization_name,
            registered_transporter_profile_id=profile.id,
            operating_scope="regional",
            has_cold_chain=False,
            contact_phone=profile.contact_phone,
            contact_email=profile.contact_email,
            is_active=True,
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)
    return provider


def get_transporter_me(db: Session, user_id: UUID) -> TransporterMeResponse:
    profile = _get_transporter_profile(db, user_id)
    provider = db.scalar(
        select(LogisticsProvider).where(
            LogisticsProvider.registered_transporter_profile_id == profile.id
        )
    )

    vehicles: list[Vehicle] = []
    if provider:
        vehicles = db.scalars(
            select(Vehicle).where(Vehicle.provider_id == provider.id)
        ).all()

    open_opps_count = db.scalar(
        select(func.count(TransportOpportunity.id)).where(
            TransportOpportunity.transporter_profile_id == profile.id,
            TransportOpportunity.status.in_([TransportOpportunityStatus.OPEN, TransportOpportunityStatus.OFFERED]),
        )
    ) or 0

    active_shipments_count = 0
    delivered_shipments_count = 0
    if provider:
        active_shipments_count = db.scalar(
            select(func.count(Shipment.id)).where(
                Shipment.provider_id == provider.id,
                Shipment.status.in_([ShipmentStatus.SCHEDULED, ShipmentStatus.DISPATCHED, ShipmentStatus.IN_TRANSIT]),
            )
        ) or 0
        delivered_shipments_count = db.scalar(
            select(func.count(Shipment.id)).where(
                Shipment.provider_id == provider.id,
                Shipment.status == ShipmentStatus.DELIVERED,
            )
        ) or 0

    return TransporterMeResponse(
        profile=TransporterProfileResponse.model_validate(profile),
        provider_id=provider.id if provider else None,
        provider_name=provider.name if provider else profile.organization_name,
        total_vehicles_count=len(vehicles),
        available_vehicles_count=len([v for v in vehicles if v.is_available and v.operational_status == "available"]),
        open_opportunities_count=open_opps_count,
        active_shipments_count=active_shipments_count,
        delivered_shipments_count=delivered_shipments_count,
    )


def update_transporter_profile(
    db: Session, user_id: UUID, payload: TransporterProfileUpdate
) -> TransporterProfileResponse:
    profile = _get_transporter_profile(db, user_id)

    if payload.organization_name is not None:
        profile.organization_name = payload.organization_name
    if payload.contact_phone is not None:
        profile.contact_phone = payload.contact_phone
    if payload.contact_email is not None:
        profile.contact_email = payload.contact_email
    if payload.service_area_districts is not None:
        profile.service_area_districts = payload.service_area_districts
    if payload.preferred_commodities is not None:
        profile.preferred_commodities = payload.preferred_commodities
    if payload.operational_status is not None:
        profile.operational_status = payload.operational_status

    # Sync provider record name & contact
    provider = db.scalar(
        select(LogisticsProvider).where(
            LogisticsProvider.registered_transporter_profile_id == profile.id
        )
    )
    if provider:
        provider.name = profile.organization_name
        provider.contact_phone = profile.contact_phone
        provider.contact_email = profile.contact_email

    db.commit()
    db.refresh(profile)
    return TransporterProfileResponse.model_validate(profile)


def list_transporter_vehicles(db: Session, user_id: UUID) -> list[TransporterVehicleResponse]:
    profile = _get_transporter_profile(db, user_id)
    provider = _get_or_create_provider(db, profile)

    vehicles = db.scalars(
        select(Vehicle).where(Vehicle.provider_id == provider.id).order_by(Vehicle.created_at.desc())
    ).all()

    return [
        TransporterVehicleResponse(
            id=v.id,
            provider_id=v.provider_id,
            registration_number=v.registration_number,
            vehicle_type=v.vehicle_type,
            model_name=v.model_name,
            payload_capacity_kg=v.payload_capacity_kg,
            payload_capacity_quintals=Decimal(str(round(float(v.payload_capacity_kg) / 100.0, 2))),
            payload_capacity_tonnes=Decimal(str(round(float(v.payload_capacity_kg) / 1000.0, 2))),
            volumetric_capacity_cbm=v.volumetric_capacity_cbm,
            is_refrigerated=v.is_refrigerated,
            temp_min_celsius=v.temp_min_celsius,
            temp_max_celsius=v.temp_max_celsius,
            is_available=v.is_available,
            operational_status=v.operational_status,
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in vehicles
    ]


def register_transporter_vehicle(
    db: Session, user_id: UUID, payload: TransporterVehicleCreate
) -> TransporterVehicleResponse:
    profile = _get_transporter_profile(db, user_id)
    provider = _get_or_create_provider(db, profile)

    # Check registration number uniqueness if provided
    if payload.registration_number:
        existing = db.scalar(
            select(Vehicle).where(Vehicle.registration_number == payload.registration_number.strip().upper())
        )
        if existing:
            raise ApiError(400, "vehicle_registration_exists", f"Vehicle with registration {payload.registration_number} is already registered.")

    vehicle = Vehicle(
        provider_id=provider.id,
        registration_number=payload.registration_number.strip().upper() if payload.registration_number else None,
        vehicle_type=payload.vehicle_type,
        model_name=payload.model_name,
        payload_capacity_kg=payload.payload_capacity_kg,
        volumetric_capacity_cbm=payload.volumetric_capacity_cbm,
        is_refrigerated=payload.is_refrigerated,
        temp_min_celsius=payload.temp_min_celsius,
        temp_max_celsius=payload.temp_max_celsius,
        is_available=payload.is_available,
        operational_status=payload.operational_status,
    )
    db.add(vehicle)

    # Update provider cold chain capability
    if payload.is_refrigerated:
        provider.has_cold_chain = True

    db.commit()
    db.refresh(vehicle)

    return TransporterVehicleResponse(
        id=vehicle.id,
        provider_id=vehicle.provider_id,
        registration_number=vehicle.registration_number,
        vehicle_type=vehicle.vehicle_type,
        model_name=vehicle.model_name,
        payload_capacity_kg=vehicle.payload_capacity_kg,
        payload_capacity_quintals=Decimal(str(round(float(vehicle.payload_capacity_kg) / 100.0, 2))),
        payload_capacity_tonnes=Decimal(str(round(float(vehicle.payload_capacity_kg) / 1000.0, 2))),
        volumetric_capacity_cbm=vehicle.volumetric_capacity_cbm,
        is_refrigerated=vehicle.is_refrigerated,
        temp_min_celsius=vehicle.temp_min_celsius,
        temp_max_celsius=vehicle.temp_max_celsius,
        is_available=vehicle.is_available,
        operational_status=vehicle.operational_status,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


def update_transporter_vehicle(
    db: Session, user_id: UUID, vehicle_id: UUID, payload: TransporterVehicleUpdate
) -> TransporterVehicleResponse:
    profile = _get_transporter_profile(db, user_id)
    provider = _get_or_create_provider(db, profile)

    vehicle = db.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.provider_id == provider.id)
    )
    if not vehicle:
        raise ApiError(404, "vehicle_not_found", f"Vehicle {vehicle_id} not found for this transporter.")

    if payload.registration_number is not None:
        vehicle.registration_number = payload.registration_number.strip().upper()
    if payload.model_name is not None:
        vehicle.model_name = payload.model_name
    if payload.payload_capacity_kg is not None:
        vehicle.payload_capacity_kg = payload.payload_capacity_kg
    if payload.volumetric_capacity_cbm is not None:
        vehicle.volumetric_capacity_cbm = payload.volumetric_capacity_cbm
    if payload.is_refrigerated is not None:
        vehicle.is_refrigerated = payload.is_refrigerated
    if payload.temp_min_celsius is not None:
        vehicle.temp_min_celsius = payload.temp_min_celsius
    if payload.temp_max_celsius is not None:
        vehicle.temp_max_celsius = payload.temp_max_celsius
    if payload.is_available is not None:
        vehicle.is_available = payload.is_available
    if payload.operational_status is not None:
        vehicle.operational_status = payload.operational_status

    db.commit()
    db.refresh(vehicle)

    return TransporterVehicleResponse(
        id=vehicle.id,
        provider_id=vehicle.provider_id,
        registration_number=vehicle.registration_number,
        vehicle_type=vehicle.vehicle_type,
        model_name=vehicle.model_name,
        payload_capacity_kg=vehicle.payload_capacity_kg,
        payload_capacity_quintals=Decimal(str(round(float(vehicle.payload_capacity_kg) / 100.0, 2))),
        payload_capacity_tonnes=Decimal(str(round(float(vehicle.payload_capacity_kg) / 1000.0, 2))),
        volumetric_capacity_cbm=vehicle.volumetric_capacity_cbm,
        is_refrigerated=vehicle.is_refrigerated,
        temp_min_celsius=vehicle.temp_min_celsius,
        temp_max_celsius=vehicle.temp_max_celsius,
        is_available=vehicle.is_available,
        operational_status=vehicle.operational_status,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


def list_opportunities_for_transporter(
    db: Session, user_id: UUID, status: Optional[TransportOpportunityStatus] = None
) -> list[TransportOpportunityResponse]:
    profile = _get_transporter_profile(db, user_id)

    query = select(TransportOpportunity).where(
        TransportOpportunity.transporter_profile_id == profile.id
    )
    if status:
        query = query.where(TransportOpportunity.status == status)

    query = query.order_by(TransportOpportunity.created_at.desc())
    opportunities = db.scalars(query).all()

    return [
        TransportOpportunityResponse(
            id=o.id,
            shipment_plan_id=o.shipment_plan_id,
            shipment_id=o.shipment_id,
            transporter_profile_id=o.transporter_profile_id,
            status=o.status,
            required_vehicle_class=o.required_vehicle_class,
            required_payload_quintals=o.required_payload_quintals,
            required_payload_tonnes=Decimal(str(round(float(o.required_payload_quintals) / 10.0, 3))),
            requires_cold_chain=o.requires_cold_chain,
            pickup_stops_count=o.pickup_stops_count,
            origin_district=o.origin_district,
            destination_district=o.destination_district,
            total_distance_km=o.total_distance_km,
            distance_certainty=o.distance_certainty,
            estimated_cost=o.estimated_cost,
            cost_certainty=o.cost_certainty,
            earliest_pickup_date=o.earliest_pickup_date,
            delivery_deadline=o.delivery_deadline,
            eligibility_score=o.eligibility_score,
            matching_criteria_json=o.matching_criteria_json,
            expires_at=o.expires_at,
            responded_at=o.responded_at,
            decline_reason=o.decline_reason,
            created_at=o.created_at,
            updated_at=o.updated_at,
        )
        for o in opportunities
    ]


def get_opportunity_detail(
    db: Session, user_id: UUID, opportunity_id: UUID
) -> TransportOpportunityDetailResponse:
    profile = _get_transporter_profile(db, user_id)
    opp = db.scalar(
        select(TransportOpportunity).where(
            TransportOpportunity.id == opportunity_id,
            TransportOpportunity.transporter_profile_id == profile.id,
        )
    )
    if not opp:
        raise ApiError(404, "opportunity_not_found", f"Opportunity {opportunity_id} not found.")

    waypoints: list[RouteWaypoint] = []
    plan_code: Optional[str] = None
    commodity_name: Optional[str] = None
    buyer_org: Optional[str] = None
    lineage: Optional[dict[str, Any]] = None

    if opp.shipment_plan_id:
        plan = db.scalar(
            select(ShipmentPlan)
            .options(selectinload(ShipmentPlan.commodity))
            .where(ShipmentPlan.id == opp.shipment_plan_id)
        )
        if plan:
            plan_code = plan.plan_code
            commodity_name = plan.commodity.name if plan.commodity else None
            buyer_org = plan.buyer_organization_name
            lineage = plan.lineage_summary

            try:
                route_plan = build_and_evaluate_route_plan(db, plan.id)
                waypoints = route_plan.waypoints
            except Exception:
                pass

    # Transporter's vehicles for selection
    vehicles = list_transporter_vehicles(db, user_id)

    # Transporter's quotes for this opportunity
    quotes = db.scalars(
        select(TransporterQuote).where(
            TransporterQuote.opportunity_id == opp.id,
            TransporterQuote.transporter_profile_id == profile.id,
        ).order_by(TransporterQuote.created_at.desc())
    ).all()

    return TransportOpportunityDetailResponse(
        id=opp.id,
        shipment_plan_id=opp.shipment_plan_id,
        shipment_id=opp.shipment_id,
        transporter_profile_id=opp.transporter_profile_id,
        status=opp.status,
        required_vehicle_class=opp.required_vehicle_class,
        required_payload_quintals=opp.required_payload_quintals,
        required_payload_tonnes=Decimal(str(round(float(opp.required_payload_quintals) / 10.0, 3))),
        requires_cold_chain=opp.requires_cold_chain,
        pickup_stops_count=opp.pickup_stops_count,
        origin_district=opp.origin_district,
        destination_district=opp.destination_district,
        total_distance_km=opp.total_distance_km,
        distance_certainty=opp.distance_certainty,
        estimated_cost=opp.estimated_cost,
        cost_certainty=opp.cost_certainty,
        earliest_pickup_date=opp.earliest_pickup_date,
        delivery_deadline=opp.delivery_deadline,
        eligibility_score=opp.eligibility_score,
        matching_criteria_json=opp.matching_criteria_json,
        expires_at=opp.expires_at,
        responded_at=opp.responded_at,
        decline_reason=opp.decline_reason,
        created_at=opp.created_at,
        updated_at=opp.updated_at,
        plan_code=plan_code,
        commodity_name=commodity_name,
        buyer_organization_name=buyer_org,
        waypoints=waypoints,
        vehicle_options=vehicles,
        my_quotes=[
            TransporterQuoteResponse(
                id=q.id,
                opportunity_id=q.opportunity_id,
                transporter_profile_id=q.transporter_profile_id,
                vehicle_id=q.vehicle_id,
                quote_amount=q.quote_amount,
                quote_unit=q.quote_unit,
                currency=q.currency,
                status=q.status,
                valid_until=q.valid_until,
                notes=q.notes,
                quote_certainty=q.quote_certainty,
                created_at=q.created_at,
                updated_at=q.updated_at,
            )
            for q in quotes
        ],
        lineage_summary=lineage,
    )


def accept_opportunity_transactional(
    db: Session, user_id: UUID, opportunity_id: UUID, payload: OpportunityAcceptRequest
) -> TransportOpportunityDetailResponse:
    """
    Transactionally accepts a transport opportunity with row-level locking (SELECT FOR UPDATE)
    to prevent race conditions between competing transporters.
    Assigns transporter and vehicle to the shipment.
    """
    profile = _get_transporter_profile(db, user_id)
    provider = _get_or_create_provider(db, profile)

    # 1. Lock Opportunity row
    opp = db.scalar(
        select(TransportOpportunity)
        .where(
            TransportOpportunity.id == opportunity_id,
            TransportOpportunity.transporter_profile_id == profile.id,
        )
        .with_for_update()
    )
    if not opp:
        raise ApiError(404, "opportunity_not_found", f"Opportunity {opportunity_id} not found.")

    if opp.status == TransportOpportunityStatus.ACCEPTED:
        raise ApiError(400, "opportunity_already_accepted", "This transport opportunity has already been accepted.")

    if opp.status not in [TransportOpportunityStatus.OPEN, TransportOpportunityStatus.OFFERED]:
        raise ApiError(400, "opportunity_not_open", f"Cannot accept opportunity with status '{opp.status.value}'.")

    # 2. Lock ShipmentPlan row
    plan = db.scalar(
        select(ShipmentPlan)
        .options(
            selectinload(ShipmentPlan.pickup_stops),
            selectinload(ShipmentPlan.commodity),
            selectinload(ShipmentPlan.destination_location),
        )
        .where(ShipmentPlan.id == opp.shipment_plan_id)
        .with_for_update()
    )
    if not plan:
        raise ApiError(404, "plan_not_found", "Associated ShipmentPlan not found.")

    # 3. Guard against concurrent assignment: check if plan already assigned
    already_assigned = db.scalar(
        select(TransportOpportunity).where(
            TransportOpportunity.shipment_plan_id == plan.id,
            TransportOpportunity.status == TransportOpportunityStatus.ACCEPTED,
            TransportOpportunity.id != opp.id,
        )
    )
    if already_assigned:
        opp.status = TransportOpportunityStatus.WITHDRAWN
        opp.decline_reason = "Job was already accepted by another carrier."
        db.commit()
        raise ApiError(409, "opportunity_already_assigned", "This transport job was just assigned to another carrier.")

    # 4. Lock Vehicle row
    vehicle = db.scalar(
        select(Vehicle)
        .where(Vehicle.id == payload.vehicle_id, Vehicle.provider_id == provider.id)
        .with_for_update()
    )
    if not vehicle:
        raise ApiError(404, "vehicle_not_found", f"Vehicle {payload.vehicle_id} not found in transporter fleet.")

    if not vehicle.is_available or vehicle.operational_status == "busy":
        raise ApiError(400, "vehicle_not_available", f"Vehicle {vehicle.registration_number or vehicle.model_name} is currently busy or unavailable.")

    # Check payload capacity
    req_kg = opp.required_payload_quintals * Decimal("100")
    if vehicle.payload_capacity_kg < req_kg:
        raise ApiError(400, "vehicle_capacity_insufficient", f"Vehicle capacity ({vehicle.payload_capacity_kg} kg) is insufficient for cargo ({req_kg} kg).")

    if opp.requires_cold_chain and not vehicle.is_refrigerated:
        raise ApiError(400, "cold_chain_required", "This cargo requires refrigerated transport.")

    # 5. Create or update operational Shipment
    shipment = db.scalar(
        select(Shipment)
        .where(Shipment.shipment_plan_id == plan.id)
        .with_for_update()
    )

    first_stop_loc_id = plan.pickup_stops[0].pickup_location_id if plan.pickup_stops else plan.destination_location_id

    if not shipment:
        shipment = Shipment(
            shipment_plan_id=plan.id,
            order_id=plan.order_id,
            vehicle_id=vehicle.id,
            provider_id=provider.id,
            origin_location_id=first_stop_loc_id,
            destination_location_id=plan.destination_location_id,
            status=ShipmentStatus.SCHEDULED,
            estimated_cost=opp.estimated_cost,
            driver_name=payload.driver_name,
            driver_phone=payload.driver_phone,
        )
        db.add(shipment)
        db.flush()
    else:
        shipment.provider_id = provider.id
        shipment.vehicle_id = vehicle.id
        shipment.status = ShipmentStatus.SCHEDULED
        if payload.driver_name:
            shipment.driver_name = payload.driver_name
        if payload.driver_phone:
            shipment.driver_phone = payload.driver_phone

    # 5b. Initialize sequential execution checkpoints
    initialize_shipment_checkpoints(db, shipment)

    # 6. Update Vehicle state to BUSY
    vehicle.is_available = False
    vehicle.operational_status = "busy"

    # 7. Update accepted opportunity
    opp.status = TransportOpportunityStatus.ACCEPTED
    opp.shipment_id = shipment.id
    opp.responded_at = datetime.now(timezone.utc)

    # 8. Expire all competing open opportunities for this plan
    competing_opps = db.scalars(
        select(TransportOpportunity).where(
            TransportOpportunity.shipment_plan_id == plan.id,
            TransportOpportunity.id != opp.id,
            TransportOpportunity.status.in_([TransportOpportunityStatus.OPEN, TransportOpportunityStatus.OFFERED]),
        ).with_for_update()
    ).all()
    for comp in competing_opps:
        comp.status = TransportOpportunityStatus.WITHDRAWN
        comp.decline_reason = "Job assigned to another carrier."

    # 9. Record ShipmentEvent audit entry
    shipment_event = ShipmentEvent(
        shipment_id=shipment.id,
        event_type="TRANSPORTER_ASSIGNED",
        location_name=f"Assigned to {profile.organization_name}",
        notes=f"Vehicle: {vehicle.registration_number or vehicle.model_name} (Payload {vehicle.payload_capacity_kg} kg). Notes: {payload.notes or 'None'}",
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(shipment_event)

    # 10. In-App Notifications
    from app.modules.marketplace.service import emit_idempotent_notification
    emit_idempotent_notification(
        db=db,
        recipient_user_id=profile.user_id,
        notification_type="TRANSPORT_ASSIGNED",
        title=f"Transport Job Confirmed: {plan.commodity.name} ({plan.total_planned_quantity_quintals} qtl)",
        body=f"You have successfully accepted shipment {plan.plan_code}. Vehicle assigned: {vehicle.registration_number or vehicle.model_name}.",
        data_json={"shipment_id": str(shipment.id), "plan_id": str(plan.id), "plan_code": plan.plan_code},
        dedupe_key="shipment_id",
    )

    if plan.buyer_user_id:
        emit_idempotent_notification(
            db=db,
            recipient_user_id=plan.buyer_user_id,
            notification_type="CARRIER_ASSIGNED",
            title=f"Carrier Assigned for Shipment {plan.plan_code}",
            body=f"Transporter {profile.organization_name} has accepted and scheduled transport for your order.",
            data_json={"shipment_id": str(shipment.id), "plan_id": str(plan.id), "transporter_name": profile.organization_name},
            dedupe_key="shipment_id",
        )

    db.commit()

    return get_opportunity_detail(db, user_id, opp.id)


def decline_opportunity(
    db: Session, user_id: UUID, opportunity_id: UUID, payload: OpportunityDeclineRequest
) -> TransportOpportunityResponse:
    profile = _get_transporter_profile(db, user_id)
    opp = db.scalar(
        select(TransportOpportunity).where(
            TransportOpportunity.id == opportunity_id,
            TransportOpportunity.transporter_profile_id == profile.id,
        )
    )
    if not opp:
        raise ApiError(404, "opportunity_not_found", f"Opportunity {opportunity_id} not found.")

    if opp.status == TransportOpportunityStatus.ACCEPTED:
        raise ApiError(400, "opportunity_already_accepted", "Cannot decline an already accepted job.")

    opp.status = TransportOpportunityStatus.DECLINED
    opp.decline_reason = payload.reason or "Declined by transporter"
    opp.responded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(opp)

    return TransportOpportunityResponse.model_validate(opp)


def submit_transporter_quote(
    db: Session, user_id: UUID, opportunity_id: UUID, payload: TransporterQuoteCreate
) -> TransporterQuoteResponse:
    profile = _get_transporter_profile(db, user_id)
    provider = _get_or_create_provider(db, profile)

    opp = db.scalar(
        select(TransportOpportunity).where(
            TransportOpportunity.id == opportunity_id,
            TransportOpportunity.transporter_profile_id == profile.id,
        )
    )
    if not opp:
        raise ApiError(404, "opportunity_not_found", f"Opportunity {opportunity_id} not found.")

    if opp.status != TransportOpportunityStatus.OPEN:
        raise ApiError(400, "opportunity_not_open", f"Cannot submit quote for opportunity with status '{opp.status.value}'.")

    if payload.vehicle_id:
        vehicle = db.scalar(
            select(Vehicle).where(Vehicle.id == payload.vehicle_id, Vehicle.provider_id == provider.id)
        )
        if not vehicle:
            raise ApiError(404, "vehicle_not_found", "Selected vehicle not found in transporter fleet.")

    quote = TransporterQuote(
        opportunity_id=opp.id,
        transporter_profile_id=profile.id,
        vehicle_id=payload.vehicle_id,
        quote_amount=payload.quote_amount,
        quote_unit=payload.quote_unit,
        currency=payload.currency,
        status=QuoteStatus.SUBMITTED,
        valid_until=payload.valid_until,
        notes=payload.notes,
        quote_certainty="VERIFIED_TRANSPORTER_QUOTE",
    )
    db.add(quote)
    opp.status = TransportOpportunityStatus.OFFERED

    db.commit()
    db.refresh(quote)

    return TransporterQuoteResponse(
        id=quote.id,
        opportunity_id=quote.opportunity_id,
        transporter_profile_id=quote.transporter_profile_id,
        vehicle_id=quote.vehicle_id,
        quote_amount=quote.quote_amount,
        quote_unit=quote.quote_unit,
        currency=quote.currency,
        status=quote.status,
        valid_until=quote.valid_until,
        notes=quote.notes,
        quote_certainty=quote.quote_certainty,
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


def list_transporter_shipments(db: Session, user_id: UUID) -> list[dict[str, Any]]:
    profile = _get_transporter_profile(db, user_id)
    provider = _get_or_create_provider(db, profile)

    shipments = db.scalars(
        select(Shipment)
        .options(
            selectinload(Shipment.shipment_plan),
            selectinload(Shipment.vehicle),
            selectinload(Shipment.origin_location),
            selectinload(Shipment.destination_location),
            selectinload(Shipment.events),
        )
        .where(Shipment.provider_id == provider.id)
        .order_by(Shipment.created_at.desc())
    ).all()

    results: list[dict[str, Any]] = []
    for s in shipments:
        results.append({
            "id": str(s.id),
            "shipment_plan_id": str(s.shipment_plan_id) if s.shipment_plan_id else None,
            "plan_code": s.shipment_plan.plan_code if s.shipment_plan else None,
            "status": s.status.value,
            "vehicle_id": str(s.vehicle_id) if s.vehicle_id else None,
            "vehicle_registration": s.vehicle.registration_number if s.vehicle else None,
            "vehicle_model": s.vehicle.model_name if s.vehicle else None,
            "origin_location_name": s.origin_location.name if s.origin_location else "Farm Gate",
            "destination_location_name": s.destination_location.name if s.destination_location else "Buyer Terminal",
            "driver_name": s.driver_name,
            "driver_phone": s.driver_phone,
            "estimated_cost": float(s.estimated_cost) if s.estimated_cost is not None else None,
            "events_count": len(s.events),
            "created_at": s.created_at.isoformat(),
        })

    return results
