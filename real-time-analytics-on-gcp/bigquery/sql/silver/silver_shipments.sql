-- Silver: Shipment lifecycle events, deduplicated, event grain.
-- Includes the enrichment columns (carrier_live_status, carrier_eta) the
-- Dataflow pipeline's enrich_shipment.py transform populates on
-- SHIPMENT_DISPATCHED/SHIPMENT_IN_TRANSIT events — null on other event
-- types by design, not a data quality issue.

MERGE INTO supplychain_silver.shipments AS target
USING (
  SELECT * EXCEPT(rn) FROM (
    SELECT
      event_id, event_type, event_timestamp, schema_version, source_system,
      shipment_id, order_id, carrier, tracking_number, origin_warehouse_id,
      destination_postal_code, estimated_delivery, carrier_live_status, carrier_eta,
      _ingested_at, _pubsub_message_id, _pipeline_version,
      ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at DESC) AS rn
    FROM supplychain_bronze.shipments
    WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 26 HOUR)
  )
  WHERE rn = 1
) AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN
  INSERT (event_id, event_type, event_timestamp, schema_version, source_system,
          shipment_id, order_id, carrier, tracking_number, origin_warehouse_id,
          destination_postal_code, estimated_delivery, carrier_live_status, carrier_eta,
          _ingested_at, _pubsub_message_id, _pipeline_version)
  VALUES (source.event_id, source.event_type, source.event_timestamp, source.schema_version, source.source_system,
          source.shipment_id, source.order_id, source.carrier, source.tracking_number, source.origin_warehouse_id,
          source.destination_postal_code, source.estimated_delivery, source.carrier_live_status, source.carrier_eta,
          source._ingested_at, source._pubsub_message_id, source._pipeline_version);
