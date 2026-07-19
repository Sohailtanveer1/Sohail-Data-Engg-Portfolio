"""Reusable, declarative data-quality framework (ADR-0010).

Rules are data (not code) so they can live in config and be applied uniformly
across every entity. Phase 2 evaluates over ``list[dict]`` rows; Phase 6 will add
a Spark evaluator for the same rule objects.

Each rule has a ``severity``:
- ``error`` : failing rows are quarantined; if the failed fraction exceeds the
  rule's ``threshold`` the batch fails (DataQualityError).
- ``warn``  : logged and counted, batch continues.

    rules = [NotNull("material_id"), Unique("material_id"),
             InRange("order_qty", min_value=0), AllowedValues("currency", {"USD","CAD"})]
    report = evaluate(rows, rules)
    report.raise_if_failed()          # enforces error-severity thresholds
    clean, quarantined = report.split(rows)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence

from scb_common.errors import DataQualityError

Row = Mapping[str, Any]
Severity = str  # "error" | "warn"


@dataclass
class Rule:
    """Base rule. Subclasses implement ``passes(row)`` for a single row."""

    column: str
    severity: Severity = "error"
    threshold: float = 0.0  # max allowed fraction of failing rows (error severity)

    @property
    def name(self) -> str:
        return f"{type(self).__name__}({self.column})"

    def passes(self, row: Row) -> bool:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass
class NotNull(Rule):
    def passes(self, row: Row) -> bool:
        v = row.get(self.column)
        return v is not None and v != ""


@dataclass
class InRange(Rule):
    min_value: float | None = None
    max_value: float | None = None

    def passes(self, row: Row) -> bool:
        v = row.get(self.column)
        if v is None:
            return True  # nullness is NotNull's job
        try:
            n = float(v)
        except (TypeError, ValueError):
            return False
        if self.min_value is not None and n < self.min_value:
            return False
        if self.max_value is not None and n > self.max_value:
            return False
        return True


@dataclass
class NonNegative(InRange):
    def __post_init__(self) -> None:
        self.min_value = 0.0


@dataclass
class AllowedValues(Rule):
    allowed: set[Any] = field(default_factory=set)

    def passes(self, row: Row) -> bool:
        v = row.get(self.column)
        return v is None or v in self.allowed


@dataclass
class MatchesRegex(Rule):
    pattern: str = ".*"

    def __post_init__(self) -> None:
        self._rx = re.compile(self.pattern)

    def passes(self, row: Row) -> bool:
        v = row.get(self.column)
        return v is None or bool(self._rx.fullmatch(str(v)))


@dataclass
class ValidDate(Rule):
    fmt: str = "%Y-%m-%d"

    def passes(self, row: Row) -> bool:
        v = row.get(self.column)
        if v is None or isinstance(v, (date, datetime)):
            return True
        try:
            datetime.strptime(str(v), self.fmt)
            return True
        except ValueError:
            return False


@dataclass
class ForeignKey(Rule):
    """Referential check: value must exist in a provided set of valid keys."""

    valid_keys: set[Any] = field(default_factory=set)

    def passes(self, row: Row) -> bool:
        v = row.get(self.column)
        return v is None or v in self.valid_keys


class Unique:
    """Dataset-level uniqueness on one column (not row-by-row)."""

    def __init__(self, column: str, severity: Severity = "error", threshold: float = 0.0):
        self.column = column
        self.severity = severity
        self.threshold = threshold

    @property
    def name(self) -> str:
        return f"Unique({self.column})"


@dataclass
class RuleResult:
    rule: str
    column: str
    severity: Severity
    passed: int
    failed: int
    threshold: float
    failing_indexes: list[int] = field(default_factory=list)
    sample_keys: list[Any] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def failed_fraction(self) -> float:
        return self.failed / self.total if self.total else 0.0

    @property
    def breached(self) -> bool:
        """True if an error-severity rule exceeded its allowed failure threshold."""
        return self.severity == "error" and self.failed_fraction > self.threshold


@dataclass
class DQReport:
    results: list[RuleResult]
    failing_indexes: set[int] = field(default_factory=set)

    @property
    def breaches(self) -> list[RuleResult]:
        return [r for r in self.results if r.breached]

    def raise_if_failed(self) -> None:
        breaches = self.breaches
        if breaches:
            raise DataQualityError(
                f"{len(breaches)} data-quality rule(s) breached threshold",
                failed_rules=[r.rule for r in breaches],
            )

    def split(self, rows: Sequence[Row]) -> tuple[list[Row], list[Row]]:
        """Partition rows into (clean, quarantined) by any error-severity failure."""
        clean, quarantined = [], []
        for i, row in enumerate(rows):
            (quarantined if i in self.failing_indexes else clean).append(row)
        return clean, quarantined


def _key_of(row: Row, column: str) -> Any:
    return row.get(column)


def evaluate(rows: Sequence[Row], rules: Sequence[Rule | Unique],
             key_column: str | None = None) -> DQReport:
    """Evaluate all rules over ``rows`` and return a DQReport.

    ``key_column`` (usually the business key) is captured in ``sample_keys`` for
    failing rows so ``dq_results`` can point operators at the offending records.
    """
    results: list[RuleResult] = []
    error_failing: set[int] = set()

    for rule in rules:
        if isinstance(rule, Unique):
            seen: dict[Any, int] = {}
            failing: list[int] = []
            for i, row in enumerate(rows):
                v = row.get(rule.column)
                if v in seen:
                    failing.append(i)
                else:
                    seen[v] = i
            failed = len(failing)
            res = RuleResult(
                rule=rule.name, column=rule.column, severity=rule.severity,
                passed=len(rows) - failed, failed=failed, threshold=rule.threshold,
                failing_indexes=failing[:50],
                sample_keys=[_key_of(rows[i], key_column or rule.column) for i in failing[:10]],
            )
        else:
            failing = [i for i, row in enumerate(rows) if not rule.passes(row)]
            failed = len(failing)
            res = RuleResult(
                rule=rule.name, column=rule.column, severity=rule.severity,
                passed=len(rows) - failed, failed=failed, threshold=rule.threshold,
                failing_indexes=failing[:50],
                sample_keys=[_key_of(rows[i], key_column or rule.column) for i in failing[:10]],
            )
        if res.severity == "error":
            error_failing.update(res.failing_indexes)
        results.append(res)

    return DQReport(results=results, failing_indexes=error_failing)


# Factory so rules can be declared in YAML config (metadata-driven, ADR-0005).
_REGISTRY: dict[str, Callable[..., Rule | Unique]] = {
    "not_null": NotNull,
    "unique": Unique,
    "in_range": InRange,
    "non_negative": NonNegative,
    "allowed_values": lambda column, allowed=(), **kw: AllowedValues(
        column=column, allowed=set(allowed), **kw),
    "matches_regex": MatchesRegex,
    "valid_date": ValidDate,
    "foreign_key": lambda column, valid_keys=(), **kw: ForeignKey(
        column=column, valid_keys=set(valid_keys), **kw),
}


def rule_from_dict(spec: Mapping[str, Any]) -> Rule | Unique:
    """Build a rule from a config dict: ``{type, column, severity?, threshold?, ...}``."""
    spec = dict(spec)
    rtype = spec.pop("type")
    if rtype not in _REGISTRY:
        raise ValueError(f"Unknown DQ rule type '{rtype}'. Valid: {sorted(_REGISTRY)}")
    return _REGISTRY[rtype](**spec)
