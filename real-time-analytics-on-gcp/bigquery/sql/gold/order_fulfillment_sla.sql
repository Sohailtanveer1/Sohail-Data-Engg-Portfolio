-- Gold: one row per order, answering "did we hit our fulfillment SLA?" —
-- the exact question ops asks after a stockout complaint. This is a VIEW
-- (computed at query time on Silver, not materialized) because it's cheap
-- enough to recompute per query and staying a view means it's always
-- current with whatever Silver's latest 30-min refresh landed, with no
-- extra scheduling to manage.
SELECT
  order_id,
  ANY_VALUE(warehouse_id) AS warehouse_id,
  ANY_VALUE(customer_id) AS customer_id,
  MIN(IF(event_type = 'ORDER_CREATED', event_timestamp, NULL)) AS created_at,
  MIN(IF(event_type = 'ORDER_FULFILLED', event_timestamp, NULL)) AS fulfilled_at,
  MAX(IF(event_type = 'ORDER_CANCELLED', event_timestamp, NULL)) AS cancelled_at,
  ARRAY_AGG(order_status ORDER BY event_timestamp DESC LIMIT 1)[OFFSET(0)] AS current_status,
  TIMESTAMP_DIFF(
    MIN(IF(event_type = 'ORDER_FULFILLED', event_timestamp, NULL)),
    MIN(IF(event_type = 'ORDER_CREATED', event_timestamp, NULL)),
    HOUR
  ) AS fulfillment_hours,
  TIMESTAMP_DIFF(
    MIN(IF(event_type = 'ORDER_FULFILLED', event_timestamp, NULL)),
    MIN(IF(event_type = 'ORDER_CREATED', event_timestamp, NULL)),
    HOUR
  ) <= 48 AS within_48h_sla
FROM supplychain_silver.orders
GROUP BY order_id
