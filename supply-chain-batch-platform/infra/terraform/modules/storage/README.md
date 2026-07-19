# Module: storage

Creates the medallion + ops GCS buckets (`landing`, `bronze`, `silver`, `gold`,
`archive`, `temp`, `dataproc-staging`, `artifacts`) with uniform bucket-level
access, cost-lifecycle rules, and least-privilege bucket IAM.

**Inputs:** `project_id`, `location`, `bucket_prefix` (globally unique, e.g.
`scb-<projectid>-dev`), `force_destroy`, `labels`, `iam_members`.
**Outputs:** `bucket_names`, `bucket_urls` (maps keyed by logical name).

**Lifecycle:** `landing`/`bronze`/`archive` → Nearline after N days; `temp` and
`dataproc-staging` auto-delete; `silver`/`gold`/`artifacts` versioned. Keeps
Free-Trial storage cost near zero (see [cost doc](../../../docs/cost-optimization.md)).
