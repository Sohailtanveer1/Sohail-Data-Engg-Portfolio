"""Unit tests for the parse/validate DoFn — the DLQ-routing logic is the
part worth pinning down with tests, since a regression here means bad data
starts silently reaching BigQuery instead of being quarantined.
"""

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import apache_beam as beam
import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "transforms"))
from parse_and_validate import DLQ_TAG, VALID_TAG, ParseAndValidate  # noqa: E402


class FakePubsubMessage:
    def __init__(self, data: bytes, message_id: str = "msg-1", publish_time=None):
        self.data = data
        self.message_id = message_id
        self.publish_time = publish_time or datetime.now(UTC)


def _valid_order_event() -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "ORDER_CREATED",
        "event_timestamp": datetime.now(UTC).isoformat(),
        "schema_version": "1.0",
        "source_system": "WMS-TEST",
        "warehouse_id": "WH-EAST-01",
        "order_id": "ORD-000001",
        "customer_id": "CUST-0001",
        "order_status": "PENDING",
        "line_items": [{"sku": "SKU-00001", "quantity": 1, "unit_price": 9.99}],
    }


def test_valid_event_routes_to_valid_tag():
    event = _valid_order_event()
    message = FakePubsubMessage(json.dumps(event).encode("utf-8"))

    with TestPipeline() as p:
        result = p | beam.Create([message]) | beam.ParDo(ParseAndValidate("orders")).with_outputs(VALID_TAG, DLQ_TAG)
        assert_that(result[DLQ_TAG], equal_to([]), label="dlq_empty")


def test_invalid_json_routes_to_dlq():
    message = FakePubsubMessage(b"{not valid json")

    with TestPipeline() as p:
        result = p | beam.Create([message]) | beam.ParDo(ParseAndValidate("orders")).with_outputs(VALID_TAG, DLQ_TAG)

        def check_dlq(records):
            assert len(records) == 1
            assert records[0]["reason"] == "invalid_json"

        assert_that(result[DLQ_TAG], check_dlq, label="dlq_has_one_invalid_json")


def test_missing_required_field_routes_to_dlq():
    event = _valid_order_event()
    del event["order_id"]  # required field
    message = FakePubsubMessage(json.dumps(event).encode("utf-8"))

    with TestPipeline() as p:
        result = p | beam.Create([message]) | beam.ParDo(ParseAndValidate("orders")).with_outputs(VALID_TAG, DLQ_TAG)

        def check_dlq(records):
            assert len(records) == 1
            assert records[0]["reason"] == "schema_validation_failed"

        assert_that(result[DLQ_TAG], check_dlq, label="dlq_has_one_schema_failure")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
