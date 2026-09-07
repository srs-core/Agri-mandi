"""Create Phase 1 foundation schema.

Revision ID: 20260828_0001
Revises:
Create Date: 2026-08-28 00:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography

revision = "20260828_0001"
down_revision = None
branch_labels = None
depends_on = None

user_status = sa.Enum("active", "pending", "suspended", name="user_status", native_enum=False, create_constraint=True)
role_name = sa.Enum("farmer", "fpo", "buyer", "transporter", "admin", "government", name="role_name", native_enum=False, create_constraint=True)
verification_status = sa.Enum("pending", "verified", "rejected", name="verification_status", native_enum=False, create_constraint=True)
commodity_category = sa.Enum("vegetables", "fruits", "grains", "pulses", "spices", "other_crops", name="commodity_category", native_enum=False, create_constraint=True)
produce_lot_status = sa.Enum("draft", "published", "reserved", "sold", "cancelled", name="produce_lot_status", native_enum=False, create_constraint=True)
buyer_requirement_status = sa.Enum("draft", "active", "fulfilled", "cancelled", name="buyer_requirement_status", native_enum=False, create_constraint=True)
offer_status = sa.Enum("pending", "accepted", "declined", "expired", "withdrawn", name="offer_status", native_enum=False, create_constraint=True)
order_status = sa.Enum("draft", "confirmed", "fulfilment", "delivered", "cancelled", name="order_status", native_enum=False, create_constraint=True)
source_type = sa.Enum("government", "buyer_research", "logistics_research", "partner", "manual", "mock", name="source_type", native_enum=False, create_constraint=True)
source_verification_status = sa.Enum("unverified", "verified", "rejected", "stale", name="source_verification_status", native_enum=False, create_constraint=True)


def identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        *identity_columns(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone_number", sa.String(32)),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone_number"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_phone_number", "users", ["phone_number"])

    op.create_table(
        "roles",
        *identity_columns(),
        sa.Column("name", role_name, nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.UniqueConstraint("name"),
    )
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("name", role_name), sa.column("description", sa.String()))
    op.bulk_insert(
        roles,
        [
            {"id": uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e01"), "name": "farmer", "description": "System role: farmer"},
            {"id": uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e02"), "name": "fpo", "description": "System role: fpo"},
            {"id": uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e03"), "name": "buyer", "description": "System role: buyer"},
            {"id": uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e04"), "name": "transporter", "description": "System role: transporter"},
            {"id": uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e05"), "name": "admin", "description": "System role: admin"},
            {"id": uuid.UUID("3b6e2c94-b37e-4cfc-9e1d-5e1d91cb1e06"), "name": "government", "description": "System role: government"},
        ],
    )

    op.create_table(
        "user_roles",
        *identity_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "role_id", name="user_role"),
    )

    op.create_table(
        "locations",
        *identity_columns(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("village", sa.String(160)),
        sa.Column("taluka", sa.String(160)),
        sa.Column("district", sa.String(160)),
        sa.Column("state", sa.String(160), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="IN"),
        sa.Column("postal_code", sa.String(16)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("geo_point", Geography(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        sa.CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"),
    )
    for column in ("village", "taluka", "district", "state"):
        op.create_index(f"ix_locations_{column}", "locations", [column])
    op.create_index("ix_locations_geo_point", "locations", ["geo_point"], postgresql_using="gist")

    for profile_table, extra_columns in (
        ("farmer_profiles", [sa.Column("farm_name", sa.String(160)), sa.Column("land_area_hectares", sa.Numeric(10, 2))]),
        ("fpo_profiles", [sa.Column("legal_name", sa.String(255), nullable=False), sa.Column("registration_number", sa.String(128), unique=True)]),
        ("buyer_profiles", [sa.Column("organization_name", sa.String(255), nullable=False), sa.Column("gstin", sa.String(32), unique=True)]),
        ("transporter_profiles", [sa.Column("organization_name", sa.String(255), nullable=False)]),
    ):
        op.create_table(
            profile_table,
            *identity_columns(),
            sa.Column("user_id", sa.Uuid(), nullable=False, unique=True),
            sa.Column("primary_location_id", sa.Uuid()),
            *extra_columns,
            sa.Column("verification_status", verification_status, nullable=False, server_default="pending"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["primary_location_id"], ["locations.id"], ondelete="SET NULL"),
        )

    op.create_table(
        "data_sources",
        *identity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("verification_status", source_verification_status, nullable=False, server_default="unverified"),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1", name="confidence_range"),
    )
    op.create_table(
        "source_attributions",
        *identity_columns(),
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("external_record_id", sa.String(255)),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("verification_status", source_verification_status, nullable=False, server_default="unverified"),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.CheckConstraint("confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1", name="confidence_range"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_source_attributions_entity", "source_attributions", ["entity_type", "entity_id"])

    op.create_table(
        "commodities",
        *identity_columns(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", commodity_category, nullable=False),
        sa.Column("default_unit", sa.String(24), nullable=False, server_default="kg"),
        sa.Column("is_perishable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("storage_guidance", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_commodities_category", "commodities", ["category"])

    op.create_table(
        "produce_lots",
        *identity_columns(),
        sa.Column("seller_user_id", sa.Uuid(), nullable=False),
        sa.Column("owner_fpo_profile_id", sa.Uuid()),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("pickup_location_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("available_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(24), nullable=False, server_default="kg"),
        sa.Column("quality_grade", sa.String(80)),
        sa.Column("quality_notes", sa.Text()),
        sa.Column("asking_price_per_unit", sa.Numeric(14, 2)),
        sa.Column("available_from", sa.Date(), nullable=False),
        sa.Column("available_until", sa.Date()),
        sa.Column("is_aggregated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", produce_lot_status, nullable=False, server_default="draft"),
        sa.CheckConstraint("available_quantity > 0", name="available_quantity_positive"),
        sa.CheckConstraint("asking_price_per_unit IS NULL OR asking_price_per_unit >= 0", name="asking_price_nonnegative"),
        sa.ForeignKeyConstraint(["seller_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_fpo_profile_id"], ["fpo_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pickup_location_id"], ["locations.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_produce_lots_marketplace", "produce_lots", ["commodity_id", "status", "available_from"])

    op.create_table(
        "produce_lot_contributions",
        *identity_columns(),
        sa.Column("produce_lot_id", sa.Uuid(), nullable=False),
        sa.Column("farmer_profile_id", sa.Uuid()),
        sa.Column("fpo_profile_id", sa.Uuid()),
        sa.Column("contributed_quantity", sa.Numeric(14, 3), nullable=False),
        sa.CheckConstraint("contributed_quantity > 0", name="contributed_quantity_positive"),
        sa.CheckConstraint("farmer_profile_id IS NOT NULL OR fpo_profile_id IS NOT NULL", name="source_present"),
        sa.ForeignKeyConstraint(["produce_lot_id"], ["produce_lots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farmer_profile_id"], ["farmer_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fpo_profile_id"], ["fpo_profiles.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "buyer_requirements",
        *identity_columns(),
        sa.Column("buyer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_location_id", sa.Uuid(), nullable=False),
        sa.Column("required_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(24), nullable=False, server_default="kg"),
        sa.Column("minimum_quality_grade", sa.String(80)),
        sa.Column("target_price_per_unit", sa.Numeric(14, 2)),
        sa.Column("delivery_by", sa.Date()),
        sa.Column("status", buyer_requirement_status, nullable=False, server_default="draft"),
        sa.CheckConstraint("required_quantity > 0", name="required_quantity_positive"),
        sa.ForeignKeyConstraint(["buyer_profile_id"], ["buyer_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["delivery_location_id"], ["locations.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_buyer_requirements_matching", "buyer_requirements", ["commodity_id", "status", "delivery_by"])

    op.create_table(
        "offers",
        *identity_columns(),
        sa.Column("buyer_user_id", sa.Uuid(), nullable=False),
        sa.Column("produce_lot_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_requirement_id", sa.Uuid()),
        sa.Column("offered_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("offered_price_per_unit", sa.Numeric(14, 2), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("status", offer_status, nullable=False, server_default="pending"),
        sa.CheckConstraint("offered_quantity > 0", name="offered_quantity_positive"),
        sa.CheckConstraint("offered_price_per_unit >= 0", name="offered_price_nonnegative"),
        sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["produce_lot_id"], ["produce_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["buyer_requirement_id"], ["buyer_requirements.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "orders",
        *identity_columns(),
        sa.Column("buyer_user_id", sa.Uuid(), nullable=False),
        sa.Column("seller_user_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_offer_id", sa.Uuid(), unique=True),
        sa.Column("delivery_location_id", sa.Uuid()),
        sa.Column("status", order_status, nullable=False, server_default="draft"),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("total_amount >= 0", name="total_amount_nonnegative"),
        sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["seller_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["accepted_offer_id"], ["offers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["delivery_location_id"], ["locations.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "order_items",
        *identity_columns(),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("produce_lot_id", sa.Uuid(), nullable=False),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(24), nullable=False, server_default="kg"),
        sa.Column("agreed_price_per_unit", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint("agreed_price_per_unit >= 0", name="agreed_price_nonnegative"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["produce_lot_id"], ["produce_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "verification_requests",
        *identity_columns(),
        sa.Column("requested_by_user_id", sa.Uuid()),
        sa.Column("reviewer_user_id", sa.Uuid()),
        sa.Column("subject_type", sa.String(80), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("status", verification_status, nullable=False, server_default="pending"),
        sa.Column("document_reference", sa.String(2048)),
        sa.Column("reviewer_notes", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_verification_requests_subject", "verification_requests", ["subject_type", "subject_id"])

    op.create_table(
        "audit_events",
        *identity_columns(),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("ip_address", sa.String(64)),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_actor_created", "audit_events", ["actor_user_id", "created_at"])

    op.create_table(
        "notifications",
        *identity_columns(),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("notification_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data_json", sa.JSON()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_recipient_read", "notifications", ["recipient_user_id", "read_at"])

    op.create_table(
        "refresh_tokens",
        *identity_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_jti", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_jti"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_jti", "refresh_tokens", ["token_jti"])


def downgrade() -> None:
    for table_name in (
        "refresh_tokens", "notifications", "audit_events", "verification_requests", "order_items", "orders",
        "offers", "buyer_requirements", "produce_lot_contributions", "produce_lots", "commodities",
        "source_attributions", "data_sources", "transporter_profiles", "buyer_profiles", "fpo_profiles",
        "farmer_profiles", "locations", "user_roles", "roles", "users",
    ):
        op.drop_table(table_name)
