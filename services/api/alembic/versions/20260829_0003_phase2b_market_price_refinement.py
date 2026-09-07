"""Refine market_price_records with raw names, data_source_id, and unique constraint.

Revision ID: 20260829_0003
Revises: 20260829_0002
Create Date: 2026-08-29 01:01:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260829_0003"
down_revision = "20260829_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns
    op.add_column("market_price_records", sa.Column("raw_commodity_name", sa.String(120), nullable=True))
    op.add_column("market_price_records", sa.Column("raw_market_name", sa.String(160), nullable=True))
    op.add_column("market_price_records", sa.Column("data_source_id", sa.Uuid(), nullable=True))

    # 2. Add foreign key and index
    op.create_foreign_key(
        "fk_market_price_records_data_source",
        "market_price_records",
        "data_sources",
        ["data_source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_market_prices_data_source", "market_price_records", ["data_source_id"])

    # 3. Add unique constraint for daily observations
    op.create_unique_constraint(
        "uq_market_price_observation",
        "market_price_records",
        ["commodity_id", "market_location_id", "price_date", "variety", "grade"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_market_price_observation", "market_price_records", type_="unique")
    op.drop_index("ix_market_prices_data_source", table_name="market_price_records")
    op.drop_constraint("fk_market_price_records_data_source", "market_price_records", type_="foreignkey")
    op.drop_column("market_price_records", "data_source_id")
    op.drop_column("market_price_records", "raw_market_name")
    op.drop_column("market_price_records", "raw_commodity_name")
