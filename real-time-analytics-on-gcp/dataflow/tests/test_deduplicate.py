"""Confirms DeduplicateByEventId drops a repeated event_id within the same
window and keeps distinct event_ids — the core idempotency guarantee this
transform exists to provide (see the module docstring for why this is
layered on top of, not a replacement for, producer-side idempotence).
"""

import sys
from pathlib import Path

import apache_beam as beam
import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "transforms"))
from deduplicate import DeduplicateByEventId  # noqa: E402


class FakeRecord:
    def __init__(self, event_id: str):
        self.event = {"event_id": event_id}

    def __eq__(self, other):
        return isinstance(other, FakeRecord) and self.event == other.event

    def __repr__(self):
        return f"FakeRecord({self.event['event_id']})"


def test_duplicate_event_id_is_dropped():
    records = [FakeRecord("evt-1"), FakeRecord("evt-1"), FakeRecord("evt-2")]

    with TestPipeline() as p:
        result = (
            p
            | beam.Create(records)
            | beam.Map(lambda r: (r.event["event_id"], r))
            | beam.ParDo(DeduplicateByEventId())
            | beam.Map(lambda r: r.event["event_id"])
        )
        assert_that(result, equal_to(["evt-1", "evt-2"]))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
