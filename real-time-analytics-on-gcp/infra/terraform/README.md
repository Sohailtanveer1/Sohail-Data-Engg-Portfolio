# Terraform Documentation

## Layout

```
infra/terraform/
├── bootstrap/          # Run ONCE per GCP project, by hand, local backend.
│                        # Creates the GCS bucket every environment's remote state lives in.
├── modules/             # Resource-type-scoped, reusable across environments (and other projects).
│   ├── networking/       # VPC, subnet, firewall rules, Cloud Router + NAT
│   ├── iam/              # Service accounts, IAM grants, Workload Identity Federation
│   ├── storage/          # GCS: Dataflow staging bucket, raw event archive
│   ├── pubsub/            # Topics, DLQ topics, ordered subscriptions, Avro schemas
│   ├── bigquery/          # Bronze tables, Silver tables + scheduled MERGE, Gold views
│   ├── dataflow/          # Artifact Registry repo for Flex Template images
│   ├── secret_manager/    # Carrier API key secret container
│   └── monitoring/        # Alert policies, notification channel, log-based metrics
└── environments/
    ├── dev/               # Wires every module together, dev-sized defaults
    ├── uat/                # Same wiring, uat-sized defaults (higher alert thresholds, load-test friendly)
    └── prod/               # Same wiring, prod-sized defaults (tighter alert thresholds, deletion_protection on)
```

## Why resource-type-scoped modules, not domain-scoped

A domain-scoped alternative would bundle e.g. "ingestion" (Pub/Sub + IAM +
monitoring together) into one module. Resource-type scoping was chosen
instead because it maximizes reuse: the `iam` module here is generic
enough to drop into an unrelated future project unchanged, where a
domain-scoped `ingestion` module would carry this project's specific
assumptions baked in.

## Why environments are separate root configs, not Terraform workspaces

Each environment (`dev/`, `uat/`, `prod/`) is its own root Terraform
configuration with its own state file, not a `terraform workspace` sharing
one root config. Workspaces share the same backend config and provider —
a mistake in the root config affects every workspace identically. Separate
root configs with separate `backend.tf` prefixes mean a bad `dev` apply
physically cannot touch `prod`'s state, and each environment can diverge
in ways workspaces make awkward (different variable defaults, different
module version pins if you ever need that).

## How environment-specific sizing is expressed

Not via separate module code paths — the SAME modules are used for every
environment; environment-specific behavior comes from `var.environment`
conditionals inside each module (e.g.
`deletion_protection = var.environment == "prod"` in the bigquery module)
plus different tfvars values passed in from each environment's
`terraform.tfvars` (e.g. `backlog_threshold` is 500 in prod, 2000 in uat —
see each environment's `variables.tf` defaults).

## Remote state

`bootstrap/` creates one GCS bucket (`<project_id>-tfstate`); each
environment's `backend.tf` points at that same bucket with a distinct
`prefix` (`environments/dev`, `environments/uat`, `environments/prod`) —
one bucket, three independent state files, versioning enabled so a bad
apply's state can be recovered from a prior version.

## Running Terraform locally

Terraform itself isn't installed on the machine this repo was built on —
install it (>= 1.7.0) before running any of the commands below.

```bash
# One-time, per GCP project
cd infra/terraform/bootstrap
terraform init && terraform apply -var="project_id=YOUR_PROJECT"

# Per environment
cd infra/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars   # fill in, gitignored
terraform init
terraform fmt -check -recursive ..              # from environments/dev, checks the whole infra/terraform tree
terraform validate
terraform plan
terraform apply
```

CI runs `terraform fmt -check` and `terraform validate` (no credentials
needed, `-backend=false`) on every PR across all three environments, and a
real `terraform plan` against dev specifically — see
`.github/workflows/ci.yml`.
