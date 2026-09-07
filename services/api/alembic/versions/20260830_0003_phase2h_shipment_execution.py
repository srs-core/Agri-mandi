"""Create Phase 2H Shipment Execution & Checkpoint Tracking schema.

Revision ID: 20260830_0003
Revises: 20260830_0002
Create Date: 2026-08-30 18:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260830_0003"
down_revision = "20260830_0002"
branch_labels = None
depends_on = None

checkpoint_type = sa.Enum(
    "pickup",
    "destination",
    name="checkpoint_type",
    native_enum=False,
    create_constraint=True,
)

checkpoint_status = sa.Enum(
    "pending",
    "arrived",
    "loading",
    "completed",
    name="checkpoint_status",
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
    # 1. Update shipments status check constraint and widen status column to support assigned, in_pickup, at_destination
    op.alter_column("shipments", "status", type_=sa.String(32))
    op.drop_constraint("ck_shipments_shipment_status", "shipments", type_="check")
    op.create_check_constraint(
        "ck_shipments_shipment_status",
        "shipments",
        "status IN ('draft', 'scheduled', 'assigned', 'in_pickup', 'dispatched', 'in_transit', 'at_destination', 'delivered', 'cancelled', 'delayed')"
    )

    # 2. Add execution tracking columns to shipments
    op.add_column("shipments", sa.Column("total_planned_quantity_quintals", sa.Numeric(14, 3), nullable=True))
    op.add_column("shipments", sa.Column("total_picked_up_quantity_quintals", sa.Numeric(14, 3), server_default="0.000", nullable=False))
    op.add_column("shipments", sa.Column("delivered_quantity_quintals", sa.Numeric(14, 3), nullable=True))
    op.add_column("shipments", sa.Column("delivery_variance_reason", sa.Text(), nullable=True))
    op.add_column("shipments", sa.Column("receiver_name", sa.String(255), nullable=True))
    op.add_column("shipments", sa.Column("delivery_notes", sa.Text(), nullable=True))
    op.add_column("shipments", sa.Column("current_checkpoint_sequence", sa.Integer(), server_default="1", nullable=False))

    # 2. Create shipment_checkpoints table
    op.create_table(
        "shipment_checkpoints",
        *identity_columns(),
        sa.Column("shipment_id", sa.Uuid(), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_type", checkpoint_type, server_default="pickup", nullable=False),
        sa.Column("stop_sequence", sa.Integer(), nullable=False),
        sa.Column("pickup_stop_id", sa.Uuid(), sa.ForeignKey("shipment_plan_pickup_stops.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_name", sa.String(255), nullable=False),
        sa.Column("seller_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seller_name", sa.String(255), nullable=True),
        sa.Column("status", checkpoint_status, server_default="pending", nullable=False),
        sa.Column("planned_quantity_quintals", sa.Numeric(14, 3), server_default="0.000", nullable=False),
        sa.Column("loaded_quantity_quintals", sa.Numeric(14, 3), nullable=True),
        sa.Column("variance_quintals", sa.Numeric(14, 3), nullable=True),
        sa.Column("variance_reason", sa.Text(), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("loading_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("loading_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("shipment_id", "stop_sequence", name="uq_shipment_checkpoint_sequence"),
    )
    op.create_index("ix_checkpoints_shipment_seq", "shipment_checkpoints", ["shipment_id", "stop_sequence"])
    op.create_index("ix_checkpoints_status", "shipment_checkpoints", ["shipment_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_checkpoints_status", table_name="shipment_checkpoints")
    op.drop_index("ix_checkpoints_shipment_seq", table_name="shipment_checkpoints")
    op.drop_table("shipment_checkpoints")

    op.drop_column("shipments", "current_checkpoint_sequence")
    op.drop_column("shipments", "delivery_notes")
    op.drop_column("shipments", "receiver_name")
    op.drop_column("shipments", "delivery_variance_reason")
    op.drop_column("shipments", "delivered_quantity_quintals")
    op.drop_column("shipments", "total_picked_up_quantity_quintals")
    op.drop_column("shipments", "total_planned_quantity_quintals")
