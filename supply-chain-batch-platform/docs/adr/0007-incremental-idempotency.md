# ADR-0007 — Incremental loading & idempotency

**Status:** Proposed · **Date:** 2026-07-19

## Context
Daily/4-hourly batches must not reprocess everything, must be safe to re-run
after a failure, and must not double-count when a file/API page is delivered
twice. Incremental extraction and idempotent writes are the two halves of this.

## Options (incremental)
- **Full reload every run** — simple, correct, but wasteful and slow at scale.
- **Watermark incremental** ✅ — track the last processed `updated_ts`/id/partition
  per entity in a `watermark` table; extract only newer records.
- **CDC / log-based** — most efficient, but sources here don't all expose logs.

## Options (idempotency)
- **Blind append** — re-runs duplicate data. ❌
- **Partition overwrite** ✅ — for snapshot/partitioned data, overwrite the
  batch's partitions (deterministic).
- **MERGE on business key** ✅ — for dimensions/upserts, `MERGE` so re-runs
  converge to the same state.

## Decision
**Watermark-based incremental** + **idempotent writes** (Iceberg `MERGE INTO` for
dims/upserts; **dynamic partition overwrite** for partitioned facts/Bronze).
Every run is keyed by `batch_id`; the `file_audit`/`watermark` tables guard
against reprocessing. Late-arriving facts referencing an unknown dimension insert
an **inferred member** (backfilled later). Failures are restartable from the last
committed watermark; long jobs checkpoint.

## Consequences
- ➕ Re-running any batch is safe and produces identical results (idempotent).
- ➕ Efficient — only new/changed data moves.
- ➕ Late/duplicate/out-of-order data handled explicitly, not by luck.
- ➖ Watermark + audit state must itself be managed transactionally.
- ➖ Choosing the right watermark column per source needs care (clock skew, deletes).

## Enterprise vs Portfolio
- **Enterprise:** CDC (Datastream/log-based) where available; exactly-once
  semantics with reconciliation jobs.
- **Portfolio:** watermark + MERGE/overwrite + audit tables — the widely-used,
  interview-standard pattern.
