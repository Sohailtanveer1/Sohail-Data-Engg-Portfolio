"""Gold builders: dim_date generation + point-in-time fact assembly (pure).

All functions here are pure (no SparkSession) and unit-tested:
- ``generate_dim_date`` produces the calendar dimension (also runnable/loadable
  directly to BigQuery without Spark).
- ``pit_join_clause`` builds the **point-in-time** join used to resolve SCD2
  surrogate keys ("the material attributes *as of* the order date").
- ``build_fact_select`` assembles the fact SELECT (SK resolution + measures).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from spark.transforms.expressions import col, surrogate_key_expr


def generate_dim_date(start: date, end: date, *, fiscal_start_month: int = 1
                      ) -> list[dict[str, Any]]:
    """Generate one row per calendar day in [start, end] inclusive."""
    rows: list[dict[str, Any]] = []
    d = start
    while d <= end:
        fiscal_year = d.year if d.month >= fiscal_start_month else d.year - 1
        rows.append({
            "date_key": int(d.strftime("%Y%m%d")),
            "date": d.isoformat(),
            "year": d.year,
            "quarter": (d.month - 1) // 3 + 1,
            "month": d.month,
            "day": d.day,
            "day_of_week": d.isoweekday(),          # 1=Mon..7=Sun
            "fiscal_year": fiscal_year,
            "is_weekend": d.isoweekday() >= 6,
        })
        d += timedelta(days=1)
    return rows


@dataclass
class DimJoin:
    name: str            # logical dim name -> produces <name>_sk
    table: str           # Silver dim table (Iceberg)
    business_key: str    # FK column on the fact
    sk_column: str       # surrogate-key column on the dim
    scd: str = "scd1"    # scd1 (current row) | scd2 (point-in-time)
    fact_date: str | None = None  # required for scd2 (the "as of" date)
    dim_key: str | None = None    # dim-side business key (defaults to business_key)


def pit_join_clause(dim: DimJoin, fact_alias: str = "f") -> str:
    """Join condition resolving the correct dim row for a fact.

    SCD2 uses point-in-time (fact_date within [effective_from, effective_to));
    SCD1/current dims join on the business key alone (one row per key).
    """
    d = dim.name
    dk = dim.dim_key or dim.business_key
    base = f"{d}.{col(dk)} = {fact_alias}.{col(dim.business_key)}"
    if dim.scd == "scd2":
        if not dim.fact_date:
            raise ValueError(f"scd2 dim '{dim.name}' needs fact_date for PIT join")
        fd = f"{fact_alias}.{col(dim.fact_date)}"
        return (f"{base} AND {fd} >= {d}.`effective_from` "
                f"AND {fd} < {d}.`effective_to`")
    return base


def build_fact_select(fact_source: str, *, surrogate_name: str,
                      surrogate_keys: list[str], date_column: str,
                      dims: list[DimJoin], measures: list[dict[str, str]],
                      fact_alias: str = "f") -> str:
    """Assemble the Gold fact SELECT: surrogate PK + resolved dim SKs + measures.

    ``measures`` items are ``{"name": ...}`` (passthrough column) or
    ``{"name": ..., "expr": "..."}`` (computed).
    LEFT JOINs so a fact referencing a not-yet-loaded dimension still lands
    (SK null) — late-arriving-dimension safe (ADR-0007).
    """
    select_parts = [f"{surrogate_key_expr(surrogate_keys)} AS {col(surrogate_name)}"]
    for k in surrogate_keys:
        select_parts.append(f"{fact_alias}.{col(k)} AS {col(k)}")
    for dim in dims:
        select_parts.append(f"{dim.name}.{col(dim.sk_column)} AS {col(dim.name + '_sk')}")
    select_parts.append(f"{fact_alias}.{col(date_column)} AS {col(date_column)}")
    for m in measures:
        if "expr" in m:
            select_parts.append(f"({m['expr']}) AS {col(m['name'])}")
        else:
            select_parts.append(f"{fact_alias}.{col(m['name'])} AS {col(m['name'])}")

    joins = []
    for dim in dims:
        joins.append(f"LEFT JOIN {dim.table} {dim.name} ON {pit_join_clause(dim, fact_alias)}")

    select_sql = ",\n       ".join(select_parts)
    join_sql = "\n".join(joins)
    return (f"SELECT {select_sql}\n"
            f"FROM {fact_source} {fact_alias}\n"
            f"{join_sql}").rstrip()
