# Phase 9 — Data Quality, Monitoring & Logging

> The 15-step walkthrough for making the platform **trustworthy and observable**:
> a hardened DQ framework, structured logs → Cloud Logging metrics, alert policies
> (failure, freshness, high rejection), and a freshness monitor over the audit trail.

---

## 1. Objectives

Turn "it ran" into "I can prove it ran correctly, and I'm alerted when it didn't":
harden DQ (corrupted files), ship structured logs to Cloud Logging as metrics, and
alert on **pipeline failure**, **data freshness**, and **high rejection**.

## 2. Theory

- **Structured logs are the metric source.** Our JSON `pipeline_metrics` line
  (`status`, `rows_rejected`, `duration_s`) becomes `jsonPayload` in Cloud Logging
  automatically on GCP — log-based metrics extract from it, no extra plumbing.
- **Freshness = absence of success.** The most important batch alert isn't "a task
  failed" — it's "no successful run happened in the expected window" (a silent
  scheduler death). Modeled as a metric-absence alert + an audit-trail monitor.
- **Fail soft on bad data, fail loud on bad rules.** A corrupted *file* is
  quarantined and the batch continues; a breached *quality threshold* fails the batch.

## 3. Business Context

An executive dashboard that's silently a day stale is worse than one that's down —
people make decisions on it. Freshness + failure + rejection alerts are what let a
team trust the numbers and catch problems before the business does.

## 4. Architecture

```
jobs ──► JSON stdout (pipeline_metrics: status, rows_read/written/rejected, duration)
              │  (Cloud Logging parses to jsonPayload automatically)
              ▼
   log-based metrics:  pipeline_success · pipeline_failure · rows_rejected
              ▼
   alert policies:  failure(>0) · freshness(no success in N h) · high_rejection
              ▼
   notification channel (email)     +     scb_common.monitoring freshness report (audit trail)
```

## 5. Folder Creation

`infra/terraform/modules/monitoring/`,
[`common/scb_common/monitoring.py`](../common/scb_common/monitoring.py), plus the
Cloud Logging helper in `scb_common/logging.py`.

## 6. Infrastructure

The **`monitoring` Terraform module**: 3 log-based metrics, 3 alert policies, and
an optional email notification channel. Wired into all env roots (free-tier
friendly, so on by default). `resource.type="global"` in the filters (adjust to
Composer/Dataproc resources in production).

## 7. Implementation

- **DQ hardening:** the extractor now **quarantines a corrupted/unreadable file**
  (`file_audit` status `failed`) and continues — one bad drop can't fail the source.
- **Cloud Logging:** `enable_cloud_logging()` attaches a StructuredLogHandler
  (lazy `google-cloud-logging`); on managed runtimes JSON stdout is enough.
- **Freshness monitor:** `scb_common.monitoring` reads `batch_audit`, finds the
  latest success per pipeline, and flags stale ones (failed-only or too-old ⇒ stale).

## 8. Testing / Verification

- **94 tests passing** (+7: freshness logic incl. failed-only/missing/old, JSONL
  read, handler attach; +1 corrupted-file quarantine).
- **Live:** `python -m scb_common.monitoring --audit-dir data/_audit` on the real
  Phase-5 audit → 4 pipelines `ok` (0.74h old, exit 0); forcing the window → all
  `STALE` (exit 1). Corrupted-file test: a bad JSON is quarantined, batch succeeds.
- **`terraform validate` Success** on dev/uat/prod with the monitoring module; `fmt` clean.

## 9. Documentation

This doc + `monitoring` module README + `common` README + PROJECT_PROGRESS.

## 10. Code Review notes

- Freshness treats a **failed-only** pipeline as stale (we've seen it, it hasn't
  succeeded) and an **expected-but-missing** pipeline as stale — both are real
  "did last night run?" failure modes.
- `rows_rejected` is a **distribution** metric (exponential buckets) so we can
  alert on max and chart percentiles.
- The corrupted-file catch is deliberately broad (`Exception`) but audited and
  per-file — it never hides a bug silently (it's logged + `file_audit=failed`).

## 11. Data-quality validation coverage (the requested checklist)

| Requirement | Mechanism |
|---|---|
| Missing columns | `TableSchema.validate_rows` (required-column check) |
| Duplicate records | `Unique` rule + Silver dedup window |
| Invalid dates | `ValidDate` rule / `to_date` cast |
| Negative quantities | `NonNegative` rule |
| Invalid SKUs | `MatchesRegex` rule |
| Null business keys | `NotNull` rule |
| Invalid currency | `AllowedValues` rule |
| Missing warehouse | `ForeignKey` rule (vs `dim_warehouse`) |
| Invalid supplier | `ForeignKey` rule (vs `dim_vendor/supplier`) |
| Corrupted files | extractor quarantine + `file_audit=failed` (this phase) |

## 12. Best Practices applied

Logs-as-metrics (no bespoke metric code); freshness-as-absence alerting; fail-soft
on data / fail-loud on rules; audit-trail-driven monitoring; free-tier observability.

## 13. Common Mistakes (avoided)

Alerting only on task failure (misses silent staleness); one bad file failing the
whole source; unstructured logs (unqueryable); no notification channel; treating
rejected-rows as pass/fail instead of a trend.

## 14. Cost Considerations

**~$0** — Cloud Logging/Monitoring free allotment covers our volume; metrics and
alert policies are free. The freshness monitor is local Python.

## 15. Next Steps

**Phase 10 — CI/CD & testing:** GitHub Actions running format/lint/type/tests,
`terraform fmt/validate/plan`, DAG validation, and a deploy path — turning the 94
tests + validations into an automated gate.

---

## Run it

```bash
# freshness over the local audit trail
python -m scb_common.monitoring --audit-dir data/_audit --max-age-hours 26

# apply monitoring (with alert email) — part of the dev stack
terraform apply -var-file=dev.tfvars -var="notification_email=you@example.com"
terraform output alert_policies
```
