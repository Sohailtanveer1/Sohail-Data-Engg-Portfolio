"""Spark data-quality gate: apply the same ``Rule`` objects to a Spark DataFrame.

Reuses the engine-agnostic rules from ``scb_common.dq`` (Phase 2) via the pure
``rule_to_condition`` translator. Error-severity failures are quarantined; the
batch fails if any error rule breaches its threshold. Returns (clean, quarantine,
results) so the job can persist quarantine + write ``dq_results``.

Requires a SparkSession (compile-checked here; executed on a JDK/Dataproc).
"""

from __future__ import annotations

from scb_common.dq import ForeignKey, RuleResult, Unique
from spark.transforms.expressions import rule_to_condition

_PASS_PREFIX = "_dq_pass_"


def _pass_col(i: int) -> str:
    return f"{_PASS_PREFIX}{i}"


def evaluate_spark(df, rules, *, key_column=None, fk_sets=None):
    """Evaluate rules on ``df``. Returns (clean_df, quarantine_df, results).

    ``fk_sets``: optional {column: [valid keys]} for ForeignKey rules.
    """
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    fk_sets = fk_sets or {}
    pass_cols: list[tuple[int, object, bool]] = []  # (idx, rule, is_error)

    for i, rule in enumerate(rules):
        pcol = _pass_col(i)
        if isinstance(rule, Unique):
            w = Window.partitionBy(rule.column)
            df = df.withColumn(pcol, F.count(F.lit(1)).over(w) == 1)
        elif isinstance(rule, ForeignKey):
            valid = fk_sets.get(rule.column, [])
            df = df.withColumn(
                pcol, F.col(rule.column).isNull() | F.col(rule.column).isin(list(valid))
            )
        else:
            cond = rule_to_condition(rule)
            df = df.withColumn(pcol, F.expr(cond))
        pass_cols.append((i, rule, rule.severity == "error"))

    # Combined gate over error-severity rules only.
    error_cols = [F.col(_pass_col(i)) for i, _, is_err in pass_cols if is_err]
    gate = error_cols[0]
    for c in error_cols[1:]:
        gate = gate & c
    df = df.withColumn("_dq_ok", gate if error_cols else F.lit(True))

    total = df.count()
    results: list[RuleResult] = []
    for i, rule, _ in pass_cols:
        failed = df.filter(~F.col(_pass_col(i))).count()
        results.append(
            RuleResult(
                rule=rule.name,
                column=rule.column,
                severity=rule.severity,
                passed=total - failed,
                failed=failed,
                threshold=rule.threshold,
            )
        )

    drop_cols = [_pass_col(i) for i, _, _ in pass_cols]
    clean = df.filter(F.col("_dq_ok")).drop("_dq_ok", *drop_cols)
    quarantine = df.filter(~F.col("_dq_ok")).drop("_dq_ok", *drop_cols)
    return clean, quarantine, results
