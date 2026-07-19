# Sequence Diagrams

## 1. Happy path — a single order event, end to end

```mermaid
sequenceDiagram
    participant WMS as Warehouse System
    participant Producer as Kafka Producer
    participant Kafka
    participant Bridge as Kafka→Pub/Sub Bridge
    participant PubSub as Pub/Sub
    participant Dataflow
    participant BQ as BigQuery Bronze
    participant Silver as BigQuery Silver (scheduled MERGE)

    WMS->>Producer: order created
    Producer->>Producer: validate against JSON Schema
    Producer->>Kafka: produce(key=order_id, acks=all)
    Kafka-->>Producer: ack (all in-sync replicas)
    Bridge->>Kafka: poll (consumer group: pubsub-bridge)
    Bridge->>Bridge: validate (defense in depth)
    Bridge->>PubSub: publish(ordering_key=order_id)
    Bridge->>Kafka: commit offset (only after publish succeeds)
    Dataflow->>PubSub: pull (ordered subscription)
    Dataflow->>Dataflow: parse, validate, window, dedup(event_id)
    Dataflow->>BQ: WriteToBigQuery (Storage Write API, exactly-once)
    Note over Silver: every 30 min
    Silver->>BQ: MERGE ... WHEN NOT MATCHED (idempotent dedup)
```

## 2. DLQ path — a malformed event

```mermaid
sequenceDiagram
    participant Producer as Kafka Producer (chaos mode)
    participant Kafka
    participant Consumer as Kafka Consumer
    participant DLQ as Kafka DLQ topic
    participant Alert as Cloud Monitoring

    Producer->>Kafka: produce(corrupted event)
    Consumer->>Kafka: poll
    Consumer->>Consumer: json.loads() or schema validation FAILS
    Consumer->>DLQ: produce({reason, detail, raw_value})
    Consumer->>Kafka: commit offset (always — never redeliver a poison message)
    Note over DLQ: DLQ monitoring subscription
    DLQ->>Alert: num_undelivered_messages > 0 for 10m
    Alert-->>Alert: page on-call (see monitoring-guide.md)
```

## 3. Replay / backfill from the GCS raw archive

```mermaid
sequenceDiagram
    participant Archive as GCS Raw Archive
    participant Batch as Batch Beam Pipeline (replay)
    participant BQ as BigQuery Bronze
    participant Silver as BigQuery Silver

    Note over Archive: Kafka retention (7-14d) has long since expired;<br/>GCS archive is the only remaining source
    Batch->>Archive: ReadFromText(gs://.../<domain>/*.jsonl)
    Batch->>Batch: same parse/validate/dedup transforms as streaming
    Batch->>BQ: WriteToBigQuery (WRITE_APPEND — Bronze is append-only)
    Note over Silver: next scheduled run picks up the backfilled rows
    Silver->>BQ: MERGE ... WHEN NOT MATCHED (safe to re-run — event_id dedup)
```
