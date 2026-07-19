# Testing Guide

## What's actually tested (verified, not aspirational)

Every test file in this repo has been run and passes — not just written.
Current counts:

| Suite | Location | Count | What it covers |
|---|---|---|---|
| Common library | `tests/unit/test_schema_validator.py` | 6 | JSON Schema validation: valid events pass, missing/wrong-typed/extra fields fail |
| Retry/backoff | `tests/unit/test_retry.py` | 4 | Succeeds first try, succeeds after transient failures, gives up after max attempts, doesn't retry unlisted exceptions |
| Config/naming | `tests/unit/test_config.py` | 5 | Topic naming, DLQ naming, partition key derivation (single and composite keys) |
| Event generator | `tests/unit/test_event_generator.py` | 3 | Every domain's generator produces schema-valid events; `make_malformed` reliably breaks validation; `make_late` backdates but stays valid |
| Beam: parse/validate | `dataflow/tests/test_parse_and_validate.py` | 3 | Valid event routes to `valid` tag; invalid JSON and schema failures route to `dlq` tag |
| Beam: dedup | `dataflow/tests/test_deduplicate.py` | 1 | Duplicate `event_id` within a window is dropped; distinct IDs pass through |
| Beam: windowing | `dataflow/tests/test_windowing.py` | 1 | An event within `allowed_lateness` of a closed window is still emitted (TestStream-driven watermark control) |

**Total: 23 tests, all passing**, run against Python 3.12 (see the
Python-version note below).

## Running the tests

```bash
# Common + Kafka producer/generator logic — no GCP or Kafka needed
pip install -r requirements-dev.txt
pip install -e common
pip install jsonschema
pytest tests/unit -v

# Beam/Dataflow transforms — needs Python 3.11 or 3.12 specifically
pip install -r dataflow/pipelines/requirements.txt
pytest dataflow/tests -v
```

**Why Python version matters here:** `apache-beam` does not support every
Python version immediately after release (confirmed while building this —
`apache-beam==2.57.0` fails to build on Python 3.14 with a `pkg_resources`
/ `grpcio-tools` build error). Use a dedicated virtualenv on 3.11 or 3.12
for anything touching `dataflow/`. This isn't a hypothetical caveat — it's
exactly the failure encountered building this repo, documented here so it
doesn't cost you the same debugging time.

## Testing strategy by layer

**Schema validation (unit):** the highest-leverage tests in the repo — a
regression here means bad data silently reaches BigQuery instead of being
quarantined. Covered thoroughly (valid, missing field, wrong type, extra
field) because the cost of a false negative is high and the cost of
writing the test is low.

**Beam transforms (unit, via `TestPipeline`/`TestStream`):** each DoFn is
tested in isolation with fake inputs, not against a live Pub/Sub
subscription. `TestStream` specifically is what makes watermark/lateness
behavior testable without deploying anything — see `test_windowing.py`
for the pattern: advance the watermark explicitly, assert on what a window
does and doesn't emit.

**Terraform (`terraform validate` + `fmt -check` in CI):** validated for
syntax and internal consistency on every PR
(`.github/workflows/ci.yml`'s `terraform-fmt-and-validate` job, run with
`-backend=false` so it needs no real credentials). `terraform plan`
against the real dev project also runs in CI, but only for PRs from this
repo directly (not forks, which have no access to the deploy credentials)
— see the `terraform-plan-dev` job's `if` condition.

## What's NOT automated (and why)

**Integration tests against a live Kafka cluster.** `tests/integration/`
exists as a placeholder for this — a true integration test (producer →
Kafka → consumer, asserting messages round-trip and DLQ routing works
against a real broker) needs Kafka actually running, which CI doesn't
stand up by default in this repo (no `docker compose up` step in
`ci.yml`). Adding a CI job that spins up `kafka/docker/docker-compose.yml`
and runs a real produce/consume round trip is the natural next addition —
flagged here rather than silently left out.

**End-to-end pipeline tests against real GCP resources.** No test in this
repo launches an actual Dataflow job or writes to real BigQuery — that
would require a live GCP project on every CI run, with real cost and much
slower feedback than the DoFn-level unit tests provide. The Beam unit
tests are the intentional trade-off: fast, free, and they cover the actual
logic (validation, dedup, windowing) that's most likely to have a bug —
what they don't cover is "does this deploy and run correctly against real
GCP infrastructure," which is inherently a manual verification step (see
`docs/setup-guide.md`) the first time a change touches the pipeline's
deployment shape.

**`terraform apply` in CI beyond dev.** uat/prod applies are gated behind
manual `workflow_dispatch` + GitHub Environment approval
(`.github/workflows/cd-promote.yml`) — deliberately not automatically
tested/applied on every push, since an uat/prod apply is a real-world
action with real cost and real blast radius, not something that should
happen as a side effect of CI running.

## Common mistakes this test suite is built to catch

- A schema change that isn't reflected in the event generator (`test_event_generator.py`
  would fail — the generator's output is validated against the live schema,
  not a frozen fixture).
- A DoFn that accidentally lets a malformed event through to the `valid`
  tag instead of `dlq` (`test_parse_and_validate.py`).
- A dedup regression that lets a duplicate `event_id` through
  (`test_deduplicate.py`).
- A windowing/lateness config change that silently starts dropping events
  that should still be within the allowed lateness window
  (`test_windowing.py`).
