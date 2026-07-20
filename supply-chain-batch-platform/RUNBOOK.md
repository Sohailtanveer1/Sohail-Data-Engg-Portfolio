# RUNBOOK — deploy, operate, tear down

Exact commands, in order. Three tracks: **local ($0)**, **GCP dev**, and
**cleanup**. Prereqs for cloud: a GCP Free-Trial project, `gcloud` + `terraform`,
and `gcloud auth application-default login`.

---

## A. Local everything ($0)

```bash
# 1. venv + deps
python -m venv .venv && . .venv/Scripts/activate      # PS: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt && pip install -e common -e data_generators

# 2. quality gate
black --check . && ruff check . && pytest -q          # 94 tests

# 3. generate a day of data + land it to Bronze
python -m data_generators.generate --source all --date 2026-07-19
python -m ingestion.run --source sap_erp        --date 2026-07-19
python -m ingestion.run --source salesforce     --date 2026-07-19
python -m ingestion.run --source tms            --date 2026-07-19
python -m ingestion.run --source supplier_portal --date 2026-07-19

# 4. observability
python -m scb_common.monitoring --audit-dir data/_audit --max-age-hours 26

# 5. dim_date (no Spark)
PYTHONPATH=. python scripts/build_dim_date.py --start 2024-01-01 --end 2027-12-31

# 6. the full local stack (Postgres WMS, mock Salesforce, SFTP)
powershell -File scripts/bootstrap_local.ps1 -Date 2026-07-19   # needs Docker Desktop
python -m ingestion.run --source wms --date 2026-07-19          # JDBC once Postgres is up
```

Spark Silver/Gold locally need a **JDK (Temurin 17)** + a py3.12 venv with
`pyspark` — see [docs/phase-06](docs/phase-06-spark-silver.md#run-it-needs-a-jdk-pyspark-on-python-312).

---

## B. GCP dev

```bash
# 1. bootstrap: state bucket + CI deployer SA (once)
cd infra/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars   # edit project_id, state_bucket_prefix
terraform init && terraform apply              # note: state_bucket, ci_deployer_email

# 2. foundation + BigQuery + monitoring (dev)
cd ../environments/dev
cp backend.hcl.example backend.hcl             # bucket = <state_bucket from step 1>
# edit dev.tfvars: project_id, billing_account, notification_email
terraform init -backend-config=backend.hcl
terraform apply -var-file=dev.tfvars           # Composer stays OFF (enable_composer=false)

# 3. secrets (out-of-band, never in Terraform)
printf '%s' "$SF_TOKEN" | gcloud secrets versions add scb-dev-salesforce-token --data-file=-
#   ...repeat for scb-dev-sap-sftp-password, scb-dev-wms-db-password

# 4. Gold views for Looker
bash scripts/create_gold_views.sh <project_id> scb_gold_dev

# 5. Spark on Dataproc Serverless (Silver, then Gold) — see phase-06/07 runbooks
# 6. (optional) real Composer for a session — see phase-08 runbook, then DESTROY it
```

Verify:
```bash
terraform output
gcloud storage buckets list --project <project_id>
bq ls <project_id>:scb_gold_dev
```

---

## C. Cleanup — verify $0 run-rate

Run at the end of every session; the platform is designed to fully round-trip.

```bash
# local
docker compose -f local/docker-compose.yml down -v
docker compose -f airflow/docker-compose.airflow.yml down -v
rm -rf data/                                   # generated data (git-ignored)

# GCP — destroy the dev stack
cd infra/terraform/environments/dev
terraform destroy -var-file=dev.tfvars         # includes Composer if it was enabled
# (optional) bootstrap teardown:
cd ../../bootstrap && terraform destroy
```

**Verification checklist (must all be empty/zero):**
```bash
gcloud composer environments list --locations us-central1     # → empty
gcloud dataproc batches list --region us-central1             # → no RUNNING
gcloud dataproc clusters list --region us-central1            # → empty (we never create any)
gcloud storage buckets list --project <project_id>            # → only intended/none
```
Then open **Billing → Reports** and confirm today's run-rate is ~$0. The **$50
budget alert** is the backstop. Full DR/cleanup detail:
[docs/disaster-recovery.md](docs/disaster-recovery.md).
