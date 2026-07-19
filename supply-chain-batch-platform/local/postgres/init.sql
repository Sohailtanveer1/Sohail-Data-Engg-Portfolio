-- WMS source schema. Mirrors data_generators/wms.py so Phase 5 can extract these
-- tables over JDBC exactly as it would from the real Warehouse Management System.
-- Runs once on first container start (empty volume). Seed data via scripts/seed_wms.py.

CREATE SCHEMA IF NOT EXISTS wms;

CREATE TABLE IF NOT EXISTS wms.warehouse_location (
    location_id    TEXT PRIMARY KEY,
    warehouse_id   TEXT NOT NULL,
    aisle          INTEGER,
    bin            INTEGER,
    location_type  TEXT
);

CREATE TABLE IF NOT EXISTS wms.inventory (
    warehouse_id   TEXT NOT NULL,
    material_id    TEXT NOT NULL,
    on_hand_qty    INTEGER,
    allocated_qty  INTEGER,
    location_id    TEXT,
    updated_at     TIMESTAMPTZ,
    PRIMARY KEY (warehouse_id, material_id)
);

CREATE TABLE IF NOT EXISTS wms.stock_movement (
    movement_id    TEXT PRIMARY KEY,
    material_id    TEXT NOT NULL,
    warehouse_id   TEXT NOT NULL,
    movement_type  TEXT,
    move_qty       INTEGER,
    movement_ts    TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS wms.cycle_count (
    count_id       TEXT PRIMARY KEY,
    material_id    TEXT NOT NULL,
    warehouse_id   TEXT NOT NULL,
    system_qty     INTEGER,
    counted_qty    INTEGER,
    variance       INTEGER,
    count_date     DATE
);

-- Incremental-extraction support: indexes on the watermark columns.
CREATE INDEX IF NOT EXISTS ix_inventory_updated_at ON wms.inventory (updated_at);
CREATE INDEX IF NOT EXISTS ix_stock_movement_updated_at ON wms.stock_movement (updated_at);
