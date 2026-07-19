# Security Guide

Every permission granted anywhere in `infra/terraform/` is listed here with
its justification. If a grant exists that isn't explained below, that's a
bug — file it as tech debt, don't just leave it.

## Service accounts and their exact permissions

### `sa-dataflow-worker-<env>` (`infra/terraform/modules/iam/main.tf`)

The identity the streaming pipeline actually runs as. No `roles/editor`,
no `roles/owner` — every grant is scoped to the specific resource it needs:

| Role | Scope | Why |
|---|---|---|
| `roles/dataflow.worker` | project | Required to exist as a Dataflow worker at all |
| `roles/monitoring.metricWriter` | project | Writes its own operational metrics |
| `roles/logging.logWriter` | project | Writes its own logs |
| `roles/storage.objectAdmin` | staging + raw-archive buckets only | Staging files + raw archive writes — NOT the whole project's storage |
| `roles/pubsub.subscriber` | the 5 domain subscriptions only | Reads events — cannot subscribe to anything else in the project |
| `roles/pubsub.publisher` | the 5 DLQ topics only | Writes its own DLQ side-output — cannot publish anywhere else |
| `roles/bigquery.dataEditor` | `supplychain_bronze` dataset only | Writes Bronze rows — no access to Silver or Gold |
| `roles/bigquery.jobUser` | project (BigQuery has no dataset-level job-running role) | Required to run the write job at all |
| `roles/secretmanager.secretAccessor` | the carrier API key secret only | Reads the one secret it needs for enrichment — nothing else in Secret Manager |

### `sa-pubsub-bridge-<env>`

Runs outside GCP (on-prem/laptop) — the seam between Kafka and Pub/Sub.

| Role | Scope | Why |
|---|---|---|
| `roles/pubsub.publisher` | the 5 domain topics only | Publishes bridged events — cannot publish to DLQ topics (only the pipeline and consumer/bridge's own DLQ-routing code path does that, via direct Kafka DLQ, not Pub/Sub) |

**Auth model:** Application Default Credentials (`gcloud auth
application-default login`) for local development, or a downloaded service
account key for a genuinely long-running bridge deployment. A downloaded
key is a real trade-off here — Workload Identity Federation (used for
CI/CD, see below) isn't available for a process running outside any
supported external identity provider. If this bridge ran on-prem with a
supported IdP (Okta, Azure AD, etc.), workload identity federation for
that IdP would be the better choice; documented here as a known
compromise, not an oversight.

### `sa-bq-transform-<env>`

Runs the scheduled Bronze → Silver MERGE queries.

| Role | Scope | Why |
|---|---|---|
| `roles/bigquery.dataViewer` | `supplychain_bronze` only | Reads Bronze to MERGE from |
| `roles/bigquery.dataEditor` | `supplychain_silver` only | Writes Silver — no access to Bronze writes or Gold |
| `roles/bigquery.jobUser` | project | Required to run the query job |

Also: the BigQuery Data Transfer Service's own service agent
(`service-<project_number>@gcp-sa-bigquerydatatransfer.iam.gserviceaccount.com`)
is granted `roles/iam.serviceAccountTokenCreator` on this SA specifically
— required for DTS to impersonate it when running the scheduled query.
Easy to miss; the failure mode (scheduled query silently never runs) gives
no obvious pointer back to this missing grant.

### `sa-cicd-deployer-<env>`

The identity GitHub Actions assumes to run Terraform. Broad by necessity —
Terraform itself provisions IAM, networking, and every data resource in
this project, so its deployer needs correspondingly broad create/manage
permissions (`roles/*.admin` across compute, IAM, storage, Pub/Sub,
BigQuery, Dataflow, Secret Manager, monitoring, logging — see
`infra/terraform/modules/iam/main.tf` for the full list).

**This is the one place in this repo with a standing broad grant, and it's
worth naming as a trade-off rather than glossing over:** a real
enterprise platform team would either scope this per-resource-type per
environment (a `terraform-networking-deployer`, a
`terraform-bigquery-deployer`, etc. — more setup, smaller blast radius per
compromised credential) or front deploys with a just-in-time elevation
workflow (the deployer identity has no standing permissions; a human
approval grants temporary elevated access for the duration of an apply).
Neither was built here — the honest reason is that it's meaningfully more
Terraform/process to build for a portfolio project's marginal security
benefit, but you should be able to describe both alternatives and why a
larger org would pick one over the standing-broad-grant approach used here.

**Auth:** Workload Identity Federation, not a downloaded JSON key — see
below.

## Workload Identity Federation (no static keys for CI/CD)

`infra/terraform/modules/iam/main.tf` provisions a
`google_iam_workload_identity_pool` + OIDC provider trusting
`token.actions.githubusercontent.com`, with an `attribute_condition`
restricting token exchange to this exact repo (`owner/repo` string). GitHub
Actions exchanges its own short-lived OIDC token for a GCP access token at
deploy time — no long-lived credential is ever stored as a GitHub secret,
downloaded, or capable of being replayed outside a workflow run from this
specific repo.

**Why this matters over a downloaded SA key:** a leaked Actions log or a
compromised dependency in the CI pipeline can't be used to authenticate
as this SA outside of an actual workflow run — there's no static secret
to leak in the first place.

## Secret Manager

One secret: `carrier-tracking-api-key-<env>`
(`infra/terraform/modules/secret_manager/main.tf`), used only by
`dataflow/transforms/enrich_shipment.py`'s shipment enrichment call.

- Terraform provisions the secret **container** and a placeholder version
  only (`lifecycle { ignore_changes = [secret_data] }`) — the real value
  is set via `gcloud secrets versions add`, never through
  `terraform plan`/`apply`, so it never appears in a plan diff, CI log, or
  state file in plaintext at rest in a way Terraform would surface it.
- Only `sa-dataflow-worker` has `secretAccessor` on it — not the bridge,
  not the CI/CD deployer beyond what `secretmanager.admin` already implies
  for provisioning (see the CI/CD deployer trade-off above).
- **Explicitly NOT used for service account keys.** Workload Identity
  Federation (CI/CD) and Application Default Credentials (local dev) are
  used instead wherever possible — Secret Manager holds application
  secrets, not machine identity credentials, by design.

## Network security

See [docs/diagrams/network/network-diagram.md](diagrams/network/network-diagram.md)
for the full picture and reasoning. Summary:
- Dataflow workers: no public IP, reach GCP APIs via Private Google
  Access, reach the one external dependency (carrier API) via Cloud NAT.
- Firewall rules are allow-list only (custom-mode VPC creates zero
  implicit rules) — worker-to-worker shuffle traffic and IAP-tunneled SSH
  are the only two ingress rules that exist. No rule permits SSH or any
  other ingress from `0.0.0.0/0`.
- Environment isolation is project-level, not just VPC-level — dev, uat,
  and prod are recommended as separate GCP projects specifically so an IAM
  or quota mistake in one cannot touch another.

## Environment isolation

Each environment has its own: GCP project (recommended), VPC, subnet CIDR
range (non-overlapping: `10.10.0.0/20` dev, `10.11.0.0/20` uat,
`10.12.0.0/20` prod), service accounts, Terraform state (separate GCS
prefix per environment, same bucket — see `infra/terraform/bootstrap`),
and CI/CD gating (dev auto-deploys on merge; uat/prod require manual
`workflow_dispatch` plus GitHub Environment protection rules/reviewers —
see `.github/workflows/cd-promote.yml`).
