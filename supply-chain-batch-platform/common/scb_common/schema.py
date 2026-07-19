"""Declarative schema contracts + validation & evolution primitives.

A ``TableSchema`` is engine-agnostic: it describes the expected columns and
logical types of an entity. Phase 2 evaluates it over plain ``list[dict]`` rows
(fast, dependency-free, unit-testable). Phase 6 reuses the *same* specs with a
Spark evaluator — the contract is defined once (see ADR-0004, ADR-0005).

Evolution policy:
- **additive** (new nullable columns appear)  -> allowed, logged
- **breaking** (missing required col / type change) -> raise SchemaValidationError
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from scb_common.errors import SchemaValidationError

# Logical type -> acceptable python types for row-level checks.
_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "int": (int,),
    "long": (int,),
    "double": (float, int),
    "bool": (bool,),
    "date": (date, str),
    "timestamp": (datetime, str),
}


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str = "string"
    nullable: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if self.dtype not in _TYPES:
            raise ValueError(f"Unknown dtype '{self.dtype}' for column '{self.name}'. "
                             f"Valid: {sorted(_TYPES)}")


@dataclass
class TableSchema:
    entity: str
    columns: list[ColumnSpec]
    version: int = 1
    business_keys: list[str] = field(default_factory=list)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def required_names(self) -> list[str]:
        return [c.name for c in self.columns if not c.nullable]

    @classmethod
    def from_dict(cls, entity: str, spec: Mapping[str, Any]) -> TableSchema:
        """Build from config: ``{version, business_keys, columns: [{name,dtype,nullable}]}``."""
        cols = [
            ColumnSpec(
                name=c["name"],
                dtype=c.get("dtype", "string"),
                nullable=c.get("nullable", True),
                description=c.get("description", ""),
            )
            for c in spec.get("columns", [])
        ]
        return cls(
            entity=entity,
            columns=cols,
            version=int(spec.get("version", 1)),
            business_keys=list(spec.get("business_keys", [])),
        )

    def diff(self, observed_columns: Iterable[str]) -> tuple[list[str], list[str]]:
        """Return (missing_expected, unexpected_new) columns vs the observed set."""
        observed = set(observed_columns)
        expected = set(self.column_names)
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        return missing, unexpected

    def validate_rows(self, rows: list[Mapping[str, Any]], *,
                      allow_additive: bool = True, sample: int = 1000) -> list[str]:
        """Validate a sample of rows against the contract.

        Returns the list of *newly observed* columns (additive evolution) when
        allowed. Raises SchemaValidationError on breaking changes:
        missing required columns, unexpected columns (if additive disallowed),
        or non-nullable-null / wrong-type values.
        """
        if not rows:
            return []

        observed_cols: set[str] = set()
        for r in rows[:sample]:
            observed_cols.update(r.keys())

        missing, unexpected = self.diff(observed_cols)
        required_missing = [c for c in missing if c in self.required_names()]
        if required_missing:
            raise SchemaValidationError(
                f"{self.entity}: missing required columns {required_missing}",
                missing=required_missing,
            )
        if unexpected and not allow_additive:
            raise SchemaValidationError(
                f"{self.entity}: unexpected columns {unexpected}", unexpected=unexpected
            )

        type_errors: list[str] = []
        by_name = {c.name: c for c in self.columns}
        for i, r in enumerate(rows[:sample]):
            for name, spec in by_name.items():
                if name not in r:
                    continue
                val = r[name]
                if val is None:
                    if not spec.nullable:
                        type_errors.append(f"row {i}: '{name}' is null but not nullable")
                    continue
                if not isinstance(val, _TYPES[spec.dtype]) or (
                    spec.dtype != "bool" and isinstance(val, bool)
                ):
                    type_errors.append(
                        f"row {i}: '{name}'={val!r} not compatible with dtype '{spec.dtype}'"
                    )
        if type_errors:
            raise SchemaValidationError(
                f"{self.entity}: {len(type_errors)} type/nullability violations",
                type_errors=type_errors[:20],
            )
        return unexpected  # additive columns actually seen
