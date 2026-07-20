-- Supplier performance: lead time (order -> receipt), fill rate, and spend by
-- vendor. Joins POs to their goods receipts. Grain: one row per PO line.
-- Powers the "Supplier Performance" Looker dashboard.
CREATE OR REPLACE VIEW `${DATASET}.vw_supplier_performance` AS
WITH receipts AS (
  SELECT po_number, po_line,
         MIN(receipt_date) AS first_receipt_date,
         SUM(received_qty) AS received_qty
  FROM `${DATASET}.fact_goods_receipt`
  GROUP BY po_number, po_line
)
SELECT
  v.vendor_id,
  v.vendor_name,
  m.category,
  po.order_date,
  r.first_receipt_date,
  DATE_DIFF(r.first_receipt_date, po.order_date, DAY) AS lead_time_days,
  po.order_qty,
  r.received_qty,
  SAFE_DIVIDE(r.received_qty, po.order_qty) AS fill_rate,
  po.line_amount AS spend
FROM `${DATASET}.fact_purchase_order` po
LEFT JOIN receipts r
  ON po.po_number = r.po_number AND po.po_line = r.po_line
LEFT JOIN `${DATASET}.dim_vendor` v
  ON po.vendor_sk = v.vendor_sk AND v.is_current
LEFT JOIN `${DATASET}.dim_material` m
  ON po.material_sk = m.material_sk AND m.is_current;
