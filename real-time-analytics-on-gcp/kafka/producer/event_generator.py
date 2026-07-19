"""Synthetic supply-chain event generator.

Generates realistic-looking Order/Inventory/Shipment/Return/Supplier events.
Also deliberately injects the failure modes the rest of the platform is
built to handle, at caller-controlled rates:

- malformed events (missing/wrong-typed required field)      -> exercises the DLQ path
- duplicate event_ids (same event sent twice)                 -> exercises dedup/idempotency
- late/out-of-order event_timestamp (backdated into the past) -> exercises watermarking/windowing

A real upstream system doesn't misbehave on command, but in a portfolio
project you have to manufacture the failure modes you want to demonstrate
handling — otherwise the DLQ and watermarking code paths are unreachable
and untested.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

WAREHOUSES = ["WH-EAST-01", "WH-EAST-02", "WH-WEST-01", "WH-CENTRAL-01"]
SKUS = [f"SKU-{i:05d}" for i in range(1, 51)]
CARRIERS = ["UPS", "FedEx", "USPS", "XPO", "Old Dominion"]
SUPPLIERS = [f"SUP-{i:04d}" for i in range(1, 21)]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _envelope(source_system: str) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_timestamp": _now_iso(),
        "schema_version": "1.0",
        "source_system": source_system,
    }


def gen_order_event() -> dict:
    order_id = f"ORD-{random.randint(100000, 999999)}"
    event = {
        **_envelope("WMS-" + random.choice(WAREHOUSES)),
        "event_type": random.choice(["ORDER_CREATED", "ORDER_UPDATED", "ORDER_CANCELLED", "ORDER_FULFILLED"]),
        "warehouse_id": random.choice(WAREHOUSES),
        "order_id": order_id,
        "customer_id": f"CUST-{random.randint(1000, 9999)}",
        "order_status": random.choice(["PENDING", "CONFIRMED", "CANCELLED", "FULFILLED"]),
        "line_items": [
            {
                "sku": random.choice(SKUS),
                "quantity": random.randint(1, 5),
                "unit_price": round(random.uniform(5, 250), 2),
            }
            for _ in range(random.randint(1, 3))
        ],
    }
    return event


def gen_inventory_event() -> dict:
    delta = random.choice([-10, -5, -1, 1, 5, 20, 50])
    return {
        **_envelope("IMS-" + random.choice(WAREHOUSES)),
        "event_type": random.choice(["STOCK_RECEIVED", "STOCK_ADJUSTED", "STOCK_RESERVED", "STOCK_RELEASED"]),
        "warehouse_id": random.choice(WAREHOUSES),
        "sku": random.choice(SKUS),
        "quantity_delta": delta,
        "quantity_on_hand": max(0, random.randint(0, 500) + delta),
    }


def gen_shipment_event() -> dict:
    shipment_id = f"SHP-{random.randint(100000, 999999)}"
    return {
        **_envelope("TMS-CENTRAL"),
        "event_type": random.choice(
            ["SHIPMENT_CREATED", "SHIPMENT_DISPATCHED", "SHIPMENT_IN_TRANSIT", "SHIPMENT_DELIVERED", "SHIPMENT_DELAYED"]
        ),
        "shipment_id": shipment_id,
        "order_id": f"ORD-{random.randint(100000, 999999)}",
        "carrier": random.choice(CARRIERS),
        "tracking_number": uuid.uuid4().hex[:12].upper(),
        "origin_warehouse_id": random.choice(WAREHOUSES),
        "destination_postal_code": f"{random.randint(10000, 99999)}",
        "estimated_delivery": (datetime.now(UTC) + timedelta(days=random.randint(1, 7))).date().isoformat(),
    }


def gen_return_event() -> dict:
    return {
        **_envelope("RMS-" + random.choice(WAREHOUSES)),
        "event_type": random.choice(["RETURN_INITIATED", "RETURN_RECEIVED", "RETURN_INSPECTED", "RETURN_REFUNDED"]),
        "warehouse_id": random.choice(WAREHOUSES),
        "return_id": f"RET-{random.randint(100000, 999999)}",
        "order_id": f"ORD-{random.randint(100000, 999999)}",
        "sku": random.choice(SKUS),
        "quantity": random.randint(1, 3),
        "reason_code": random.choice(["DAMAGED", "WRONG_ITEM", "NOT_NEEDED", "QUALITY_ISSUE", "OTHER"]),
    }


def gen_supplier_event() -> dict:
    return {
        **_envelope("SRM-CENTRAL"),
        "event_type": random.choice(
            [
                "SUPPLIER_ONBOARDED",
                "SUPPLIER_PO_ISSUED",
                "SUPPLIER_PO_ACKNOWLEDGED",
                "SUPPLIER_PO_DELAYED",
                "SUPPLIER_RATING_UPDATED",
            ]
        ),
        "supplier_id": random.choice(SUPPLIERS),
        "po_number": f"PO-{random.randint(10000, 99999)}",
        "sku_list": random.sample(SKUS, k=random.randint(1, 4)),
        "expected_delivery_date": (datetime.now(UTC) + timedelta(days=random.randint(2, 21))).date().isoformat(),
        "rating": round(random.uniform(2.5, 5.0), 1),
    }


GENERATORS = {
    "orders": gen_order_event,
    "inventory": gen_inventory_event,
    "shipments": gen_shipment_event,
    "returns": gen_return_event,
    "suppliers": gen_supplier_event,
}


def make_malformed(event: dict) -> dict:
    """Corrupts a valid event so it fails schema validation — simulates a
    misbehaving upstream producer (wrong type, dropped required field)."""
    corrupted = dict(event)
    choice = random.choice(["drop_required_field", "wrong_type", "unknown_field"])
    if choice == "drop_required_field":
        corrupted.pop("event_id", None)
    elif choice == "wrong_type":
        corrupted["event_timestamp"] = 12345  # should be a string
    else:
        corrupted["totally_unexpected_field"] = "shouldn't be here"
    return corrupted


def make_late(event: dict, min_minutes: int = 10, max_minutes: int = 90) -> dict:
    """Backdates event_timestamp to simulate a late-arriving event (e.g. a
    warehouse with an intermittent network link uploading a batch late)."""
    late = dict(event)
    delay = timedelta(minutes=random.randint(min_minutes, max_minutes))
    ts = datetime.now(UTC) - delay
    late["event_timestamp"] = ts.isoformat()
    return late
