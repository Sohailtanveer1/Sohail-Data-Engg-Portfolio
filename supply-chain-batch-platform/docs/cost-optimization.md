# Cost Optimization & GCP Free-Trial Plan

> **Read this before provisioning anything.** The GCP Free Trial gives you
> **~$300 in credit for 90 days**. That is plenty for this project *if* we
> respect a few rules — and dangerous if we don't (one forgotten Composer
> environment can burn the entire credit in ~3 weeks).

---

## 1. The seven questions (asked before every new service)

For any GCP service we introduce, we answer:

1. Is it included in / covered by the Free Trial credit?
2. Can it generate *unexpected* cost (always-on, per-hour, egress)?
3. Roughly what would it cost if left running for a month?
4. Should it be always-on, or started only when needed?
5. How do we safely shut it down after development?
6. How do we verify no billable resource remains?
7. What quotas/limits should I know about?

---

## 2. Service-by-service cost posture

| Service | Free-Trial friendly | Cost risk if idle | ~Monthly if left on | Default posture | Local alternative |
|---|---|---|---|---|---|
| **Cloud Storage (GCS)** | ✅ Yes | 🟢 Low | pennies–$1 (small data) | Always-on (tiny) | local folders in dev |
| **BigQuery** | ✅ Yes (10 GB storage + 1 TB query/mo free) | 🟢 Low | ~$0 at our volume | Always-on | DuckDB locally |
| **Dataproc Serverless** | ✅ Yes | 🟢 **None when idle** (per-batch) | $0 idle; ~$0.06–0.20/batch | Per-job, auto-terminates | **local Spark** |
| **Dataproc cluster (persistent)** | ⚠️ Careful | 🔴 High | ~$150–400 (2-node, 24/7) | ❌ **Avoided** — Serverless instead | local Spark |
| **Cloud Composer 2** | 🔴 **Expensive** | 🔴 **Very high** | **~$300–450** if left 24/7 all month | ✅ **Run for real** (ADR-0003), created Phase 8, destroyed between breaks | local Airflow (Docker) for dev |
| **Secret Manager** | ✅ Yes | 🟢 Low | ~$0 (6 free secret versions) | Always-on | `.env` locally (never committed) |
| **VPC / subnet / firewall / PGA** | ✅ Yes | 🟢 Low | $0 (no charge for the network itself) | Always-on | n/a |
| **Cloud NAT** | ⚠️ Small | 🟡 Low-med | ~$1–3 + data | On when clusters run | n/a |
| **Cloud Logging / Monitoring** | ✅ Yes (free allotment) | 🟢 Low | ~$0 at our volume | Always-on | stdout locally |
| **Looker Studio** | ✅ **Free** | 🟢 None | $0 | Always-on | n/a |
| **PostgreSQL (WMS source)** | — | — | $0 | **Docker local** | Cloud SQL (avoided) |
| **Salesforce / SAP / SFTP** | — | — | $0 | **Docker/Python emulators** | n/a |

**Two rules that keep us safe:**
1. **No *accidental* always-on compute.** Dataproc Serverless (auto-terminates) +
   local Spark. No persistent Dataproc cluster. The **one deliberate exception is
   Cloud Composer** (ADR-0003): we run a real environment, but only for Phases
   8–11 and we **`terraform destroy` it between multi-day breaks**.
2. **Prefer local for iteration.** Sources, Postgres, Airflow, and dev-scale Spark
   all run in Docker on your laptop. GCP hosts the services we want to
   *demonstrate for real* (GCS, BigQuery, IAM, networking, Dataproc Serverless,
   and Cloud Composer).

---

## 3. The Composer decision (the big one)

**You chose to run a real Cloud Composer environment** (ADR-0003) rather than a
local-only demo — the most realistic, most interview-credible option. This is the
single largest cost in the project, so it must be **actively managed**.

Cloud Composer has **no free tier** and **no scale-to-zero** — even the smallest
environment runs a GKE cluster + a Cloud SQL instance + a web server 24/7, at
roughly **$10–15/day whether you use it or not**. Left running for the full
90-day trial it would consume the *entire* $300 credit and then some. So we do
**not** leave it running.

**Our approach:**
- **Phases 1–7:** develop everything with **local Airflow in Docker** — DAGs are
  written to be **environment-portable** (no Composer-only APIs in core logic).
- **Phase 8:** stand up the real Composer 2 environment via Terraform
  (`enable_composer = true`), deploy the DAGs to its GCS bucket, and run the full
  daily batch on managed Airflow. Capture evidence (UI, logs, runs).
- **Phases 9–11:** keep Composer only for the sessions that need it.
- **Between multi-day breaks:** `terraform destroy` the Composer module (DAGs
  live in git/GCS and redeploy in minutes), then re-`apply` when you resume.
- The `enable_composer` flag **defaults to false**, so it is never created by
  accident — you turn it on deliberately in Phase 8.

**Budgeting the spend:** at ~$10–15/day, keeping Composer's *live* lifetime to the
handful of days actually spent on Phases 8–11 (target < ~2 weeks total, less if
torn down between sessions) puts realistic Composer cost at **~$50–150** —
comfortably inside the $300 credit, with the $50 budget alert as a backstop.

This is also the honest enterprise story: *"Composer for production scheduling;
local Airflow for development to keep the feedback loop fast and cheap."*

---

## 4. Estimated total project cost (Free-Trial run)

| Phase | Main GCP spend | Estimate |
|---|---|---|
| 1 Planning | none | $0 |
| 2 Local env | none | $0 |
| 3 Terraform foundation | buckets, network (NAT idle) | <$1 |
| 4 BigQuery | free tier | ~$0 |
| 5 Ingestion | GCS ops | ~$1 |
| 6 Silver (Spark) | Dataproc Serverless batches | ~$2–5 |
| 7 Gold | Serverless + BQ loads | ~$1–3 |
| 8 Orchestration | **real Cloud Composer** (created here) | ~$40–80 |
| 9 Monitoring | free allotment + Composer if still up | ~$10–30 |
| 10 CI/CD | GitHub (free) | $0 |
| 11 Looker + cleanup | Composer for final runs, then destroy | ~$10–30 |
| **Total** | | **~$70–170** of the $300 credit (dominated by Composer) |

The non-Composer platform costs **under ~$15**. Composer is the whole budget
story — the total is a direct function of **how many days you leave Composer
running**. Destroy it between sessions and you land near the low end.

---

## 5. Per-phase safe-shutdown & cleanup

Every phase ends with a cleanup checklist in
[PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md). The universal ones:

**After each work session:**
- [ ] No Dataproc **clusters** running: `gcloud dataproc clusters list --region <r>` → empty.
- [ ] No Dataproc **batches** stuck: `gcloud dataproc batches list --region <r>`.
- [ ] Composer only present when actively working Phases 8–11 — otherwise destroyed: `gcloud composer environments list --locations <r>`.
- [ ] Check the **Billing → Reports** page; confirm today's run rate is near $0.

**Full teardown (end of project or a long break):**
```bash
cd infra/terraform/environments/dev
terraform destroy        # removes everything Terraform created
```
Then verify no orphans (Console → Billing, and per-service list commands). The
platform is designed so **`terraform apply` recreates it and `terraform destroy`
removes it with no orphaned resources** ([ADR-0008](adr/0008-terraform-environments.md)).

---

## 6. Budget guardrails (set these up in Phase 3)

- A **Billing Budget** at $50 with email alerts at 50 / 90 / 100%.
- (Optional) A billing-alert → Pub/Sub → Cloud Function that disables billing at
  100% — the ultimate safety net (enterprise pattern; documented, optional for
  portfolio).
- BigQuery **maximum bytes billed** cap on queries to prevent a runaway scan.

---

## 7. Enterprise vs Portfolio, summarized

| Concern | Enterprise | Portfolio (this repo) |
|---|---|---|
| Spark compute | Autoscaling / ephemeral Dataproc clusters | Dataproc Serverless + local Spark |
| Orchestration | Multiple HA Composer envs, always-on | One small Composer 2 env; local Airflow for dev; destroyed between breaks |
| WMS source | Cloud SQL read replica | Postgres in Docker |
| Secrets | Secret Manager + CMEK + rotation | Secret Manager, manual |
| Storage tiering | Multi-region + lifecycle + retention lock | Single region + Nearline lifecycle |
| Cost control | FinOps, reservations, org budgets | $50 budget alert + destroy discipline |
