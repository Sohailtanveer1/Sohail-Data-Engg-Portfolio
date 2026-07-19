"""Single source of truth for names shared across Kafka, Pub/Sub, and BigQuery.

Every component (producer, consumer, bridge, Dataflow pipeline, Terraform
variable defaults) derives topic/table names from here rather than
hardcoding strings, so a rename is a one-line change instead of a grep-and-pray.
"""

from __future__ import annotations

DOMAINS = ("orders", "inventory", "shipments", "returns", "suppliers")

SCHEMA_VERSION = "v1"


# Kafka and Pub/Sub use the identical topic name — the bridge is a straight
# passthrough, which is the point (see bridge/kafka_to_pubsub_bridge.py).
def topic_name(domain: str) -> str:
    if domain not in DOMAINS:
        raise ValueError(f"Unknown domain {domain!r}, expected one of {DOMAINS}")
    return f"supplychain.{domain}.{SCHEMA_VERSION}"


def dlq_topic_name(domain: str) -> str:
    return f"{topic_name(domain)}.dlq"


# event_type -> domain, used by the bridge/consumer to route a decoded
# message to the right schema without needing a separate lookup table.
EVENT_TYPE_TO_DOMAIN = {
    "ORDER_CREATED": "orders",
    "ORDER_UPDATED": "orders",
    "ORDER_CANCELLED": "orders",
    "ORDER_FULFILLED": "orders",
    "STOCK_RECEIVED": "inventory",
    "STOCK_ADJUSTED": "inventory",
    "STOCK_RESERVED": "inventory",
    "STOCK_RELEASED": "inventory",
    "SHIPMENT_CREATED": "shipments",
    "SHIPMENT_DISPATCHED": "shipments",
    "SHIPMENT_IN_TRANSIT": "shipments",
    "SHIPMENT_DELIVERED": "shipments",
    "SHIPMENT_DELAYED": "shipments",
    "RETURN_INITIATED": "returns",
    "RETURN_RECEIVED": "returns",
    "RETURN_INSPECTED": "returns",
    "RETURN_REFUNDED": "returns",
    "SUPPLIER_ONBOARDED": "suppliers",
    "SUPPLIER_PO_ISSUED": "suppliers",
    "SUPPLIER_PO_ACKNOWLEDGED": "suppliers",
    "SUPPLIER_PO_DELAYED": "suppliers",
    "SUPPLIER_RATING_UPDATED": "suppliers",
}

# Partition/ordering key field per domain — must match docs/architecture/kafka-topic-design.md
DOMAIN_KEY_FIELDS = {
    "orders": ("order_id",),
    "inventory": ("warehouse_id", "sku"),
    "shipments": ("shipment_id",),
    "returns": ("return_id",),
    "suppliers": ("supplier_id",),
}


def partition_key(domain: str, event: dict) -> str:
    fields = DOMAIN_KEY_FIELDS[domain]
    return ":".join(str(event[f]) for f in fields)


KAFKA_BOOTSTRAP_SERVERS_DEFAULT = "localhost:9092,localhost:9094,localhost:9095"

BIGQUERY_DATASETS = {
    "bronze": "supplychain_bronze",
    "silver": "supplychain_silver",
    "gold": "supplychain_gold",
}
