"""Exactly-once-per-window deduplication keyed by event_id, using Beam's
per-key state.

Why this exists on top of the producer's idempotent-producer config and the
Pub/Sub Storage Write API's own dedup: those two mechanisms each cover one
hop (Kafka broker, BigQuery insert). Neither covers "the bridge crashed
after publishing to Pub/Sub but before committing its Kafka offset, so on
restart it republishes the same event_id" — that's a genuine at-least-once
gap between Kafka and Pub/Sub, and this is where it gets closed.

State is scoped to (key, window) automatically because this DoFn runs on a
windowed PCollection — when FixedWindows(60s) closes (past allowed
lateness), the runner garbage-collects the state for that window. This is
what "dedup within a bounded window" gets you for free instead of having to
hand-manage a TTL with timers: duplicates arriving within the same window
are caught; a genuine duplicate arriving a day later would need something
sturdier (e.g. a BigQuery MERGE on event_id in the Silver layer — see
bigquery/sql/silver/), which is why Silver does its own dedup pass too.
Defense in depth, not one clever trick.
"""

from __future__ import annotations

import apache_beam as beam
from apache_beam.coders import BooleanCoder
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec


class DeduplicateByEventId(beam.DoFn):
    SEEN = ReadModifyWriteStateSpec("seen", BooleanCoder())

    def process(self, element, seen=beam.DoFn.StateParam(SEEN)):
        # element is (event_id, ParsedRecord) — see streaming_pipeline.py's
        # `beam.Map(lambda r: (r.event["event_id"], r))` upstream of this.
        event_id, record = element
        if seen.read():
            return  # duplicate within this window — drop silently, no DLQ (not an error, expected behavior)
        seen.write(True)
        yield record
