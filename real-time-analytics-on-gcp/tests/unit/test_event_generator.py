"""Ties the producer's synthetic data generator to the actual JSON schemas —
if a schema changes (a new required field, say) and the generator isn't
updated to match, this is what catches it instead of finding out via a
flood of DLQ messages after deploying.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.schema_validator import SchemaValidationError, validate_event  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kafka" / "producer"))
from event_generator import GENERATORS, make_late, make_malformed  # noqa: E402


def test_every_generator_produces_schema_valid_events():
    for domain, generator in GENERATORS.items():
        for _ in range(20):
            event = generator()
            validate_event(event, domain=domain)  # raises on failure


def test_make_malformed_fails_validation():
    domain = "orders"
    event = GENERATORS[domain]()
    corrupted = make_malformed(event)
    try:
        validate_event(corrupted, domain=domain)
        raised = False
    except SchemaValidationError:
        raised = True
    assert raised, "make_malformed should always produce a schema-invalid event"


def test_make_late_backdates_timestamp_but_stays_valid():
    domain = "orders"
    event = GENERATORS[domain]()
    late = make_late(event, min_minutes=30, max_minutes=30)
    assert late["event_timestamp"] != event["event_timestamp"]
    validate_event(late, domain=domain)  # still schema-valid, just old
