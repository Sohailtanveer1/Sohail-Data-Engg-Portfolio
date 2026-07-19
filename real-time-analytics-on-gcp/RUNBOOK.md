# Runbook: Standing This Up on Your GCP Free Trial

This is the document to actually *perform* the deployment yourself, start
to finish, on your own machine and your own GCP free trial project. Every
other doc in this repo (`docs/setup-guide.md`, `docs/architecture/`, etc.)
explains *why* things are built the way they are; this one is *do this,
then this, then this*, with exact commands and exactly what success looks
like at each step, so you never have to guess whether a step worked before
moving to the next.

Follow it in order. Do not skip the verification line after each step —
Terraform/GCP failures three steps downstream of a silent misconfiguration
are the most time-consuming kind to debug.

**Time estimate:** 2-4 hours for a first full pass through Steps 1-11 (GCP
account setup and Terraform learning curve dominate; the commands
themselves run in minutes). Steps 12-14 (CI/CD, promotion, teardown) are
each their own separate session.

**Cost estimate:** this is designed to run comfortably inside a $300 GCP
free trial. The single biggest cost risk is **leaving the Dataflow
streaming job running continuously** — it bills by the hour whether or not
you're actively using it. Step 14 covers stopping it between sessions.
Read `docs/cost-optimization.md` before your first deploy, not after your
first bill surprise.

---

## Step 0 — What you need before starting

- A Google account you're willing to attach a GCP free trial to.
- Windows 11 with **Git Bash** (comes with Git for Windows — you already
  have this if `git` works in a terminal). All commands below are bash;
  run them in Git Bash, not PowerShell or cmd.exe.
- Admin rights on this machine (to install Docker Desktop).

---

## Step 1 — Install prerequisites

```bash
winget install Docker.DockerDesktop
winget install HashiCorp.Terraform
winget install Google.CloudSDK
```

After installing, **restart your terminal** (PATH changes need a fresh
shell), then verify:

```bash
docker --version && docker compose version
terraform version
gcloud version
python --version   # need 3.11 or 3.12 for anything under dataflow/ — see docs/testing-guide.md
```

If `python --version` shows something other than 3.11/3.12 and you plan to
run the Beam tests or work on the pipeline code, install Python 3.12
separately (`winget install Python.Python.3.12`) and create a dedicated
virtualenv for `dataflow/` work — do not fight this by trying to force a
newer Python to work with `apache-beam`; it won't.

**✅ Success looks like:** all four commands print a version number with
no errors.

---

## Step 2 — Create and configure your GCP project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and
   activate your free trial if you haven't already.
2. Create a new project dedicated to this — do not reuse an existing
   project with other work in it:
   ```bash
   gcloud projects create YOUR_PROJECT_ID --name="Supply Chain Platform Dev"
   gcloud config set project YOUR_PROJECT_ID
   ```
   Replace `YOUR_PROJECT_ID` with something globally unique (GCP project
   IDs are global) — e.g. `supplychain-dev-yourname-2026`.
3. Link billing (required even on the free trial — the console will
   prompt you, or):
   ```bash
   gcloud billing projects link YOUR_PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID
   ```
   Find your billing account ID with `gcloud billing accounts list`.
4. Authenticate for local development:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

**✅ Success looks like:** `gcloud config get-value project` prints your
new project ID, and the console shows billing as linked (not "no billing
account").

---

## Step 3 — Stand up local Kafka

```bash
cd kafka/docker
docker compose up -d
docker compose ps
```

**✅ Success looks like:** 4 containers (`kafka-1`, `kafka-2`, `kafka-3`,
`kafka-ui`), all `Up`/`healthy`. If any container is restarting or
unhealthy, check `docker compose logs <container>` before continuing —
don't proceed to topic creation against a broken cluster.

```bash
./create-topics.sh
```

**✅ Success looks like:** the final `--list` output shows 10 topics (5
domains + 5 `.dlq`).

```bash
./smoke-test.sh
```

**✅ Success looks like:** it prints the produced message back and ends
with `OK: cluster is reachable and the topic round-trips messages.`

Optional: open http://localhost:8080 to browse the cluster visually in
Kafka UI.

---

## Step 4 — Smoke-test the producer and consumer locally

Two terminals, both in Git Bash, from the repo root.

**Terminal A — consumer:**
```bash
cd kafka/consumer
pip install -r requirements.txt
python consumer.py --domains all
```

**Terminal B — producer:**
```bash
cd kafka/producer
pip install -r requirements.txt
python producer.py --domains all --rate 5 --duration 60
```

**✅ Success looks like:** Terminal A logs `valid event: ...` lines as
Terminal B sends. Occasionally (by design — see
`kafka/producer/event_generator.py`) you'll see a `routed to DLQ` warning
in Terminal A — that's the chaos injection working as intended, not a bug.

Stop both with Ctrl+C when satisfied. You've now proven the entire local
half of the platform works before spending any GCP quota.

---

## Step 5 — Bootstrap Terraform remote state

Once per GCP project:

```bash
cd ../../infra/terraform/bootstrap
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

Type `yes` when prompted. This enables the required APIs and creates the
`YOUR_PROJECT_ID-tfstate` GCS bucket.

**✅ Success looks like:** `Apply complete!` with the `state_bucket_name`
output showing your bucket name. Verify: `gsutil ls gs://YOUR_PROJECT_ID-tfstate/`
(should exist and be empty — that's correct, nothing's been written yet).

---

## Step 6 — Deploy the dev environment infrastructure

```bash
cd ../environments/dev
```

Edit `backend.tf` — replace `YOUR_PROJECT_ID` with your real project ID
(Terraform can't interpolate variables into a backend block, so this one
file needs a literal edit, not a tfvars value):
```hcl
backend "gcs" {
  bucket = "YOUR_PROJECT_ID-tfstate"   # <- edit this line
  prefix = "environments/dev"
}
```

Copy and fill in your tfvars:
```bash
cp terraform.tfvars.example terraform.tfvars
```
Edit `terraform.tfvars`:
```hcl
project_id         = "YOUR_PROJECT_ID"
region             = "us-central1"
bq_location        = "US"
subnet_cidr        = "10.10.0.0/20"
github_repository  = "your-github-username/data-engineering-portfolio"
alert_email        = "your-real-email@example.com"
looker_studio_viewers = [
  "user:your-real-email@example.com",
]
```

```bash
terraform init
terraform plan
```

**Read the plan output before applying.** You should see it planning to
CREATE roughly 60-80 resources (VPC, subnets, firewall rules, service
accounts, Pub/Sub topics/subscriptions, BigQuery datasets/tables/views,
monitoring alert policies, etc.) and nothing planning to destroy anything
(there's nothing to destroy on a first apply).

```bash
terraform apply
```

Type `yes`. **This step takes several minutes** — BigQuery scheduled
queries and the Workload Identity Federation pool are the slowest
individual resources.

**✅ Success looks like:** `Apply complete! Resources: XX added, 0
changed, 0 destroyed.` with no errors. Save the outputs — you'll need
several of them shortly:
```bash
terraform output
```

**If it fails partway through:** re-running `terraform apply` is safe —
Terraform is idempotent and will pick up where it left off. If it fails on
the `dts_impersonates_bq_transform` resource specifically, see
`docs/troubleshooting-guide.md` — that's a known easy-to-hit ordering
issue with the BigQuery Data Transfer API needing a moment to fully enable
after `bootstrap` runs.

---

## Step 7 — Set the real carrier API secret value

Terraform deliberately only creates a placeholder (see
`docs/security-guide.md#secret-manager`). If you don't have a real carrier
tracking API, any non-empty string works for this demo — the enrichment
transform degrades gracefully if the API call fails, it does not block the
pipeline:

```bash
echo -n "demo-placeholder-key" | gcloud secrets versions add carrier-tracking-api-key-dev \
  --data-file=- --project=YOUR_PROJECT_ID
```

**✅ Success looks like:** `Created version [2] of the secret ...`.

---

## Step 8 — Start the Kafka → Pub/Sub bridge

```bash
cd ../../../bridge
pip install -r requirements.txt
python kafka_to_pubsub_bridge.py --gcp-project YOUR_PROJECT_ID
```

Leave this running in its own terminal. It uses the Application Default
Credentials from Step 2.4.

**✅ Success looks like:** it logs `bridging [...] -> Pub/Sub
project=YOUR_PROJECT_ID` and stays running with no immediate errors.

---

## Step 9 — Deploy the streaming Dataflow pipeline

```bash
cd ../scripts
PROJECT_ID=YOUR_PROJECT_ID REGION=us-central1 bash deploy_dataflow_pipeline.sh dev
```

**This takes 5-10 minutes** — it builds a Docker image via Cloud Build,
stages a Flex Template, and launches the job.

**✅ Success looks like:** the script ends with `Done. Job:
supplychain-streaming-dev (version ...)`. Verify:
```bash
gcloud dataflow jobs list --region=us-central1 --project=YOUR_PROJECT_ID
```
Status should be `Running` (it may show `Pending`/`Starting` for the first
minute or two — wait and re-check before treating that as a failure).

---

## Step 10 — Generate traffic and verify data flows through Bronze → Silver → Gold

With the bridge (Step 8) still running, generate real traffic:

```bash
cd ../kafka/producer
python producer.py --domains all --rate 10 --duration 300
```

Let it run for a few minutes, then check Bronze:

```bash
bq query --use_legacy_sql=false --project_id=YOUR_PROJECT_ID \
  'SELECT COUNT(*) FROM supplychain_bronze.orders WHERE event_timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)'
```

**✅ Success looks like:** a non-zero, growing count.

Silver refreshes every 30 minutes (see `docs/cost-optimization.md` for
why) — you can trigger the scheduled query manually instead of waiting:
```bash
bq show --transfer_config --project_id=YOUR_PROJECT_ID   # find the transfer config name
bq mk --transfer_run --run_time=$(date -u +%Y-%m-%dT%H:%M:%SZ) <transfer_config_resource_name>
```
Or just wait 30 minutes, then:
```bash
bq query --use_legacy_sql=false --project_id=YOUR_PROJECT_ID \
  'SELECT COUNT(*) FROM supplychain_silver.orders'
```

Then check a Gold view:
```bash
bq query --use_legacy_sql=false --project_id=YOUR_PROJECT_ID \
  'SELECT * FROM supplychain_gold.order_fulfillment_sla LIMIT 10'
```

**✅ Success looks like:** rows come back. If Bronze has data but Silver
is empty after 30+ minutes, see
`docs/troubleshooting-guide.md` — the DTS impersonation grant is the
most likely cause.

**You have now proven the entire pipeline end to end, on real GCP
infrastructure, with real (synthetic) data flowing through it.** This is
the milestone worth taking a screenshot of for a portfolio/interview
conversation.

---

## Step 11 — Build the Looker Studio dashboards

This is a manual UI step — Looker Studio has no meaningful
infrastructure-as-code story (see `looker/dashboard-spec.md` for why).

1. Go to [lookerstudio.google.com](https://lookerstudio.google.com).
2. Create a new report → **Add data** → **BigQuery** connector → select
   your project → `supplychain_gold` dataset → one of the 5 views.
3. Build each page exactly per the spec table in
   [looker/dashboard-spec.md](looker/dashboard-spec.md) — chart type,
   fields, and the *why* for each tile are all listed there so you're not
   guessing at what to build.
4. Repeat for all 5 Gold views (4 dashboard pages, since two views share
   Page 1).

**✅ Success looks like:** a dashboard with live data, refreshable, that
you can screen-record or screenshot for a portfolio.

---

## Step 12 — Wire up CI/CD (GitHub Actions)

Only do this once you've pushed this repo to your own GitHub remote.

1. Get the values Terraform already created:
   ```bash
   cd infra/terraform/environments/dev
   terraform output dataflow_worker_sa_email
   terraform output cicd_deployer_sa_email
   terraform output workload_identity_provider_name
   ```
2. In your GitHub repo → **Settings → Environments** → create an
   environment named `dev` (no protection rules needed for dev).
3. In that environment (or repo-level, under **Settings → Secrets and
   variables → Actions → Variables**), add these **Variables** (not
   secrets — none of this is sensitive, it's all resource names):
   - `WIF_PROVIDER_DEV` = the `workload_identity_provider_name` output
   - `CICD_DEPLOYER_SA_DEV` = the `cicd_deployer_sa_email` output
   - `GCP_PROJECT_ID_DEV` = `YOUR_PROJECT_ID`
   - `GCP_REGION` = `us-central1`
4. Also create `uat` and `prod` GitHub Environments (for
   `cd-promote.yml`), each with **required reviewers** configured under
   the environment's protection rules — this is what makes promotion
   pause for manual approval.
5. Push a commit to `main`. `.github/workflows/ci.yml` should run
   automatically; `.github/workflows/cd-dev.yml` should run and deploy.

**✅ Success looks like:** green checks on the Actions tab, and a fresh
Dataflow job version if you changed the pipeline code.

---

## Step 13 — Promote to UAT/Prod (optional, do this later)

Repeat Steps 2, 5, 6, 7 against **separate GCP projects** for `uat` and
`prod` (see `docs/security-guide.md#environment-isolation` for why
separate projects, not just separate configs in one project). Then set the
same GitHub Environment variables for `uat`/`prod`, and trigger promotion
via **Actions → CD - Promote to UAT/Prod → Run workflow**.

---

## Step 14 — Cost control: stopping between sessions

**Before you walk away from a working session**, stop the two things that
bill continuously:

```bash
# Stop the Dataflow job (the single biggest cost risk)
gcloud dataflow jobs list --region=us-central1 --project=YOUR_PROJECT_ID
gcloud dataflow jobs drain JOB_ID --region=us-central1 --project=YOUR_PROJECT_ID

# Stop local Kafka (no GCP cost, but frees your machine's resources)
cd kafka/docker && docker compose down
```

Redeploy the Dataflow job with `scripts/deploy_dataflow_pipeline.sh dev`
whenever you pick the project back up — it launches fresh since there's no
running job with that name for `--update` to target (see the script's own
comment on this).

---

## Full teardown (when you're completely done)

```bash
cd infra/terraform/environments/dev
terraform destroy -var-file=terraform.tfvars
```

This does NOT delete the Terraform state bucket itself (bootstrap is a
separate config) — if you want the GCP project gone entirely:
```bash
gcloud projects delete YOUR_PROJECT_ID
```

Local Kafka:
```bash
cd kafka/docker && docker compose down -v   # -v also removes the topic data volumes
```
