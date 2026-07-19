# Lessons Learned

A running log of real decisions and real problems hit while building this,
not a retrospective written after the fact from memory. Keep this updated
as the project evolves past its initial build.

> **The full catalogue of deployment war stories** (packaging the Beam
> pipeline, IAM/service-agent issues, zone exhaustion, streaming-sink
> constraints, Pub/Sub ordering/schema, and Windows tooling) now lives in
> [HANDBOOK.md Part 5](../HANDBOOK.md#part-5--the-debugging-journey-war-stories),
> organized as Symptom → Root cause → Fix → Lesson for interview use. This
> file keeps the earlier build-time notes below.

## Deployment saga — one-line index (full detail in HANDBOOK Part 5)

Hit while taking the pipeline from "code complete" to "running on Dataflow":
Cloud Build SA missing `builds.builder` · worker SA missing
`artifactregistry.reader` · DTS service agent not auto-created ·
`ZONE_RESOURCE_POOL_EXHAUSTED` (n1 family / us-central1-c) · Flex Template
`-e` requirements bug · Beam "Missing required option: project" · `WriteToText`
illegal on unbounded PCollection · `STORAGE_WRITE_API` needs explicit schema
· workers on stock SDK container (missing code) · missing `kafka/schemas` in
image · Pub/Sub publisher ordering flag · Pub/Sub Avro-vs-plain-JSON · WIF
pool 30-day soft-delete on recreate · Windows: CLOUDSDK_PYTHON stub,
MSYS path mangling, `bq` parsing `--` SQL comments as flags. Each one is a
real, transferable lesson — see the Handbook.

## Environment/tooling problems hit while building this (worth knowing before you hit them too)

**`apache-beam` doesn't install on Python 3.14.** Tried first — failed with
a `pkg_resources`/`grpcio-tools` build error. Beam's dependency chain
doesn't yet support every new Python release the moment it ships. Fix: use
a dedicated Python 3.12 virtualenv for anything touching `dataflow/`. This
cost real debugging time; it's called out explicitly in
`docs/testing-guide.md` and `docs/troubleshooting-guide.md` so it doesn't
cost you the same time.

**Pinning `requests==2.32.3` exactly broke `apache-beam[gcp]`'s dependency
resolution**, but leaving `requests` unpinned resolved cleanly. Lesson:
when a package conflicts with a large framework's dependency tree, an
exact pin is often the problem, not the solution — let the resolver pick
within the framework's constraints unless you have a specific reason to
need an exact version.

**A `.env` file for a genuinely non-secret value (the Kafka KRaft
`CLUSTER_ID`) got silently excluded by the repo's blanket `.gitignore`
rule for `.env` files.** The fix was NOT to carve an exception into the
gitignore rule — that's exactly the kind of hole that lets a real secret
slip through later — but to inline the non-secret value directly into
`docker-compose.yml`. General principle: a blanket secrets-safety rule
should never get exceptions for convenience; change the thing that
conflicts with it instead.

**BigQuery Data Transfer Service scheduled queries need an extra,
easy-to-miss IAM grant:** the DTS service agent needs
`roles/iam.serviceAccountTokenCreator` on whatever custom service account
runs the scheduled query, or the query silently never executes — no
obvious error points back at the missing grant. Documented in
`docs/security-guide.md` and `docs/troubleshooting-guide.md` specifically
because the failure mode gives so little signal.

## Design decisions and why (the ones worth remembering the reasoning for)

**Terraform modules are resource-type-scoped (networking, iam, pubsub,
bigquery...) not domain-scoped (one "ingestion" module bundling several
resource types).** Maximizes reuse across unrelated future projects — the
`iam` module here is generic enough to reuse elsewhere unchanged.

**Dataflow jobs are launched imperatively (`scripts/deploy_dataflow_pipeline.sh`
+ Flex Templates), not as a `google_dataflow_flex_template_job` Terraform
resource.** Streaming jobs are a poor fit for Terraform's plan/apply model
— in-place pipeline updates need `--update` semantics Terraform's provider
handles inconsistently, and drift detection on a long-running streaming
job is noisy. Terraform owns the durable infra around the job (buckets,
Artifact Registry, IAM); the job launch itself is a script, called from CI.

**Bronze/Silver/Gold split isn't just "medallion architecture because
that's the pattern" — it's specifically "streaming writes fast and dumb
(Bronze), batch SQL conforms and dedupes (Silver), business logic lives in
plain views (Gold)."** Each layer is independently testable and
re-runnable — Silver's MERGE can be re-run without touching Kafka/Pub/Sub
at all, which matters a lot when debugging a dedup issue.

**Chose to manufacture failure modes (malformed/duplicate/late events) in
the producer's synthetic data generator rather than relying on organic
failures during testing.** A real upstream system doesn't misbehave on
command — without deliberately injecting these, the DLQ and
watermarking/lateness code paths would be unreachable and effectively
untested in any local/demo run.

## What's genuinely incomplete, flagged rather than hidden

- **No integration test against a live Kafka cluster in CI** — `tests/integration/`
  is a placeholder. The natural next addition: a CI job that stands up
  `kafka/docker/docker-compose.yml` and runs a real produce/consume/DLQ
  round trip.
- **No batch replay pipeline actually built** — the GCS raw archive exists
  and the batch replay approach is documented
  (`docs/architecture/architecture-overview.md#replay-and-backfill`), but
  the actual `ReadFromText`-based batch variant of the streaming
  transforms hasn't been written. Natural v2 addition.
- **CI/CD deployer service account has broad standing IAM grants**
  (`roles/*.admin` across several services) rather than either
  per-resource-type scoping or just-in-time elevation. Named explicitly as
  a trade-off in `docs/security-guide.md`, not left unexplained.
- **No Looker Studio dashboard actually built** — only the spec
  (`looker/dashboard-spec.md`). Looker Studio has no real Terraform
  support, so this is a manual UI step by design, not an oversight.
