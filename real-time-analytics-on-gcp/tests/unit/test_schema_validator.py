import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.schema_validator import SchemaValidationError, domain_for_event, validate_event  # noqa: E402


def _valid_inventory_event() -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "STOCK_RECEIVED",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "source_system": "IMS-TEST",
        "warehouse_id": "WH-EAST-01",
        "sku": "SKU-00001",
        "quantity_delta": 10,
        "quantity_on_hand": 110,
    }


def test_valid_event_passes():
    event = _valid_inventory_event()
    assert validate_event(event) == "inventory"


def test_missing_required_field_raises():
    event = _valid_inventory_event()
    del event["sku"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_event(event)
    assert exc_info.value.domain == "inventory"


def test_wrong_type_raises():
    event = _valid_inventory_event()
    event["quantity_delta"] = "not-a-number"
    with pytest.raises(SchemaValidationError):
        validate_event(event)


def test_additional_property_rejected():
    event = _valid_inventory_event()
    event["totally_unexpected_field"] = "nope"
    with pytest.raises(SchemaValidationError):
        validate_event(event)


def test_domain_for_event_unknown_type_raises():
    with pytest.raises(SchemaValidationError):
        domain_for_event({"event_type": "NOT_A_REAL_TYPE"})


def test_domain_for_event_missing_type_raises():
    with pytest.raises(SchemaValidationError):
        domain_for_event({})
