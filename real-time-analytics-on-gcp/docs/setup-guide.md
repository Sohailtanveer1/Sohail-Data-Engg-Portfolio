# Setup Guide

This is the reference overview — prerequisites, the order things must
happen in, and where each step's actual instructions live. It's the map,
not the turn-by-turn directions. (A fuller step-by-step execution runbook,
including exact commands to type in order, is a natural companion
document if you want one written up separately.)

## Prerequisites

| Tool | Needed for | Notes |
|---|---|---|
| Docker Desktop | Local Kafka cluster | Not installed as of this writing on this machine — install before Phase 2 |
| Python 3.12 | Producer, consumer, bridge, common lib | Also works on 3.11 |
| Python 3.11 or 3.12 (separate venv) | Dataflow/Beam pipeline and its tests | `apache-beam` doesn't support every Python version immediately — see `docs/testing-guide.md` |
| Terraform >= 1.7.0 | All infrastructure | Not installed as of this writing — install before Phase 5 |
| `gcloud` CLI | Deploying the pipeline, bootstrap | |
| A GCP project with billing/free-trial credit enabled | Everything past Phase 1 | |
| GitHub repo (this one, pushed to your own remote) | CI/CD | Needed before wiring Workload Identity Federation |

## Order of operations

1. **Local Kafka.** `cd kafka/docker && docker compose up -d && ./create-topics.sh && ./smoke-test.sh`
   — see [kafka/docker/README.md](../kafka/docker/README.md).
2. **Producer + consumer smoke test**, entirely local, no GCP needed yet:
   ```bash
   cd kafka/producer && pip install -r requirements.txt && python producer.py --domains all --rate 5 --duration 30
   cd kafka/consumer && pip install -r requirements.txt && python consumer.py --domains all
   ```
3. **GCP bootstrap** (once per GCP project, creates the Terraform state
   bucket): `cd infra/terraform/bootstrap && terraform init && terraform apply -var="project_id=YOUR_PROJECT"`.
4. **Dev environment infra:**
   ```bash
   cd infra/terraform/environments/dev
   cp terraform.tfvars.example terraform.tfvars   # fill in real values — this file is gitignored
   terraform init && terraform plan && terraform apply
   ```
5. **Kafka → Pub/Sub bridge:**
   `cd bridge && pip install -r requirements.txt && python kafka_to_pubsub_bridge.py --gcp-project YOUR_PROJECT`
   (uses Application Default Credentials — `gcloud auth application-default login` first).
6. **Set the real carrier API secret value** (Terraform only creates a
   placeholder — see `docs/security-guide.md#secret-manager`):
   `echo -n "your-key" | gcloud secrets versions add carrier-tracking-api-key-dev --data-file=-`
7. **Deploy the streaming pipeline:**
   `PROJECT_ID=YOUR_PROJECT REGION=us-central1 bash scripts/deploy_dataflow_pipeline.sh dev`
8. **Verify data is flowing:** `bq query` against `supplychain_bronze.orders`,
   confirm the scheduled Silver MERGE ran (`supplychain_silver.orders`),
   query a Gold view.
9. **Build the Looker Studio dashboards** by hand against the Gold views —
   see [looker/dashboard-spec.md](../looker/dashboard-spec.md) for the
   exact spec.
10. **Wire up CI/CD:** create the Workload Identity Federation provider +
    deployer SA (already provisioned by step 4's Terraform), then set the
    corresponding GitHub repo/environment variables
    (`WIF_PROVIDER_DEV`, `CICD_DEPLOYER_SA_DEV`, `GCP_PROJECT_ID_DEV`,
    `GCP_REGION`) referenced in `.github/workflows/cd-dev.yml`.
11. **uat/prod:** repeat steps 3-9 against separate GCP projects, using
    `infra/terraform/environments/uat` and `.../prod`, then promote via
    `.github/workflows/cd-promote.yml` (`workflow_dispatch`).

## Verifying each phase before moving to the next

Don't chain all 11 steps blind — confirm each one before moving on, since
a broken step 4 (bad IAM grant, wrong project ID) produces confusing
errors three steps later otherwise:

- After step 1: `docker compose ps` shows 4 healthy containers, `./smoke-test.sh` prints "OK."
- After step 4: `terraform output` shows all the expected resource names — cross-check against `infra/terraform/environments/dev/outputs.tf`.
- After step 7: `gcloud dataflow jobs list --region=us-central1` shows `supplychain-streaming-dev` in `Running` state, not `Failed`.
- After step 8: row counts in Bronze/Silver/Gold are non-zero and growing while the producer runs.

If any step fails, [docs/troubleshooting-guide.md](troubleshooting-guide.md)
covers the failure modes actually encountered building this repo.
