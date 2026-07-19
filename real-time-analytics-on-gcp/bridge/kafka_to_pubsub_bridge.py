"""Bridges validated Kafka events into Google Pub/Sub.

Why a bridge process instead of publishing to Pub/Sub directly from the
warehouse producers: it models the realistic enterprise seam between an
on-prem/self-hosted system (Kafka, something IT already runs today) and
the cloud platform. It also means Kafka can keep running — and buffering —
during a GCP outage or a Pub/Sub quota incident without the warehouses'
producers ever knowing anything is wrong downstream.

This is a *separate* consumer group from kafka/consumer/consumer.py
(different group.id) so both can run against the same topics independently
— that's normal Kafka fan-out, not a conflict.

Auth: uses Application Default Credentials. Run `gcloud auth application-
default login` locally, or set GOOGLE_APPLICATION_CREDENTIALS to a service
account key when running as the dedicated bridge service account
(see infra/terraform/modules/iam).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from confluent_kafka import Consumer, KafkaError, Producer
from google.cloud import pubsub_v1

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from supplychain_common.config import DOMAINS, KAFKA_BOOTSTRAP_SERVERS_DEFAULT, topic_name  # noqa: E402
from supplychain_common.retry import call_with_backoff  # noqa: E402
from supplychain_common.schema_validator import SchemaValidationError, validate_event  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bridge")

BRIDGE_CONSUMER_GROUP = "supplychain-pubsub-bridge"


def build_kafka_consumer(bootstrap_servers: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": BRIDGE_CONSUMER_GROUP,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )


def build_kafka_dlq_producer(bootstrap_servers: str) -> Producer:
    return Producer({"bootstrap.servers": bootstrap_servers, "acks": "all"})


def send_kafka_dlq(dlq_producer: Producer, source_topic: str, raw_value: bytes, reason: str, detail: str) -> None:
    dlq_producer.produce(
        f"{source_topic}.dlq",
        value=json.dumps(
            {
                "reason": reason,
                "detail": detail,
                "raw_value": raw_value.decode("utf-8", errors="replace"),
                "stage": "kafka_to_pubsub_bridge",
            }
        ).encode("utf-8"),
    )
    dlq_producer.poll(0)
    logger.warning("bridge DLQ'd message: topic=%s reason=%s", source_topic, reason)


def publish_to_pubsub(publisher: pubsub_v1.PublisherClient, topic_path: str, event: dict, ordering_key: str) -> None:
    def _publish():
        future = publisher.publish(
            topic_path,
            data=json.dumps(event).encode("utf-8"),
            ordering_key=ordering_key,  # requires the Pub/Sub topic to have message ordering enabled
            event_id=event["event_id"],
        )
        return future.result(timeout=30)

    call_with_backoff(_publish, max_attempts=5, base_delay_seconds=1.0)


def run(domains: list[str], bootstrap_servers: str, gcp_project: str) -> None:
    consumer = build_kafka_consumer(bootstrap_servers)
    dlq_producer = build_kafka_dlq_producer(bootstrap_servers)
    # enable_message_ordering must be set on the CLIENT for publish() to
    # accept an ordering_key at all — it's a client-side guard, separate from
    # the subscription's enable_message_ordering (which is what actually makes
    # Pub/Sub deliver in order). Both are required: this to send the key, the
    # subscription (set in the pubsub Terraform module) to honor it.
    publisher = pubsub_v1.PublisherClient(
        publisher_options=pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
    )

    topics = [topic_name(d) for d in domains]
    consumer.subscribe(topics)
    logger.info("bridging %s -> Pub/Sub project=%s", topics, gcp_project)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("kafka consumer error: %s", msg.error())
                continue

            source_topic = msg.topic()
            try:
                event = json.loads(msg.value())
                validate_event(event)
            except json.JSONDecodeError as exc:
                send_kafka_dlq(dlq_producer, source_topic, msg.value(), "invalid_json", str(exc))
                consumer.commit(msg, asynchronous=False)
                continue
            except SchemaValidationError as exc:
                send_kafka_dlq(
                    dlq_producer, source_topic, msg.value(), "schema_validation_failed", "; ".join(exc.errors)
                )
                consumer.commit(msg, asynchronous=False)
                continue

            topic_path = publisher.topic_path(gcp_project, source_topic)
            ordering_key = msg.key().decode("utf-8") if msg.key() else event["event_id"]
            try:
                publish_to_pubsub(publisher, topic_path, event, ordering_key)
            except Exception:
                # Transient Pub/Sub failure after retries exhausted: do NOT
                # commit. Leaving the offset uncommitted means this message
                # is redelivered on restart instead of silently dropped —
                # unlike a validation failure, a Pub/Sub outage is not the
                # message's fault, so it deserves a retry, not a DLQ.
                logger.exception(
                    "giving up publishing event_id=%s to Pub/Sub; leaving offset uncommitted", event.get("event_id")
                )
                continue

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
    parser.add_argument("--gcp-project", required=True, help="GCP project ID that owns the Pub/Sub topics")
    args = parser.parse_args()

    domains = list(DOMAINS) if args.domains == "all" else [d.strip() for d in args.domains.split(",")]
    for d in domains:
        if d not in DOMAINS:
            parser.error(f"unknown domain {d!r}, expected one of {DOMAINS}")

    run(domains, args.bootstrap_servers, args.gcp_project)


if __name__ == "__main__":
    main()
