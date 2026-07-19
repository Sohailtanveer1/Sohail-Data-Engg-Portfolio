# Risk Assessment

Risks are rated **Likelihood × Impact** and paired with a concrete mitigation.
Cost risks are called out first because they threaten the whole exercise.

---

## 1. Cost / Free-Trial risks

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| C1 | **Cloud Composer left running** drains the $300 credit (~$10–15/day) — we deliberately run a real Composer env (ADR-0003) | **High** | 🔴 High | Created only in Phase 8 (`enable_composer=true`); **`terraform destroy` between multi-day breaks**; $50 budget alert; develop DAGs locally first. [cost doc](cost-optimization.md#3-the-composer-decision-the-big-one) |
| C2 | **Persistent Dataproc cluster** forgotten | Med | 🔴 High | Use Dataproc **Serverless** (auto-terminates) + local Spark; no persistent clusters |
| C3 | **BigQuery runaway scan** on a bad query | Low | Med | `maximum_bytes_billed` cap; partitioned/clustered tables |
| C4 | **Cloud NAT / egress** charges accrue quietly | Low | Low | NAT only present while clusters run; small data |
| C5 | Trial credit expires (90 days) mid-build | Med | Med | Phased plan front-loads local work; teardown between phases; everything re-`apply`-able |

**Primary control:** a $50 **billing budget** with 50/90/100% alerts (Phase 3) +
end-of-session cleanup checklist.

---

## 2. Technical / data risks

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| T1 | **Schema drift** from sources breaks pipelines | High | Med | Schema registry + validation; additive auto-evolve, breaking = fail loud ([ADR-0004](adr/0004-table-format-iceberg.md)) |
| T2 | **Duplicate / reprocessed files** double-count | Med | High | `file_audit` checksum dedup; idempotent MERGE ([ADR-0007](adr/0007-incremental-idempotency.md)) |
| T3 | **Late-arriving data / dimensions** | Med | Med | Inferred dim members + backfill; event-time partitioning |
| T4 | **SCD2 bugs** create overlapping/duplicate current rows | Med | High | Hash-based change detection, single `is_current`, unit tests on merge logic |
| T5 | **Messy Excel / CSV** silently corrupts data | High | Med | DQ framework quarantine + audit; strict parsing, no silent coercion ([ADR-0010](adr/0010-data-quality-framework.md)) |
| T6 | **Spark data skew / OOM** on large joins | Med | Med | Broadcast small dims, AQE, salting, partition tuning (Phase 6 topics) |
| T7 | **Small-file problem** in Bronze/Silver | Med | Low | Compaction / `coalesce` on write; Iceberg `rewrite_data_files` + `expire_snapshots` |
| T8 | **Non-idempotent re-runs** leave partial state | Med | High | Batch-id keyed writes, partition overwrite, checkpointing/restart |

---

## 3. Security / governance risks

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| S1 | **Secrets committed** to git (SFTP pw, SF token, service-account keys) | Med | 🔴 High | `.gitignore` blocks keys/`.env`; Secret Manager; pre-commit secret scan |
| S2 | **Over-privileged service accounts** | Med | Med | One SA per component, least-privilege roles, documented ([ADR-0009](adr/0009-networking.md), IAM module) |
| S3 | **Public buckets / open firewall** | Low | High | Uniform bucket-level access, no `allUsers`; private subnet, deny-by-default firewall |
| S4 | **Data egress to public internet** from workers | Low | Med | Private Google Access + Cloud NAT with restricted egress; no external IPs |

---

## 4. Operational / delivery risks

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| O1 | **Windows/Docker local Spark** friction | High | Low | Pin versions; document setup; fall back to Dataproc Serverless if local Spark misbehaves |
| O2 | **Scope creep** (project is very large) | High | Med | Strict phase gating; stop for review after each phase; MVP-first |
| O3 | **Composer/Airflow version mismatch** local vs cloud | Med | Med | Match Airflow version to a Composer 2 image; keep DAG logic portable |
| O4 | **`terraform destroy` orphans** (buckets with data, etc.) | Med | Med | `force_destroy` on non-prod buckets; cleanup verification step ([ADR-0008](adr/0008-terraform-environments.md)) |
| O5 | Losing the "why" (interview readiness) | Low | Med | ADRs + per-phase interview questions captured as we go |

---

## 5. Top 5 to watch

1. **C1 Composer cost** — the biggest spend by far (we run a real env by choice).
   Controlled by create-in-Phase-8 + destroy-between-breaks + budget alert.
2. **T2/T8 Idempotency** — the difference between a toy and a production pipeline.
3. **S1 Secret leakage** — irreversible; blocked at multiple layers.
4. **T1/T5 Schema & DQ** — where real supply-chain data actually breaks.
5. **O2 Scope** — mitigated by the phase-gate teaching model itself.
