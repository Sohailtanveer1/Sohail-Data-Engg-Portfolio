-- Silver: Return lifecycle events, deduplicated, event grain.

MERGE INTO supplychain_silver.returns AS target
USING (
  SELECT * EXCEPT(rn) FROM (
    SELECT
      event_id, event_type, event_timestamp, schema_version, source_system,
      warehouse_id, return_id, order_id, sku, quantity, reason_code, inspection_result,
      _ingested_at, _pubsub_message_id, _pipeline_version,
      ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at DESC) AS rn
    FROM supplychain_bronze.returns
    WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 26 HOUR)
  )
  WHERE rn = 1
) AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN
  INSERT (event_id, event_type, event_timestamp, schema_version, source_system,
          warehouse_id, return_id, order_id, sku, quantity, reason_code, inspection_result,
          _ingested_at, _pubsub_message_id, _pipeline_version)
  VALUES (source.event_id, source.event_type, source.event_timestamp, source.schema_version, source.source_system,
          source.warehouse_id, source.return_id, source.order_id, source.sku, source.quantity, source.reason_code, source.inspection_result,
          source._ingested_at, source._pubsub_message_id, source._pipeline_version);
