"""Create Phase 2A Data Foundation schema.

Revision ID: 20260829_0001
Revises: 20260828_0001
Create Date: 2026-08-29 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography

revision = "20260829_0001"
down_revision = "20260828_0001"
branch_labels = None
depends_on = None

buyer_type = sa.Enum("wholesaler", "processor", "commission_agent", "exporter", "retailer", "horeca", "other", name="buyer_type", native_enum=False, create_constraint=True)
vehicle_type = sa.Enum("mini_truck", "pickup", "medium_commercial", "heavy_truck", "container", "reefer_van", "other", name="vehicle_type", native_enum=False, create_constraint=True)
storage_type = sa.Enum("dry_warehouse", "cold_storage", "ca_storage", "ripening_chamber", "silo", "mandi_shed", name="storage_type", native_enum=False, create_constraint=True)
shipment_status = sa.Enum("draft", "scheduled", "dispatched", "in_transit", "delivered", "cancelled", "delayed", name="shipment_status", native_enum=False, create_constraint=True)


def identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    # 1. Buyer Directory Entries
    op.create_table(
        "buyer_directory_entries",
        *identity_columns(),
        sa.Column("business_name", sa.String(255), nullable=False),
        sa.Column("buyer_type", buyer_type, nullable=False, server_default="wholesaler"),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("registered_buyer_profile_id", sa.Uuid()),
        sa.Column("contact_person", sa.String(160)),
        sa.Column("contact_phone", sa.String(32)),
        sa.Column("contact_email", sa.String(320)),
        sa.Column("procurement_radius_km", sa.Numeric(8, 2)),
        sa.Column("daily_capacity_mt", sa.Numeric(10, 3)),
        sa.Column("typical_payment_terms", sa.String(120)),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["registered_buyer_profile_id"], ["buyer_profiles.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_buyer_directory_location", "buyer_directory_entries", ["location_id"])
    op.create_index("ix_buyer_directory_type", "buyer_directory_entries", ["buyer_type"])

    # 2. Buyer Preferred Commodities (Junction)
    op.create_table(
        "buyer_preferred_commodities",
        *identity_columns(),
        sa.Column("buyer_entry_id", sa.Uuid(), nullable=False),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("min_quality_grade", sa.String(80)),
        sa.Column("typical_volume_quintals", sa.Numeric(12, 3)),
        sa.Column("max_price_per_unit", sa.Numeric(12, 2)),
        sa.ForeignKeyConstraint(["buyer_entry_id"], ["buyer_directory_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("buyer_entry_id", "commodity_id", name="uq_buyer_preferred_commodity"),
    )

    # 3. Logistics Providers
    op.create_table(
        "logistics_providers",
        *identity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("registered_transporter_profile_id", sa.Uuid()),
        sa.Column("primary_location_id", sa.Uuid()),
        sa.Column("operating_scope", sa.String(80), nullable=False, server_default="regional"),
        sa.Column("has_cold_chain", sa.Boolean(), default=False, nullable=False, server_default=sa.false()),
        sa.Column("contact_phone", sa.String(32)),
        sa.Column("contact_email", sa.String(320)),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["registered_transporter_profile_id"], ["transporter_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["primary_location_id"], ["locations.id"], ondelete="SET NULL"),
    )

    # 4. Vehicles
    op.create_table(
        "vehicles",
        *identity_columns(),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("registration_number", sa.String(32), unique=True),
        sa.Column("vehicle_type", vehicle_type, nullable=False, server_default="mini_truck"),
        sa.Column("model_name", sa.String(120)),
        sa.Column("payload_capacity_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("volumetric_capacity_cbm", sa.Numeric(8, 2)),
        sa.Column("is_refrigerated", sa.Boolean(), default=False, nullable=False, server_default=sa.false()),
        sa.Column("temp_min_celsius", sa.Numeric(4, 1)),
        sa.Column("temp_max_celsius", sa.Numeric(4, 1)),
        sa.Column("is_available", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["provider_id"], ["logistics_providers.id"], ondelete="CASCADE"),
        sa.CheckConstraint("payload_capacity_kg > 0", name="payload_capacity_positive"),
    )
    op.create_index("ix_vehicles_provider_type", "vehicles", ["provider_id", "vehicle_type"])

    # 5. Storage Facilities
    op.create_table(
        "storage_facilities",
        *identity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("facility_type", storage_type, nullable=False, server_default="dry_warehouse"),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("operator_name", sa.String(255)),
        sa.Column("total_capacity_mt", sa.Numeric(10, 3), nullable=False),
        sa.Column("available_capacity_mt", sa.Numeric(10, 3), nullable=False),
        sa.Column("is_cold_chain", sa.Boolean(), default=False, nullable=False, server_default=sa.false()),
        sa.Column("temp_min_celsius", sa.Numeric(4, 1)),
        sa.Column("temp_max_celsius", sa.Numeric(4, 1)),
        sa.Column("humidity_controlled", sa.Boolean(), default=False, nullable=False, server_default=sa.false()),
        sa.Column("daily_rate_per_mt", sa.Numeric(10, 2)),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("total_capacity_mt > 0", name="total_capacity_positive"),
        sa.CheckConstraint("available_capacity_mt >= 0", name="available_capacity_nonnegative"),
    )
    op.create_index("ix_storage_location", "storage_facilities", ["location_id"])

    # 6. Collection Centres
    op.create_table(
        "collection_centres",
        *identity_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("operator_name", sa.String(255)),
        sa.Column("has_grading_line", sa.Boolean(), default=False, nullable=False, server_default=sa.false()),
        sa.Column("has_precooling", sa.Boolean(), default=False, nullable=False, server_default=sa.false()),
        sa.Column("weighbridge_capacity_mt", sa.Numeric(8, 2)),
        sa.Column("max_throughput_mt_day", sa.Numeric(8, 2)),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_collection_centre_location", "collection_centres", ["location_id"])

    # 7. Transport Rate Cards
    op.create_table(
        "transport_rate_cards",
        *identity_columns(),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_type", vehicle_type, nullable=False),
        sa.Column("base_fare", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("per_km_rate", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("min_distance_km", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("reefer_surcharge_per_km", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("loading_unloading_charge", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date()),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["provider_id"], ["logistics_providers.id"], ondelete="CASCADE"),
        sa.CheckConstraint("base_fare >= 0", name="base_fare_nonnegative"),
        sa.CheckConstraint("per_km_rate >= 0", name="per_km_rate_nonnegative"),
    )
    op.create_index("ix_rate_cards_provider", "transport_rate_cards", ["provider_id", "vehicle_type"])

    # 8. Shipments
    op.create_table(
        "shipments",
        *identity_columns(),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid()),
        sa.Column("provider_id", sa.Uuid()),
        sa.Column("origin_location_id", sa.Uuid(), nullable=False),
        sa.Column("destination_location_id", sa.Uuid(), nullable=False),
        sa.Column("storage_facility_id", sa.Uuid()),
        sa.Column("collection_centre_id", sa.Uuid()),
        sa.Column("status", shipment_status, nullable=False, server_default="scheduled"),
        sa.Column("scheduled_pickup_at", sa.DateTime(timezone=True)),
        sa.Column("actual_pickup_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_arrival_at", sa.DateTime(timezone=True)),
        sa.Column("actual_arrival_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_cost", sa.Numeric(12, 2)),
        sa.Column("actual_cost", sa.Numeric(12, 2)),
        sa.Column("driver_name", sa.String(160)),
        sa.Column("driver_phone", sa.String(32)),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["logistics_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["origin_location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["storage_facility_id"], ["storage_facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["collection_centre_id"], ["collection_centres.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_shipments_order_status", "shipments", ["order_id", "status"])

    # 9. Shipment Events
    op.create_table(
        "shipment_events",
        *identity_columns(),
        sa.Column("shipment_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("location_name", sa.String(160)),
        sa.Column("geo_point", Geography(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.Column("notes", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_shipment_events_recorded", "shipment_events", ["shipment_id", "recorded_at"])

    # 10. Market Price Records
    op.create_table(
        "market_price_records",
        *identity_columns(),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("market_location_id", sa.Uuid(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("variety", sa.String(80)),
        sa.Column("grade", sa.String(40)),
        sa.Column("min_price", sa.Numeric(10, 2)),
        sa.Column("max_price", sa.Numeric(10, 2)),
        sa.Column("modal_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_unit", sa.String(24), nullable=False, server_default="Rs/quintal"),
        sa.Column("arrivals_quantity", sa.Numeric(12, 3)),
        sa.Column("arrivals_unit", sa.String(24), nullable=False, server_default="quintal"),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["market_location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("modal_price >= 0", name="modal_price_nonnegative"),
        sa.CheckConstraint("min_price IS NULL OR min_price >= 0", name="min_price_nonnegative"),
        sa.CheckConstraint("max_price IS NULL OR max_price >= 0", name="max_price_nonnegative"),
        sa.CheckConstraint("arrivals_quantity IS NULL OR arrivals_quantity >= 0", name="arrivals_nonnegative"),
    )
    op.create_index("ix_market_prices_commodity_date", "market_price_records", ["commodity_id", "market_location_id", "price_date"])


def downgrade() -> None:
    op.drop_table("market_price_records")
    op.drop_table("shipment_events")
    op.drop_table("shipments")
    op.drop_table("transport_rate_cards")
    op.drop_table("collection_centres")
    op.drop_table("storage_facilities")
    op.drop_table("vehicles")
    op.drop_table("logistics_providers")
    op.drop_table("buyer_preferred_commodities")
    op.drop_table("buyer_directory_entries")
