# Module: monitoring

Log-based metrics + alert policies built on the platform's structured JSON logs
(the `pipeline_metrics` envelope: `status`, `rows_rejected`, `duration_s`, …).

**Metrics:** `pipeline_success`, `pipeline_failure` (counters), `rows_rejected`
(distribution).
**Alerts:** pipeline failure (`>0`), **data freshness** (no successful run within
`freshness_hours` — the "did last night's batch run?" alert), high rejected-row count.

**Inputs:** `project_id`, `name_prefix`, `notification_email` (optional),
`freshness_hours` (default 26), `rejected_rows_threshold` (default 500).
**Outputs:** `notification_channel_ids`, `alert_policy_names`.

Covered by the Cloud Logging/Monitoring free allotment at our volume (~$0). The
alert filters use `resource.type="global"`; adjust to the Composer/Dataproc
resource types where the logs actually originate in production.
