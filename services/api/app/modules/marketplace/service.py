from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.entities import (
    AuditEvent,
    BuyerProfile,
    BuyerRequirement,
    BuyerRequirementStatus,
    Commodity,
    CommodityCategory,
    FarmerProfile,
    FPOProfile,
    Location,
    Notification,
    Offer,
    OfferProposal,
    OfferStatus,
    Order,
    OrderItem,
    OrderStatus,
    ProduceLot,
    ProduceLotContribution,
    ProduceLotStatus,
    Role,
    RoleName,
    TransporterProfile,
    User,
    UserRole,
    UserStatus,
    VerificationRequest,
    VerificationStatus,
)
from app.modules.audit.service import record_audit_event
from app.schemas.marketplace import (
    BuyerRequirementCreate,
    BuyerRequirementResponse,
    BuyerRequirementUpdateRequest,
    CommodityResponse,
    CounterOfferCreate,
    LocationCreate,
    LocationResponse,
    NegotiationProposalResponse,
    MarketplaceProduceLotsResponse,
    NotificationResponse,
    OfferCreate,
    OfferResponse,
    OrderItemResponse,
    OrderResponse,
    PlatformMetricsResponse,
    ProduceLotContributionResponse,
    ProduceLotCreate,
    ProduceLotDetailResponse,
    ProduceLotSummaryResponse,
    ProduceLotUpdateRequest,
    ProfileUpdateRequest,
    UserProfileResponse,
    VerificationCreateRequest,
    VerificationRequestResponse,
    VerificationReviewRequest,
)

SYSTEM_COMMODITIES = [
    # Vegetables
    {"name": "Onion (Nashik Red)", "category": CommodityCategory.VEGETABLES, "default_unit": "quintal", "is_perishable": True, "storage_guidance": "Well-ventilated dry storage"},
    {"name": "Tomato (Hybrid)", "category": CommodityCategory.VEGETABLES, "default_unit": "crate (25kg)", "is_perishable": True, "storage_guidance": "Cool dry storage or cold storage at 10-12°C"},
    {"name": "Potato (Jyoti)", "category": CommodityCategory.VEGETABLES, "default_unit": "quintal", "is_perishable": True, "storage_guidance": "Dark cold storage at 4-8°C"},
    {"name": "Cauliflower", "category": CommodityCategory.VEGETABLES, "default_unit": "quintal", "is_perishable": True, "storage_guidance": "Cool moist storage 0-4°C"},
    {"name": "Green Chilli", "category": CommodityCategory.VEGETABLES, "default_unit": "kg", "is_perishable": True, "storage_guidance": "Ventilated packing 7-10°C"},
    {"name": "Cabbage", "category": CommodityCategory.VEGETABLES, "default_unit": "quintal", "is_perishable": True, "storage_guidance": "Cold storage 0-2°C"},
    # Fruits
    {"name": "Mango (Alphonso)", "category": CommodityCategory.FRUITS, "default_unit": "box (dozen)", "is_perishable": True, "storage_guidance": "Controlled atmosphere 13°C"},
    {"name": "Banana (Robusta)", "category": CommodityCategory.FRUITS, "default_unit": "quintal", "is_perishable": True, "storage_guidance": "Ripening room 14-16°C"},
    {"name": "Pomegranate (Bhagwa)", "category": CommodityCategory.FRUITS, "default_unit": "kg", "is_perishable": True, "storage_guidance": "Cold storage 5-7°C"},
    {"name": "Grapes (Thompson Seedless)", "category": CommodityCategory.FRUITS, "default_unit": "box (4kg)", "is_perishable": True, "storage_guidance": "Pre-cooled cold chain 0-1°C"},
    {"name": "Orange (Nagpur)", "category": CommodityCategory.FRUITS, "default_unit": "quintal", "is_perishable": True, "storage_guidance": "Cold storage 5-8°C"},
    {"name": "Apple (Royal Delicious)", "category": CommodityCategory.FRUITS, "default_unit": "box (20kg)", "is_perishable": True, "storage_guidance": "Cold storage -1 to 0°C"},
    # Grains
    {"name": "Wheat (Sharbati)", "category": CommodityCategory.GRAINS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Moisture below 12%, hermetic/silo storage"},
    {"name": "Rice (Sona Masoori)", "category": CommodityCategory.GRAINS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry ventilated warehouse"},
    {"name": "Basmati Rice (1121)", "category": CommodityCategory.GRAINS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Aged dry warehouse storage"},
    {"name": "Maize (Yellow Dent)", "category": CommodityCategory.GRAINS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Moisture below 14%"},
    {"name": "Bajra (Pearl Millet)", "category": CommodityCategory.GRAINS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry cool storage"},
    {"name": "Jowar (Sorghum)", "category": CommodityCategory.GRAINS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry ventilated warehouse"},
    # Pulses
    {"name": "Chana (Desi Chickpea)", "category": CommodityCategory.PULSES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Pest-protected dry warehouse"},
    {"name": "Tur / Arhar (Pigeon Pea)", "category": CommodityCategory.PULSES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry warehouse storage"},
    {"name": "Moong (Green Gram)", "category": CommodityCategory.PULSES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Airtight dry storage"},
    {"name": "Urad (Black Gram)", "category": CommodityCategory.PULSES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry moisture-free storage"},
    {"name": "Masoor (Red Lentil)", "category": CommodityCategory.PULSES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry warehouse"},
    # Spices
    {"name": "Turmeric (Salem)", "category": CommodityCategory.SPICES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry moisture-free storage with curcumin protection"},
    {"name": "Cumin / Jeera (Unjha)", "category": CommodityCategory.SPICES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Cool, dry and insect-free"},
    {"name": "Coriander / Dhania", "category": CommodityCategory.SPICES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Low-humidity warehouse"},
    {"name": "Red Chilli (Guntur)", "category": CommodityCategory.SPICES, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Cold storage to maintain color"},
    {"name": "Black Pepper (Malabar)", "category": CommodityCategory.SPICES, "default_unit": "kg", "is_perishable": False, "storage_guidance": "Airtight cool dry storage"},
    # Other Crops
    {"name": "Soybean (Yellow)", "category": CommodityCategory.OTHER_CROPS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Moisture below 10%, aerated storage"},
    {"name": "Cotton (Medium Staple)", "category": CommodityCategory.OTHER_CROPS, "default_unit": "bale (170kg)", "is_perishable": False, "storage_guidance": "Dry covered godown"},
    {"name": "Groundnut (Bold)", "category": CommodityCategory.OTHER_CROPS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Moisture below 8% to prevent aflatoxin"},
    {"name": "Mustard (Black)", "category": CommodityCategory.OTHER_CROPS, "default_unit": "quintal", "is_perishable": False, "storage_guidance": "Dry cool warehouse"},
    {"name": "Sugarcane", "category": CommodityCategory.OTHER_CROPS, "default_unit": "ton", "is_perishable": True, "storage_guidance": "Direct factory dispatch within 24 hours of harvest"},
]


def ensure_system_commodities(db: Session) -> None:
    existing_names = set(db.scalars(select(Commodity.name)).all())
    to_add = [
        Commodity(
            name=c["name"],
            category=c["category"],
            default_unit=c["default_unit"],
            is_perishable=c["is_perishable"],
            storage_guidance=c["storage_guidance"],
            is_active=True,
        )
        for c in SYSTEM_COMMODITIES
        if c["name"] not in existing_names
    ]
    if to_add:
        db.add_all(to_add)
        db.commit()


def get_user_roles(user: User) -> list[RoleName]:
    return [user_role.role.name for user_role in user.user_roles if user_role.role is not None]


def ensure_user_profile(db: Session, user: User) -> None:
    roles = get_user_roles(user)
    if RoleName.FARMER in roles and user.farmer_profile is None:
        db.add(FarmerProfile(user_id=user.id))
    if RoleName.FPO in roles and user.fpo_profile is None:
        db.add(FPOProfile(user_id=user.id, legal_name=user.display_name))
    if RoleName.BUYER in roles and user.buyer_profile is None:
        db.add(BuyerProfile(user_id=user.id, organization_name=user.display_name))
    if RoleName.TRANSPORTER in roles and user.transporter_profile is None:
        db.add(TransporterProfile(user_id=user.id, organization_name=user.display_name))
    db.commit()
    db.refresh(user)


def _serialize_location(location: Location | None) -> LocationResponse | None:
    if location is None:
        return None
    return LocationResponse(
        id=location.id,
        name=location.name,
        village=location.village,
        taluka=location.taluka,
        district=location.district,
        state=location.state,
        country_code=location.country_code,
        postal_code=location.postal_code,
        latitude=location.latitude,
        longitude=location.longitude,
    )


def get_user_profile(db: Session, user: User) -> UserProfileResponse:
    ensure_user_profile(db, user)
    roles = [role.value for role in get_user_roles(user)]

    farm_name = None
    land_area = None
    legal_name = None
    reg_no = None
    org_name = None
    gstin = None
    verification_status = VerificationStatus.PENDING
    primary_location = None

    if user.farmer_profile:
        farm_name = user.farmer_profile.farm_name
        land_area = user.farmer_profile.land_area_hectares
        verification_status = user.farmer_profile.verification_status
        primary_location = _serialize_location(user.farmer_profile.primary_location)
    elif user.fpo_profile:
        legal_name = user.fpo_profile.legal_name
        reg_no = user.fpo_profile.registration_number
        verification_status = user.fpo_profile.verification_status
        primary_location = _serialize_location(user.fpo_profile.primary_location)
    elif user.buyer_profile:
        org_name = user.buyer_profile.organization_name
        gstin = user.buyer_profile.gstin
        verification_status = user.buyer_profile.verification_status
        primary_location = _serialize_location(user.buyer_profile.primary_location)
    elif user.transporter_profile:
        org_name = user.transporter_profile.organization_name
        verification_status = user.transporter_profile.verification_status
        primary_loc = getattr(user.transporter_profile, "primary_location", None)
        if primary_loc:
            primary_location = _serialize_location(primary_loc)

    return UserProfileResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        phone_number=user.phone_number,
        roles=roles,
        status=user.status.value,
        farm_name=farm_name,
        land_area_hectares=land_area,
        legal_name=legal_name,
        registration_number=reg_no,
        organization_name=org_name,
        gstin=gstin,
        verification_status=verification_status,
        primary_location=primary_location,
    )


def update_user_profile(db: Session, user: User, payload: ProfileUpdateRequest) -> UserProfileResponse:
    ensure_user_profile(db, user)
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.phone_number is not None:
        user.phone_number = payload.phone_number

    location_id = None
    if payload.primary_location is not None:
        geo_point = None
        if payload.primary_location.latitude is not None and payload.primary_location.longitude is not None:
            geo_point = f"POINT({payload.primary_location.longitude} {payload.primary_location.latitude})"
        loc = Location(
            name=payload.primary_location.name,
            village=payload.primary_location.village,
            taluka=payload.primary_location.taluka,
            district=payload.primary_location.district,
            state=payload.primary_location.state,
            country_code=payload.primary_location.country_code,
            postal_code=payload.primary_location.postal_code,
            latitude=payload.primary_location.latitude,
            longitude=payload.primary_location.longitude,
            geo_point=geo_point,
        )
        db.add(loc)
        db.flush()
        location_id = loc.id

    if user.farmer_profile:
        if payload.farm_name is not None:
            user.farmer_profile.farm_name = payload.farm_name
        if payload.land_area_hectares is not None:
            user.farmer_profile.land_area_hectares = payload.land_area_hectares
        if location_id is not None:
            user.farmer_profile.primary_location_id = location_id
    elif user.fpo_profile:
        if payload.legal_name is not None:
            user.fpo_profile.legal_name = payload.legal_name
        if payload.registration_number is not None:
            user.fpo_profile.registration_number = payload.registration_number
        if location_id is not None:
            user.fpo_profile.primary_location_id = location_id
    elif user.buyer_profile:
        if payload.organization_name is not None:
            user.buyer_profile.organization_name = payload.organization_name
        if payload.gstin is not None:
            user.buyer_profile.gstin = payload.gstin
        if location_id is not None:
            user.buyer_profile.primary_location_id = location_id
    elif user.transporter_profile:
        if payload.organization_name is not None:
            user.transporter_profile.organization_name = payload.organization_name

    db.commit()
    db.refresh(user)
    return get_user_profile(db, user)


def list_commodities(db: Session, category: CommodityCategory | None = None, search: str | None = None) -> list[CommodityResponse]:
    stmt = select(Commodity).where(Commodity.is_active.is_(True))
    if category is not None:
        stmt = stmt.where(Commodity.category == category)
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(func.lower(Commodity.name).like(search_pattern))
    stmt = stmt.order_by(Commodity.name)
    rows = db.scalars(stmt).all()
    return [
        CommodityResponse(
            id=c.id,
            name=c.name,
            category=c.category,
            default_unit=c.default_unit,
            is_perishable=c.is_perishable,
            storage_guidance=c.storage_guidance,
            is_active=c.is_active,
        )
        for c in rows
    ]


def _create_or_get_location(db: Session, location_create: LocationCreate | None, location_id: UUID | None) -> Location:
    if location_id is not None:
        loc = db.get(Location, location_id)
        if loc is None:
            raise ApiError(404, "location_not_found", "The specified location was not found.")
        return loc
    if location_create is not None:
        geo_point = None
        if location_create.latitude is not None and location_create.longitude is not None:
            geo_point = f"POINT({location_create.longitude} {location_create.latitude})"
        loc = Location(
            name=location_create.name,
            village=location_create.village,
            taluka=location_create.taluka,
            district=location_create.district,
            state=location_create.state,
            country_code=location_create.country_code,
            postal_code=location_create.postal_code,
            latitude=location_create.latitude,
            longitude=location_create.longitude,
            geo_point=geo_point,
        )
        db.add(loc)
        db.flush()
        return loc
    raise ApiError(400, "location_required", "Pickup/Delivery location is required.")


def _get_seller_meta(seller: User) -> tuple[str, VerificationStatus]:
    seller_roles = get_user_roles(seller)
    if RoleName.FPO in seller_roles and seller.fpo_profile:
        return "fpo", seller.fpo_profile.verification_status
    if seller.farmer_profile:
        return "farmer", seller.farmer_profile.verification_status
    return "farmer", VerificationStatus.PENDING


def create_produce_lot(db: Session, user: User, payload: ProduceLotCreate, ip_address: str | None = None) -> ProduceLotDetailResponse:
    roles = get_user_roles(user)
    if RoleName.FARMER not in roles and RoleName.FPO not in roles:
        raise ApiError(403, "insufficient_permissions", "Only farmers and FPOs can list produce.")

    commodity = db.get(Commodity, payload.commodity_id)
    if commodity is None or not commodity.is_active:
        raise ApiError(404, "commodity_not_found", "The specified commodity was not found.")

    location = _create_or_get_location(db, payload.pickup_location, payload.pickup_location_id)

    fpo_profile_id = user.fpo_profile.id if (RoleName.FPO in roles and user.fpo_profile) else None

    lot = ProduceLot(
        seller_user_id=user.id,
        owner_fpo_profile_id=fpo_profile_id,
        commodity_id=commodity.id,
        pickup_location_id=location.id,
        title=payload.title,
        available_quantity=payload.available_quantity,
        unit=payload.unit,
        quality_grade=payload.quality_grade,
        quality_notes=payload.quality_notes,
        asking_price_per_unit=payload.asking_price_per_unit,
        available_from=payload.available_from,
        available_until=payload.available_until,
        is_aggregated=payload.is_aggregated,
        status=ProduceLotStatus.PUBLISHED,
    )
    db.add(lot)
    db.flush()

    if payload.contributions:
        for c in payload.contributions:
            contrib = ProduceLotContribution(
                produce_lot_id=lot.id,
                farmer_profile_id=c.farmer_profile_id,
                fpo_profile_id=c.fpo_profile_id,
                contributed_quantity=c.contributed_quantity,
            )
            db.add(contrib)

    record_audit_event(
        db,
        event_type="produce_lot.created",
        entity_type="produce_lot",
        entity_id=lot.id,
        actor_user_id=user.id,
        metadata={"commodity": commodity.name, "quantity": str(payload.available_quantity), "price": str(payload.asking_price_per_unit)},
        ip_address=ip_address,
    )
    db.commit()
    return get_produce_lot_detail(db, lot.id)


def _serialize_produce_lot_summary(lot: ProduceLot) -> ProduceLotSummaryResponse:
    seller_role, seller_vstatus = _get_seller_meta(lot.seller)
    price_mode = "NEGOTIABLE" if lot.asking_price_per_unit is None else "FIXED_PRICE"
    return ProduceLotSummaryResponse(
        id=lot.id,
        seller_user_id=lot.seller_user_id,
        seller_name=lot.seller.display_name,
        seller_role=seller_role,
        seller_verification_status=seller_vstatus,
        commodity_id=lot.commodity_id,
        commodity_name=lot.commodity.name,
        commodity_category=lot.commodity.category,
        title=lot.title,
        available_quantity=lot.available_quantity,
        unit=lot.unit,
        quality_grade=lot.quality_grade,
        quality_notes=lot.quality_notes,
        asking_price_per_unit=lot.asking_price_per_unit,
        price_mode=price_mode,
        available_from=lot.available_from,
        available_until=lot.available_until,
        is_aggregated=lot.is_aggregated,
        status=lot.status,
        pickup_location=_serialize_location(lot.pickup_location),
        contributions_count=len(lot.contributions),
        created_at=lot.created_at,
    )


def get_produce_lot_detail(db: Session, lot_id: UUID) -> ProduceLotDetailResponse:
    stmt = (
        select(ProduceLot)
        .options(
            selectinload(ProduceLot.seller).selectinload(User.farmer_profile),
            selectinload(ProduceLot.seller).selectinload(User.fpo_profile),
            selectinload(ProduceLot.seller).selectinload(User.user_roles).selectinload(UserRole.role),
            selectinload(ProduceLot.commodity),
            selectinload(ProduceLot.pickup_location),
            selectinload(ProduceLot.contributions),
        )
        .where(ProduceLot.id == lot_id)
    )
    lot = db.scalar(stmt)
    if lot is None:
        raise ApiError(404, "produce_lot_not_found", "Produce listing not found.")

    seller_role, seller_vstatus = _get_seller_meta(lot.seller)
    contributions = [
        ProduceLotContributionResponse(
            id=c.id,
            farmer_profile_id=c.farmer_profile_id,
            fpo_profile_id=c.fpo_profile_id,
            contributed_quantity=c.contributed_quantity,
        )
        for c in lot.contributions
    ]
    return ProduceLotDetailResponse(
        id=lot.id,
        seller_user_id=lot.seller_user_id,
        seller_name=lot.seller.display_name,
        seller_phone=lot.seller.phone_number,
        seller_email=lot.seller.email,
        seller_role=seller_role,
        seller_verification_status=seller_vstatus,
        commodity_id=lot.commodity_id,
        commodity_name=lot.commodity.name,
        commodity_category=lot.commodity.category,
        title=lot.title,
        available_quantity=lot.available_quantity,
        unit=lot.unit,
        quality_grade=lot.quality_grade,
        quality_notes=lot.quality_notes,
        asking_price_per_unit=lot.asking_price_per_unit,
        price_mode="NEGOTIABLE" if lot.asking_price_per_unit is None else "FIXED_PRICE",
        available_from=lot.available_from,
        available_until=lot.available_until,
        is_aggregated=lot.is_aggregated,
        status=lot.status,
        pickup_location=_serialize_location(lot.pickup_location),
        contributions_count=len(contributions),
        contributions=contributions,
        created_at=lot.created_at,
    )


def list_my_produce_lots(db: Session, user: User) -> list[ProduceLotSummaryResponse]:
    stmt = (
        select(ProduceLot)
        .options(
            selectinload(ProduceLot.seller).selectinload(User.farmer_profile),
            selectinload(ProduceLot.seller).selectinload(User.fpo_profile),
            selectinload(ProduceLot.seller).selectinload(User.user_roles).selectinload(UserRole.role),
            selectinload(ProduceLot.commodity),
            selectinload(ProduceLot.pickup_location),
            selectinload(ProduceLot.contributions),
        )
        .where(ProduceLot.seller_user_id == user.id)
        .order_by(ProduceLot.created_at.desc())
    )
    rows = db.scalars(stmt).all()
    return [_serialize_produce_lot_summary(lot) for lot in rows]


def update_produce_lot(db: Session, user: User, lot_id: UUID, payload: ProduceLotUpdateRequest) -> ProduceLotDetailResponse:
    lot = db.get(ProduceLot, lot_id)
    if lot is None:
        raise ApiError(404, "produce_lot_not_found", "Produce listing not found.")
    if lot.seller_user_id != user.id:
        raise ApiError(403, "not_owner", "You can only update your own produce listings.")

    if payload.title is not None:
        lot.title = payload.title
    if payload.available_quantity is not None:
        lot.available_quantity = payload.available_quantity
    if payload.asking_price_per_unit is not None:
        lot.asking_price_per_unit = payload.asking_price_per_unit
    if payload.available_from is not None:
        lot.available_from = payload.available_from
    if payload.available_until is not None:
        lot.available_until = payload.available_until
    if payload.quality_grade is not None:
        lot.quality_grade = payload.quality_grade
    if payload.quality_notes is not None:
        lot.quality_notes = payload.quality_notes
    if payload.status is not None:
        lot.status = payload.status

    db.commit()
    return get_produce_lot_detail(db, lot.id)


def search_marketplace(
    db: Session,
    commodity_id: UUID | None = None,
    category: CommodityCategory | None = None,
    state: str | None = None,
    district: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    min_quantity: Decimal | None = None,
    quality_grade: str | None = None,
    search: str | None = None,
    seller_role: str | None = None,
    sort_by: str | None = "recommended",
    page: int = 1,
    page_size: int = 12,
) -> MarketplaceProduceLotsResponse:
    stmt = (
        select(ProduceLot)
        .join(Commodity, ProduceLot.commodity_id == Commodity.id)
        .join(Location, ProduceLot.pickup_location_id == Location.id)
        .where(ProduceLot.status == ProduceLotStatus.PUBLISHED)
        .where(ProduceLot.available_quantity > 0)
    )

    if commodity_id is not None:
        stmt = stmt.where(ProduceLot.commodity_id == commodity_id)
    if category is not None:
        stmt = stmt.where(Commodity.category == category)
    if state:
        stmt = stmt.where(func.lower(Location.state) == state.strip().lower())
    if district:
        stmt = stmt.where(func.lower(Location.district) == district.strip().lower())
    if min_price is not None:
        stmt = stmt.where(ProduceLot.asking_price_per_unit >= min_price)
    if max_price is not None:
        stmt = stmt.where(ProduceLot.asking_price_per_unit <= max_price)
    if min_quantity is not None:
        stmt = stmt.where(ProduceLot.available_quantity >= min_quantity)
    if quality_grade:
        stmt = stmt.where(func.lower(ProduceLot.quality_grade) == quality_grade.strip().lower())
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(ProduceLot.title).like(search_pattern),
                func.lower(Commodity.name).like(search_pattern),
                func.lower(Location.district).like(search_pattern),
                func.lower(Location.state).like(search_pattern),
            )
        )

    if seller_role:
        role_clean = seller_role.strip().lower()
        if role_clean == "fpo":
            stmt = stmt.join(FPOProfile, ProduceLot.seller_user_id == FPOProfile.user_id)
        elif role_clean == "farmer":
            stmt = stmt.join(FarmerProfile, ProduceLot.seller_user_id == FarmerProfile.user_id)

    # Calculate total count before pagination
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0

    # Apply deterministic sorting
    if sort_by == "price_asc":
        stmt = stmt.order_by(ProduceLot.asking_price_per_unit.asc().nulls_last(), ProduceLot.created_at.desc())
    elif sort_by == "price_desc":
        stmt = stmt.order_by(ProduceLot.asking_price_per_unit.desc().nulls_last(), ProduceLot.created_at.desc())
    elif sort_by == "qty_desc":
        stmt = stmt.order_by(ProduceLot.available_quantity.desc(), ProduceLot.created_at.desc())
    elif sort_by == "qty_asc":
        stmt = stmt.order_by(ProduceLot.available_quantity.asc(), ProduceLot.created_at.desc())
    elif sort_by == "newest":
        stmt = stmt.order_by(ProduceLot.created_at.desc())
    else:  # "recommended" or default
        stmt = stmt.order_by(ProduceLot.created_at.desc())

    # Apply eager loading
    stmt = stmt.options(
        selectinload(ProduceLot.seller).selectinload(User.farmer_profile),
        selectinload(ProduceLot.seller).selectinload(User.fpo_profile),
        selectinload(ProduceLot.seller).selectinload(User.user_roles).selectinload(UserRole.role),
        selectinload(ProduceLot.commodity),
        selectinload(ProduceLot.pickup_location),
        selectinload(ProduceLot.contributions),
    )

    page_num = max(1, page)
    limit_num = max(1, min(page_size, 100))
    offset_num = (page_num - 1) * limit_num

    paginated_stmt = stmt.offset(offset_num).limit(limit_num)
    rows = db.scalars(paginated_stmt).all()
    items = [_serialize_produce_lot_summary(lot) for lot in rows]
    total_pages = (total + limit_num - 1) // limit_num if total > 0 else 1

    return MarketplaceProduceLotsResponse(
        items=items,
        total=total,
        page=page_num,
        page_size=limit_num,
        total_pages=total_pages,
    )


def create_buyer_requirement(db: Session, user: User, payload: BuyerRequirementCreate) -> BuyerRequirementResponse:
    roles = get_user_roles(user)
    if RoleName.BUYER not in roles:
        raise ApiError(403, "insufficient_permissions", "Only buyers can post crop requirements.")

    ensure_user_profile(db, user)
    buyer_profile = user.buyer_profile
    if buyer_profile is None:
        buyer_profile = BuyerProfile(user_id=user.id, organization_name=user.display_name)
        db.add(buyer_profile)
        db.flush()

    commodity = db.get(Commodity, payload.commodity_id)
    if commodity is None or not commodity.is_active:
        raise ApiError(404, "commodity_not_found", "The specified commodity was not found.")

    location = _create_or_get_location(db, payload.delivery_location, payload.delivery_location_id)

    req = BuyerRequirement(
        buyer_profile_id=buyer_profile.id,
        commodity_id=commodity.id,
        delivery_location_id=location.id,
        required_quantity=payload.required_quantity,
        unit=payload.unit,
        minimum_quality_grade=payload.minimum_quality_grade,
        target_price_per_unit=payload.target_price_per_unit,
        delivery_by=payload.delivery_by,
        status=BuyerRequirementStatus.ACTIVE,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _serialize_buyer_requirement(req)


def _serialize_buyer_requirement(req: BuyerRequirement) -> BuyerRequirementResponse:
    buyer_user = req.buyer_profile.user
    return BuyerRequirementResponse(
        id=req.id,
        buyer_user_id=buyer_user.id,
        buyer_name=buyer_user.display_name,
        buyer_organization=req.buyer_profile.organization_name,
        buyer_verification_status=req.buyer_profile.verification_status,
        commodity_id=req.commodity_id,
        commodity_name=req.commodity.name,
        commodity_category=req.commodity.category,
        required_quantity=req.required_quantity,
        unit=req.unit,
        minimum_quality_grade=req.minimum_quality_grade,
        target_price_per_unit=req.target_price_per_unit,
        delivery_by=req.delivery_by,
        delivery_location=_serialize_location(req.delivery_location),
        status=req.status,
        created_at=req.created_at,
    )


def list_buyer_requirements(
    db: Session,
    user: User | None = None,
    my_only: bool = False,
    commodity_id: UUID | None = None,
    category: CommodityCategory | None = None,
) -> list[BuyerRequirementResponse]:
    stmt = (
        select(BuyerRequirement)
        .join(BuyerProfile, BuyerRequirement.buyer_profile_id == BuyerProfile.id)
        .join(Commodity, BuyerRequirement.commodity_id == Commodity.id)
        .join(Location, BuyerRequirement.delivery_location_id == Location.id)
        .options(
            selectinload(BuyerRequirement.buyer_profile).selectinload(BuyerProfile.user),
            selectinload(BuyerRequirement.commodity),
            selectinload(BuyerRequirement.delivery_location),
        )
    )
    if my_only and user is not None:
        stmt = stmt.where(BuyerProfile.user_id == user.id)
    else:
        stmt = stmt.where(BuyerRequirement.status == BuyerRequirementStatus.ACTIVE)

    if commodity_id is not None:
        stmt = stmt.where(BuyerRequirement.commodity_id == commodity_id)
    if category is not None:
        stmt = stmt.where(Commodity.category == category)

    stmt = stmt.order_by(BuyerRequirement.created_at.desc())
    rows = db.scalars(stmt).all()
    return [_serialize_buyer_requirement(r) for r in rows]


def create_offer(db: Session, buyer: User, payload: OfferCreate, ip_address: str | None = None) -> OfferResponse:
    roles = get_user_roles(buyer)
    if RoleName.BUYER not in roles:
        raise ApiError(403, "insufficient_permissions", "Only buyers can make offers on produce lots.")

    lot = db.get(ProduceLot, payload.produce_lot_id)
    if lot is None:
        raise ApiError(404, "produce_lot_not_found", "The specified produce lot was not found.")
    if lot.status != ProduceLotStatus.PUBLISHED:
        raise ApiError(400, "lot_not_available", "This produce listing is no longer available for offers.")
    if lot.available_quantity <= Decimal("0.000"):
        raise ApiError(400, "lot_sold", "This produce lot is completely sold out.")
    if payload.offered_quantity <= Decimal("0.000"):
        raise ApiError(400, "invalid_quantity", "Offered quantity must be greater than zero.")
    if payload.offered_quantity > lot.available_quantity:
        raise ApiError(400, "quantity_exceeded", f"Offered quantity exceeds available quantity of {lot.available_quantity} {lot.unit}.")
    if payload.offered_price_per_unit <= Decimal("0.00"):
        raise ApiError(400, "invalid_price", "Offered price per unit must be greater than zero.")
    if lot.seller_user_id == buyer.id:
        raise ApiError(400, "self_offer_forbidden", "You cannot make an offer on your own produce listing.")

    offer = Offer(
        buyer_user_id=buyer.id,
        produce_lot_id=lot.id,
        buyer_requirement_id=payload.buyer_requirement_id,
        offered_quantity=payload.offered_quantity,
        offered_price_per_unit=payload.offered_price_per_unit,
        current_price_per_unit=payload.offered_price_per_unit,
        current_quantity=payload.offered_quantity,
        current_proposer_user_id=buyer.id,
        current_proposer_role="buyer",
        response_required_from_user_id=lot.seller_user_id,
        expires_at=payload.expires_at,
        status=OfferStatus.PENDING,
    )
    db.add(offer)
    db.flush()

    initial_proposal = OfferProposal(
        offer_id=offer.id,
        proposer_user_id=buyer.id,
        proposer_role="buyer",
        price_per_unit=payload.offered_price_per_unit,
        quantity=payload.offered_quantity,
        notes=payload.notes,
        status_at_step="proposed",
    )
    db.add(initial_proposal)
    db.flush()

    emit_idempotent_notification(
        db=db,
        recipient_user_id=lot.seller_user_id,
        notification_type="offer_received",
        title="New Commercial Offer Received",
        body=f"{buyer.display_name} offered ₹{payload.offered_price_per_unit:,.2f}/{lot.unit} for {payload.offered_quantity} {lot.unit} of {lot.title}.",
        data_json={"offer_id": str(offer.id), "lot_id": str(lot.id)},
        dedupe_key="offer_id",
    )

    record_audit_event(
        db,
        event_type="offer.created",
        entity_type="offer",
        entity_id=offer.id,
        actor_user_id=buyer.id,
        metadata={"lot_id": str(lot.id), "quantity": str(payload.offered_quantity), "price": str(payload.offered_price_per_unit)},
        ip_address=ip_address,
    )
    db.commit()
    return _get_offer_detail_with_relations(db, offer.id)


def _serialize_offer(offer: Offer) -> OfferResponse:
    price_mode = "NEGOTIABLE" if offer.produce_lot.asking_price_per_unit is None else "FIXED_PRICE"
    cur_price = offer.current_price_per_unit if offer.current_price_per_unit is not None else offer.offered_price_per_unit
    cur_qty = offer.current_quantity if offer.current_quantity is not None else offer.offered_quantity
    total = cur_qty * cur_price

    cur_proposer_id = offer.current_proposer_user_id or offer.buyer_user_id
    cur_proposer_name = (
        offer.current_proposer.display_name
        if offer.current_proposer
        else (offer.buyer.display_name if cur_proposer_id == offer.buyer_user_id else offer.produce_lot.seller.display_name)
    )
    cur_proposer_role = offer.current_proposer_role or "buyer"

    resp_required_id = offer.response_required_from_user_id or offer.produce_lot.seller_user_id
    resp_required_name = (
        offer.response_required_from_user.display_name
        if offer.response_required_from_user
        else (offer.produce_lot.seller.display_name if resp_required_id == offer.produce_lot.seller_user_id else offer.buyer.display_name)
    )

    proposals_sorted = sorted(offer.proposals or [], key=lambda p: p.created_at)
    history = [
        NegotiationProposalResponse(
            id=p.id,
            proposer_user_id=p.proposer_user_id,
            proposer_name=(
                p.proposer.display_name
                if p.proposer
                else (offer.buyer.display_name if p.proposer_user_id == offer.buyer_user_id else offer.produce_lot.seller.display_name)
            ),
            proposer_role=p.proposer_role,
            price_per_unit=p.price_per_unit,
            quantity=p.quantity,
            total_amount=p.quantity * p.price_per_unit,
            notes=p.notes,
            status_at_step=p.status_at_step,
            created_at=p.created_at,
        )
        for p in proposals_sorted
    ]

    return OfferResponse(
        id=offer.id,
        produce_lot_id=offer.produce_lot_id,
        produce_title=offer.produce_lot.title,
        commodity_name=offer.produce_lot.commodity.name,
        buyer_user_id=offer.buyer_user_id,
        buyer_name=offer.buyer.display_name,
        seller_user_id=offer.produce_lot.seller_user_id,
        seller_name=offer.produce_lot.seller.display_name,
        offered_quantity=offer.offered_quantity,
        unit=offer.produce_lot.unit,
        offered_price_per_unit=offer.offered_price_per_unit,
        current_price_per_unit=cur_price,
        current_quantity=cur_qty,
        total_amount=total,
        price_mode=price_mode,
        current_proposer_user_id=cur_proposer_id,
        current_proposer_name=cur_proposer_name,
        current_proposer_role=cur_proposer_role,
        response_required_from_user_id=resp_required_id,
        response_required_from_name=resp_required_name,
        expires_at=offer.expires_at,
        status=offer.status,
        history=history,
        created_at=offer.created_at,
    )


def _get_offer_detail_with_relations(db: Session, offer_id: UUID) -> OfferResponse:
    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.buyer),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.seller),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.commodity),
            selectinload(Offer.current_proposer),
            selectinload(Offer.response_required_from_user),
            selectinload(Offer.proposals).selectinload(OfferProposal.proposer),
        )
        .where(Offer.id == offer_id)
    )
    offer = db.scalar(stmt)
    if offer is None:
        raise ApiError(404, "offer_not_found", "Offer not found.")
    return _serialize_offer(offer)


def list_offers(
    db: Session,
    user: User,
    role_perspective: str | None = None,
    status: OfferStatus | None = None,
    lot_id: UUID | None = None,
) -> list[OfferResponse]:
    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.buyer),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.seller),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.commodity),
            selectinload(Offer.current_proposer),
            selectinload(Offer.response_required_from_user),
            selectinload(Offer.proposals).selectinload(OfferProposal.proposer),
        )
    )

    if role_perspective == "sent":
        stmt = stmt.where(Offer.buyer_user_id == user.id)
    elif role_perspective == "received":
        stmt = stmt.join(ProduceLot, Offer.produce_lot_id == ProduceLot.id).where(ProduceLot.seller_user_id == user.id)
    else:
        stmt = stmt.join(ProduceLot, Offer.produce_lot_id == ProduceLot.id).where(
            or_(Offer.buyer_user_id == user.id, ProduceLot.seller_user_id == user.id)
        )

    if status is not None:
        stmt = stmt.where(Offer.status == status)
    if lot_id is not None:
        stmt = stmt.where(Offer.produce_lot_id == lot_id)

    stmt = stmt.order_by(Offer.created_at.desc())
    rows = db.scalars(stmt).all()
    return [_serialize_offer(o) for o in rows]


def counter_offer(
    db: Session,
    user: User,
    offer_id: UUID,
    payload: CounterOfferCreate,
    ip_address: str | None = None,
) -> OfferResponse:
    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.buyer),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.seller),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.commodity),
            selectinload(Offer.current_proposer),
            selectinload(Offer.response_required_from_user),
            selectinload(Offer.proposals).selectinload(OfferProposal.proposer),
        )
        .where(Offer.id == offer_id)
        .with_for_update()
    )
    offer = db.scalar(stmt)
    if offer is None:
        raise ApiError(404, "offer_not_found", "Offer not found.")

    lot = offer.produce_lot
    is_seller = lot.seller_user_id == user.id
    is_buyer = offer.buyer_user_id == user.id

    if not (is_seller or is_buyer):
        raise ApiError(403, "not_authorized", "You are not an authorized participant in this commercial offer.")

    if offer.status not in (OfferStatus.PENDING, OfferStatus.COUNTERED):
        raise ApiError(400, "invalid_offer_status", f"Cannot counter an offer with status '{offer.status.value}'.")

    if lot.status != ProduceLotStatus.PUBLISHED:
        raise ApiError(400, "lot_not_available", "The produce listing is no longer published or available.")

    # Strict turn-based validation
    if offer.response_required_from_user_id and user.id != offer.response_required_from_user_id:
        raise ApiError(400, "not_your_turn", "It is not your turn to respond to this proposal.")

    if offer.current_proposer_user_id and user.id == offer.current_proposer_user_id:
        raise ApiError(400, "self_counter_forbidden", "You cannot submit a counter-offer to your own proposal.")

    new_quantity = payload.quantity if payload.quantity is not None else (offer.current_quantity or offer.offered_quantity)
    if new_quantity > lot.available_quantity:
        raise ApiError(400, "quantity_exceeded", f"Counter quantity ({new_quantity} {lot.unit}) exceeds available quantity ({lot.available_quantity} {lot.unit}).")

    # Mark existing active proposals as countered
    for p in offer.proposals:
        if p.status_at_step == "proposed":
            p.status_at_step = "countered"

    proposer_role = "seller" if is_seller else "buyer"
    next_recipient_user_id = offer.buyer_user_id if is_seller else lot.seller_user_id

    new_proposal = OfferProposal(
        offer_id=offer.id,
        proposer_user_id=user.id,
        proposer_role=proposer_role,
        price_per_unit=payload.price_per_unit,
        quantity=new_quantity,
        notes=payload.notes,
        status_at_step="proposed",
    )
    db.add(new_proposal)

    offer.status = OfferStatus.COUNTERED
    offer.current_price_per_unit = payload.price_per_unit
    offer.current_quantity = new_quantity
    offer.current_proposer_user_id = user.id
    offer.current_proposer_role = proposer_role
    offer.response_required_from_user_id = next_recipient_user_id

    actor_label = "Farmer" if is_seller else "Buyer"
    emit_idempotent_notification(
        db=db,
        recipient_user_id=next_recipient_user_id,
        notification_type="offer_countered",
        title=f"Counter-Offer from {user.display_name}",
        body=f"{actor_label} sent a counter-offer: ₹{payload.price_per_unit:,.2f}/{lot.unit} for {new_quantity} {lot.unit} of {lot.title}.",
        data_json={"offer_id": str(offer.id), "proposal_price": str(payload.price_per_unit)},
        dedupe_key="offer_id",
    )

    record_audit_event(
        db,
        event_type="offer.countered",
        entity_type="offer",
        entity_id=offer.id,
        actor_user_id=user.id,
        metadata={"price": str(payload.price_per_unit), "quantity": str(new_quantity)},
        ip_address=ip_address,
    )
    db.commit()
    return _get_offer_detail_with_relations(db, offer.id)


def accept_offer(db: Session, user: User, offer_id: UUID, ip_address: str | None = None) -> OrderResponse:
    # 1. Idempotency check: if order already exists for this offer, return it
    existing_order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.buyer),
            selectinload(Order.seller),
            selectinload(Order.delivery_location),
            selectinload(Order.items).selectinload(OrderItem.commodity),
        )
        .where(Order.accepted_offer_id == offer_id)
    )
    if existing_order is not None:
        return _serialize_order(existing_order)

    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.buyer),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.seller),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.commodity),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.pickup_location),
            selectinload(Offer.current_proposer),
            selectinload(Offer.response_required_from_user),
            selectinload(Offer.proposals),
        )
        .where(Offer.id == offer_id)
        .with_for_update()
    )
    offer = db.scalar(stmt)
    if offer is None:
        raise ApiError(404, "offer_not_found", "Offer not found.")

    lot = offer.produce_lot
    is_seller = lot.seller_user_id == user.id
    is_buyer = offer.buyer_user_id == user.id

    if not (is_seller or is_buyer):
        raise ApiError(403, "not_authorized", "You are not authorized to accept this commercial offer.")

    if offer.status == OfferStatus.ACCEPTED:
        existing_order = db.scalar(
            select(Order)
            .options(
                selectinload(Order.buyer),
                selectinload(Order.seller),
                selectinload(Order.delivery_location),
                selectinload(Order.items).selectinload(OrderItem.commodity),
            )
            .where(Order.accepted_offer_id == offer_id)
        )
        if existing_order:
            return _serialize_order(existing_order)

    if offer.status not in (OfferStatus.PENDING, OfferStatus.COUNTERED):
        raise ApiError(400, "invalid_offer_status", f"Cannot accept offer with status '{offer.status.value}'.")

    # Strict turn-based permission: only the party responding to the current proposal can accept
    if offer.response_required_from_user_id and user.id != offer.response_required_from_user_id:
        raise ApiError(400, "not_your_turn", "You cannot accept your own proposal. Waiting for counterparty response.")

    qty_to_transact = offer.current_quantity if offer.current_quantity is not None else offer.offered_quantity
    price_to_transact = offer.current_price_per_unit if offer.current_price_per_unit is not None else offer.offered_price_per_unit

    if lot.available_quantity < qty_to_transact:
        raise ApiError(400, "insufficient_quantity", f"Available quantity on produce lot ({lot.available_quantity} {lot.unit}) is less than requested quantity ({qty_to_transact} {lot.unit}).")

    offer.status = OfferStatus.ACCEPTED
    for p in offer.proposals:
        if p.status_at_step == "proposed":
            p.status_at_step = "accepted"

    lot.available_quantity -= qty_to_transact
    if lot.available_quantity <= Decimal("0.000"):
        lot.available_quantity = Decimal("0.000")
        lot.status = ProduceLotStatus.SOLD

    total_order_amount = qty_to_transact * price_to_transact
    now = datetime.now(UTC)

    order = Order(
        buyer_user_id=offer.buyer_user_id,
        seller_user_id=lot.seller_user_id,
        accepted_offer_id=offer.id,
        delivery_location_id=lot.pickup_location_id,
        status=OrderStatus.CONFIRMED,
        total_amount=total_order_amount,
        confirmed_at=now,
    )
    db.add(order)
    db.flush()

    order_item = OrderItem(
        order_id=order.id,
        produce_lot_id=lot.id,
        commodity_id=lot.commodity_id,
        quantity=qty_to_transact,
        unit=lot.unit,
        agreed_price_per_unit=price_to_transact,
    )
    db.add(order_item)

    # Notify proposer that their offer/counter was accepted
    proposer_id = offer.current_proposer_user_id or (offer.buyer_user_id if is_seller else lot.seller_user_id)
    emit_idempotent_notification(
        db=db,
        recipient_user_id=proposer_id,
        notification_type="offer_accepted",
        title="Offer Accepted! Order Confirmed",
        body=f"{user.display_name} accepted the proposal for {qty_to_transact} {lot.unit} of {lot.title} at ₹{price_to_transact:,.2f}/{lot.unit}. Total: ₹{total_order_amount:,.2f}.",
        data_json={"order_id": str(order.id), "offer_id": str(offer.id)},
        dedupe_key="order_id",
    )

    record_audit_event(
        db,
        event_type="order.confirmed",
        entity_type="order",
        entity_id=order.id,
        actor_user_id=user.id,
        metadata={"offer_id": str(offer.id), "total_amount": str(total_order_amount), "agreed_price": str(price_to_transact)},
        ip_address=ip_address,
    )
    db.commit()
    return get_order_detail(db, user, order.id)


def reject_offer(db: Session, user: User, offer_id: UUID, ip_address: str | None = None) -> OfferResponse:
    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.buyer),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.seller),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.commodity),
            selectinload(Offer.current_proposer),
            selectinload(Offer.response_required_from_user),
            selectinload(Offer.proposals).selectinload(OfferProposal.proposer),
        )
        .where(Offer.id == offer_id)
    )
    offer = db.scalar(stmt)
    if offer is None:
        raise ApiError(404, "offer_not_found", "Offer not found.")

    lot = offer.produce_lot
    is_seller = lot.seller_user_id == user.id
    is_buyer = offer.buyer_user_id == user.id

    if not (is_seller or is_buyer):
        raise ApiError(403, "not_authorized", "You are not an authorized participant in this commercial offer.")

    if offer.status not in (OfferStatus.PENDING, OfferStatus.COUNTERED):
        raise ApiError(400, "invalid_offer_status", f"Cannot decline offer with status '{offer.status.value}'.")

    if offer.response_required_from_user_id and user.id != offer.response_required_from_user_id:
        raise ApiError(400, "not_your_turn", "You cannot decline an offer you proposed. You can withdraw it instead.")

    offer.status = OfferStatus.DECLINED
    for p in offer.proposals:
        if p.status_at_step == "proposed":
            p.status_at_step = "declined"

    proposer_id = offer.current_proposer_user_id or (offer.buyer_user_id if is_seller else lot.seller_user_id)
    emit_idempotent_notification(
        db=db,
        recipient_user_id=proposer_id,
        notification_type="offer_declined",
        title="Offer Declined",
        body=f"Your proposal for {offer.produce_lot.title} was declined by {user.display_name}.",
        data_json={"offer_id": str(offer.id)},
        dedupe_key="offer_id",
    )

    record_audit_event(
        db,
        event_type="offer.declined",
        entity_type="offer",
        entity_id=offer.id,
        actor_user_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    return _get_offer_detail_with_relations(db, offer.id)


def withdraw_offer(db: Session, user: User, offer_id: UUID, ip_address: str | None = None) -> OfferResponse:
    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.buyer),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.seller),
            selectinload(Offer.produce_lot).selectinload(ProduceLot.commodity),
            selectinload(Offer.current_proposer),
            selectinload(Offer.response_required_from_user),
            selectinload(Offer.proposals).selectinload(OfferProposal.proposer),
        )
        .where(Offer.id == offer_id)
    )
    offer = db.scalar(stmt)
    if offer is None:
        raise ApiError(404, "offer_not_found", "Offer not found.")

    lot = offer.produce_lot
    is_seller = lot.seller_user_id == user.id
    is_buyer = offer.buyer_user_id == user.id

    if not (is_seller or is_buyer):
        raise ApiError(403, "not_authorized", "You are not an authorized participant in this commercial offer.")

    if offer.status not in (OfferStatus.PENDING, OfferStatus.COUNTERED):
        raise ApiError(400, "invalid_offer_status", f"Cannot withdraw offer with status '{offer.status.value}'.")

    # Proposer can withdraw their active proposal before acceptance
    if offer.current_proposer_user_id and user.id != offer.current_proposer_user_id and not is_buyer:
        raise ApiError(403, "not_proposer", "Only the party who submitted the active proposal can withdraw it.")

    offer.status = OfferStatus.WITHDRAWN
    for p in offer.proposals:
        if p.status_at_step == "proposed":
            p.status_at_step = "withdrawn"

    record_audit_event(
        db,
        event_type="offer.withdrawn",
        entity_type="offer",
        entity_id=offer.id,
        actor_user_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    return _get_offer_detail_with_relations(db, offer.id)


def _serialize_order(order: Order) -> OrderResponse:
    items = [
        OrderItemResponse(
            id=item.id,
            produce_lot_id=item.produce_lot_id,
            commodity_id=item.commodity_id,
            commodity_name=item.commodity.name,
            quantity=item.quantity,
            unit=item.unit,
            agreed_price_per_unit=item.agreed_price_per_unit,
            total_item_amount=item.quantity * item.agreed_price_per_unit,
        )
        for item in order.items
    ]
    return OrderResponse(
        id=order.id,
        buyer_user_id=order.buyer_user_id,
        buyer_name=order.buyer.display_name,
        seller_user_id=order.seller_user_id,
        seller_name=order.seller.display_name,
        accepted_offer_id=order.accepted_offer_id,
        status=order.status,
        total_amount=order.total_amount,
        confirmed_at=order.confirmed_at,
        delivery_location=_serialize_location(order.delivery_location),
        items=items,
        created_at=order.created_at,
    )


def list_orders(db: Session, user: User) -> list[OrderResponse]:
    roles = get_user_roles(user)
    is_admin = RoleName.ADMIN in roles

    stmt = (
        select(Order)
        .options(
            selectinload(Order.buyer),
            selectinload(Order.seller),
            selectinload(Order.delivery_location),
            selectinload(Order.items).selectinload(OrderItem.commodity),
        )
    )
    if not is_admin:
        stmt = stmt.where(or_(Order.buyer_user_id == user.id, Order.seller_user_id == user.id))

    stmt = stmt.order_by(Order.created_at.desc())
    rows = db.scalars(stmt).all()
    return [_serialize_order(o) for o in rows]


def get_order_detail(db: Session, user: User, order_id: UUID) -> OrderResponse:
    roles = get_user_roles(user)
    is_admin = RoleName.ADMIN in roles

    stmt = (
        select(Order)
        .options(
            selectinload(Order.buyer),
            selectinload(Order.seller),
            selectinload(Order.delivery_location),
            selectinload(Order.items).selectinload(OrderItem.commodity),
        )
        .where(Order.id == order_id)
    )
    order = db.scalar(stmt)
    if order is None:
        raise ApiError(404, "order_not_found", "Order not found.")
    if not is_admin and order.buyer_user_id != user.id and order.seller_user_id != user.id:
        raise ApiError(403, "access_denied", "You do not have permission to view this order.")
    return _serialize_order(order)


def update_order_status(db: Session, user: User, order_id: UUID, new_status: OrderStatus, ip_address: str | None = None) -> OrderResponse:
    order = db.get(Order, order_id)
    if order is None:
        raise ApiError(404, "order_not_found", "Order not found.")

    roles = get_user_roles(user)
    is_admin = RoleName.ADMIN in roles
    is_seller = order.seller_user_id == user.id
    is_buyer = order.buyer_user_id == user.id

    if not (is_admin or is_seller or is_buyer):
        raise ApiError(403, "access_denied", "You cannot update this order.")

    valid_transitions: dict[OrderStatus, list[OrderStatus]] = {
        OrderStatus.DRAFT: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
        OrderStatus.CONFIRMED: [OrderStatus.FULFILMENT, OrderStatus.CANCELLED],
        OrderStatus.FULFILMENT: [OrderStatus.DELIVERED, OrderStatus.CANCELLED],
        OrderStatus.DELIVERED: [],
        OrderStatus.CANCELLED: [],
    }

    if new_status not in valid_transitions.get(order.status, []):
        raise ApiError(400, "invalid_status_transition", f"Cannot transition order from '{order.status.value}' to '{new_status.value}'.")

    order.status = new_status

    other_user_id = order.buyer_user_id if user.id == order.seller_user_id else order.seller_user_id
    notification = Notification(
        recipient_user_id=other_user_id,
        notification_type="order_status_updated",
        title="Order Status Updated",
        body=f"Order #{str(order.id)[:8]} status changed to {new_status.value.upper()}.",
        data_json={"order_id": str(order.id), "status": new_status.value},
    )
    db.add(notification)

    record_audit_event(
        db,
        event_type="order.status_updated",
        entity_type="order",
        entity_id=order.id,
        actor_user_id=user.id,
        metadata={"new_status": new_status.value},
        ip_address=ip_address,
    )
    db.commit()
    return get_order_detail(db, user, order.id)


def submit_verification_request(db: Session, user: User, payload: VerificationCreateRequest) -> VerificationRequestResponse:
    ensure_user_profile(db, user)
    roles = get_user_roles(user)

    subject_type = "farmer"
    subject_id = user.id
    if RoleName.FPO in roles and user.fpo_profile:
        subject_type = "fpo"
        subject_id = user.fpo_profile.id
    elif RoleName.BUYER in roles and user.buyer_profile:
        subject_type = "buyer"
        subject_id = user.buyer_profile.id
    elif RoleName.TRANSPORTER in roles and user.transporter_profile:
        subject_type = "transporter"
        subject_id = user.transporter_profile.id
    elif user.farmer_profile:
        subject_type = "farmer"
        subject_id = user.farmer_profile.id

    req = VerificationRequest(
        requested_by_user_id=user.id,
        subject_type=subject_type,
        subject_id=subject_id,
        status=VerificationStatus.PENDING,
        document_reference=payload.document_reference,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return VerificationRequestResponse(
        id=req.id,
        requested_by_user_id=req.requested_by_user_id,
        user_name=user.display_name,
        user_email=user.email,
        user_role=subject_type,
        subject_type=req.subject_type,
        subject_id=req.subject_id,
        status=req.status,
        document_reference=req.document_reference,
        reviewer_notes=req.reviewer_notes,
        reviewed_at=req.reviewed_at,
        created_at=req.created_at,
    )


def list_verification_requests(db: Session, status: VerificationStatus | None = None) -> list[VerificationRequestResponse]:
    stmt = (
        select(VerificationRequest)
        .options(selectinload(VerificationRequest.requested_by_user))
        .order_by(VerificationRequest.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(VerificationRequest.status == status)

    rows = db.scalars(stmt).all()
    results = []
    for r in rows:
        user_name = r.requested_by_user.display_name if r.requested_by_user else "Unknown"
        user_email = r.requested_by_user.email if r.requested_by_user else "Unknown"
        results.append(
            VerificationRequestResponse(
                id=r.id,
                requested_by_user_id=r.requested_by_user_id,
                user_name=user_name,
                user_email=user_email,
                user_role=r.subject_type,
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                status=r.status,
                document_reference=r.document_reference,
                reviewer_notes=r.reviewer_notes,
                reviewed_at=r.reviewed_at,
                created_at=r.created_at,
            )
        )
    return results


def review_verification_request(
    db: Session, admin_user: User, request_id: UUID, payload: VerificationReviewRequest, ip_address: str | None = None
) -> VerificationRequestResponse:
    req = db.get(VerificationRequest, request_id)
    if req is None:
        raise ApiError(404, "request_not_found", "Verification request not found.")

    req.status = payload.status
    req.reviewer_user_id = admin_user.id
    req.reviewer_notes = payload.reviewer_notes
    req.reviewed_at = datetime.now(UTC)

    target_user = db.get(User, req.requested_by_user_id) if req.requested_by_user_id else None
    if target_user:
        if target_user.farmer_profile:
            target_user.farmer_profile.verification_status = payload.status
        if target_user.fpo_profile:
            target_user.fpo_profile.verification_status = payload.status
        if target_user.buyer_profile:
            target_user.buyer_profile.verification_status = payload.status
        if target_user.transporter_profile:
            target_user.transporter_profile.verification_status = payload.status

        notification = Notification(
            recipient_user_id=target_user.id,
            notification_type="verification_update",
            title=f"Verification {payload.status.value.capitalize()}",
            body=f"Your profile verification status is now {payload.status.value.upper()}.",
            data_json={"status": payload.status.value, "notes": payload.reviewer_notes},
        )
        db.add(notification)

    record_audit_event(
        db,
        event_type="verification.reviewed",
        entity_type="verification_request",
        entity_id=req.id,
        actor_user_id=admin_user.id,
        metadata={"status": payload.status.value, "subject_type": req.subject_type},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(req)

    user_name = target_user.display_name if target_user else "Unknown"
    user_email = target_user.email if target_user else "Unknown"
    return VerificationRequestResponse(
        id=req.id,
        requested_by_user_id=req.requested_by_user_id,
        user_name=user_name,
        user_email=user_email,
        user_role=req.subject_type,
        subject_type=req.subject_type,
        subject_id=req.subject_id,
        status=req.status,
        document_reference=req.document_reference,
        reviewer_notes=req.reviewer_notes,
        reviewed_at=req.reviewed_at,
        created_at=req.created_at,
    )


def get_platform_metrics(db: Session) -> PlatformMetricsResponse:
    total_users = db.scalar(select(func.count(User.id))) or 0
    total_farmers = db.scalar(select(func.count(FarmerProfile.id))) or 0
    total_fpos = db.scalar(select(func.count(FPOProfile.id))) or 0
    total_buyers = db.scalar(select(func.count(BuyerProfile.id))) or 0
    total_commodities = db.scalar(select(func.count(Commodity.id)).where(Commodity.is_active.is_(True))) or 0
    active_lots = db.scalar(select(func.count(ProduceLot.id)).where(ProduceLot.status == ProduceLotStatus.PUBLISHED)) or 0
    active_reqs = db.scalar(select(func.count(BuyerRequirement.id)).where(BuyerRequirement.status == BuyerRequirementStatus.ACTIVE)) or 0
    total_offers = db.scalar(select(func.count(Offer.id))) or 0
    pending_offers = db.scalar(select(func.count(Offer.id)).where(Offer.status == OfferStatus.PENDING)) or 0
    confirmed_orders = db.scalar(select(func.count(Order.id)).where(Order.status != OrderStatus.CANCELLED)) or 0
    total_gmv = db.scalar(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.status != OrderStatus.CANCELLED)) or Decimal(0)
    pending_verifications = db.scalar(select(func.count(VerificationRequest.id)).where(VerificationRequest.status == VerificationStatus.PENDING)) or 0

    return PlatformMetricsResponse(
        total_users=total_users,
        total_farmers=total_farmers,
        total_fpos=total_fpos,
        total_buyers=total_buyers,
        total_commodities=total_commodities,
        active_produce_lots=active_lots,
        active_buyer_requirements=active_reqs,
        total_offers=total_offers,
        pending_offers=pending_offers,
        confirmed_orders=confirmed_orders,
        total_gmv=Decimal(total_gmv),
        pending_verifications=pending_verifications,
    )


def list_notifications(db: Session, user: User) -> list[NotificationResponse]:
    stmt = (
        select(Notification)
        .where(Notification.recipient_user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    rows = db.scalars(stmt).all()
    return [
        NotificationResponse(
            id=n.id,
            notification_type=n.notification_type,
            title=n.title,
            body=n.body,
            data_json=n.data_json,
            read_at=n.read_at,
            created_at=n.created_at,
        )
        for n in rows
    ]


def mark_notification_read(db: Session, user: User, notification_id: UUID) -> NotificationResponse:
    notif = db.get(Notification, notification_id)
    if notif is None or notif.recipient_user_id != user.id:
        raise ApiError(404, "notification_not_found", "Notification not found.")
    notif.read_at = datetime.now(UTC)
    db.commit()
    db.refresh(notif)
    return NotificationResponse(
        id=notif.id,
        notification_type=notif.notification_type,
        title=notif.title,
        body=notif.body,
        data_json=notif.data_json,
        read_at=notif.read_at,
        created_at=notif.created_at,
    )


def emit_idempotent_notification(
    db: Session,
    recipient_user_id: UUID,
    notification_type: str,
    title: str,
    body: str,
    data_json: dict[str, Any] | None = None,
    dedupe_key: str = "opportunity_id",
) -> Notification:
    """
    Emits an in-app notification idempotently. If a notification for the same recipient,
    notification_type, and entity identifier (e.g. opportunity_id or shipment_id in data_json)
    already exists, returns the existing notification without creating duplicate rows.
    """
    if data_json and dedupe_key in data_json:
        dedupe_val = str(data_json[dedupe_key])
        existing_notifications = db.scalars(
            select(Notification).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.notification_type == notification_type,
            )
        ).all()
        for notif in existing_notifications:
            if notif.data_json and str(notif.data_json.get(dedupe_key)) == dedupe_val:
                return notif

    new_notif = Notification(
        recipient_user_id=recipient_user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        data_json=data_json,
    )
    db.add(new_notif)
    db.flush()
    return new_notif

