-- Order fulfillment: PO -> receipt cycle time and fill rate, rolled up by day.
-- Grain: one row per PO line (detail); dashboards aggregate by order_date.
-- Powers the "Order Fulfillment" Looker dashboard.
CREATE OR REPLACE VIEW `${DATASET}.vw_order_fulfillment` AS
WITH receipts AS (
  SELECT po_number, po_line,
         MIN(receipt_date) AS first_receipt_date,
         SUM(received_qty) AS received_qty
  FROM `${DATASET}.fact_goods_receipt`
  GROUP BY po_number, po_line
)
SELECT
  po.order_date,
  w.warehouse_id,
  w.region,
  po.po_number,
  po.po_line,
  po.order_qty,
  r.received_qty,
  r.first_receipt_date,
  DATE_DIFF(r.first_receipt_date, po.order_date, DAY) AS cycle_time_days,
  SAFE_DIVIDE(r.received_qty, po.order_qty) AS fill_rate,
  CASE WHEN r.received_qty >= po.order_qty THEN 1 ELSE 0 END AS fully_received
FROM `${DATASET}.fact_purchase_order` po
LEFT JOIN receipts r
  ON po.po_number = r.po_number AND po.po_line = r.po_line
LEFT JOIN `${DATASET}.dim_warehouse` w
  ON po.warehouse_sk = w.warehouse_sk;
