# ADR-0010 — Data quality framework

**Status:** Proposed · **Date:** 2026-07-19

## Context
Supply-chain source data is messy (Excel quirks, SAP encodings, negative
quantities, invalid SKUs, null business keys, bad currencies). We need
consistent, reusable validation with clear pass/quarantine/fail semantics and an
audit trail — not ad-hoc `if` checks scattered across pipelines.

## Options
1. **Inline ad-hoc checks per pipeline.** Fast to write, impossible to govern,
   inconsistent, untestable.
2. **Adopt Great Expectations / Soda.** Powerful, but heavier dependency and
   another system to learn/operate; can be overkill for a portfolio.
3. **Lightweight declarative in-house framework.** ✅ Rules declared in config,
   evaluated in Spark, results written to `dq_results`, failures quarantined —
   transparent and fully owned (great to explain in interviews).

## Decision
**Option 3.** A reusable framework where each entity declares rules in its config:
- **Schema/structure:** missing columns, type mismatch, corrupted files.
- **Completeness:** null business keys, missing warehouse/supplier.
- **Validity:** negative quantities, invalid dates, invalid currency, invalid SKU
  pattern.
- **Uniqueness:** duplicate records on business key.
- **Referential:** supplier/material/warehouse exists in its dimension.
- **Freshness:** data arrived within the expected window.

Each rule has a **severity**: `error` (quarantine row + fail batch if threshold
breached) or `warn` (log + continue). Failing rows go to a **quarantine** path;
results (rule, counts, sample keys) land in `dq_results` keyed by `batch_id`.

## Consequences
- ➕ Consistent, testable, governed quality across all entities.
- ➕ Bad data is quarantined and auditable, not silently dropped or propagated.
- ➕ Config-driven → integrates with the metadata framework ([ADR-0005](0005-metadata-driven-framework.md)).
- ➖ In-house framework is ours to maintain (mitigated: small, well-tested).
- ➖ Threshold tuning needed to avoid false-fail noise.

## Enterprise vs Portfolio
- **Enterprise:** Great Expectations/Soda + Dataplex data profiling, SLAs on
  quality, data contracts with upstream owners.
- **Portfolio:** lightweight in-house framework — demonstrates the concepts and
  the *why* without extra infrastructure. GE/Soda noted as the scale-up path.
