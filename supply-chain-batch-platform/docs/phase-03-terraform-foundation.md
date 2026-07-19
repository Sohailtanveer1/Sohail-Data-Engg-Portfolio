# Phase 3 — Terraform Foundation (dev)

> The 15-step walkthrough for the first real (tiny) GCP footprint: APIs, private
> networking, least-privilege IAM, buckets, secrets, and a $50 budget — all as
> reusable, environment-isolated Terraform (ADR-0008/0009). **No compute yet.**

---

## 1. Objectives

- Provision the platform's foundation with **Terraform only** (never by hand).
- Reusable **modules** composed per environment (`dev`/`uat`/`prod`).
- **Least-privilege** identities and **private-by-default** networking.
- Prove a clean **`apply` / `destroy`** round-trip with **no orphans**.
- A **$50 billing budget** guardrail before any spend can accumulate.

## 2. Theory

- **Modules + per-env roots** (not workspaces): isolated state, explicit blast
  radius, per-env `*.tfvars` (ADR-0008).
- **Remote state** in a versioned GCS bucket, one prefix per env, created by a
  one-time **bootstrap** (chicken-and-egg: bootstrap uses local state).
- **Least privilege**: one SA per component; project roles in `iam`, bucket roles
  in `storage`, secret roles in `secret_manager`, cross-SA `actAs` in the root.
- **Private by default**: custom VPC, private subnet, PGA, NAT, deny-by-default
  firewall, no external IPs (ADR-0009).

## 3. Business Context

In a Fortune-500 platform, "who can touch what" and "what can talk to the
internet" are audited controls. Building least-privilege IAM and private
networking from the first commit is what separates a portfolio piece from a toy —
and it costs essentially nothing on the Free Trial.

## 4. Architecture (what Terraform creates)

```
bootstrap/                -> state bucket (versioned) + CI deployer SA
environments/dev/  composes:
  project_services  -> enable 13 APIs
  networking        -> VPC, private subnet, Cloud Router + NAT, firewall, PGA
  iam               -> SAs: dataproc, composer, ingestion (+ least-privilege roles)
  storage           -> buckets: landing/bronze/silver/gold/archive/temp/
                       dataproc-staging/artifacts (lifecycle + bucket IAM)
  secret_manager    -> secrets: sap-sftp-password, salesforce-token, wms-db-password
  budget            -> $50 budget w/ 50/90/100% alerts
```

## 5. Folder Creation

Populated: [`infra/terraform/modules/`](../infra/terraform/modules) (6 modules),
[`infra/terraform/bootstrap/`](../infra/terraform/bootstrap),
[`infra/terraform/environments/{dev,uat,prod}/`](../infra/terraform/environments).

## 6. Infrastructure

Six modules, each with `main.tf`/`variables.tf`/`outputs.tf`/`README.md`. `dev`,
`uat`, `prod` roots are identical `.tf` parameterised by `<env>.tfvars`
(`prod.tfvars` sets `force_destroy_buckets = false`).

## 7. Implementation notes (defensible design choices)

- **`project_services`**: `disable_on_destroy = false` — destroying the stack
  doesn't yank APIs out from under a shared project.
- **`storage`**: uniform bucket-level access (no ACLs); lifecycle tiers
  landing/bronze/archive to Nearline; auto-deletes `temp`/`dataproc-staging`;
  versions silver/gold/artifacts; per-bucket least-privilege IAM.
- **`iam`**: Dataproc SA gets `dataproc.worker` + BigQuery data/job + logging;
  Composer SA gets `composer.worker`; ingestion SA is minimal (logging) and gains
  bucket/secret access only where wired. Composer→Dataproc `actAs` is explicit.
- **`secret_manager`**: creates containers only — **values never touch Terraform
  state**; added out-of-band with `gcloud secrets versions add`.
- **`budget`**: alerts (doesn't cap); optional Pub/Sub hook for the enterprise
  auto-disable-billing pattern.

## 8. Testing / Verification

```bash
terraform fmt -recursive infra/terraform      # style
terraform validate                            # per root
```

**Authoring session result:** `fmt` clean; **`terraform validate` = Success** for
`bootstrap`, `dev`, and `prod` roots (uat is byte-identical `.tf`), initialised
against the real `hashicorp/google ~> 5.45` provider. `plan`/`apply` require a
real project + credentials and are run by you (see the runbook below).

## 9. Documentation

This doc + 6 module READMEs + updated env/infra READMEs + PROJECT_PROGRESS.

## 10. Code Review notes

- Budget `all_updates_rule`: `monitoring_notification_channels` and `pubsub_topic`
  are mutually exclusive in the API — defaults leave both empty (billing admins
  get emails), which is valid. Set one, not both, when customising.
- `.terraform.lock.hcl` currently records windows hashes only; Phase 10 CI will
  regenerate it with `linux_amd64` hashes for the pipeline.
- Backend uses **partial config** (`backend.hcl`) so the state bucket name is not
  hardcoded and secrets stay out of committed files.

## 11. Interview Questions

- *Why bootstrap separately?* The state bucket can't store its own creation —
  bootstrap runs on local state and creates the remote backend everything else uses.
- *How is least privilege enforced across three layers?* Project roles (`iam`),
  bucket roles (`storage`), secret roles (`secret_manager`) — each SA only where needed.
- *Why no external IPs on workers?* PGA reaches Google APIs privately; NAT gives
  outbound-only egress; firewall denies all other ingress (ADR-0009).
- *How do you guarantee no orphaned resources on teardown?* Everything is in
  Terraform state; `force_destroy` on non-prod buckets; `destroy` is verified.
- *Why partial backend config?* Keeps the bucket name/env out of committed code
  and lets one root target different state per env.

## 12. Best Practices applied

Modules + per-env roots; remote versioned state; least privilege; private
networking; secrets out of state; cost guardrail first; `fmt`+`validate` gates.

## 13. Common Mistakes (avoided)

Using the default VPC (broad firewall); Owner/Editor on the CI SA; secret values
in tfvars/state; hardcoding globally-unique bucket names; `disable_on_destroy=true`
on shared APIs; forgetting `force_destroy` (destroy fails on non-empty buckets).

## 14. Cost Considerations

| Resource | Cost while idle | Note |
|---|---|---|
| APIs enabled | $0 | enabling is free |
| VPC/subnet/firewall/PGA | $0 | no charge for the network itself |
| Cloud NAT | ~$1–3/mo + data | only matters once compute runs; destroy with the stack |
| Buckets (empty/small) | pennies | lifecycle keeps it tiny |
| Secret Manager | ~$0 | first 6 versions free |
| Budget | $0 | free |
| **Phase 3 total** | **< $1** | foundation only; no compute |

## 15. Next Steps

**Phase 4 — BigQuery datasets & metadata model:** `bigquery` module + DDL for the
`*_metadata` control/audit/watermark/DQ/schema-registry tables and the Gold
dims/facts. Free-tier only. The `metadata.py` store gains a BigQuery backend.

---

## Runbook — apply the foundation (you drive this)

> Prereqs: a GCP **Free-Trial project**, its **project_id** and **billing account
> id**, plus `gcloud` + `terraform`. Authenticate once:
> `gcloud auth application-default login` and `gcloud config set project <id>`.

**1. Bootstrap (once):**
```bash
cd infra/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars   # edit project_id, state_bucket_prefix
terraform init
terraform apply                                # note outputs: state_bucket, ci_deployer_email
```

**2. Dev environment:**
```bash
cd ../environments/dev
cp backend.hcl.example backend.hcl             # set bucket = <state_bucket from step 1>
# edit dev.tfvars: project_id, billing_account
terraform init -backend-config=backend.hcl
terraform apply -var-file=dev.tfvars
```

**3. Add secret values (out-of-band, never in Terraform):**
```bash
printf '%s' "$SAP_SFTP_PW"   | gcloud secrets versions add scb-dev-sap-sftp-password --data-file=-
printf '%s' "$SF_TOKEN"      | gcloud secrets versions add scb-dev-salesforce-token  --data-file=-
printf '%s' "$WMS_DB_PW"     | gcloud secrets versions add scb-dev-wms-db-password   --data-file=-
```

**4. Verify:**
```bash
terraform output
gcloud storage buckets list --project <project_id>
gcloud iam service-accounts list --project <project_id>
gcloud compute networks list --project <project_id>
```

**5. Teardown (leave nothing billing):**
```bash
terraform destroy -var-file=dev.tfvars         # removes the dev stack
# (optional) tear down bootstrap too — keeps nothing except what you choose:
cd ../../bootstrap && terraform destroy
```
Then confirm in **Billing → Reports** that the run-rate is ~$0.
