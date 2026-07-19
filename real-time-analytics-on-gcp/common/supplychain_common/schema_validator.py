"""Validates event payloads against the JSON Schemas in kafka/schemas/.

kafka/schemas/ (not this package) is the source of truth for the contracts —
this module only loads and applies them, so producer, consumer, bridge, and
the Dataflow pipeline can never drift into checking slightly different rules.
"""

from __future__ import annotations

import json
import os
from functools import cache
from pathlib import Path

import jsonschema

from supplychain_common.config import DOMAINS, EVENT_TYPE_TO_DOMAIN


class SchemaValidationError(Exception):
    """Raised when an event fails schema validation. Carries the domain and
    original errors so callers can route the raw message to a DLQ with
    enough context to debug it without replaying from Kafka."""

    def __init__(self, domain: str, errors: list[str]):
        self.domain = domain
        self.errors = errors
        super().__init__(f"{domain}: {'; '.join(errors)}")


def _schema_dir() -> Path:
    override = os.environ.get("SUPPLYCHAIN_SCHEMA_DIR")
    if override:
        return Path(override)
    # common/supplychain_common/schema_validator.py -> repo_root/kafka/schemas
    return Path(__file__).resolve().parents[2] / "kafka" / "schemas"


_DOMAIN_TO_FILENAME = {
    "orders": "order_event.schema.json",
    "inventory": "inventory_event.schema.json",
    "shipments": "shipment_event.schema.json",
    "returns": "return_event.schema.json",
    "suppliers": "supplier_event.schema.json",
}


@cache
def _load_validator(domain: str) -> jsonschema.protocols.Validator:
    if domain not in DOMAINS:
        raise ValueError(f"Unknown domain {domain!r}, expected one of {DOMAINS}")
    schema_path = _schema_dir() / _DOMAIN_TO_FILENAME[domain]
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    return validator_cls(schema)


def domain_for_event(event: dict) -> str:
    event_type = event.get("event_type")
    domain = EVENT_TYPE_TO_DOMAIN.get(event_type)
    if domain is None:
        raise SchemaValidationError(
            domain="unknown",
            errors=[f"unrecognized or missing event_type: {event_type!r}"],
        )
    return domain


def validate_event(event: dict, domain: str | None = None) -> str:
    """Validates `event` against its domain's schema.

    Returns the resolved domain on success. Raises SchemaValidationError
    (never a bare jsonschema exception) so every caller has one exception
    type to catch when deciding whether to route to a DLQ.
    """
    if domain is None:
        domain = domain_for_event(event)

    validator = _load_validator(domain)
    errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
    if errors:
        raise SchemaValidationError(
            domain=domain,
            errors=[f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors],
        )
    return domain
