"""Create Phase 2G Transporter Marketplace schema: Transport Opportunities, Quotes, and Profile enhancements.

Revision ID: 20260830_0002
Revises: 20260830_0001
Create Date: 2026-08-30 01:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260830_0002"
down_revision = "20260830_0001"
branch_labels = None
depends_on = None

transport_opportunity_status = sa.Enum(
    "open",
    "offered",
    "accepted",
    "declined",
    "expired",
    "withdrawn",
    "cancelled",
    name="transport_opportunity_status",
    native_enum=False,
    create_constraint=True,
)

quote_status = sa.Enum(
    "submitted",
    "accepted",
    "rejected",
    "expired",
    "withdrawn",
    name="quote_status",
    native_enum=False,
    create_constraint=True,
)


def identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    # 1. Enhance transporter_profiles with operational and service metadata
    op.add_column("transporter_profiles", sa.Column("operational_status", sa.String(40), server_default="active", nullable=False))
    op.add_column("transporter_profiles", sa.Column("service_area_districts", sa.JSON(), nullable=True))
    op.add_column("transporter_profiles", sa.Column("contact_phone", sa.String(32), nullable=True))
    op.add_column("transporter_profiles", sa.Column("contact_email", sa.String(320), nullable=True))
    op.add_column("transporter_profiles", sa.Column("preferred_commodities", sa.JSON(), nullable=True))

    # 2. Enhance vehicles with operational status
    op.add_column("vehicles", sa.Column("operational_status", sa.String(40), server_default="available", nullable=False))

    # 3. Create transport_opportunities table
    op.create_table(
        "transport_opportunities",
        *identity_columns(),
        sa.Column("shipment_plan_id", sa.Uuid(), sa.ForeignKey("shipment_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shipment_id", sa.Uuid(), sa.ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("transporter_profile_id", sa.Uuid(), sa.ForeignKey("transporter_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", transport_opportunity_status, server_default="open", nullable=False),
        sa.Column("required_vehicle_class", sa.String(120), nullable=False),
        sa.Column("required_payload_quintals", sa.Numeric(14, 3), nullable=False),
        sa.Column("requires_cold_chain", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pickup_stops_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("origin_district", sa.String(120), nullable=False),
        sa.Column("destination_district", sa.String(120), nullable=False),
        sa.Column("total_distance_km", sa.Numeric(10, 2), nullable=False),
        sa.Column("distance_certainty", sa.String(80), server_default="MODELED_GEOGRAPHIC_DISTANCE", nullable=False),
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("cost_certainty", sa.String(80), server_default="MODELED_REGIONAL_ESTIMATE", nullable=False),
        sa.Column("earliest_pickup_date", sa.Date(), nullable=False),
        sa.Column("delivery_deadline", sa.Date(), nullable=True),
        sa.Column("eligibility_score", sa.Numeric(6, 2), server_default="100.0", nullable=False),
        sa.Column("matching_criteria_json", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("shipment_plan_id", "transporter_profile_id", name="uq_opportunity_plan_transporter"),
    )
    op.create_index("ix_opportunities_transporter_status", "transport_opportunities", ["transporter_profile_id", "status"])
    op.create_index("ix_opportunities_plan", "transport_opportunities", ["shipment_plan_id"])
    op.create_index("ix_opportunities_shipment", "transport_opportunities", ["shipment_id"])

    # 4. Create transporter_quotes table
    op.create_table(
        "transporter_quotes",
        *identity_columns(),
        sa.Column("opportunity_id", sa.Uuid(), sa.ForeignKey("transport_opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transporter_profile_id", sa.Uuid(), sa.ForeignKey("transporter_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quote_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("quote_unit", sa.String(40), server_default="INR_TOTAL", nullable=False),
        sa.Column("currency", sa.String(10), server_default="INR", nullable=False),
        sa.Column("status", quote_status, server_default="submitted", nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("quote_certainty", sa.String(80), server_default="VERIFIED_TRANSPORTER_QUOTE", nullable=False),
    )
    op.create_index("ix_transporter_quotes_opportunity", "transporter_quotes", ["opportunity_id"])
    op.create_index("ix_transporter_quotes_transporter", "transporter_quotes", ["transporter_profile_id"])


def downgrade() -> None:
    op.drop_table("transporter_quotes")
    op.drop_table("transport_opportunities")
    op.drop_column("vehicles", "operational_status")
    op.drop_column("transporter_profiles", "preferred_commodities")
    op.drop_column("transporter_profiles", "contact_email")
    op.drop_column("transporter_profiles", "contact_phone")
    op.drop_column("transporter_profiles", "service_area_districts")
    op.drop_column("transporter_profiles", "operational_status")
