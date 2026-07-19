# The Complete Handbook
## Real-Time Supply Chain Order & Inventory Analytics Platform

> One document to learn the entire project from zero, run it as a hands-on
> lab, understand *why* every decision was made, and defend all of it in a
> senior data-engineering interview.
>
> This handbook is the map. It links to the deep-dive docs under `docs/` for
> detail, but it stands on its own as a learning path. Read it top to bottom
> once; then use it as a reference.

---

## Table of Contents

- [Part 0 — How to use this handbook](#part-0--how-to-use-this-handbook)
- [Part 1 — The 10,000-foot view](#part-1--the-10000-foot-view)
- [Part 2 — The technology map](#part-2--the-technology-map-every-tool-why-its-here)
- [Part 3 — Concept deep-dives (the interview core)](#part-3--concept-deep-dives-the-interview-core)
- [Part 4 — The hands-on lab](#part-4--the-hands-on-lab)
- [Part 5 — The debugging journey (war stories)](#part-5--the-debugging-journey-war-stories)
- [Part 6 — Defending it in an interview](#part-6--defending-it-in-an-interview)
- [Part 7 — Glossary](#part-7--glossary)
- [Part 8 — Where everything lives](#part-8--where-everything-lives)

---

## Part 0 — How to use this handbook

**If you have 30 minutes:** read Part 1 (the view) and Part 6 (interview
defense). You'll be able to *talk* about the project convincingly.

**If you have a day:** read Parts 1–3, then skim Part 5 (war stories). You'll
*understand* the project.

**If you want to truly own it:** do Part 4 (the lab) end to end on your own
GCP free trial, hit some of the same walls in Part 5, and you'll be able to
*defend* it against any follow-up question — because you'll have actually
done it, not just read about it.

**The single most valuable thing in this handbook is Part 5.** Anyone can
describe a happy-path architecture. What separates a senior engineer in an
interview is being able to say *"here's what broke, here's how I diagnosed
it, here's the fix, and here's what I learned"* — and Part 5 is a catalogue
of exactly those, all real, all from building this.

---

## Part 1 — The 10,000-foot view

### The business problem

A supply-chain operator runs disconnected systems for Orders, Inventory,
Shipments, Returns, and Suppliers. Data reaches analysts hours late via
nightly batch. Three concrete costs result:

1. **Overselling / stockouts** — inventory decrements arrive too late, so
   the storefront sells stock that's already gone.
2. **Missed shipment SLAs** — a delay is discovered the next morning, after
   the customer already knows.
3. **Slow supplier accountability** — a supplier's late-delivery pattern is
   only visible in a quarterly report.

### What the platform does

Ingests those events in **real time**, validates and enriches them, and
serves trustworthy metrics within seconds — turning "discovered next
morning" into "alertable now."

### The architecture in one line

```
Warehouses → Kafka (local) → Pub/Sub → Dataflow (Apache Beam) → BigQuery (Bronze → Silver → Gold) → Looker Studio
```

### Why each hop exists (the elevator answer)

- **Kafka (local, Dockerized):** models the on-prem broker most enterprises
  already run; durable local buffering + replay; lets you develop offline
  with zero cloud cost.
- **Pub/Sub:** the cloud-native front door Dataflow reads natively; global,
  serverless, scales without ops.
- **Dataflow / Apache Beam:** the streaming brain — validation, windowing,
  watermarking, deduplication, enrichment, DLQ routing, exactly the place
  stateful stream processing belongs.
- **BigQuery Medallion:** Bronze (raw, replayable) → Silver (deduplicated,
  conformed) → Gold (business marts). Separates "append fast" from "make
  trustworthy" from "answer business questions."
- **Looker Studio:** the serving layer ops and finance actually look at.

### Supporting infrastructure (all Terraform-managed, dev/uat/prod isolated)

VPC + firewall + NAT · IAM with least-privilege service accounts · Workload
Identity Federation for CI/CD · Secret Manager · Cloud Storage · Cloud
Logging & Monitoring with real alert policies · CI/CD via GitHub Actions.

**Deep dive:** [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md),
[docs/business/README.md](docs/business/README.md).

---

## Part 2 — The technology map (every tool, why it's here)

| Tool | Role in this project | Why it (vs. the obvious alternative) |
|---|---|---|
| **Python** | Producer, consumer, bridge, Beam transforms | Ubiquitous in data eng; Beam's Python SDK |
| **Docker** | Runs the local Kafka cluster | Reproducible local broker without installing Kafka on the host |
| **Apache Kafka** (KRaft, 3 brokers) | Local durable ingestion buffer | Models real on-prem ingestion; replay; ordering per partition |
| **Kafka Producer/Consumer** | Emit + validate events | Demonstrates producer idempotence, consumer offset management, DLQ |
| **Google Pub/Sub** | Cloud ingestion, ordered subscriptions, DLQ policy | Serverless, global; native Dataflow source; vs. self-managing Kafka in cloud |
| **Apache Beam** | Portable stream-processing model | One model for windowing/state/triggers; portable across runners |
| **Google Dataflow** | Managed Beam runner (streaming) | No cluster to run; autoscaling; vs. self-managed Flink/Spark |
| **BigQuery** | Serverless warehouse, Medallion layers | Separation of storage/compute, partition/cluster pruning; vs. Snowflake/Redshift |
| **Cloud Storage** | Dataflow staging + raw event archive (replay source) | Cheap, durable; outlives Kafka retention for backfills |
| **Terraform** | All infra as code, 3 environments | Reproducible, reviewable, environment-isolated; vs. clicking in console |
| **GitHub Actions** | CI/CD (lint, test, plan, deploy) | Native to the repo; OIDC → no static keys |
| **IAM + Service Accounts** | Least-privilege identity per component | Blast-radius isolation; vs. one over-privileged SA |
| **VPC + Firewall + NAT** | Private network for Dataflow workers | No public IPs; outbound-only via NAT; vs. default network |
| **Secret Manager** | Runtime secrets (carrier API key) | Secrets never in code/state; vs. env vars in plaintext |
| **Cloud Logging/Monitoring** | Log-based metrics + alert policies | Ops observability mapped to real failure modes |
| **Looker Studio** | Dashboards on Gold views | Free, native BigQuery connector; vs. Looker/Tableau licensing |

**The meta-point for interviews:** you didn't pick tools because they're
trendy — each one earns its place against a named alternative. That framing
(*"we chose X over Y because Z"*) is what senior interviewers listen for.

---

## Part 3 — Concept deep-dives (the interview core)

Each concept below has the same shape: **what it is → why it matters →
how it's implemented here → the interview soundbite.** Full treatment with
alternatives/trade-offs is in
[docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md);
this is the condensed, memorizable version.

### 3.1 Idempotency & deduplication (layered, not solved once)

- **What:** processing the same event twice has the same effect as once.
- **Where, in three layers:**
  1. **Producer** — `enable.idempotence=True` + `acks=all` (Kafka broker
     de-dups retried sends within a partition session).
  2. **Dataflow** — `DeduplicateByEventId` stateful DoFn, keyed by
     `event_id`, scoped to a 60s window (catches the Kafka→Pub/Sub gap).
  3. **Silver** — `MERGE ... WHEN NOT MATCHED` on `event_id` (catches
     anything older than the window).
- **Soundbite:** *"Idempotency is a property of the operation; dedup is the
  mechanism. I layer three of them because each covers a gap the others
  can't — no single 'exactly-once' switch exists across heterogeneous hops."*

### 3.2 Exactly-once vs. at-least-once (know exactly where you stand)

- Producer→broker: exactly-once per partition. Bridge→Pub/Sub:
  at-least-once. Pub/Sub→Dataflow: at-least-once. Dataflow→BigQuery:
  at-least-once (we use `STREAMING_INSERTS`).
- **Net:** *effectively-once* = at-least-once delivery + idempotent
  processing (event_id dedup + Silver MERGE).
- **Soundbite:** *"No system I've built is truly end-to-end exactly-once
  across different systems. The honest, defensible design is at-least-once
  delivery plus idempotent processing, which is observably equivalent."*

### 3.3 Schema validation & evolution

- **Validation:** JSON Schema in `kafka/schemas/` (draft 2020-12,
  `additionalProperties: false`), applied identically by producer, consumer,
  bridge, and Dataflow via `common/supplychain_common/schema_validator.py`.
- **Evolution rules:** additive optional field → deploy schema first, stays
  on `v1`; breaking change (new required field / type change) → cut a new
  topic `v2`.
- **Soundbite:** *"One source of truth for the contract, enforced at every
  layer. Additive changes are backward-compatible; breaking changes get a
  new version so old and new consumers migrate independently."*

### 3.4 Dead-letter queues & poison messages

- **Poison message:** one that fails *every* retry identically (malformed
  JSON, schema violation) — retrying is harmful, so quarantine it.
- **Three DLQ layers:** Kafka-side `.dlq` topics (consumer/bridge), Pub/Sub
  `dead_letter_policy`, and Dataflow's DLQ side-output.
- **Soundbite:** *"Retry transient failures with backoff; DLQ permanent
  ones. Mixing them up either drops good data or wedges a partition behind
  a message that can never succeed."*

### 3.5 Windowing, watermarking, late data

- **Event time, not processing time:** `parse_and_validate.py` timestamps
  each record from `event_timestamp` — that's what makes "late" meaningful.
- **Windows:** `FixedWindows(60s)`, `allowed_lateness=1h`. Events later than
  that are dropped from the streaming path (recovered via the GCS archive
  backfill).
- **Watermark:** the pipeline's estimate of "I've seen everything before
  time T." A heuristic — which is exactly why `allowed_lateness` is a
  tunable trade-off between latency and completeness.
- **Soundbite:** *"The watermark is a heuristic, not a guarantee. Allowed
  lateness is how I trade result latency against completeness."*

### 3.6 Partitioning & clustering

- Every Bronze/Silver table: `time_partitioning` on `event_timestamp`,
  `require_partition_filter=true` on Bronze (an unfiltered scan becomes an
  *error*, not a surprise bill). Clustering columns chosen per query pattern.
- **Soundbite:** *"Partitioning prunes whole days; clustering prunes blocks
  within a day. They compose. And I force a partition filter on the big raw
  table so nobody can accidentally scan 90 days."*

### 3.7 Metadata / audit columns

- `_ingested_at`, `_pubsub_message_id`, `_pubsub_publish_time`,
  `_pipeline_version` on every Bronze row (see `AddAuditColumns`).
- **Soundbite:** *"`_pipeline_version` turns 'which deploy caused this bad
  data' from an investigation into a WHERE clause."*

### 3.8 Replay & backfill

- Kafka retention (7–14 days) and Beam allowed-lateness (1h) both have hard
  limits. The **GCS raw archive** (validated events, pre-dedup) is the
  long-term replay source; a batch Beam job reruns the same transforms and
  the idempotent Silver MERGE handles the rest.
- **Soundbite:** *"'Backfill three months' isn't 'replay Kafka' — retention
  doesn't reach. It's replay from the GCS archive through the same idempotent
  transforms."* (Note: the archive write is a documented pending item — see
  Part 5 / lessons-learned.)

### 3.9 Retries, backoff, checkpointing

- Full-jitter exponential backoff (`common/supplychain_common/retry.py`) for
  transient failures (Pub/Sub publish, carrier API). Kafka offsets committed
  **only after** a message is processed or DLQ'd — never left uncommitted on
  a permanent failure, always left uncommitted on a transient one worth
  retrying.
- **Soundbite:** *"Full jitter stops every client retrying in lockstep and
  re-hammering a service that's already down."*

---

## Part 4 — The hands-on lab

The lab is [RUNBOOK.md](RUNBOOK.md) — 14 steps from installing tools to full
teardown, each with a "✅ success looks like" checkpoint. Do it on your own
GCP free trial. Here's the learning framing to layer on top of it.

### Lab structure: do → observe → understand

For each phase, don't just run the command — **observe** the result and
**understand** why. Suggested observation exercises:

| Phase | Do | Observe | Understand |
|---|---|---|---|
| Local Kafka | `producer.py` + Kafka UI | Watch messages land in topics | Partition keys keep an order's events together |
| DLQ | Producer injects 2% malformed | `.dlq` topics fill; alert-worthy | Poison messages quarantined, not retried forever |
| Dedup | Producer injects 3% duplicates | Bronze row count < events sent | event_id dedup working |
| Windowing | Producer injects 5% late events | Some late events processed, very-late dropped | allowed_lateness in action |
| Medallion | Query Bronze, Silver, Gold | Bronze = every event; Silver = deduped; Gold = business answer | Each layer's distinct job |
| Cost | Leave Dataflow running vs. drained | Watch billing | Streaming compute is the one continuous cost |

### The three things every lab-runner should prove to themselves

1. **A malformed event does not reach Bronze** — it's in a `.dlq` topic.
   (Query Bronze for the bad event_id; it's absent. Pull from the DLQ; it's
   there.)
2. **A duplicate event_id produces one Bronze/Silver row, not two.**
3. **Stopping Dataflow stops the meter** but leaves all data queryable —
   proving compute and storage are decoupled.

### Cost discipline (do this every session)

The Dataflow streaming job bills continuously. Drain it when you pause:

```bash
gcloud dataflow jobs list --region=us-east1 --project=YOUR_PROJECT
gcloud dataflow jobs drain <JOB_ID> --region=us-east1 --project=YOUR_PROJECT
```

Everything else (Pub/Sub, BigQuery, GCS, logging) is within free-tier at
this volume. Full teardown: `terraform destroy` in `environments/dev`.

---

## Part 5 — The debugging journey (war stories)

**This is the most interview-valuable part of the whole project.** Every
item below is a real failure hit while deploying this platform, with the
symptom, the root cause, the fix, and the transferable lesson. When an
interviewer asks *"tell me about a hard problem you solved,"* you pick one
of these and walk it end to end.

They cluster into six themes. For each: **Symptom → Root cause → Fix → Lesson.**

### Theme A — Packaging a Beam pipeline for Dataflow (the big one)

**A1. `-e ../../common` broke the Flex Template launcher.**
Symptom: launch failed with "Failed to read the result file." Root cause:
`FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE` pointed at a requirements file
containing an editable path (`-e ../../common`) that didn't resolve inside
the container. Fix: bake a cleaned `requirements-runtime.txt` (no editable
line) and point the env var at it. Lesson: *the file the launcher installs
at runtime must contain only installable packages — editable/relative paths
are a repo-layout convenience that doesn't survive containerization.*

**A2. Beam rejected the pipeline: "Missing required option: project."**
Symptom: graph construction failed on `beam.Pipeline(...)`. Root cause: our
own argparse consumed `--project` (we use it for subscription paths), so it
never reached Beam's `PipelineOptions`. Fix: set
`GoogleCloudOptions.project` explicitly. Lesson: *when you parse args that
Beam also needs, you consume them out from under Beam — set them back.*

**A3. Workers crashed: "SDK harness disconnected."**
Symptom: job reached Running, then workers crash-looped. Root cause: workers
ran the *stock* Beam SDK container, which had none of our code or deps
(`supplychain_common`, transforms, `jsonschema`). Our image was a *launcher*
image, not a *worker* image. Fix: build **one dual-purpose image** —
`FROM apache/beam_python3.11_sdk` (valid worker) + copy the launcher binary
in — and set `--sdk_container_image` so workers use it. Lesson: *for Flex
Templates with custom code/deps, the launcher and the workers must run the
same image; the stock SDK container has nothing of yours.*

**A4. Worker crash: `FileNotFoundError: .../kafka/schemas/...`.**
Symptom: workers ran our code but couldn't find the JSON Schemas. Root
cause: the Dockerfile copied `dataflow/` and `common/` but not
`kafka/schemas/`, which the validator loads at runtime. Fix: `COPY
kafka/schemas/` into the image. Lesson: *data files your code reads at
runtime are dependencies too — package them, not just the `.py` files.*

### Theme B — IAM & Google-managed identities

**B1. Cloud Build couldn't read its own source.**
Symptom: `builds.submit` → `storage.objects.get denied` on the
`_cloudbuild` bucket. Root cause: new GCP projects run Cloud Build as the
Compute Engine default SA, which now gets **no** roles by default. Fix:
grant it `roles/cloudbuild.builds.builder`. Lesson: *"fresh project" defaults
changed in 2024; the compute default SA is no longer auto-privileged.*

**B2. Dataflow workers couldn't pull the pipeline image.**
Symptom: launcher VM → `artifactregistry.repositories.downloadArtifacts
denied`. Root cause: the worker SA had no read access to the image repo
(Cloud Build could *push*, but the worker couldn't *pull*). Fix: grant the
worker SA `roles/artifactregistry.reader` on the repo (now codified in the
`dataflow` module). Lesson: *push and pull are different permissions on
different identities — check both.*

**B3. The BigQuery Data Transfer Service agent "did not exist."**
Symptom: granting `serviceAccountTokenCreator` to the DTS agent failed. Root
cause: Google-managed service agents aren't created until first use. Fix:
explicitly create it with `google_project_service_identity` in bootstrap.
Lesson: *some Google-managed identities must be provisioned before you can
grant to them; the failure mode ("does not exist") is not obvious.*

### Theme C — Infrastructure capacity

**C1. `ZONE_RESOURCE_POOL_EXHAUSTED` in `us-central1-c`.**
Symptom: launcher VM failed to start, repeatedly, in one zone. Root cause:
that zone was out of capacity for the default `n1` machine family (this is
*capacity*, not *quota* — quota says `QUOTA_EXCEEDED`). Fix: switch to the
`e2` family and move the environment to `us-east1`. Lesson: *`--worker-zone`
doesn't move the Flex Template launcher VM; `--region` does. And exhaustion
is usually family-specific — changing machine type often clears it.*

### Theme D — Streaming semantics

**D1. `GroupByKey cannot be applied to an unbounded PCollection`.**
Symptom: graph construction failed on the GCS archive write. Root cause:
`beam.io.WriteToText` is a *batch* sink; it collapses to a global window and
does a GBK, illegal on a streaming PCollection. Fix: remove it for now
(pending re-add via streaming-capable `fileio.WriteToFiles`). Lesson: *not
every transform works in streaming mode; batch file sinks are a classic trap.*

**D2. "A schema is required for STORAGE_WRITE_API."**
Symptom: `WriteToBigQuery` failed at construction. Root cause: the Storage
Write API needs an explicit schema (it can't infer from "table exists").
Fix: switch to `STREAMING_INSERTS`, which reads the schema from the existing
table (correctness preserved by our downstream dedup). Lesson: *the "best"
API sometimes needs more wiring than the demo needs; pick the method whose
requirements match your constraints and know the trade-off.*

### Theme E — Pub/Sub & messaging

**E1. "Cannot publish a message with an ordering key when message ordering
is not enabled."** Root cause: the *publisher client* needs
`enable_message_ordering=True` (separate from the subscription's ordering).
Fix: set it on the client. Lesson: *ordering is a two-sided contract —
publisher client flag AND subscription setting.*

**E2. Pub/Sub Avro schema rejected our plain JSON.** Root cause: an Avro
schema with JSON encoding expects Avro's JSON encoding (nullable field =
`{"string": v}`), incompatible with our plain JSON. Fix: drop the Pub/Sub
schema binding; validation already happens at four app layers. Lesson:
*Avro-JSON ≠ plain JSON; don't bolt on a redundant validator that speaks a
different dialect.*

### Theme F — Local tooling (Windows / Git Bash)

**F1.** `gcloud` broke with "Bad address" → the Windows Store Python *stub*
was picked; fix: `CLOUDSDK_PYTHON` → a real interpreter.
**F2.** `docker exec /opt/kafka/...` got rewritten to a Windows path → MSYS
path conversion; fix: `MSYS_NO_PATHCONV=1`.
**F3.** `bq query "$(cat file.sql)"` parsed `--` SQL comments as CLI flags;
fix: feed SQL via stdin (`< file.sql`).
**F4.** `.env` for a non-secret was silently gitignored; fix: inline the
value, never weaken a secrets-ignore rule.

**Lesson across F:** *cross-platform tooling has sharp edges; know that Git
Bash mangles paths, that Store Python is a stub, and that CLI arg parsers
choke on leading `--`.*

> **Full running log:** [docs/lessons-learned.md](docs/lessons-learned.md).
> **Triage procedures:** [docs/troubleshooting-guide.md](docs/troubleshooting-guide.md).

---

## Part 6 — Defending it in an interview

### 6.1 The 90-second pitch (memorize the shape, not the words)

> "It's a real-time supply-chain analytics platform. Warehouses emit order,
> inventory, shipment, return, and supplier events. They flow through a local
> Kafka cluster — modeling the on-prem broker most companies already run —
> into Pub/Sub, then an Apache Beam pipeline on Dataflow that validates,
> windows, deduplicates, and enriches them, writing to BigQuery in a
> Bronze-Silver-Gold medallion. Looker Studio serves the dashboards. Every
> piece of infrastructure is Terraform across dev, uat, and prod with
> least-privilege IAM, Workload Identity Federation for CI/CD, and monitoring
> mapped to real failure modes. The interesting engineering is in the
> failure handling — layered idempotency, dead-letter queues, watermarking
> for late data, and a replay path for backfills."

### 6.2 The whiteboard walk

Draw the one-line architecture, then annotate each arrow with *the failure
it handles*: Kafka arrow → "durable buffer, replay"; Pub/Sub arrow →
"ordered delivery, DLQ policy"; Dataflow box → "dedup, windowing,
watermark"; Bronze→Silver arrow → "idempotent MERGE"; Silver→Gold → "business
logic as views." Interviewers care that you know *why each edge exists*.

### 6.3 The "tell me about a hard problem" answer

Pick one war story from Part 5 (A3, the SDK container crash, is the
strongest) and walk it: symptom you saw → how you localized it (read the
*worker* logs, not the job-message logs) → the root cause (launcher image ≠
worker image) → the fix (dual-purpose image + `sdk_container_image`) → the
lesson. This demonstrates *diagnosis*, which is what senior interviews probe.

### 6.4 Curated Q&A

The full bank is [docs/interview-questions.md](docs/interview-questions.md).
The five you must be able to answer cold:

1. *"Is this exactly-once?"* → No — effectively-once via at-least-once
   delivery + idempotent processing. (§3.2)
2. *"Why Kafka AND Pub/Sub?"* → Kafka models on-prem/replay; Pub/Sub is the
   cloud front door Dataflow reads natively. (§1)
3. *"How do you handle a schema change?"* → additive optional field deployed
   first; breaking change → new topic version. (§3.3)
4. *"What happens to a malformed event?"* → DLQ, not retried, alertable —
   never reaches Bronze. (§3.4)
5. *"How would you backfill three months?"* → replay from the GCS archive
   through the same idempotent transforms, not from Kafka. (§3.8)

### 6.5 Red flags to avoid (things that lose credibility)

- **Don't claim exactly-once end-to-end.** It's a tell that you haven't
  thought about it. Say effectively-once and explain the layering.
- **Don't say "Dataflow autoscaling handles everything."** Know that it
  bills continuously and that you drain it to control cost.
- **Don't hand-wave the medallion as "best practice."** Give the *reason*:
  Bronze is replayable raw fidelity; Silver is conformed/deduped; Gold is
  business logic — each independently testable and re-runnable.
- **Don't hide the gaps.** Naming known limitations (the GCS archive write
  pending a `fileio.WriteToFiles` rewrite; the synthetic generator emitting
  independent events, not correlated lifecycles) reads as *senior*, not
  weak. See §6.6.

### 6.6 Known limitations (state these proactively — it's a strength)

- **Synthetic data is uncorrelated.** The generator emits independent events
  with random IDs, so cross-event metrics (order SLA, shipment transit time)
  are empty. Single-event metrics (status mix, low-stock, returns by reason,
  supplier delay rate) are real. *Fix on the roadmap:* a stateful generator
  that advances entities through their lifecycle.
- **GCS raw archive is temporarily disabled** (batch `WriteToText` is
  streaming-incompatible; pending `fileio.WriteToFiles`).
- **WIF pool** needs an undelete+import after a destroy/recreate cycle (WIF
  pools soft-delete for 30 days).
- **BigQuery writes are `STREAMING_INSERTS`** (at-least-once) rather than the
  Storage Write API (exactly-once) — a deliberate simplification, correct
  because of downstream dedup; the upgrade path is documented.

Being able to list these — and the fix for each — is exactly what makes the
project defensible rather than a black box.

---

## Part 7 — Glossary

- **Bronze/Silver/Gold (Medallion):** raw → cleaned/deduped → business marts.
- **DLQ (dead-letter queue):** where unprocessable messages are quarantined.
- **Poison message:** one that fails every retry identically.
- **Watermark:** the pipeline's estimate that all events before time T have
  arrived.
- **Allowed lateness:** how long after a window closes late events are still
  accepted.
- **Idempotent:** running twice = running once.
- **Effectively-once:** at-least-once delivery + idempotent processing.
- **KRaft:** Kafka's ZooKeeper-less consensus mode.
- **Flex Template:** a containerized Dataflow pipeline template.
- **WIF (Workload Identity Federation):** keyless cloud auth via OIDC.
- **Service agent:** a Google-managed identity for a GCP service.
- **Partition pruning / clustering:** BigQuery skipping data it doesn't need
  to scan.

---

## Part 8 — Where everything lives

| I want to… | Go to |
|---|---|
| Deploy it myself, step by step | [RUNBOOK.md](RUNBOOK.md) |
| Understand the architecture deeply | [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md) |
| See the data flow visually | [docs/diagrams/sequence/](docs/diagrams/sequence/), [docs/diagrams/network/](docs/diagrams/network/) |
| Understand Kafka topic design | [docs/architecture/kafka-topic-design.md](docs/architecture/kafka-topic-design.md) |
| Understand every IAM grant | [docs/security-guide.md](docs/security-guide.md) |
| Run / understand the tests | [docs/testing-guide.md](docs/testing-guide.md) |
| Understand monitoring & alerts | [docs/monitoring-guide.md](docs/monitoring-guide.md) |
| Triage a failure | [docs/troubleshooting-guide.md](docs/troubleshooting-guide.md) |
| Control cost | [docs/cost-optimization.md](docs/cost-optimization.md) |
| Read the event/API contracts | [docs/api/README.md](docs/api/README.md) |
| Understand the Terraform layout | [infra/terraform/README.md](infra/terraform/README.md) |
| Build the dashboards | [looker/dashboard-spec.md](looker/dashboard-spec.md) |
| See the running decision log | [docs/lessons-learned.md](docs/lessons-learned.md) |
| Prep for interviews | [docs/interview-questions.md](docs/interview-questions.md) + Part 6 above |

---

*This handbook is the front door. If you can explain Parts 1–3, have done
Part 4, and can tell two stories from Part 5, you can defend this project to
anyone.*
