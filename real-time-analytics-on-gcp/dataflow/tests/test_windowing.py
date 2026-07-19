"""Demonstrates testing watermark/lateness behavior in isolation from any
I/O, using Beam's TestStream to control the watermark explicitly. This is
the standard way to unit-test windowing logic — the interview-relevant
takeaway is that "does my allowed_lateness config actually drop what I
think it drops" is testable without deploying anything.

This exercises the SAME window/trigger/lateness configuration
streaming_pipeline.py uses (see WINDOW_SIZE_SECONDS / ALLOWED_LATENESS_SECONDS
there), applied to a minimal record type instead of the full ParsedRecord
graph, to keep the test focused on windowing behavior specifically.
"""

import sys
from pathlib import Path

import apache_beam as beam
import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.test_stream import TestStream
from apache_beam.testing.util import assert_that, equal_to
from apache_beam.transforms.trigger import AccumulationMode, AfterCount, AfterProcessingTime, AfterWatermark
from apache_beam.transforms.window import FixedWindows
from apache_beam.utils.timestamp import Duration, Timestamp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))
from streaming_pipeline import ALLOWED_LATENESS_SECONDS, WINDOW_SIZE_SECONDS  # noqa: E402


def test_event_within_allowed_lateness_is_kept():
    """An event whose timestamp falls in a window that has already closed,
    but within allowed_lateness of the current watermark, must still come
    through — that's the entire point of allowed_lateness existing."""
    test_stream = (
        TestStream()
        .advance_watermark_to(0)
        .add_elements([beam.window.TimestampedValue("on-time", Timestamp(0))])
        .advance_watermark_to(WINDOW_SIZE_SECONDS + 1)  # closes the [0, 60s) window
        .add_elements([beam.window.TimestampedValue("late-but-allowed", Timestamp(5))])  # belongs to the closed window
        .advance_watermark_to_infinity()
    )

    with TestPipeline() as p:
        result = (
            p
            | test_stream
            | beam.WindowInto(
                FixedWindows(WINDOW_SIZE_SECONDS),
                trigger=AfterWatermark(early=AfterProcessingTime(30), late=AfterCount(1)),
                accumulation_mode=AccumulationMode.DISCARDING,
                allowed_lateness=Duration(seconds=ALLOWED_LATENESS_SECONDS),
            )
        )
        # Both elements belong to window [0, 60s) and both arrive within
        # allowed_lateness of the watermark that eventually closes it.
        assert_that(result, equal_to(["on-time", "late-but-allowed"]))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
