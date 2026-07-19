import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.config import dlq_topic_name, partition_key, topic_name  # noqa: E402


def test_topic_name_format():
    assert topic_name("orders") == "supplychain.orders.v1"


def test_dlq_topic_name_format():
    assert dlq_topic_name("orders") == "supplychain.orders.v1.dlq"


def test_topic_name_rejects_unknown_domain():
    with pytest.raises(ValueError):
        topic_name("not-a-domain")


def test_partition_key_single_field():
    assert partition_key("orders", {"order_id": "ORD-1"}) == "ORD-1"


def test_partition_key_composite_field():
    event = {"warehouse_id": "WH-EAST-01", "sku": "SKU-00001"}
    assert partition_key("inventory", event) == "WH-EAST-01:SKU-00001"
