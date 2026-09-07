"""Create Phase 2E Shipment Planning schema and link to Shipments.

Revision ID: 20260830_0001
Revises: 20260829_0003
Create Date: 2026-08-30 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260830_0001"
down_revision = "20260829_0003"
branch_labels = None
depends_on = None

shipment_planning_status = sa.Enum(
    "planned",
    "ready_for_logistics",
    "cancelled",
    name="shipment_planning_status",
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
    # 1. Shipment Plans
    op.create_table(
        "shipment_plans",
        *identity_columns(),
        sa.Column("plan_code", sa.String(80), nullable=False),
        sa.Column("planning_status", shipment_planning_status, nullable=False, server_default="planned"),
        sa.Column("buyer_requirement_id", sa.Uuid()),
        sa.Column("order_id", sa.Uuid()),
        sa.Column("aggregation_opportunity_id", sa.String(120)),
        sa.Column("buyer_user_id", sa.Uuid()),
        sa.Column("buyer_organization_name", sa.String(255)),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("variety", sa.String(80)),
        sa.Column("quality_grade", sa.String(80)),
        sa.Column("total_planned_quantity_quintals", sa.Numeric(14, 3), nullable=False),
        sa.Column("destination_location_id", sa.Uuid(), nullable=False),
        sa.Column("earliest_pickup_date", sa.Date(), nullable=False),
        sa.Column("delivery_deadline", sa.Date()),
        sa.Column("estimated_gross_merchandise_value", sa.Numeric(14, 2)),
        sa.Column("is_geographic_distance_exact", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.Column("geographic_precision_notes", sa.Text()),
        sa.Column(
            "economic_disclaimer",
            sa.Text(),
            nullable=False,
            server_default="Logistics transportation pricing, carrier dispatch, and route optimization are deferred to subsequent logistics execution.",
        ),
        sa.Column("lineage_summary", sa.JSON()),
        sa.CheckConstraint("total_planned_quantity_quintals > 0", name="total_planned_quantity_positive"),
        sa.ForeignKeyConstraint(["buyer_requirement_id"], ["buyer_requirements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("plan_code", name="uq_shipment_plans_plan_code"),
    )
    op.create_index("ix_shipment_plans_code", "shipment_plans", ["plan_code"])
    op.create_index("ix_shipment_plans_status", "shipment_plans", ["planning_status"])
    op.create_index("ix_shipment_plans_commodity", "shipment_plans", ["commodity_id"])
    op.create_index("ix_shipment_plans_requirement", "shipment_plans", ["buyer_requirement_id"])
    op.create_index("ix_shipment_plans_order", "shipment_plans", ["order_id"])

    # 2. Shipment Plan Pickup Stops
    op.create_table(
        "shipment_plan_pickup_stops",
        *identity_columns(),
        sa.Column("shipment_plan_id", sa.Uuid(), nullable=False),
        sa.Column("stop_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("seller_user_id", sa.Uuid(), nullable=False),
        sa.Column("seller_name", sa.String(255), nullable=False),
        sa.Column("seller_role", sa.String(40), nullable=False, server_default="FARMER"),
        sa.Column("pickup_location_id", sa.Uuid(), nullable=False),
        sa.Column("allocated_quantity_quintals", sa.Numeric(14, 3), nullable=False),
        sa.Column("earliest_pickup_date", sa.Date(), nullable=False),
        sa.Column("latest_pickup_date", sa.Date()),
        sa.Column("is_exact_gps", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("allocated_quantity_quintals > 0", name="stop_quantity_positive"),
        sa.ForeignKeyConstraint(["shipment_plan_id"], ["shipment_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pickup_location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("shipment_plan_id", "stop_sequence", name="uq_shipment_plan_stop_sequence"),
    )
    op.create_index("ix_pickup_stops_plan", "shipment_plan_pickup_stops", ["shipment_plan_id"])
    op.create_index("ix_pickup_stops_seller", "shipment_plan_pickup_stops", ["seller_user_id"])

    # 3. Shipment Plan Contributors
    op.create_table(
        "shipment_plan_contributors",
        *identity_columns(),
        sa.Column("pickup_stop_id", sa.Uuid(), nullable=False),
        sa.Column("produce_lot_id", sa.Uuid(), nullable=False),
        sa.Column("seller_user_id", sa.Uuid(), nullable=False),
        sa.Column("fpo_member_id", sa.Uuid()),
        sa.Column("lot_allocated_quantity_quintals", sa.Numeric(14, 3), nullable=False),
        sa.Column("asking_price_per_quintal", sa.Numeric(12, 2)),
        sa.Column("quality_grade", sa.String(80)),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("lot_allocated_quantity_quintals > 0", name="contributor_quantity_positive"),
        sa.ForeignKeyConstraint(["pickup_stop_id"], ["shipment_plan_pickup_stops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["produce_lot_id"], ["produce_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["seller_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fpo_member_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_plan_contributors_stop", "shipment_plan_contributors", ["pickup_stop_id"])
    op.create_index("ix_plan_contributors_lot", "shipment_plan_contributors", ["produce_lot_id"])

    # 4. Update Shipments table: add shipment_plan_id & make order_id nullable
    op.add_column("shipments", sa.Column("shipment_plan_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_shipments_shipment_plan",
        "shipments",
        "shipment_plans",
        ["shipment_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_shipments_plan_status", "shipments", ["shipment_plan_id", "status"])
    op.alter_column("shipments", "order_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.alter_column("shipments", "order_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_shipments_plan_status", table_name="shipments")
    op.drop_constraint("fk_shipments_shipment_plan", "shipments", type_="foreignkey")
    op.drop_column("shipments", "shipment_plan_id")

    op.drop_index("ix_plan_contributors_lot", table_name="shipment_plan_contributors")
    op.drop_index("ix_plan_contributors_stop", table_name="shipment_plan_contributors")
    op.drop_table("shipment_plan_contributors")

    op.drop_index("ix_pickup_stops_seller", table_name="shipment_plan_pickup_stops")
    op.drop_index("ix_pickup_stops_plan", table_name="shipment_plan_pickup_stops")
    op.drop_table("shipment_plan_pickup_stops")

    op.drop_index("ix_shipment_plans_order", table_name="shipment_plans")
    op.drop_index("ix_shipment_plans_requirement", table_name="shipment_plans")
    op.drop_index("ix_shipment_plans_commodity", table_name="shipment_plans")
    op.drop_index("ix_shipment_plans_status", table_name="shipment_plans")
    op.drop_index("ix_shipment_plans_code", table_name="shipment_plans")
    op.drop_table("shipment_plans")
