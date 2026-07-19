"""Kafka consumer for supply-chain events: validates and routes to DLQ.

This is the reference implementation for "what does a well-behaved
consumer do when it hits a bad message" — the same pattern (try/except
around decode+validate, DLQ on failure, always commit) is reused almost
verbatim in the Dataflow pipeline's DoFn later, just ported to Beam.

Failure handling, in order:
1. Bytes that aren't valid JSON at all               -> DLQ, reason="invalid_json"
2. Valid JSON that fails schema validation            -> DLQ, reason="schema_validation_failed"
3. Valid event                                        -> processed, offset committed

Offsets are committed manually, and ALWAYS after a message is either
processed or DLQ'd — never left uncommitted on failure. An uncommitted
poison message just gets redelivered forever and wedges the partition for
every other event behind it; that's strictly worse than routing it to a
DLQ a human can inspect on their own schedule.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from confluent_kafka import Consumer, KafkaError, Producer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.config import DOMAINS, KAFKA_BOOTSTRAP_SERVERS_DEFAULT, topic_name  # noqa: E402
from supplychain_common.schema_validator import SchemaValidationError, validate_event  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("consumer")


def build_consumer(bootstrap_servers: str, group_id: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "max.poll.interval.ms": 300000,
        }
    )


def build_dlq_producer(bootstrap_servers: str) -> Producer:
    return Producer({"bootstrap.servers": bootstrap_servers, "acks": "all"})


def send_to_dlq(
    dlq_producer: Producer,
    source_topic: str,
    raw_value: bytes,
    key: bytes | None,
    reason: str,
    detail: str,
    partition: int,
    offset: int,
) -> None:
    dlq_record = {
        "failed_at": datetime.now(UTC).isoformat(),
        "source_topic": source_topic,
        "source_partition": partition,
        "source_offset": offset,
        "reason": reason,
        "detail": detail,
        # decode-or-fallback: the whole point of the DLQ is to preserve the
        # original bytes for a human to inspect, even if they aren't UTF-8/JSON.
        "raw_value": raw_value.decode("utf-8", errors="replace"),
    }
    dlq_topic = source_topic if source_topic.endswith(".dlq") else f"{source_topic}.dlq"
    dlq_producer.produce(
        dlq_topic,
        key=key,
        value=json.dumps(dlq_record).encode("utf-8"),
    )
    dlq_producer.poll(0)
    logger.warning("routed to DLQ: topic=%s reason=%s detail=%s", dlq_topic, reason, detail)


def process_message(msg, dlq_producer: Producer) -> None:
    source_topic = msg.topic()
    try:
        event = json.loads(msg.value())
    except json.JSONDecodeError as exc:
        send_to_dlq(
            dlq_producer, source_topic, msg.value(), msg.key(), "invalid_json", str(exc), msg.partition(), msg.offset()
        )
        return

    try:
        validate_event(event)
    except SchemaValidationError as exc:
        send_to_dlq(
            dlq_producer,
            source_topic,
            msg.value(),
            msg.key(),
            "schema_validation_failed",
            "; ".join(exc.errors),
            msg.partition(),
            msg.offset(),
        )
        return

    # Valid event — this is where a real consumer would do its work
    # (write-through cache, trigger a downstream call, etc). Here we just
    # log; the actual system-of-record write happens via the Dataflow
    # pipeline reading from Pub/Sub, not from this consumer.
    logger.info(
        "valid event: topic=%s event_type=%s event_id=%s", source_topic, event.get("event_type"), event.get("event_id")
    )


def run(domains: list[str], bootstrap_servers: str, group_id: str) -> None:
    consumer = build_consumer(bootstrap_servers, group_id)
    dlq_producer = build_dlq_producer(bootstrap_servers)
    topics = [topic_name(d) for d in domains]
    consumer.subscribe(topics)
    logger.info("subscribed to %s as group=%s", topics, group_id)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("consumer error: %s", msg.error())
                continue

            process_message(msg, dlq_producer)
            consumer.commit(msg, asynchronous=False)
    except KeyboardInterrupt:
        logger.info("interrupted, shutting down...")
    finally:
        dlq_producer.flush(10)
        consumer.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domains", default="all", help="comma-separated domains or 'all'")
    parser.add_argument("--bootstrap-servers", default=KAFKA_BOOTSTRAP_SERVERS_DEFAULT)
    parser.add_argument("--group-id", default="supplychain-consumer-group")
    args = parser.parse_args()

    domains = list(DOMAINS) if args.domains == "all" else [d.strip() for d in args.domains.split(",")]
    for d in domains:
        if d not in DOMAINS:
            parser.error(f"unknown domain {d!r}, expected one of {DOMAINS}")

    run(domains, args.bootstrap_servers, args.group_id)


if __name__ == "__main__":
    main()
