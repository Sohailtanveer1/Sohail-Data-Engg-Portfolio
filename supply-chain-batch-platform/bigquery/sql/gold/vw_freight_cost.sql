-- Freight cost analysis: cost per lb and on-time rate by carrier, mode and lane.
-- Grain: one row per shipment. Powers the "Freight Cost" Looker dashboard.
CREATE OR REPLACE VIEW `${DATASET}.vw_freight_cost` AS
SELECT
  sh.ship_date,
  c.carrier_scac,
  c.carrier_name,
  c.mode,
  w.region        AS origin_region,
  sh.origin_warehouse_sk,
  sh.freight_cost,
  sh.weight_lb,
  SAFE_DIVIDE(sh.freight_cost, NULLIF(sh.weight_lb, 0)) AS cost_per_lb,
  sh.transit_days,
  sh.on_time,
  sh.delivery_status
FROM `${DATASET}.fact_shipment` sh
LEFT JOIN `${DATASET}.dim_carrier` c
  ON sh.carrier_sk = c.carrier_sk
LEFT JOIN `${DATASET}.dim_warehouse` w
  ON sh.origin_warehouse_sk = w.warehouse_sk;
