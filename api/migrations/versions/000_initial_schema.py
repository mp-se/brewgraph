# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Initial schema — create all base tables.

Revision ID: 000
Revises:
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all base tables in FK-dependency order."""
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()

    if "batch" not in existing:
        op.create_table(
            "batch",
            sa.Column("id", sa.Uuid(), nullable=False),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID. There is no tenant table to reference.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("name", sa.String(60), nullable=True),
            sa.Column("description", sa.String(200), nullable=True),
            sa.Column("accept_ingest", sa.Boolean(), nullable=False),
            sa.Column("brew_date", sa.Date(), nullable=True),
            sa.Column("style", sa.String(60), nullable=True),
            sa.Column("brewer", sa.String(60), nullable=True),
            sa.Column("og", sa.Float(), nullable=True),
            sa.Column("fg", sa.Float(), nullable=True),
            sa.Column("og_measured", sa.Float(), nullable=True),
            sa.Column("fg_measured", sa.Float(), nullable=True),
            sa.Column("abv", sa.Float(), nullable=True),
            sa.Column("ebc", sa.Float(), nullable=True),
            sa.Column("ibu", sa.Float(), nullable=True),
            sa.Column("carbonation_volumes", sa.Float(), nullable=True),
            sa.Column("brewfather_batch_id", sa.String(40), nullable=True),
            sa.Column("volume", sa.Float(), nullable=True),
            sa.Column("package_date", sa.Date(), nullable=True),
            sa.Column("conditioning_days", sa.Integer(), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("yeast", sa.String(100), nullable=True),
            sa.Column("yeast_product_id", sa.String(40), nullable=True),
            sa.Column("yeast_amount", sa.Float(), nullable=True),
            sa.Column("yeast_amount_unit", sa.String(10), nullable=True),
            sa.Column("yeast_form", sa.String(10), nullable=True),
            sa.Column("yeast_starter_used", sa.Boolean(), nullable=True),
            sa.Column("yeast_starter_size_l", sa.Float(), nullable=True),
            sa.Column("yeast_manufacturing_date", sa.Date(), nullable=True),
            sa.Column("yeast_best_before_date", sa.Date(), nullable=True),
            sa.Column("yeast_generation", sa.Integer(), nullable=True),
            sa.Column("gravity_device_id", sa.Uuid(), nullable=True),
            sa.Column("pressure_device_id", sa.Uuid(), nullable=True),
            sa.Column("temp_device_id", sa.Uuid(), nullable=True),
            sa.Column("recipe_cost", sa.Numeric(10, 2), nullable=True),
            sa.Column("cost_currency", sa.String(3), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="fermenting"),
            sa.Column("chamber_control_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_batch_tenant_id", "batch", ["tenant_id"])

    if "tap" not in existing:
        op.create_table(
            "tap",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("name", sa.String(60), nullable=False),
            sa.Column("tap_number", sa.Integer(), nullable=True),
            sa.Column("glass_size", sa.Float(), nullable=True),
            sa.Column("location", sa.String(100), nullable=True),
            sa.Column("notes", sa.String(200), nullable=True),
            sa.Column("token", sa.String(64), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=True),
            sa.Column("device_id", sa.Uuid(), nullable=True),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_cleaned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_volume_poured", sa.Float(), nullable=False),
            sa.Column("volume_at_last_clean", sa.Float(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_tap_tenant_id", "tap", ["tenant_id"])
        op.create_index("ix_tap_token", "tap", ["token"], unique=True)
        op.create_index("ix_tap_token_hash", "tap", ["token_hash"])

    if "tenant_settings" not in existing:
        op.create_table(
            "tenant_settings",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("backup_source_id", sa.Uuid(), nullable=False),
            sa.Column(
                "temperature_format",
                sa.Enum("c", "f", name="temperatureformat"),
                nullable=False,
            ),
            sa.Column(
                "gravity_format",
                sa.Enum("sg", "p", name="gravityformat"),
                nullable=False,
            ),
            sa.Column(
                "pressure_format",
                sa.Enum("kpa", "psi", "bar", name="pressureformat"),
                nullable=False,
            ),
            sa.Column(
                "volume_format",
                sa.Enum("metric", "us", "uk", name="volumeformat"),
                nullable=False,
            ),
            sa.Column("brewery_name", sa.String(length=100), nullable=True),
            sa.Column("logo_url", sa.String(length=2048), nullable=True),
            sa.Column("theme", sa.String(length=20), nullable=False, server_default="dark"),
            sa.Column("primary_color", sa.String(length=7), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "storage_vessel" not in existing:
        op.create_table(
            "storage_vessel",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("batch_id", sa.Uuid(), nullable=True),
            sa.Column("tap_id", sa.Uuid(), nullable=True, unique=True),
            sa.Column("vessel_number", sa.Integer(), nullable=True),
            sa.Column("vessel_type", sa.String(10), nullable=False),
            sa.Column("name", sa.String(60), nullable=False),
            sa.Column("fill_date", sa.Date(), nullable=False),
            sa.Column("total_volume", sa.Float(), nullable=False),
            sa.Column("volume_remaining", sa.Float(), nullable=False),
            sa.Column("bottle_volume", sa.Float(), nullable=True),
            sa.Column("bottle_count", sa.Integer(), nullable=True),
            sa.Column("bottles_remaining", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(15), nullable=False),
            sa.Column("location", sa.String(100), nullable=True),
            sa.Column("notes", sa.String(200), nullable=True),
            sa.Column("serving_temp_alert_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("serving_temp_min", sa.Float(), nullable=True),
            sa.Column("serving_temp_max", sa.Float(), nullable=True),
            sa.Column("conditioning_days", sa.Integer(), nullable=True),
            sa.Column("priming_sugar_type", sa.String(20), nullable=True),
            sa.Column("priming_sugar_amount", sa.Float(), nullable=True),
            sa.Column("conditioning_temp", sa.Float(), nullable=True),
            sa.Column("carbonation_volumes_target", sa.Float(), nullable=True),
            sa.Column("keg_identifier", sa.String(60), nullable=True),
            sa.Column("fill_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"]),
            sa.ForeignKeyConstraint(["tap_id"], ["tap.id"]),
            sa.CheckConstraint(
                "total_volume >= 0", name="ck_storage_vessel_total_volume_non_negative"
            ),
            sa.CheckConstraint(
                "volume_remaining >= 0", name="ck_storage_vessel_volume_remaining_non_negative"
            ),
            sa.CheckConstraint(
                "volume_remaining <= total_volume",
                name="ck_storage_vessel_volume_remaining_le_total",
            ),
            sa.CheckConstraint(
                "bottle_count IS NULL OR bottle_count >= 0",
                name="ck_storage_vessel_bottle_count_non_negative",
            ),
            sa.CheckConstraint(
                "bottles_remaining IS NULL OR bottles_remaining >= 0",
                name="ck_storage_vessel_bottles_remaining_non_negative",
            ),
            sa.CheckConstraint(
                "bottle_count IS NULL OR bottles_remaining IS NULL "
                "OR bottles_remaining <= bottle_count",
                name="ck_storage_vessel_bottles_remaining_le_count",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_storage_vessel_tenant_id", "storage_vessel", ["tenant_id"])

    if "device" not in existing:
        op.create_table(
            "device",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("name", sa.String(60), nullable=True),
            sa.Column("chip_id", sa.String(32), nullable=True),
            sa.Column("token", sa.String(64), nullable=True),
            sa.Column("token_prefix", sa.String(8), nullable=True),
            sa.Column("mdns", sa.String(80), nullable=True),
            sa.Column("description", sa.String(200), nullable=True),
            sa.Column("device_type", sa.String(20), nullable=True),
            sa.Column("url", sa.String(80), nullable=True),
            sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column(
                "device_color",
                sa.Enum(
                    "black", "red", "orange", "yellow", "green",
                    "blue", "purple", "pink", "white",
                    name="devicecolor",
                ),
                nullable=False,
                server_default="white",
            ),
            sa.Column("collect_logs", sa.Boolean(), nullable=False),
            sa.Column("chip_family", sa.String(10), nullable=True),
            sa.Column("board", sa.String(10), nullable=True),
            sa.Column("gyro_model", sa.String(20), nullable=True),
            sa.Column("device_filtered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("last_ingest_ip_hash", sa.String(64), nullable=True),
            sa.Column("batch_id", sa.Uuid(), nullable=True),
            sa.Column(
                "batch_role",
                sa.Enum("gravity", "pressure", "chamber", name="devicebatchrole"),
                nullable=True,
            ),
            sa.Column("vessel_id", sa.Uuid(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_ingest_counter", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"], name="fk_device_batch_id",
                                    use_alter=True),
            sa.ForeignKeyConstraint(["vessel_id"], ["storage_vessel.id"],
                                    name="fk_device_vessel_id", use_alter=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_device_tenant_id", "device", ["tenant_id"])
        op.create_index("ix_device_token_prefix", "device", ["token_prefix"])
        op.create_index("uq_device_token", "device", ["token"], unique=True)
        op.create_index(
            "uq_device_type_chip", "device", ["device_type", "chip_id"], unique=True
        )
        op.create_index("ix_device_last_ingest_ip_hash", "device", ["last_ingest_ip_hash"])

    if "integration" not in existing:
        op.create_table(
            "integration",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("name", sa.String(60), nullable=False),
            sa.Column("measurement", sa.String(10), nullable=False,
                      server_default="gravity"),
            sa.Column("type", sa.String(30), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_failure_code", sa.String(50), nullable=True),
            sa.Column("disabled_reason", sa.String(20), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_integration_tenant_id", "integration", ["tenant_id"])
        op.create_index(
            "ix_integration_tenant_measurement_enabled", "integration",
            ["tenant_id", "measurement", "enabled"],
        )

    if "device" not in existing:
        # batch.gravity_device_id/pressure_device_id reference device, which is
        # only just created above -- added as separate constraints to avoid a
        # circular table-creation dependency (batch <-> device).
        #
        # batch_alter_table keeps this runnable on SQLite, which cannot ALTER ADD
        # CONSTRAINT outside batch mode, while staying a plain ALTER on Postgres.
        # Without it the migration cannot execute on SQLite at all, which is what
        # kept tests/test_migration_orm_parity.py from existing here.
        with op.batch_alter_table("batch") as batch_op:
            batch_op.create_foreign_key(
                "fk_batch_gravity_device_id_device", "device", ["gravity_device_id"], ["id"],
            )
        with op.batch_alter_table("batch") as batch_op:
            batch_op.create_foreign_key(
                "fk_batch_pressure_device_id_device", "device", ["pressure_device_id"], ["id"],
            )
        with op.batch_alter_table("batch") as batch_op:
            batch_op.create_foreign_key(
                "fk_batch_temp_device_id_device", "device", ["temp_device_id"], ["id"],
            )
        # tap.device_id references device, added here for the same reason
        # (tap is created before device above).
        with op.batch_alter_table("tap") as batch_op:
            batch_op.create_foreign_key(
                "fk_tap_device_id_device", "device", ["device_id"], ["id"],
            )

    if "gravity_reading" not in existing:
        op.create_table(
            "gravity_reading",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                sa.Identity(),
                primary_key=True,
                nullable=False,
            ),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID. There is no tenant table to reference.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("batch_id", sa.Uuid(), nullable=False),
            sa.Column("device_id", sa.Uuid(), nullable=True),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("gravity", sa.Float(), nullable=False),
            sa.Column("angle", sa.Float(), nullable=True),
            sa.Column("velocity", sa.Float(), nullable=True),
            sa.Column("battery", sa.Float(), nullable=True),
            sa.Column("rssi", sa.Float(), nullable=True),
            sa.Column("run_time", sa.Float(), nullable=True),
            sa.Column("excluded", sa.Boolean(), nullable=False),
            sa.Column("is_aggregate", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"]),
            sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_gravity_reading_batch_created", "gravity_reading", ["batch_id", "created_at"])
        op.create_index("ix_gravity_reading_device_created", "gravity_reading", ["device_id", "created_at"])
        op.create_index("ix_gravity_reading_tenant_batch_created", "gravity_reading", ["tenant_id", "batch_id", "created_at"])

    if "pressure_reading" not in existing:
        op.create_table(
            "pressure_reading",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                sa.Identity(),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("batch_id", sa.Uuid(), nullable=True),
            sa.Column("vessel_id", sa.Uuid(), nullable=True),
            sa.Column("device_id", sa.Uuid(), nullable=True),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("pressure", sa.Float(), nullable=False),
            sa.Column("battery", sa.Float(), nullable=True),
            sa.Column("rssi", sa.Float(), nullable=True),
            sa.Column("run_time", sa.Float(), nullable=True),
            sa.Column("excluded", sa.Boolean(), nullable=False),
            sa.Column("is_aggregate", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"]),
            sa.ForeignKeyConstraint(["vessel_id"], ["storage_vessel.id"]),
            sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
            sa.CheckConstraint(
                "batch_id IS NOT NULL OR vessel_id IS NOT NULL",
                name="ck_pressure_reading_has_context",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pressure_reading_batch_created", "pressure_reading", ["batch_id", "created_at"])
        op.create_index("ix_pressure_reading_vessel_created", "pressure_reading", ["vessel_id", "created_at"])
        op.create_index("ix_pressure_reading_device_created", "pressure_reading", ["device_id", "created_at"])
        op.create_index("ix_pressure_reading_tenant_id", "pressure_reading", ["tenant_id"])

    if "fermentation_step" not in existing:
        op.create_table(
            "fermentation_step",
            sa.Column("id", sa.Uuid(), nullable=False),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("batch_id", sa.Uuid(), nullable=False),
            sa.Column("device_id", sa.Uuid(), nullable=True),
            sa.Column("order", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(30), nullable=True),
            sa.Column("name", sa.String(30), nullable=True),
            sa.Column("temp", sa.Float(), nullable=False),
            sa.Column("days", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=True),
            sa.Column("control", sa.String(10), nullable=True),
            sa.Column(
                "trigger_type", sa.String(20), nullable=False, server_default="day_offset"
            ),
            sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"]),
            sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_fermentation_step_batch_order", "fermentation_step", ["batch_id", "order"])
        op.create_index("ix_fermentation_step_tenant_id", "fermentation_step", ["tenant_id"])
        op.create_index("ix_fermentation_step_tenant_batch_order", "fermentation_step",
                        ["tenant_id", "batch_id", "order"])

    if "pour_event" not in existing:
        op.create_table(
            "pour_event",
            sa.Column("id", sa.Uuid(), nullable=False),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID. There is no tenant table to reference.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("vessel_id", sa.Uuid(), nullable=False),
            sa.Column("batch_id", sa.Uuid(), nullable=True),
            sa.Column("tap_id", sa.Uuid(), nullable=True),
            sa.Column("event_id", sa.String(128), nullable=True),
            sa.Column("pour_amount", sa.Float(), nullable=False),
            sa.Column("volume_remaining", sa.Float(), nullable=False),
            sa.Column("is_manual", sa.Boolean(), nullable=False),
            sa.Column("excluded", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["vessel_id"], ["storage_vessel.id"]),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"]),
            sa.ForeignKeyConstraint(["tap_id"], ["tap.id"]),
            sa.UniqueConstraint("tap_id", "event_id", name="uq_pour_event_tap_event_id"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pour_event_tenant_id", "pour_event", ["tenant_id"])
        op.create_index("ix_pour_event_batch_created", "pour_event", ["batch_id", "created_at"])

    if "prediction" not in existing:
        op.create_table(
            "prediction",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                sa.Identity(),
                primary_key=True,
                nullable=False,
            ),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID. There is no tenant table to reference.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("batch_id", sa.Uuid(), nullable=True),
            sa.Column("device_id", sa.Uuid(), nullable=True),
            sa.Column("vessel_id", sa.Uuid(), nullable=True),
            sa.Column("tap_id", sa.Uuid(), nullable=True),
            sa.Column(
                "prediction_type",
                sa.Enum(
                    "fermentation_progress", "battery_low", "keg_empty", "wifi_signal",
                    name="predictiontype",
                ),
                nullable=False,
            ),
            sa.Column("outcome", sa.String(30), nullable=False),
            sa.Column("hours_left", sa.Float(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"]),
            sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
            sa.ForeignKeyConstraint(["vessel_id"], ["storage_vessel.id"]),
            sa.ForeignKeyConstraint(["tap_id"], ["tap.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prediction_batch_created", "prediction", ["batch_id", "created_at"])
        op.create_index("ix_prediction_device_created", "prediction", ["device_id", "created_at"])
        op.create_index("ix_prediction_vessel_created", "prediction", ["vessel_id", "created_at"])
        op.create_index("ix_prediction_tap_created", "prediction", ["tap_id", "created_at"])
        op.create_index("ix_prediction_tenant_batch_created", "prediction", ["tenant_id", "batch_id", "created_at"])

    if "temp_reading" not in existing:
        op.create_table(
            "temp_reading",
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                sa.Identity(),
                primary_key=True,
                nullable=False,
            ),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID. There is no tenant table to reference.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("vessel_id", sa.Uuid(), nullable=True),
            sa.Column("batch_id", sa.Uuid(), nullable=True),
            sa.Column("device_id", sa.Uuid(), nullable=True),
            sa.Column("temperature", sa.Float(), nullable=False),
            sa.Column("battery", sa.Float(), nullable=True),
            sa.Column("rssi", sa.Float(), nullable=True),
            sa.Column("temp_type", sa.String(10), nullable=False, server_default="beer"),
            sa.Column("is_aggregate", sa.Boolean(), nullable=False),
            sa.Column("excluded", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["vessel_id"], ["storage_vessel.id"]),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"]),
            sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
            sa.CheckConstraint(
                "NOT (batch_id IS NOT NULL AND vessel_id IS NOT NULL)",
                name="ck_temp_reading_no_conflicting_context",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_temp_reading_vessel_created", "temp_reading", ["vessel_id", "created_at"])
        op.create_index("ix_temp_reading_batch_created", "temp_reading", ["batch_id", "created_at"])
        op.create_index("ix_temp_reading_tenant_id", "temp_reading", ["tenant_id"])
        op.create_index("ix_temp_reading_tenant_vessel_created", "temp_reading", ["tenant_id", "vessel_id", "created_at"])
        op.create_index("ix_temp_reading_tenant_batch_created", "temp_reading", ["tenant_id", "batch_id", "created_at"])

    if "batch_note" not in existing:
        op.create_table(
            "batch_note",
            sa.Column("id", sa.Uuid(), nullable=False),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID. There is no tenant table to reference.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("batch_id", sa.Uuid(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_by", sa.String(100), nullable=True),
            sa.Column("note_type", sa.String(20), nullable=True),
            sa.Column("test_result", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_batch_note_batch_created", "batch_note", ["batch_id", "created_at"])
        op.create_index("ix_batch_note_batch_id", "batch_note", ["batch_id"])
        op.create_index("ix_batch_note_tenant_id", "batch_note", ["tenant_id"])
        op.create_index("ix_batch_note_tenant_batch_created", "batch_note", ["tenant_id", "batch_id", "created_at"])

    if "batch_dry_hop" not in existing:
        op.create_table(
            "batch_dry_hop",
            sa.Column("id", sa.Uuid(), nullable=False),
            # Bare column, no FK: there is no tenant table. Every row carries the nil-UUID
            # DEFAULT_TENANT_ID.
            sa.Column("tenant_id", sa.Uuid(), nullable=False,
                      server_default="00000000-0000-0000-0000-000000000000"),
            sa.Column("batch_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(60), nullable=True),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("trigger_method", sa.String(30), nullable=False,
                      server_default="hours_before_completion"),
            sa.Column("trigger_gravity", sa.Float(), nullable=True),
            sa.Column("trigger_hours_before", sa.Integer(), nullable=True),
            sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["batch.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_batch_dry_hop_batch_created", "batch_dry_hop", ["batch_id", "created_at"])
        op.create_index("ix_batch_dry_hop_tenant_id", "batch_dry_hop", ["tenant_id"])
        op.create_index("ix_batch_dry_hop_tenant_batch_created", "batch_dry_hop",
                        ["tenant_id", "batch_id", "created_at"])

    # Operator tables. These are infrastructure rather than domain data, which is
    # how they came to be missing here: nothing in the app's own model files
    # mentions them, so they were never added alongside the tables that do.
    # core/log.py writes to both -- SystemLog on every startup -- so a deployment
    # whose schema comes from this migration alone had neither table.
    if "system_log" not in existing:
        op.create_table(
            "system_log",
            # Identity(), not autoincrement: matches the model, which uses it because
            # Oracle does not honour autoincrement and fails the INSERT with ORA-01400.
            sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
            sa.Column("level", sa.String(10), nullable=False, server_default="INFO"),
            sa.Column("event", sa.String(80), nullable=True),
            sa.Column("message", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "ingestion_log" not in existing:
        op.create_table(
            "ingestion_log",
            sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
            # Bare nullable columns, no FK: an unrecognised token resolves to no
            # tenant and no device, and those rows must still be recorded.
            sa.Column("tenant_id", sa.Uuid(), nullable=True),
            sa.Column("device_id", sa.Uuid(), nullable=True),
            # Validated string, not a DB enum: IngestionSource grows with every device
            # type, and device types register through a registry precisely so that
            # adding one needs no migration.
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("device_type", sa.String(12), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("reason", sa.String(30), nullable=True),
            sa.Column("error_detail", sa.String(200), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Drop all base tables in reverse FK-dependency order."""
    op.drop_table("ingestion_log")
    op.drop_table("system_log")
    op.drop_index("ix_batch_dry_hop_tenant_batch_created", table_name="batch_dry_hop")
    op.drop_index("ix_batch_dry_hop_tenant_id", table_name="batch_dry_hop")
    op.drop_index("ix_batch_dry_hop_batch_created", table_name="batch_dry_hop")
    op.drop_table("batch_dry_hop")
    op.drop_index("ix_batch_note_tenant_batch_created", table_name="batch_note")
    op.drop_index("ix_batch_note_tenant_id", table_name="batch_note")
    op.drop_index("ix_batch_note_batch_id", table_name="batch_note")
    op.drop_index("ix_batch_note_batch_created", table_name="batch_note")
    op.drop_table("batch_note")
    op.drop_index("ix_temp_reading_tenant_batch_created", table_name="temp_reading")
    op.drop_index("ix_temp_reading_tenant_vessel_created", table_name="temp_reading")
    op.drop_index("ix_temp_reading_tenant_id", table_name="temp_reading")
    op.drop_index("ix_temp_reading_batch_created", table_name="temp_reading")
    op.drop_index("ix_temp_reading_vessel_created", table_name="temp_reading")
    op.drop_table("temp_reading")
    op.drop_index("ix_prediction_tenant_batch_created", table_name="prediction")
    op.drop_index("ix_prediction_vessel_created", table_name="prediction")
    op.drop_index("ix_prediction_device_created", table_name="prediction")
    op.drop_index("ix_prediction_batch_created", table_name="prediction")
    op.drop_table("prediction")
    op.drop_index("ix_pour_event_batch_created", table_name="pour_event")
    op.drop_index("ix_pour_event_tenant_id", table_name="pour_event")
    op.drop_table("pour_event")
    op.drop_index("ix_fermentation_step_tenant_batch_order", table_name="fermentation_step")
    op.drop_index("ix_fermentation_step_tenant_id", table_name="fermentation_step")
    op.drop_index("ix_fermentation_step_batch_order", table_name="fermentation_step")
    op.drop_table("fermentation_step")
    op.drop_index("ix_pressure_reading_tenant_id", table_name="pressure_reading")
    op.drop_index("ix_pressure_reading_device_created", table_name="pressure_reading")
    op.drop_index("ix_pressure_reading_vessel_created", table_name="pressure_reading")
    op.drop_index("ix_pressure_reading_batch_created", table_name="pressure_reading")
    op.drop_table("pressure_reading")
    op.drop_index("ix_gravity_reading_tenant_batch_created", table_name="gravity_reading")
    op.drop_index("ix_gravity_reading_device_created", table_name="gravity_reading")
    op.drop_index("ix_gravity_reading_batch_created", table_name="gravity_reading")
    op.drop_table("gravity_reading")
    # Batch mode for the same reason as the matching create_foreign_key calls in
    # upgrade(): SQLite cannot ALTER a constraint outside it. Kept symmetrical so
    # the upgrade -> downgrade -> upgrade round trip runs on every backend.
    with op.batch_alter_table("tap") as batch_op:
        batch_op.drop_constraint("fk_tap_device_id_device", type_="foreignkey")
    with op.batch_alter_table("batch") as batch_op:
        batch_op.drop_constraint("fk_batch_temp_device_id_device", type_="foreignkey")
    with op.batch_alter_table("batch") as batch_op:
        batch_op.drop_constraint("fk_batch_pressure_device_id_device", type_="foreignkey")
    with op.batch_alter_table("batch") as batch_op:
        batch_op.drop_constraint("fk_batch_gravity_device_id_device", type_="foreignkey")
    op.drop_index("ix_integration_tenant_measurement_enabled", table_name="integration")
    op.drop_index("ix_integration_tenant_id", table_name="integration")
    op.drop_table("integration")
    op.drop_index("ix_device_last_ingest_ip_hash", table_name="device")
    op.drop_index("ix_device_token_prefix", table_name="device")
    op.drop_index("ix_device_tenant_id", table_name="device")
    op.drop_table("device")
    op.drop_table("storage_vessel")
    op.drop_table("tenant_settings")
    op.drop_index("ix_tap_token_hash", table_name="tap")
    op.drop_table("tap")
    op.drop_index("ix_batch_tenant_id", table_name="batch")
    op.drop_table("batch")

    # Postgres keeps enum types after their last table is dropped, so a downgrade → upgrade
    # round-trip fails on "type already exists" unless they go too. No-op on SQLite.
    if op.get_bind().dialect.name == "postgresql":
        for enum_name in (
            "devicecolor",
            "devicebatchrole",
            "gravityformat",
            "predictiontype",
            "pressureformat",
            "temperatureformat",
            "volumeformat",
        ):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
