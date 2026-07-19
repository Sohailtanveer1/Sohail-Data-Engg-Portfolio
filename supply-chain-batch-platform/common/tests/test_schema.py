import pytest

from scb_common.errors import SchemaValidationError
from scb_common.schema import ColumnSpec, TableSchema

SCHEMA = TableSchema(
    entity="material",
    columns=[
        ColumnSpec("material_id", "string", nullable=False),
        ColumnSpec("category", "string"),
        ColumnSpec("std_cost", "double"),
    ],
    business_keys=["material_id"],
)


def test_valid_rows_pass():
    rows = [{"material_id": "M1", "category": "RAW", "std_cost": 1.5}]
    assert SCHEMA.validate_rows(rows) == []


def test_missing_required_column_raises():
    rows = [{"category": "RAW", "std_cost": 1.5}]
    with pytest.raises(SchemaValidationError) as e:
        SCHEMA.validate_rows(rows)
    assert "material_id" in e.value.missing


def test_null_in_non_nullable_raises():
    rows = [{"material_id": None, "category": "RAW", "std_cost": 1.5}]
    with pytest.raises(SchemaValidationError):
        SCHEMA.validate_rows(rows)


def test_type_mismatch_raises():
    rows = [{"material_id": "M1", "category": "RAW", "std_cost": "not-a-number"}]
    with pytest.raises(SchemaValidationError):
        SCHEMA.validate_rows(rows)


def test_additive_column_allowed_and_reported():
    rows = [{"material_id": "M1", "category": "RAW", "std_cost": 1.5, "new_col": "x"}]
    added = SCHEMA.validate_rows(rows, allow_additive=True)
    assert added == ["new_col"]


def test_additive_column_disallowed_raises():
    rows = [{"material_id": "M1", "category": "RAW", "std_cost": 1.5, "new_col": "x"}]
    with pytest.raises(SchemaValidationError):
        SCHEMA.validate_rows(rows, allow_additive=False)


def test_from_dict_builds_schema():
    spec = {
        "version": 2,
        "business_keys": ["material_id"],
        "columns": [{"name": "material_id", "dtype": "string", "nullable": False}],
    }
    s = TableSchema.from_dict("material", spec)
    assert s.version == 2
    assert s.required_names() == ["material_id"]
