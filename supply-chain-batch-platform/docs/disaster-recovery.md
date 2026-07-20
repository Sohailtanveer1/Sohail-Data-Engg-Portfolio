# Disaster Recovery

DR for a batch platform is mostly about **recomputability** and **state you can't
regenerate**. Because Bronze is immutable raw history and every stage is
idempotent, most of the platform can be rebuilt by re-running — the precious
things are raw data, Terraform state, and secrets.

---

## 1. What must survive vs what can be rebuilt

| Asset | Strategy | RPO | RTO |
|---|---|---|---|
| **Raw source drops (Bronze/landing)** | GCS **versioning** + lifecycle to Nearline; multi-region in enterprise | last successful land | minutes (re-read) |
| **Terraform remote state** | GCS state bucket **versioned**, `force_destroy=false` | last apply | minutes (restore version) |
| **Secrets** | Secret Manager (versioned); values re-injectable from source-of-truth | n/a | minutes |
| **Silver (Iceberg)** | Rebuildable from Bronze; Iceberg **snapshots** enable time-travel/rollback | rebuild | Serverless batch time |
| **Gold (BigQuery)** | Rebuildable from Silver; BigQuery **time-travel** (7 days) + table snapshots | rebuild | batch time |
| **Metadata/audit tables** | Rebuildable-ish; export to GCS for history | last export | minutes |
| **DAGs / code** | Git (source of truth) | last commit | minutes (redeploy) |

## 2. Recovery playbooks

**A source landed bad data.** Bronze is immutable and partitioned by `ingest_date`
— re-run Silver/Gold for the affected date after fixing the source; idempotent
MERGE/overwrite converges. Quarantined rows are in `data/quarantine` / the
quarantine bucket for inspection.

**A Silver/Gold job corrupted output.** Iceberg: `rollback_to_snapshot` (or
`SELECT ... TIMESTAMP AS OF`). BigQuery: restore via time-travel
(`FOR SYSTEM_TIME AS OF`) or a table snapshot, then re-run the build.

**Terraform state lost/corrupted.** Restore the previous object version from the
versioned state bucket (`gcloud storage cp gs://<state>/... --version=...`). State
bucket is `force_destroy=false` so it can't be accidentally wiped.

**Whole environment gone.** `terraform apply` rebuilds all infra; re-inject
secrets; re-run backfill for the required date range (Bronze from archive if
landing was cleared). This is the routine we already exercise every cleanup cycle
— **DR here is just the normal apply/backfill path**, which is the point.

**Region outage (enterprise).** Multi-region buckets + a second Composer/Dataproc
region; promote and re-point. Portfolio runs single-region (documented trade-off).

## 3. Backfill

Every stage is date-parameterized (`--date` / `{{ ds }}`), so backfilling a range
is a loop over dates; idempotency makes re-processing safe. Bronze is the replay
source of truth.

## 4. Testing DR

- Restore a Terraform state version into a scratch prefix and `plan` (no drift).
- `terraform destroy` + `apply` round-trip in dev (we do this every session).
- Re-run a Silver batch twice and assert identical Gold output (idempotency test).

## 5. Enterprise vs Portfolio

- **Enterprise:** multi-region storage, cross-region compute standby, automated
  state backups, documented RPO/RTO SLOs, periodic game-days.
- **Portfolio:** single-region, versioned state/buckets, rebuild-from-Bronze,
  destroy/apply as the practiced recovery path.
