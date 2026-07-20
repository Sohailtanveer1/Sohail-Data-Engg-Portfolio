-- Inventory health: on-hand, value, and days-of-supply by warehouse & material,
-- with a stock-status flag. Grain: one row per material x warehouse x snapshot_date.
-- Semi-additive: do NOT SUM on_hand across snapshot_date (use latest / average).
-- Powers the "Inventory Health" Looker dashboard.
CREATE OR REPLACE VIEW `${DATASET}.vw_inventory_health` AS
SELECT
  s.snapshot_date,
  w.warehouse_id,
  w.warehouse_name,
  w.region,
  m.material_id,
  m.description AS material_desc,
  m.category,
  s.on_hand_qty,
  s.on_hand_value,
  s.days_of_supply,
  CASE
    WHEN s.days_of_supply IS NULL THEN 'UNKNOWN'
    WHEN s.days_of_supply < 7  THEN 'CRITICAL'
    WHEN s.days_of_supply < 14 THEN 'LOW'
    ELSE 'OK'
  END AS stock_status
FROM `${DATASET}.fact_inventory_snapshot` s
JOIN `${DATASET}.dim_warehouse` w
  ON s.warehouse_sk = w.warehouse_sk
JOIN `${DATASET}.dim_material` m
  ON s.material_sk = m.material_sk AND m.is_current;
