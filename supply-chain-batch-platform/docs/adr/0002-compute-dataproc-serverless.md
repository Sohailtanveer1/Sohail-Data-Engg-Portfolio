# ADR-0002 — Spark compute: Dataproc Serverless + local Spark

**Status:** Proposed · **Date:** 2026-07-19

## Context
We need Spark compute for Bronze→Silver→Gold. The dominant constraint is the
Free Trial: a persistent Dataproc cluster left running is one of the top ways to
burn the credit. We also want a fast local dev loop.

## Options
1. **Persistent Dataproc cluster.** Familiar, interactive, autoscaling. But
   always-on cost (~$150–400/mo for a modest 24/7 cluster) — dangerous on trial.
2. **Ephemeral job-scoped clusters** (create → run → delete via workflow
   templates). No idle cost, but ~90s spin-up per job and more moving parts.
3. **Dataproc Serverless (Spark batches).** ✅ No cluster to manage, **zero idle
   cost**, pay per batch, auto-terminates. Slightly less tunable than a cluster.
4. **Local Spark only.** Free, fastest loop, but doesn't demonstrate GCP Spark.

## Decision
**Dataproc Serverless** for cloud runs + **local Spark (Docker)** for
development. No persistent cluster.

## Consequences
- ➕ Nothing left billing when idle — the single biggest cost risk removed.
- ➕ Local Spark = instant, free iteration; Serverless proves it at cloud scale.
- ➕ Same PySpark code runs both places (write once, run anywhere).
- ➖ Serverless is less interactive (no long-lived UI); tuning is via batch props.
- ➖ Cold-start seconds per batch (irrelevant for daily batch).

## Enterprise vs Portfolio
- **Enterprise:** autoscaling persistent clusters for interactive/heavy workloads,
  or ephemeral clusters per job with reservations for cost control.
- **Portfolio:** Serverless + local. We *document* how the cluster/ephemeral
  approaches would differ and when to prefer them.
