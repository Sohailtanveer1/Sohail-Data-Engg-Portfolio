-- Gold: one row per shipment — dispatch-to-delivery duration and whether it
-- beat the carrier's own estimate. Feeds the "carrier performance" tile
-- ops uses to decide who to route future volume to.
SELECT
  shipment_id,
  ANY_VALUE(order_id) AS order_id,
  ANY_VALUE(carrier) AS carrier,
  ANY_VALUE(origin_warehouse_id) AS origin_warehouse_id,
  MIN(IF(event_type = 'SHIPMENT_DISPATCHED', event_timestamp, NULL)) AS dispatched_at,
  MIN(IF(event_type = 'SHIPMENT_DELIVERED', event_timestamp, NULL)) AS delivered_at,
  MAX(estimated_delivery) AS estimated_delivery,
  LOGICAL_OR(event_type = 'SHIPMENT_DELAYED') AS was_flagged_delayed,
  TIMESTAMP_DIFF(
    MIN(IF(event_type = 'SHIPMENT_DELIVERED', event_timestamp, NULL)),
    MIN(IF(event_type = 'SHIPMENT_DISPATCHED', event_timestamp, NULL)),
    HOUR
  ) AS transit_hours,
  DATE(MIN(IF(event_type = 'SHIPMENT_DELIVERED', event_timestamp, NULL))) > MAX(estimated_delivery) AS delivered_after_estimate
FROM supplychain_silver.shipments
GROUP BY shipment_id
