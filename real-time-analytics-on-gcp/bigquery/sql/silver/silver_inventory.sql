-- Silver: Inventory movements, deduplicated, event grain (a ledger of
-- deltas, not a snapshot — gold/inventory_snapshot.sql derives current
-- on-hand quantity from this by taking the latest event per warehouse+sku).
-- See silver_orders.sql for the lookback/MERGE rationale — identical here.

MERGE INTO supplychain_silver.inventory AS target
USING (
  SELECT * EXCEPT(rn) FROM (
    SELECT
      event_id, event_type, event_timestamp, schema_version, source_system,
      warehouse_id, sku, quantity_delta, quantity_on_hand, reference_order_id,
      _ingested_at, _pubsub_message_id, _pipeline_version,
      ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at DESC) AS rn
    FROM supplychain_bronze.inventory
    WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 26 HOUR)
  )
  WHERE rn = 1
) AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN
  INSERT (event_id, event_type, event_timestamp, schema_version, source_system,
          warehouse_id, sku, quantity_delta, quantity_on_hand, reference_order_id,
          _ingested_at, _pubsub_message_id, _pipeline_version)
  VALUES (source.event_id, source.event_type, source.event_timestamp, source.schema_version, source.source_system,
          source.warehouse_id, source.sku, source.quantity_delta, source.quantity_on_hand, source.reference_order_id,
          source._ingested_at, source._pubsub_message_id, source._pipeline_version);
