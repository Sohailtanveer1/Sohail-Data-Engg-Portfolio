"""Kafka producer for supply-chain events.

Design choices worth defending in an interview:

- acks=all + enable.idempotence=True: the broker won't ack until all
  in-sync replicas have the record, and idempotent producer sequence
  numbers mean a retried send after a broker timeout can't create a
  duplicate on the broker side. This gets us exactly-once *per partition*
  producer semantics — it does NOT dedup two genuinely separate produce()
  calls with different event_ids, which is why the consumer/Dataflow side
  still does event_id-based dedup (idempotency is layered, not solved once).
- Malformed/duplicate/late events are injected here on purpose (see
  event_generator.py) to make the downstream failure-handling paths
  (DLQ, dedup, watermarking) reachable in a demo without needing a real
  misbehaving upstream system.

Usage:
    python producer.py --domains orders,inventory --rate 5 --duration 120
    python producer.py --domains all --rate 10 --malformed-rate 0.03
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

from confluent_kafka import Producer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.config import DOMAINS, KAFKA_BOOTSTRAP_SERVERS_DEFAULT, partition_key, topic_name  # noqa: E402
from supplychain_common.retry import call_with_backoff  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from event_generator import GENERATORS, make_late, make_malformed  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("producer")


def build_producer(bootstrap_servers: str) -> Producer:
    return Producer(
        {
            "bootstrap.servers": bootstrap_servers,
            "acks": "all",
            "enable.idempotence": True,
            "retries": 10,
            "retry.backoff.ms": 200,
            "request.timeout.ms": 15000,
            "linger.ms": 20,  # small batching window; trades a little latency for throughput
            "compression.type": "snappy",
        }
    )


def delivery_report(err, msg):
    if err is not None:
        logger.error("delivery failed: topic=%s key=%s error=%s", msg.topic(), msg.key(), err)
    else:
        logger.debug("delivered: topic=%s partition=%s offset=%s", msg.topic(), msg.partition(), msg.offset())


def produce_one(producer: Producer, domain: str, event: dict) -> None:
    topic = topic_name(domain)
    key = partition_key(domain, event)
    payload = json.dumps(event).encode("utf-8")

    def _send():
        producer.produce(topic, key=key.encode("utf-8"), value=payload, callback=delivery_report)

    try:
        call_with_backoff(_send, max_attempts=5, retry_on=(BufferError,))
    except Exception:
        logger.exception("giving up on event_id=%s after retries", event.get("event_id"))


def run(
    domains: list[str],
    rate_per_sec: float,
    duration_seconds: float | None,
    malformed_rate: float,
    duplicate_rate: float,
    late_rate: float,
    bootstrap_servers: str,
) -> None:
    producer = build_producer(bootstrap_servers)
    interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0
    start = time.monotonic()
    sent = 0
    recent_by_domain: dict[str, list[dict]] = {d: [] for d in domains}

    logger.info(
        "producing to domains=%s rate=%.1f/s duration=%s bootstrap=%s",
        domains,
        rate_per_sec,
        duration_seconds,
        bootstrap_servers,
    )

    try:
        while duration_seconds is None or (time.monotonic() - start) < duration_seconds:
            domain = random.choice(domains)
            event = GENERATORS[domain]()

            roll = random.random()
            if roll < malformed_rate:
                event = make_malformed(event)
            elif roll < malformed_rate + late_rate:
                event = make_late(event)
            else:
                recent = recent_by_domain[domain]
                recent.append(event)
                if len(recent) > 50:
                    recent.pop(0)
                if recent and random.random() < duplicate_rate:
                    event = random.choice(recent)  # resend a prior event_id verbatim

            produce_one(producer, domain, event)
            sent += 1
            producer.poll(0)

            if sent % 100 == 0:
                logger.info("sent %d events", sent)

            if interval:
                time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("interrupted, flushing...")
    finally:
        producer.flush(30)
        logger.info("done. total sent=%d", sent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domains", default="all", help="comma-separated domains or 'all'")
    parser.add_argument("--rate", type=float, default=5.0, help="events per second, combined across domains")
    parser.add_argument("--duration", type=float, default=None, help="seconds to run; omit to run until Ctrl+C")
    parser.add_argument("--malformed-rate", type=float, default=0.02)
    parser.add_argument("--duplicate-rate", type=float, default=0.03)
    parser.add_argument("--late-rate", type=float, default=0.05)
    parser.add_argument("--bootstrap-servers", default=KAFKA_BOOTSTRAP_SERVERS_DEFAULT)
    args = parser.parse_args()

    domains = list(DOMAINS) if args.domains == "all" else [d.strip() for d in args.domains.split(",")]
    for d in domains:
        if d not in DOMAINS:
            parser.error(f"unknown domain {d!r}, expected one of {DOMAINS}")

    run(
        domains,
        args.rate,
        args.duration,
        args.malformed_rate,
        args.duplicate_rate,
        args.late_rate,
        args.bootstrap_servers,
    )


if __name__ == "__main__":
    main()
