"""Add Phase 2A Data Foundation refinements (external IDs, preferred categories, historical infra).

Revision ID: 20260829_0002
Revises: 20260829_0001
Create Date: 2026-08-29 00:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260829_0002"
down_revision = "20260829_0001"
branch_labels = None
depends_on = None

commodity_category = sa.Enum("vegetables", "fruits", "grains", "pulses", "spices", "other_crops", name="commodity_category", native_enum=False, create_constraint=True)


def identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    # 1. Add external_id to buyer_directory_entries
    op.add_column("buyer_directory_entries", sa.Column("external_id", sa.String(80), nullable=True))
    op.create_unique_constraint("uq_buyer_directory_external_id", "buyer_directory_entries", ["external_id"])
    op.create_index("ix_buyer_directory_external_id", "buyer_directory_entries", ["external_id"])

    # 2. Add buyer_preferred_categories table
    op.create_table(
        "buyer_preferred_categories",
        *identity_columns(),
        sa.Column("buyer_entry_id", sa.Uuid(), nullable=False),
        sa.Column("category", commodity_category, nullable=False),
        sa.Column("notes", sa.String(255)),
        sa.ForeignKeyConstraint(["buyer_entry_id"], ["buyer_directory_entries.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("buyer_entry_id", "category", name="uq_buyer_preferred_category"),
    )

    # 3. Add historical_infrastructure_records table
    op.create_table(
        "historical_infrastructure_records",
        *identity_columns(),
        sa.Column("external_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("lead_type", sa.String(120), nullable=False),
        sa.Column("commodity_sector", sa.String(80), nullable=False),
        sa.Column("district_area", sa.String(120)),
        sa.Column("state", sa.String(80), nullable=False, server_default="Maharashtra"),
        sa.Column("coverage_label", sa.String(120)),
        sa.Column("location_granularity", sa.String(80)),
        sa.Column("evidence_type", sa.String(160), nullable=False),
        sa.Column("government_project_status", sa.String(80)),
        sa.Column("evidence_date", sa.Date()),
        sa.Column("current_service_status", sa.String(80), nullable=False, server_default="Unknown"),
        sa.Column("verification_status", sa.String(120), nullable=False, server_default="Historical infrastructure evidence"),
        sa.Column("location_id", sa.Uuid()),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("external_id", name="uq_historical_infra_external_id"),
    )
    op.create_index("ix_historical_infra_external_id", "historical_infrastructure_records", ["external_id"])
    op.create_index("ix_historical_infra_location", "historical_infrastructure_records", ["location_id"])
    op.create_index("ix_historical_infra_sector", "historical_infrastructure_records", ["commodity_sector"])


def downgrade() -> None:
    op.drop_table("historical_infrastructure_records")
    op.drop_table("buyer_preferred_categories")
    op.drop_index("ix_buyer_directory_external_id", table_name="buyer_directory_entries")
    op.drop_constraint("uq_buyer_directory_external_id", "buyer_directory_entries", type_="unique")
    op.drop_column("buyer_directory_entries", "external_id")
