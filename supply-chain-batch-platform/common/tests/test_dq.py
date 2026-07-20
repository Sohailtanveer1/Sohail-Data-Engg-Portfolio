import pytest

from scb_common.dq import (
    AllowedValues,
    ForeignKey,
    NonNegative,
    NotNull,
    Unique,
    ValidDate,
    evaluate,
    rule_from_dict,
)
from scb_common.errors import DataQualityError

ROWS = [
    {"material_id": "M1", "order_qty": 10, "currency": "USD", "order_date": "2026-07-19"},
    {"material_id": "M2", "order_qty": -5, "currency": "USD", "order_date": "2026-07-19"},
    {"material_id": None, "order_qty": 3, "currency": "XXX", "order_date": "bad-date"},
    {"material_id": "M1", "order_qty": 7, "currency": "CAD", "order_date": "2026-07-20"},
]


def test_not_null_counts_failures():
    report = evaluate(ROWS, [NotNull("material_id")], key_column="material_id")
    res = report.results[0]
    assert res.failed == 1
    assert res.column == "material_id"


def test_non_negative_flags_negative():
    report = evaluate(ROWS, [NonNegative("order_qty")])
    assert report.results[0].failed == 1


def test_allowed_values_and_valid_date():
    report = evaluate(
        ROWS,
        [AllowedValues("currency", allowed={"USD", "CAD"}), ValidDate("order_date")],
    )
    by = {r.rule: r for r in report.results}
    assert by["AllowedValues(currency)"].failed == 1
    assert by["ValidDate(order_date)"].failed == 1


def test_unique_detects_duplicate_business_key():
    report = evaluate(ROWS, [Unique("material_id")], key_column="material_id")
    # M1 appears twice -> 1 duplicate
    assert report.results[0].failed == 1


def test_foreign_key_referential_check():
    report = evaluate(ROWS, [ForeignKey("material_id", valid_keys={"M1"})])
    # M2 not in {M1}; None passes (nullness is NotNull's job) -> 1 failure (M2)
    assert report.results[0].failed == 1


def test_error_threshold_breach_raises_and_quarantines():
    report = evaluate(ROWS, [NotNull("material_id", threshold=0.0)], key_column="material_id")
    assert report.breaches
    with pytest.raises(DataQualityError):
        report.raise_if_failed()
    clean, quarantined = report.split(ROWS)
    assert len(quarantined) == 1
    assert len(clean) == 3


def test_warn_severity_does_not_raise():
    report = evaluate(ROWS, [NonNegative("order_qty", severity="warn")])
    report.raise_if_failed()  # should not raise
    assert report.results[0].failed == 1


def test_threshold_tolerance_allows_small_failure_fraction():
    # 1 of 4 fails = 0.25; threshold 0.3 -> no breach
    report = evaluate(ROWS, [NonNegative("order_qty", threshold=0.3)])
    assert not report.breaches


def test_rule_from_dict_factory():
    rule = rule_from_dict(
        {"type": "allowed_values", "column": "currency", "allowed": ["USD", "CAD"]}
    )
    report = evaluate(ROWS, [rule])
    assert report.results[0].failed == 1
