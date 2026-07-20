"""Reusable PySpark transforms for Bronze -> Silver.

Design: the *logic* (rule -> SQL predicate, cast plans, SCD MERGE statements,
surrogate/hash expressions) lives in pure builder functions (``expressions.py``,
``scd.py``) that return strings/dicts and are unit-tested **without a
SparkSession**. The Spark-facing apply functions (``dq_spark.py``, the appliers
here) consume those builders. Same DQ ``Rule`` objects as Phase 2 — one contract,
two engines (ADR-0004, ADR-0005, ADR-0010).
"""
