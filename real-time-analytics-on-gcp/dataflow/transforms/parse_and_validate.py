"""First DoFn in every domain branch: decode Pub/Sub bytes, validate against
the same JSON Schema the producer/consumer/bridge use, and split into two
tagged outputs.

This is intentionally the FIRST thing that happens to a message, before
windowing or dedup — a malformed message has no reliable event_timestamp to
window on anyway, so there's nothing correct to do with it except quarantine
it immediately.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import apache_beam as beam
from apache_beam import pvalue
from apache_beam.utils.timestamp import Timestamp

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.schema_validator import SchemaValidationError, validate_event  # noqa: E402

VALID_TAG = "valid"
DLQ_TAG = "dlq"


class ParsedRecord:
    """Carries the validated event plus the Pub/Sub metadata needed for
    audit columns downstream — keeping this as one object avoids threading
    three separate pieces of metadata through every subsequent transform."""

    __slots__ = ("event", "domain", "message_id", "publish_time")

    def __init__(self, event: dict, domain: str, message_id: str, publish_time: datetime):
        self.event = event
        self.domain = domain
        self.message_id = message_id
        self.publish_time = publish_time


class ParseAndValidate(beam.DoFn):
    """Expects PubsubMessage elements (ReadFromPubSub(with_attributes=True)).

    Emits to the 'valid' tag with the record's Beam-level timestamp set to
    event_timestamp (not processing time) — this is what makes watermarking
    downstream meaningful; without it, "late data" has no definition.
    Emits to the 'dlq' tag (untimestamped — DLQ handling doesn't need
    event-time correctness) on any failure.
    """

    def __init__(self, domain: str):
        self.domain = domain

    def process(self, message):
        publish_time = message.publish_time
        try:
            event = json.loads(message.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            yield pvalue.TaggedOutput(DLQ_TAG, self._dlq_record("invalid_json", str(exc), message))
            return

        try:
            validate_event(event, domain=self.domain)
        except SchemaValidationError as exc:
            yield pvalue.TaggedOutput(
                DLQ_TAG, self._dlq_record("schema_validation_failed", "; ".join(exc.errors), message)
            )
            return

        record = ParsedRecord(event, self.domain, message.message_id, publish_time)
        event_ts = datetime.fromisoformat(event["event_timestamp"])
        if event_ts.tzinfo is None:
            event_ts = event_ts.replace(tzinfo=UTC)
        yield pvalue.TaggedOutput(
            VALID_TAG, beam.window.TimestampedValue(record, Timestamp.from_utc_datetime(event_ts))
        )

    @staticmethod
    def _dlq_record(reason: str, detail: str, message) -> dict:
        return {
            "reason": reason,
            "detail": detail,
            "raw_value": message.data.decode("utf-8", errors="replace"),
            "pubsub_message_id": message.message_id,
            "failed_at": datetime.now(UTC).isoformat(),
            "stage": "dataflow_parse_and_validate",
        }
