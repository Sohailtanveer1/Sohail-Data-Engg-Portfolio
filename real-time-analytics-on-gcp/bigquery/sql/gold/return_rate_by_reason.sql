-- Gold: daily return volume by warehouse and reason — the tile that
-- answers "is DAMAGED creeping up at one warehouse" before it becomes a
-- quarterly write-off surprise.
SELECT
  warehouse_id,
  reason_code,
  DATE(event_timestamp) AS return_date,
  COUNT(*) AS return_count,
  SUM(quantity) AS units_returned
FROM supplychain_silver.returns
WHERE event_type = 'RETURN_INITIATED'
GROUP BY warehouse_id, reason_code, return_date
