-- Gold: current on-hand quantity per warehouse+sku — derived from the
-- Silver inventory LEDGER (one row per movement) by taking the most recent
-- event per key. This is the view Looker Studio's stockout-risk tile reads.
SELECT
  warehouse_id,
  sku,
  ARRAY_AGG(quantity_on_hand ORDER BY event_timestamp DESC LIMIT 1)[OFFSET(0)] AS current_quantity_on_hand,
  ARRAY_AGG(event_timestamp ORDER BY event_timestamp DESC LIMIT 1)[OFFSET(0)] AS as_of,
  ARRAY_AGG(quantity_on_hand ORDER BY event_timestamp DESC LIMIT 1)[OFFSET(0)] <= 10 AS low_stock_flag
FROM supplychain_silver.inventory
GROUP BY warehouse_id, sku
