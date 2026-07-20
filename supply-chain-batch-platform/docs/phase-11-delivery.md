# Phase 11 — Serve, Harden & Hand Off

> The delivery phase: Looker dashboards on the Gold model, disaster recovery,
> the HANDBOOK/RUNBOOK front doors, the operational guides, a final cost review,
> and the cleanup verification. This is what turns a build into a *product*.

---

## 1. Objectives

Make the platform **usable** (dashboards), **operable** (runbook, troubleshooting,
DR), **defensible** (handbook, interview questions, lessons), and **safe to leave**
(cleanup verification, cost review).

## 2. Theory

- A platform isn't done when the data flows — it's done when someone else can run
  it, trust it, fix it, and hand it over. Docs are a deliverable, not an afterthought.
- The **serving layer** is where all the modeling work pays off: clean, conformed
  Gold + purpose-built views make dashboards trivial and correct.

## 3. Business Context

Executives consume four dashboards (inventory health, supplier performance, freight
cost, order fulfillment). Operations consume the audit/monitoring signals. Both are
first-class outputs of the platform.

## 4. Architecture (serving)

```
BigQuery Gold (facts + dims)  →  vw_* analytics views  →  Looker Studio (4 dashboards)
scb_common.monitoring + Cloud Monitoring alerts  →  operations
```

## 5. Folder Creation

[`bigquery/sql/gold/vw_*.sql`](../bigquery/sql/gold), [`looker/dashboards.md`](../looker/dashboards.md),
`HANDBOOK.md`, `RUNBOOK.md`, `CONTRIBUTING.md`, and the `docs/` guides.

## 6. Infrastructure

No new modules — the Gold views are created with `scripts/create_gold_views.sh`
(`bq query`); Looker Studio connects to them. Everything else already exists.

## 7. Implementation

- **4 Gold analytics views** (`vw_inventory_health`, `vw_supplier_performance`,
  `vw_freight_cost`, `vw_order_fulfillment`) — conformed joins, semi-additive-safe.
- **Looker dashboard definitions** (`looker/dashboards.md`) — KPIs, charts, filters.
- **Front doors & guides:** HANDBOOK, RUNBOOK, disaster-recovery, troubleshooting,
  security, lessons-learned, interview-questions, setup/developer guides, CONTRIBUTING.

## 8. Testing / Verification

- Gold view SQL is valid BigQuery SQL (templated `${DATASET}`), applied via
  `scripts/create_gold_views.sh`.
- Full local gate still green (**94 tests**, black/ruff, tf-fmt).
- Doc links resolve; runbook commands mirror what was actually run in phases 2–10.

## 9. Documentation

This *is* the documentation phase — see the file list above.

## 10. Code Review notes

- Views use `SAFE_DIVIDE`/`NULLIF` to avoid divide-by-zero on cost-per-lb / fill-rate.
- SCD2 dims are filtered `is_current` in "current-state" views; time-series views
  keep history.

## 11. Interview Questions

Covered comprehensively in [interview-questions.md](interview-questions.md).
The delivery-specific ones: *How do dashboards stay correct?* (conformed Gold +
semi-additive discipline in the views). *How do you hand this over?* (HANDBOOK +
RUNBOOK + troubleshooting + DR).

## 12. Best Practices applied

Purpose-built serving views (not BI-tool logic); definition-of-record for
dashboards; front-door + runbook + DR docs; honest limitations; verified cleanup.

## 13. Common Mistakes (avoided)

Computing metrics in the BI tool; SUMming semi-additive measures; leaving infra
running; shipping without a runbook/DR; hiding limitations.

## 14. Final cost review

| Phase | Spent (est.) | Notes |
|---|---|---|
| 1–2 | $0 | planning + local |
| 3–4 | <$1 | buckets/network/BigQuery (free tier) |
| 5 | ~$0 local | GCS ops in cloud = pennies |
| 6–7 | pay-per-batch | Dataproc Serverless, cents/batch, auto-terminate |
| 8 | ⚠️ Composer | ~$10–15/day **only while enabled** — destroy between breaks |
| 9–10 | ~$0 | monitoring free tier; GitHub Actions free |
| 11 | ~$0 | views + Looker free |
| **Total (Composer-managed)** | **~$70–150** | dominated entirely by Composer runtime days; **<$15 without it** |

Nothing was left billing during the build (no `apply` on the authoring machine).
Discipline: destroy Composer between sessions; run [RUNBOOK §C](../RUNBOOK.md#c-cleanup--verify-0-run-rate).

## 15. Next Steps (beyond this project)

Run it end-to-end on live GCP (Dataproc Serverless + a Composer session), capture
dashboard screenshots + lineage, expand Silver/Gold to all entities, and add
BigLake + data contracts. See [lessons-learned.md](lessons-learned.md) "v2".

---

## Project complete 🎉

11 phases, ~50→110 files, **94 tests**, 7 Terraform modules across dev/uat/prod,
full medallion + orchestration + observability + CI/CD + serving. Start any
review from [HANDBOOK.md](../HANDBOOK.md).
