from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GeoPoint


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [e.value for e in enum_cls]


class RoleName(str, enum.Enum):
    FARMER = "farmer"
    FPO = "fpo"
    BUYER = "buyer"
    TRANSPORTER = "transporter"
    ADMIN = "admin"
    GOVERNMENT = "government"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CommodityCategory(str, enum.Enum):
    VEGETABLES = "vegetables"
    FRUITS = "fruits"
    GRAINS = "grains"
    PULSES = "pulses"
    SPICES = "spices"
    OTHER_CROPS = "other_crops"


class ProduceLotStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RESERVED = "reserved"
    SOLD = "sold"
    CANCELLED = "cancelled"


class BuyerRequirementStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class OfferStatus(str, enum.Enum):
    PENDING = "pending"
    COUNTERED = "countered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    FULFILMENT = "fulfilment"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class SourceType(str, enum.Enum):
    GOVERNMENT = "government"
    BUYER_RESEARCH = "buyer_research"
    LOGISTICS_RESEARCH = "logistics_research"
    PARTNER = "partner"
    MANUAL = "manual"
    MOCK = "mock"


class SourceVerificationStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"
    STALE = "stale"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        SqlEnum(UserStatus, name="user_status", native_enum=False, values_callable=enum_values),
        default=UserStatus.PENDING,
        nullable=False,
    )
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="UserRole.user_id"
    )
    farmer_profile: Mapped[FarmerProfile | None] = relationship(back_populates="user", uselist=False)
    fpo_profile: Mapped[FPOProfile | None] = relationship(back_populates="user", uselist=False)
    buyer_profile: Mapped[BuyerProfile | None] = relationship(back_populates="user", uselist=False)
    transporter_profile: Mapped[TransporterProfile | None] = relationship(back_populates="user", uselist=False)
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[RoleName] = mapped_column(
        SqlEnum(RoleName, name="role_name", native_enum=False, values_callable=enum_values),
        unique=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    user_roles: Mapped[list[UserRole]] = relationship(back_populates="role")


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="user_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    user: Mapped[User] = relationship(back_populates="user_roles", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(back_populates="user_roles")


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"),
        Index("ix_locations_geo_point", "geo_point", postgresql_using="gist"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    village: Mapped[str | None] = mapped_column(String(160), index=True)
    taluka: Mapped[str | None] = mapped_column(String(160), index=True)
    district: Mapped[str | None] = mapped_column(String(160), index=True)
    state: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(16))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    geo_point: Mapped[str | None] = mapped_column(GeoPoint())


class FarmerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "farmer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    primary_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    farm_name: Mapped[str | None] = mapped_column(String(160))
    land_area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SqlEnum(VerificationStatus, name="verification_status", native_enum=False, values_callable=enum_values),
        default=VerificationStatus.PENDING,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="farmer_profile")
    primary_location: Mapped[Location | None] = relationship()


class FPOProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fpo_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    primary_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(128), unique=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SqlEnum(VerificationStatus, name="verification_status", native_enum=False, values_callable=enum_values),
        default=VerificationStatus.PENDING,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="fpo_profile")
    primary_location: Mapped[Location | None] = relationship()


class BuyerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "buyer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    primary_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(32), unique=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SqlEnum(VerificationStatus, name="verification_status", native_enum=False, values_callable=enum_values),
        default=VerificationStatus.PENDING,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="buyer_profile")
    primary_location: Mapped[Location | None] = relationship()


class TransporterProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transporter_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    primary_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SqlEnum(VerificationStatus, name="verification_status", native_enum=False, values_callable=enum_values),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    operational_status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    service_area_districts: Mapped[list[str] | None] = mapped_column(JSON)
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    preferred_commodities: Mapped[list[str] | None] = mapped_column(JSON)

    user: Mapped[User] = relationship(back_populates="transporter_profile")
    primary_location: Mapped[Location | None] = relationship()
    opportunities: Mapped[list[TransportOpportunity]] = relationship(back_populates="transporter_profile", cascade="all, delete-orphan")
    quotes: Mapped[list[TransporterQuote]] = relationship(back_populates="transporter_profile", cascade="all, delete-orphan")


class DataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1",
            name="confidence_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        SqlEnum(SourceType, name="source_type", native_enum=False, values_callable=enum_values), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(2048))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[SourceVerificationStatus] = mapped_column(
        SqlEnum(SourceVerificationStatus, name="source_verification_status", native_enum=False, values_callable=enum_values),
        default=SourceVerificationStatus.UNVERIFIED,
        nullable=False,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class SourceAttribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_attributions"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1",
            name="confidence_range",
        ),
        Index("ix_source_attributions_entity", "entity_type", "entity_id"),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    external_record_id: Mapped[str | None] = mapped_column(String(255))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[SourceVerificationStatus] = mapped_column(
        SqlEnum(SourceVerificationStatus, name="source_verification_status", native_enum=False, values_callable=enum_values),
        default=SourceVerificationStatus.UNVERIFIED,
        nullable=False,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    data_source: Mapped[DataSource] = relationship()


class Commodity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commodities"

    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    category: Mapped[CommodityCategory] = mapped_column(
        SqlEnum(CommodityCategory, name="commodity_category", native_enum=False, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    default_unit: Mapped[str] = mapped_column(String(24), default="kg", nullable=False)
    is_perishable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    storage_guidance: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProduceLot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "produce_lots"
    __table_args__ = (
        CheckConstraint("available_quantity >= 0", name="available_quantity_nonnegative"),
        CheckConstraint("asking_price_per_unit IS NULL OR asking_price_per_unit >= 0", name="asking_price_nonnegative"),
        Index("ix_produce_lots_marketplace", "commodity_id", "status", "available_from"),
    )

    seller_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    owner_fpo_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fpo_profiles.id", ondelete="SET NULL"))
    commodity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False)
    pickup_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), default="kg", nullable=False)
    quality_grade: Mapped[str | None] = mapped_column(String(80))
    quality_notes: Mapped[str | None] = mapped_column(Text)
    asking_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    available_until: Mapped[date | None] = mapped_column(Date)
    is_aggregated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[ProduceLotStatus] = mapped_column(
        SqlEnum(ProduceLotStatus, name="produce_lot_status", native_enum=False, values_callable=enum_values),
        default=ProduceLotStatus.DRAFT,
        nullable=False,
    )

    seller: Mapped[User] = relationship(foreign_keys=[seller_user_id])
    owner_fpo_profile: Mapped[FPOProfile | None] = relationship()
    commodity: Mapped[Commodity] = relationship()
    pickup_location: Mapped[Location] = relationship()
    contributions: Mapped[list[ProduceLotContribution]] = relationship(back_populates="produce_lot", cascade="all, delete-orphan")


class ProduceLotContribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "produce_lot_contributions"
    __table_args__ = (
        CheckConstraint("contributed_quantity > 0", name="contributed_quantity_positive"),
        CheckConstraint(
            "farmer_profile_id IS NOT NULL OR fpo_profile_id IS NOT NULL",
            name="source_present",
        ),
    )

    produce_lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("produce_lots.id", ondelete="CASCADE"), nullable=False)
    farmer_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farmer_profiles.id", ondelete="SET NULL"))
    fpo_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fpo_profiles.id", ondelete="SET NULL"))
    contributed_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    produce_lot: Mapped[ProduceLot] = relationship(back_populates="contributions")
    farmer_profile: Mapped[FarmerProfile | None] = relationship()
    fpo_profile: Mapped[FPOProfile | None] = relationship()


class BuyerRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "buyer_requirements"
    __table_args__ = (
        CheckConstraint("required_quantity > 0", name="required_quantity_positive"),
        Index("ix_buyer_requirements_matching", "commodity_id", "status", "delivery_by"),
    )

    buyer_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_profiles.id", ondelete="RESTRICT"), nullable=False)
    commodity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False)
    delivery_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), default="kg", nullable=False)
    minimum_quality_grade: Mapped[str | None] = mapped_column(String(80))
    target_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    delivery_by: Mapped[date | None] = mapped_column(Date)
    status: Mapped[BuyerRequirementStatus] = mapped_column(
        SqlEnum(BuyerRequirementStatus, name="buyer_requirement_status", native_enum=False, values_callable=enum_values),
        default=BuyerRequirementStatus.DRAFT,
        nullable=False,
    )

    buyer_profile: Mapped[BuyerProfile] = relationship()
    commodity: Mapped[Commodity] = relationship()
    delivery_location: Mapped[Location] = relationship()


class Offer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("offered_quantity > 0", name="offered_quantity_positive"),
        CheckConstraint("offered_price_per_unit >= 0", name="offered_price_nonnegative"),
    )

    buyer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    produce_lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("produce_lots.id", ondelete="RESTRICT"), nullable=False)
    buyer_requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("buyer_requirements.id", ondelete="SET NULL"))
    offered_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    offered_price_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    current_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    current_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    current_proposer_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    current_proposer_role: Mapped[str | None] = mapped_column(String(32))
    response_required_from_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[OfferStatus] = mapped_column(
        SqlEnum(OfferStatus, name="offer_status", native_enum=False, values_callable=enum_values), default=OfferStatus.PENDING, nullable=False
    )

    buyer: Mapped[User] = relationship(foreign_keys=[buyer_user_id])
    produce_lot: Mapped[ProduceLot] = relationship()
    buyer_requirement: Mapped[BuyerRequirement | None] = relationship()
    current_proposer: Mapped[User | None] = relationship(foreign_keys=[current_proposer_user_id])
    response_required_from_user: Mapped[User | None] = relationship(foreign_keys=[response_required_from_user_id])
    proposals: Mapped[list[OfferProposal]] = relationship(
        "OfferProposal",
        back_populates="offer",
        cascade="all, delete-orphan",
        order_by="OfferProposal.created_at.asc()",
    )


class OfferProposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offer_proposals"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="proposal_quantity_positive"),
        CheckConstraint("price_per_unit >= 0", name="proposal_price_nonnegative"),
        Index("ix_offer_proposals_offer_created", "offer_id", "created_at"),
    )

    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), nullable=False)
    proposer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    proposer_role: Mapped[str] = mapped_column(String(32), nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status_at_step: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)

    offer: Mapped[Offer] = relationship("Offer", back_populates="proposals")
    proposer: Mapped[User] = relationship("User", foreign_keys=[proposer_user_id])


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("total_amount >= 0", name="total_amount_nonnegative"),)

    buyer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    seller_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    accepted_offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"), unique=True)
    delivery_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    status: Mapped[OrderStatus] = mapped_column(
        SqlEnum(OrderStatus, name="order_status", native_enum=False, values_callable=enum_values), default=OrderStatus.DRAFT, nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    buyer: Mapped[User] = relationship(foreign_keys=[buyer_user_id])
    seller: Mapped[User] = relationship(foreign_keys=[seller_user_id])
    accepted_offer: Mapped[Offer | None] = relationship()
    delivery_location: Mapped[Location | None] = relationship()
    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("agreed_price_per_unit >= 0", name="agreed_price_nonnegative"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    produce_lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("produce_lots.id", ondelete="RESTRICT"), nullable=False)
    commodity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), default="kg", nullable=False)
    agreed_price_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    produce_lot: Mapped[ProduceLot] = relationship()
    commodity: Mapped[Commodity] = relationship()


class VerificationRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "verification_requests"
    __table_args__ = (Index("ix_verification_requests_subject", "subject_type", "subject_id"),)

    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        SqlEnum(VerificationStatus, name="verification_status", native_enum=False, values_callable=enum_values),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    document_reference: Mapped[str | None] = mapped_column(String(2048))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requested_by_user: Mapped[User | None] = relationship(foreign_keys=[requested_by_user_id])
    reviewer_user: Mapped[User | None] = relationship(foreign_keys=[reviewer_user_id])


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_actor_created", "actor_user_id", "created_at"),)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_read", "recipient_user_id", "read_at"),)

    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted refresh-token identifiers enable secure rotation and revocation."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_jti: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


# ==========================================
# PHASE 2A: DATA FOUNDATION MODELS
# ==========================================

class BuyerType(str, enum.Enum):
    WHOLESALER = "wholesaler"
    PROCESSOR = "processor"
    COMMISSION_AGENT = "commission_agent"
    EXPORTER = "exporter"
    RETAILER = "retailer"
    HORECA = "horeca"
    OTHER = "other"


class VehicleTypeEnum(str, enum.Enum):
    MINI_TRUCK = "mini_truck"
    PICKUP = "pickup"
    MEDIUM_COMMERCIAL = "medium_commercial"
    HEAVY_TRUCK = "heavy_truck"
    CONTAINER = "container"
    REEFER_VAN = "reefer_van"
    OTHER = "other"


class StorageType(str, enum.Enum):
    DRY_WAREHOUSE = "dry_warehouse"
    COLD_STORAGE = "cold_storage"
    CA_STORAGE = "ca_storage"
    RIPENING_CHAMBER = "ripening_chamber"
    SILO = "silo"
    MANDI_SHED = "mandi_shed"


class ShipmentStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ASSIGNED = "assigned"
    IN_PICKUP = "in_pickup"
    DISPATCHED = "dispatched"
    IN_TRANSIT = "in_transit"
    AT_DESTINATION = "at_destination"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    DELAYED = "delayed"


class CheckpointType(str, enum.Enum):
    PICKUP = "pickup"
    DESTINATION = "destination"


class CheckpointStatus(str, enum.Enum):
    PENDING = "pending"
    ARRIVED = "arrived"
    LOADING = "loading"
    COMPLETED = "completed"


class BuyerDirectoryEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "buyer_directory_entries"
    __table_args__ = (
        Index("ix_buyer_directory_location", "location_id"),
        Index("ix_buyer_directory_type", "buyer_type"),
    )

    external_id: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_type: Mapped[BuyerType] = mapped_column(
        SqlEnum(BuyerType, name="buyer_type", native_enum=False, values_callable=enum_values),
        default=BuyerType.WHOLESALER,
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    registered_buyer_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("buyer_profiles.id", ondelete="SET NULL"))
    contact_person: Mapped[str | None] = mapped_column(String(160))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    procurement_radius_km: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    daily_capacity_mt: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    typical_payment_terms: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location: Mapped[Location] = relationship()
    registered_buyer_profile: Mapped[BuyerProfile | None] = relationship()
    preferred_commodities: Mapped[list[BuyerPreferredCommodity]] = relationship(
        back_populates="buyer_entry", cascade="all, delete-orphan"
    )
    preferred_categories: Mapped[list[BuyerPreferredCategory]] = relationship(
        back_populates="buyer_entry", cascade="all, delete-orphan"
    )


class BuyerPreferredCommodity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "buyer_preferred_commodities"
    __table_args__ = (
        UniqueConstraint("buyer_entry_id", "commodity_id", name="uq_buyer_preferred_commodity"),
    )

    buyer_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_directory_entries.id", ondelete="CASCADE"), nullable=False)
    commodity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False)
    min_quality_grade: Mapped[str | None] = mapped_column(String(80))
    typical_volume_quintals: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    max_price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    buyer_entry: Mapped[BuyerDirectoryEntry] = relationship(back_populates="preferred_commodities")
    commodity: Mapped[Commodity] = relationship()


class BuyerPreferredCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "buyer_preferred_categories"
    __table_args__ = (
        UniqueConstraint("buyer_entry_id", "category", name="uq_buyer_preferred_category"),
    )

    buyer_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buyer_directory_entries.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[CommodityCategory] = mapped_column(
        SqlEnum(CommodityCategory, name="commodity_category", native_enum=False, values_callable=enum_values),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(255))

    buyer_entry: Mapped[BuyerDirectoryEntry] = relationship(back_populates="preferred_categories")


class HistoricalInfrastructureRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "historical_infrastructure_records"
    __table_args__ = (
        Index("ix_historical_infra_location", "location_id"),
        Index("ix_historical_infra_sector", "commodity_sector"),
    )

    external_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lead_type: Mapped[str] = mapped_column(String(120), nullable=False)
    commodity_sector: Mapped[str] = mapped_column(String(80), nullable=False)
    district_area: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(80), default="Maharashtra", nullable=False)
    coverage_label: Mapped[str | None] = mapped_column(String(120))
    location_granularity: Mapped[str | None] = mapped_column(String(80))
    evidence_type: Mapped[str] = mapped_column(String(160), nullable=False)
    government_project_status: Mapped[str | None] = mapped_column(String(80))
    evidence_date: Mapped[date | None] = mapped_column(Date)
    current_service_status: Mapped[str] = mapped_column(String(80), default="Unknown", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(120), default="Historical infrastructure evidence", nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)

    location: Mapped[Location | None] = relationship()



class LogisticsProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "logistics_providers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registered_transporter_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transporter_profiles.id", ondelete="SET NULL")
    )
    primary_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    operating_scope: Mapped[str] = mapped_column(String(80), default="regional", nullable=False)
    has_cold_chain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    primary_location: Mapped[Location | None] = relationship()
    transporter_profile: Mapped[TransporterProfile | None] = relationship()
    vehicles: Mapped[list[Vehicle]] = relationship(back_populates="provider", cascade="all, delete-orphan")
    rate_cards: Mapped[list[TransportRateCard]] = relationship(back_populates="provider", cascade="all, delete-orphan")


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("payload_capacity_kg > 0", name="payload_capacity_positive"),
        Index("ix_vehicles_provider_type", "provider_id", "vehicle_type"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("logistics_providers.id", ondelete="CASCADE"), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(32), unique=True)
    vehicle_type: Mapped[VehicleTypeEnum] = mapped_column(
        SqlEnum(VehicleTypeEnum, name="vehicle_type", native_enum=False, values_callable=enum_values),
        default=VehicleTypeEnum.MINI_TRUCK,
        nullable=False,
    )
    model_name: Mapped[str | None] = mapped_column(String(120))
    payload_capacity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    volumetric_capacity_cbm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_refrigerated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    temp_min_celsius: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    temp_max_celsius: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    operational_status: Mapped[str] = mapped_column(String(40), default="available", nullable=False)

    provider: Mapped[LogisticsProvider] = relationship(back_populates="vehicles")


class StorageFacility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "storage_facilities"
    __table_args__ = (
        CheckConstraint("total_capacity_mt > 0", name="total_capacity_positive"),
        CheckConstraint("available_capacity_mt >= 0", name="available_capacity_nonnegative"),
        Index("ix_storage_location", "location_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[StorageType] = mapped_column(
        SqlEnum(StorageType, name="storage_type", native_enum=False, values_callable=enum_values),
        default=StorageType.DRY_WAREHOUSE,
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(255))
    total_capacity_mt: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    available_capacity_mt: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    is_cold_chain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    temp_min_celsius: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    temp_max_celsius: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    humidity_controlled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    daily_rate_per_mt: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location: Mapped[Location] = relationship()


class CollectionCentre(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collection_centres"
    __table_args__ = (
        Index("ix_collection_centre_location", "location_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(255))
    has_grading_line: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_precooling: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weighbridge_capacity_mt: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    max_throughput_mt_day: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location: Mapped[Location] = relationship()


class TransportRateCard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transport_rate_cards"
    __table_args__ = (
        CheckConstraint("base_fare >= 0", name="base_fare_nonnegative"),
        CheckConstraint("per_km_rate >= 0", name="per_km_rate_nonnegative"),
        Index("ix_rate_cards_provider", "provider_id", "vehicle_type"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("logistics_providers.id", ondelete="CASCADE"), nullable=False)
    vehicle_type: Mapped[VehicleTypeEnum] = mapped_column(
        SqlEnum(VehicleTypeEnum, name="rate_card_vehicle_type", native_enum=False, values_callable=enum_values),
        nullable=False,
    )
    base_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    per_km_rate: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    min_distance_km: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    reefer_surcharge_per_km: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    loading_unloading_charge: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    provider: Mapped[LogisticsProvider] = relationship(back_populates="rate_cards")


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        Index("ix_shipments_order_status", "order_id", "status"),
        Index("ix_shipments_plan_status", "shipment_plan_id", "status"),
    )

    shipment_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shipment_plans.id", ondelete="SET NULL"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("logistics_providers.id", ondelete="SET NULL"))
    origin_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    destination_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    storage_facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("storage_facilities.id", ondelete="SET NULL"))
    collection_centre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collection_centres.id", ondelete="SET NULL"))
    status: Mapped[ShipmentStatus] = mapped_column(
        SqlEnum(ShipmentStatus, name="shipment_status", native_enum=False, values_callable=enum_values),
        default=ShipmentStatus.SCHEDULED,
        nullable=False,
    )
    scheduled_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    driver_name: Mapped[str | None] = mapped_column(String(160))
    driver_phone: Mapped[str | None] = mapped_column(String(32))
    total_planned_quantity_quintals: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    total_picked_up_quantity_quintals: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    delivered_quantity_quintals: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    delivery_variance_reason: Mapped[str | None] = mapped_column(Text)
    receiver_name: Mapped[str | None] = mapped_column(String(255))
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    current_checkpoint_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    shipment_plan: Mapped[ShipmentPlan | None] = relationship(back_populates="shipments")
    order: Mapped[Order | None] = relationship()
    vehicle: Mapped[Vehicle | None] = relationship()
    provider: Mapped[LogisticsProvider | None] = relationship()
    origin_location: Mapped[Location] = relationship(foreign_keys=[origin_location_id])
    destination_location: Mapped[Location] = relationship(foreign_keys=[destination_location_id])
    storage_facility: Mapped[StorageFacility | None] = relationship()
    collection_centre: Mapped[CollectionCentre | None] = relationship()
    events: Mapped[list[ShipmentEvent]] = relationship(back_populates="shipment", cascade="all, delete-orphan")
    checkpoints: Mapped[list[ShipmentCheckpoint]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", order_by="ShipmentCheckpoint.stop_sequence"
    )


class ShipmentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipment_events"
    __table_args__ = (
        Index("ix_shipment_events_recorded", "shipment_id", "recorded_at"),
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(160))
    geo_point: Mapped[str | None] = mapped_column(GeoPoint())
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    shipment: Mapped[Shipment] = relationship(back_populates="events")


class MarketPriceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_price_records"
    __table_args__ = (
        CheckConstraint("modal_price >= 0", name="modal_price_nonnegative"),
        CheckConstraint("min_price IS NULL OR min_price >= 0", name="min_price_nonnegative"),
        CheckConstraint("max_price IS NULL OR max_price >= 0", name="max_price_nonnegative"),
        CheckConstraint("arrivals_quantity IS NULL OR arrivals_quantity >= 0", name="arrivals_nonnegative"),
        UniqueConstraint("commodity_id", "market_location_id", "price_date", "variety", "grade", name="uq_market_price_observation"),
        Index("ix_market_prices_commodity_date", "commodity_id", "market_location_id", "price_date"),
        Index("ix_market_prices_data_source", "data_source_id"),
    )

    commodity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False)
    market_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    variety: Mapped[str | None] = mapped_column(String(80))
    grade: Mapped[str | None] = mapped_column(String(40))
    raw_commodity_name: Mapped[str | None] = mapped_column(String(120))
    raw_market_name: Mapped[str | None] = mapped_column(String(160))
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    modal_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_unit: Mapped[str] = mapped_column(String(24), default="Rs/quintal", nullable=False)
    arrivals_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    arrivals_unit: Mapped[str] = mapped_column(String(24), default="quintal", nullable=False)

    commodity: Mapped[Commodity] = relationship()
    market_location: Mapped[Location] = relationship()
    data_source: Mapped[DataSource | None] = relationship()


# ==========================================
# PHASE 2E: SHIPMENT PLANNING FOUNDATION MODELS
# ==========================================

class ShipmentPlanningStatus(str, enum.Enum):
    PLANNED = "planned"
    READY_FOR_LOGISTICS = "ready_for_logistics"
    CANCELLED = "cancelled"


class ShipmentPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Shipment Plan is the structured bridge between produce supply, buyer demand,
    and future logistics dispatch without yet allocating real carriers or trucks.
    """
    __tablename__ = "shipment_plans"
    __table_args__ = (
        CheckConstraint("total_planned_quantity_quintals > 0", name="total_planned_quantity_positive"),
        Index("ix_shipment_plans_status", "planning_status"),
        Index("ix_shipment_plans_commodity", "commodity_id"),
        Index("ix_shipment_plans_requirement", "buyer_requirement_id"),
        Index("ix_shipment_plans_order", "order_id"),
    )

    plan_code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    planning_status: Mapped[ShipmentPlanningStatus] = mapped_column(
        SqlEnum(ShipmentPlanningStatus, name="shipment_planning_status", native_enum=False, values_callable=enum_values),
        default=ShipmentPlanningStatus.PLANNED,
        nullable=False,
    )
    buyer_requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("buyer_requirements.id", ondelete="SET NULL"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    aggregation_opportunity_id: Mapped[str | None] = mapped_column(String(120))
    buyer_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    buyer_organization_name: Mapped[str | None] = mapped_column(String(255))
    commodity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commodities.id", ondelete="RESTRICT"), nullable=False)
    variety: Mapped[str | None] = mapped_column(String(80))
    quality_grade: Mapped[str | None] = mapped_column(String(80))
    total_planned_quantity_quintals: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    destination_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    earliest_pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_deadline: Mapped[date | None] = mapped_column(Date)
    estimated_gross_merchandise_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    is_geographic_distance_exact: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    geographic_precision_notes: Mapped[str | None] = mapped_column(Text)
    economic_disclaimer: Mapped[str] = mapped_column(
        Text,
        default="Logistics transportation pricing, carrier dispatch, and route optimization are deferred to subsequent logistics execution.",
        nullable=False,
    )
    lineage_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    buyer_requirement: Mapped[BuyerRequirement | None] = relationship()
    order: Mapped[Order | None] = relationship()
    buyer_user: Mapped[User | None] = relationship(foreign_keys=[buyer_user_id])
    commodity: Mapped[Commodity] = relationship()
    destination_location: Mapped[Location] = relationship(foreign_keys=[destination_location_id])
    pickup_stops: Mapped[list[ShipmentPlanPickupStop]] = relationship(
        back_populates="shipment_plan", cascade="all, delete-orphan", order_by="ShipmentPlanPickupStop.stop_sequence"
    )
    shipments: Mapped[list[Shipment]] = relationship(back_populates="shipment_plan")


class ShipmentPlanPickupStop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents an individual farm/FPO pickup point in a planned shipment."""
    __tablename__ = "shipment_plan_pickup_stops"
    __table_args__ = (
        CheckConstraint("allocated_quantity_quintals > 0", name="stop_quantity_positive"),
        UniqueConstraint("shipment_plan_id", "stop_sequence", name="uq_shipment_plan_stop_sequence"),
        Index("ix_pickup_stops_plan", "shipment_plan_id"),
        Index("ix_pickup_stops_seller", "seller_user_id"),
    )

    shipment_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipment_plans.id", ondelete="CASCADE"), nullable=False)
    stop_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    seller_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    seller_name: Mapped[str] = mapped_column(String(255), nullable=False)
    seller_role: Mapped[str] = mapped_column(String(40), default="FARMER", nullable=False)
    pickup_location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    allocated_quantity_quintals: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    earliest_pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    latest_pickup_date: Mapped[date | None] = mapped_column(Date)
    is_exact_gps: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    shipment_plan: Mapped[ShipmentPlan] = relationship(back_populates="pickup_stops")
    seller: Mapped[User] = relationship(foreign_keys=[seller_user_id])
    pickup_location: Mapped[Location] = relationship(foreign_keys=[pickup_location_id])
    contributors: Mapped[list[ShipmentPlanContributor]] = relationship(
        back_populates="pickup_stop", cascade="all, delete-orphan"
    )


class ShipmentPlanContributor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Detailed allocation record linking a pickup stop to a specific produce lot & contributor."""
    __tablename__ = "shipment_plan_contributors"
    __table_args__ = (
        CheckConstraint("lot_allocated_quantity_quintals > 0", name="contributor_quantity_positive"),
        Index("ix_plan_contributors_stop", "pickup_stop_id"),
        Index("ix_plan_contributors_lot", "produce_lot_id"),
    )

    pickup_stop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipment_plan_pickup_stops.id", ondelete="CASCADE"), nullable=False)
    produce_lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("produce_lots.id", ondelete="RESTRICT"), nullable=False)
    seller_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    fpo_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    lot_allocated_quantity_quintals: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    asking_price_per_quintal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quality_grade: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)

    pickup_stop: Mapped[ShipmentPlanPickupStop] = relationship(back_populates="contributors")
    produce_lot: Mapped[ProduceLot] = relationship()
    seller: Mapped[User] = relationship(foreign_keys=[seller_user_id])
    fpo_member: Mapped[User | None] = relationship(foreign_keys=[fpo_member_id])


# ==========================================
# PHASE 2G: TRANSPORTER MARKETPLACE MODELS
# ==========================================

class TransportOpportunityStatus(str, enum.Enum):
    OPEN = "open"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"
    CANCELLED = "cancelled"


class QuoteStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class TransportOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Logistics transport opportunity generated for eligible registered transporters.
    Maintains full lineage back to ShipmentPlan, Shipment, and aggregated farmers.
    """
    __tablename__ = "transport_opportunities"
    __table_args__ = (
        UniqueConstraint("shipment_plan_id", "transporter_profile_id", name="uq_opportunity_plan_transporter"),
        Index("ix_opportunities_transporter_status", "transporter_profile_id", "status"),
        Index("ix_opportunities_plan", "shipment_plan_id"),
        Index("ix_opportunities_shipment", "shipment_id"),
    )

    shipment_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shipment_plans.id", ondelete="SET NULL"))
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shipments.id", ondelete="SET NULL"))
    transporter_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transporter_profiles.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[TransportOpportunityStatus] = mapped_column(
        SqlEnum(TransportOpportunityStatus, name="transport_opportunity_status", native_enum=False, values_callable=enum_values),
        default=TransportOpportunityStatus.OPEN,
        nullable=False,
    )
    required_vehicle_class: Mapped[str] = mapped_column(String(120), nullable=False)
    required_payload_quintals: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    requires_cold_chain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pickup_stops_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    origin_district: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_district: Mapped[str] = mapped_column(String(120), nullable=False)
    total_distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    distance_certainty: Mapped[str] = mapped_column(String(80), default="MODELED_GEOGRAPHIC_DISTANCE", nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_certainty: Mapped[str] = mapped_column(String(80), default="MODELED_REGIONAL_ESTIMATE", nullable=False)
    earliest_pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_deadline: Mapped[date | None] = mapped_column(Date)
    eligibility_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("100.00"), nullable=False)
    matching_criteria_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(Text)

    shipment_plan: Mapped[ShipmentPlan | None] = relationship()
    shipment: Mapped[Shipment | None] = relationship()
    transporter_profile: Mapped[TransporterProfile] = relationship(back_populates="opportunities")
    quotes: Mapped[list[TransporterQuote]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")


class TransporterQuote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Commercial freight bid or quote submitted by an operational transporter for an opportunity."""
    __tablename__ = "transporter_quotes"
    __table_args__ = (
        Index("ix_transporter_quotes_opportunity", "opportunity_id"),
        Index("ix_transporter_quotes_transporter", "transporter_profile_id"),
    )

    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transport_opportunities.id", ondelete="CASCADE"), nullable=False)
    transporter_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transporter_profiles.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    quote_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quote_unit: Mapped[str] = mapped_column(String(40), default="INR_TOTAL", nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[QuoteStatus] = mapped_column(
        SqlEnum(QuoteStatus, name="quote_status", native_enum=False, values_callable=enum_values),
        default=QuoteStatus.SUBMITTED,
        nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    quote_certainty: Mapped[str] = mapped_column(String(80), default="VERIFIED_TRANSPORTER_QUOTE", nullable=False)

    opportunity: Mapped[TransportOpportunity] = relationship(back_populates="quotes")
    transporter_profile: Mapped[TransporterProfile] = relationship(back_populates="quotes")
    vehicle: Mapped[Vehicle | None] = relationship()


# ==========================================
# PHASE 2H: SHIPMENT CHECKPOINT EXECUTION
# ==========================================

class ShipmentCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents an operational milestone checkpoint (pickup stop or destination) for an executing shipment."""
    __tablename__ = "shipment_checkpoints"
    __table_args__ = (
        UniqueConstraint("shipment_id", "stop_sequence", name="uq_shipment_checkpoint_sequence"),
        Index("ix_checkpoints_shipment_seq", "shipment_id", "stop_sequence"),
        Index("ix_checkpoints_status", "shipment_id", "status"),
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    checkpoint_type: Mapped[CheckpointType] = mapped_column(
        SqlEnum(CheckpointType, name="checkpoint_type", native_enum=False, values_callable=enum_values),
        default=CheckpointType.PICKUP,
        nullable=False,
    )
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    pickup_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shipment_plan_pickup_stops.id", ondelete="SET NULL"), nullable=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    seller_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[CheckpointStatus] = mapped_column(
        SqlEnum(CheckpointStatus, name="checkpoint_status", native_enum=False, values_callable=enum_values),
        default=CheckpointStatus.PENDING,
        nullable=False,
    )
    planned_quantity_quintals: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    loaded_quantity_quintals: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    variance_quintals: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    variance_reason: Mapped[str | None] = mapped_column(Text)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    loading_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    loading_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    shipment: Mapped[Shipment] = relationship(back_populates="checkpoints")
    pickup_stop: Mapped[ShipmentPlanPickupStop | None] = relationship()
    location: Mapped[Location] = relationship()
    seller: Mapped[User | None] = relationship(foreign_keys=[seller_user_id])





