-- Silver: Supplier lifecycle events, deduplicated, event grain.

MERGE INTO supplychain_silver.suppliers AS target
USING (
  SELECT * EXCEPT(rn) FROM (
    SELECT
      event_id, event_type, event_timestamp, schema_version, source_system,
      supplier_id, po_number, sku_list, expected_delivery_date, rating,
      _ingested_at, _pubsub_message_id, _pipeline_version,
      ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at DESC) AS rn
    FROM supplychain_bronze.suppliers
    WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 26 HOUR)
  )
  WHERE rn = 1
) AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN
  INSERT (event_id, event_type, event_timestamp, schema_version, source_system,
          supplier_id, po_number, sku_list, expected_delivery_date, rating,
          _ingested_at, _pubsub_message_id, _pipeline_version)
  VALUES (source.event_id, source.event_type, source.event_timestamp, source.schema_version, source.source_system,
          source.supplier_id, source.po_number, source.sku_list, source.expected_delivery_date, source.rating,
          source._ingested_at, source._pubsub_message_id, source._pipeline_version);
