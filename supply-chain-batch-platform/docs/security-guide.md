# Security Guide

Defense-in-depth across identity, network, secrets, data, and pipeline — all
Terraform-provisioned and least-privilege by default.

---

## 1. Identity & access (least privilege)

- **One service account per component** (`dataproc`, `composer`, `ingestion`, plus
  the `ci-deployer`), each granted only the roles it needs — project roles in the
  `iam` module, bucket roles in `storage`, secret access in `secret_manager`.
- **Cross-SA `actAs`** is explicit: Composer may act as the Dataproc SA to submit
  batches; nothing broader.
- **No human uses the deployer SA interactively**; CI assumes it via **Workload
  Identity Federation** — no exported keys.

## 2. Network (private by default — ADR-0009)

- Custom VPC, single **private subnet**, **no external IPs** on compute.
- **Private Google Access** reaches GCS/BigQuery over Google's backbone.
- **Cloud NAT** for outbound-only egress (package/jar installs); no inbound.
- **Deny-by-default firewall** + explicit intra-subnet allow (+ optional IAP-SSH).

## 3. Secrets

- All credentials live in **Secret Manager**; **values never touch Terraform
  state** (containers created by TF, versions injected out-of-band with `gcloud`).
- `.gitignore` blocks `*.key`, `service-account*.json`, `.env`, `secrets/`, real
  `terraform.tfvars`/`backend.hcl`; pre-commit runs **`detect-private-key`**.
- Only the `ingestion` SA gets `secretAccessor`, and only to the secrets it uses.

## 4. Data

- **Buckets:** uniform bucket-level access (no ACLs), no `allUsers`; lifecycle
  tiering; versioning on state/gold/artifacts; `force_destroy` only in non-prod.
- **BigQuery:** dataset/table access via SA roles; prod tables have
  `deletion_protection`; `maximum_bytes_billed` caps ad-hoc scans.
- **Bronze immutability** gives an auditable raw record of exactly what arrived.

## 5. Pipeline integrity

- **Idempotent** writes + **file checksums** prevent double-processing and make
  replays safe.
- **DQ quarantine** stops bad data reaching Silver/Gold; **audit tables** record
  who/what/when for every batch and file.
- **Structured logs** feed failure/freshness/rejection **alerts**.

## 6. What an interviewer will probe

- *Where do secrets live and how do they reach a job?* Secret Manager →
  `secretAccessor` on the ingestion SA → read at runtime; never in code/state.
- *How is CI authorized to GCP?* WIF/OIDC, keyless, scoped deployer SA.
- *Could a worker exfiltrate data to the internet?* No inbound; egress via NAT
  only; PGA keeps Google-API traffic private (VPC-SC is the enterprise tightening).

## 7. Enterprise hardening (documented, beyond portfolio)

CMEK/Cloud KMS on buckets/BigQuery/secrets · secret rotation · VPC Service Controls
perimeter · Cloud Armor · Private Service Connect · org policies · Dataplex
governance · access transparency + audit-log sinks to a locked project.
