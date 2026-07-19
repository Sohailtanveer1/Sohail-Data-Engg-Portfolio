-- Silver: Orders, deduplicated and conformed, SAME grain as Bronze (one row
-- per valid event — NOT collapsed to "latest order status"; that's a Gold
-- concern, see gold/order_fulfillment_sla.sql, because collapsing to
-- latest-state throws away the event history other marts might need).
--
-- Run as a BigQuery Scheduled Query (see infra/terraform/modules/bigquery
-- — provision the schedule alongside this SQL once you're ready to
-- automate it; run by hand via `bq query` until then).
--
-- Why a 26-hour lookback + idempotent MERGE instead of a precise watermark
-- table: Beam's own dedup is scoped to a 60s window + 1hr allowed lateness
-- (see dataflow/pipelines/streaming_pipeline.py), so a duplicate that
-- slips past that gets caught here instead — event_id is the MERGE key,
-- so re-scanning overlapping time ranges on every run is safe by
-- construction, not just "probably fine." A watermark table would save
-- some scanned bytes; the idempotency guarantee is worth more than the
-- savings at this data volume.

MERGE INTO supplychain_silver.orders AS target
USING (
  SELECT * EXCEPT(rn) FROM (
    SELECT
      event_id,
      event_type,
      event_timestamp,
      schema_version,
      source_system,
      warehouse_id,
      order_id,
      customer_id,
      order_status,
      line_items,
      _ingested_at,
      _pubsub_message_id,
      _pipeline_version,
      ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at DESC) AS rn
    FROM supplychain_bronze.orders
    WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 26 HOUR)
  )
  WHERE rn = 1
) AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN
  INSERT (event_id, event_type, event_timestamp, schema_version, source_system,
          warehouse_id, order_id, customer_id, order_status, line_items,
          _ingested_at, _pubsub_message_id, _pipeline_version)
  VALUES (source.event_id, source.event_type, source.event_timestamp, source.schema_version, source.source_system,
          source.warehouse_id, source.order_id, source.customer_id, source.order_status, source.line_items,
          source._ingested_at, source._pubsub_message_id, source._pipeline_version);
-- Intentionally no WHEN MATCHED clause: event_id is immutable and
-- append-only by definition (an order's lifecycle is a sequence of
-- DISTINCT events, never a correction to a past event) — a matched
-- event_id is by definition the exact duplicate this MERGE exists to skip.
