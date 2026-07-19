-- Gold: per-supplier PO reliability and rating — feeds the "who do we
-- source from next quarter" conversation with actual data instead of gut feel.
SELECT
  supplier_id,
  COUNTIF(event_type = 'SUPPLIER_PO_ISSUED') AS pos_issued,
  COUNTIF(event_type = 'SUPPLIER_PO_ACKNOWLEDGED') AS pos_acknowledged,
  COUNTIF(event_type = 'SUPPLIER_PO_DELAYED') AS pos_delayed,
  SAFE_DIVIDE(COUNTIF(event_type = 'SUPPLIER_PO_DELAYED'), NULLIF(COUNTIF(event_type = 'SUPPLIER_PO_ISSUED'), 0)) AS delay_rate,
  ARRAY_AGG(rating IGNORE NULLS ORDER BY event_timestamp DESC LIMIT 1)[SAFE_OFFSET(0)] AS latest_rating
FROM supplychain_silver.suppliers
GROUP BY supplier_id
