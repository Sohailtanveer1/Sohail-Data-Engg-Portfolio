"""Pure expression/SQL builders (no SparkSession required — fully unit-testable).

These translate our engine-agnostic contracts into Spark SQL:
- schema `TableSchema` -> per-column CAST plan
- DQ `Rule` objects   -> boolean "passes" SQL predicates
- business keys        -> deterministic surrogate-key / row-hash expressions
- dedup                -> a row_number() window expression

The Spark apply layer (dq_spark.py, scd.py) consumes these strings.
"""

from __future__ import annotations

from scb_common.dq import (
    AllowedValues,
    ForeignKey,
    InRange,
    MatchesRegex,
    NotNull,
    Rule,
    Unique,
    ValidDate,
)
from scb_common.schema import TableSchema

# Our logical dtypes -> Spark SQL types.
SPARK_TYPES: dict[str, str] = {
    "string": "string",
    "int": "int",
    "long": "bigint",
    "double": "double",
    "bool": "boolean",
    "date": "date",
    "timestamp": "timestamp",
}


def col(name: str) -> str:
    """Backtick-quote a column name for Spark SQL."""
    return f"`{name}`"


def cast_plan(schema: TableSchema) -> dict[str, str]:
    """Column -> Spark CAST target type. Bronze is all-string; Silver is typed."""
    return {c.name: SPARK_TYPES[c.dtype] for c in schema.columns}


def cast_select_exprs(schema: TableSchema) -> list[str]:
    """selectExpr list that casts each column to its Silver type (date/timestamp
    parsed leniently; empty strings treated as null first)."""
    out: list[str] = []
    for c in schema.columns:
        spark_t = SPARK_TYPES[c.dtype]
        src = f"NULLIF({col(c.name)}, '')"  # '' -> NULL before casting
        if c.dtype == "date":
            expr = f"to_date({src})"
        elif c.dtype == "timestamp":
            expr = f"to_timestamp({src})"
        else:
            expr = f"CAST({src} AS {spark_t})"
        out.append(f"{expr} AS {col(c.name)}")
    return out


def _lit(v: object) -> str:
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def rule_to_condition(rule: Rule | Unique) -> str | None:
    """Return a Spark SQL boolean expression that is TRUE when a row PASSES.

    Returns None for rules that can't be a single-row predicate (Unique -> window;
    ForeignKey -> anti-join), which the Spark evaluator handles separately.
    """
    if isinstance(rule, Unique):
        return None
    c = col(rule.column)

    if isinstance(rule, NotNull):
        return f"({c} IS NOT NULL AND {c} <> '')"

    if isinstance(rule, InRange):  # includes NonNegative
        parts = [f"{c} IS NULL"]
        checks = []
        num = f"CAST({c} AS DOUBLE)"
        if rule.min_value is not None:
            checks.append(f"{num} >= {rule.min_value}")
        if rule.max_value is not None:
            checks.append(f"{num} <= {rule.max_value}")
        checks.append(f"{num} IS NOT NULL")  # non-numeric text fails
        return f"({' OR '.join(parts)} OR ({' AND '.join(checks)}))"

    if isinstance(rule, AllowedValues):
        vals = ", ".join(_lit(v) for v in sorted(rule.allowed, key=str))
        return f"({c} IS NULL OR {c} IN ({vals}))"

    if isinstance(rule, MatchesRegex):
        return f"({c} IS NULL OR {c} RLIKE {_lit(rule.pattern)})"

    if isinstance(rule, ValidDate):
        return f"({c} IS NULL OR to_date({c}) IS NOT NULL)"

    if isinstance(rule, ForeignKey):
        return None  # referential check -> anti-join in the evaluator

    raise ValueError(f"No Spark condition for rule type {type(rule).__name__}")


def row_hash_expr(columns: list[str]) -> str:
    """Deterministic SHA-256 over the given columns (change detection for SCD2)."""
    parts = ", ".join(f"coalesce(cast({col(x)} as string), '')" for x in columns)
    return f"sha2(concat_ws('||', {parts}), 256)"


def surrogate_key_expr(business_keys: list[str], version_col: str | None = None) -> str:
    """SHA-256 surrogate key over business keys (+ optional version discriminator
    such as effective_from, so SCD2 versions get distinct SKs)."""
    cols = list(business_keys) + ([version_col] if version_col else [])
    parts = ", ".join(f"coalesce(cast({col(x)} as string), '')" for x in cols)
    return f"sha2(concat_ws('||', {parts}), 256)"


def build_create_iceberg_table(table: str, columns: list[tuple[str, str]],
                               partition_by: list[str] | None = None) -> str:
    """CREATE TABLE IF NOT EXISTS ... USING iceberg (pure/testable)."""
    cols = ", ".join(f"{col(n)} {t}" for n, t in columns)
    ddl = f"CREATE TABLE IF NOT EXISTS {table} ({cols}) USING iceberg"
    if partition_by:
        ddl += " PARTITIONED BY (" + ", ".join(col(p) for p in partition_by) + ")"
    return ddl


def dedup_row_number_expr(business_keys: list[str], order_by: str,
                          descending: bool = True) -> str:
    """row_number() window that ranks rows within each business key; keep rank=1
    (latest by ``order_by``) to deduplicate."""
    partition = ", ".join(col(k) for k in business_keys)
    direction = "DESC" if descending else "ASC"
    return f"row_number() OVER (PARTITION BY {partition} ORDER BY {col(order_by)} {direction})"
