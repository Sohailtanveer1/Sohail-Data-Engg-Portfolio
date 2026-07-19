# Phase 2 — Local Development Environment, Data Generators & the `common` Library

> The full 15-step walkthrough for Phase 2. Everything here runs on your laptop at
> **$0 GCP cost**. It is the foundation every later phase imports.

---

## 1. Objectives

- Emulate all **five source systems** locally in their real formats and protocols.
- Build **`scb_common`** — the shared library (logging, config, batch context,
  schema contracts, data-quality, retry, metadata/audit) reused by ingestion,
  Spark, and Airflow.
- Stand up a **Docker stack** (Postgres/WMS, mock Salesforce REST API, SFTP).
- Make it all **tested and reproducible** before a single cloud resource exists.

## 2. Theory (the ideas that matter here)

- **Fixtures before infrastructure.** Realistic, *dirty* test data generated
  deterministically lets us build and prove every downstream feature (DQ, SCD,
  idempotency) without waiting on cloud or real feeds.
- **Shared kernel.** A single library for cross-cutting concerns prevents the
  "every pipeline logs/validates differently" drift. Define once, reuse everywhere.
- **Engine-agnostic contracts.** Schema and DQ rules are *data* (dataclasses /
  config), evaluated over `list[dict]` now and over Spark DataFrames in Phase 6 —
  the same rule objects, two evaluators (ADR-0004, ADR-0005, ADR-0010).
- **Dependency hygiene.** `scb_common` core depends only on PyYAML, so it imports
  fast and tests in milliseconds; Spark is an optional extra.

## 3. Business Context

Real supply-chain feeds are messy: SAP leading-zero SKUs, negative quantities,
invalid currencies, null business keys, and human-authored Excel with title rows
and numbers-as-text. If we only test on clean data, the platform looks great in
dev and breaks in production. So the generators **inject controlled dirt**
(`--dirty` fraction) and the `common` DQ framework is built to catch exactly
these classes of error from day one.

## 4. Architecture (Phase 2 slice)

```
data_generators/  --writes-->  data/landing/<source>/<date>/...   (native formats)
      │                              │
      │                              ├── sap_erp/*.csv  + _SUCCESS   -> served by SFTP
      │                              ├── salesforce/*.json          -> served by mock API
      │                              ├── wms/*.csv                  -> loaded into Postgres
      │                              ├── tms/ship_date=.../*.parquet
      │                              └── supplier_portal/*.xlsx + _SUCCESS -> SFTP
      ▼
  scb_common  (imported by generators' integration tests today; by ingestion/Spark/Airflow later)
      logging · config · context(batch_id) · schema · dq · retry · metadata
```

Local Docker services: **postgres** (WMS source), **mock-salesforce** (Flask REST
API with pagination + `?since=` incremental), **sftp** (SAP + Supplier drops).

## 5. Folder Creation

Populated this phase: [`common/`](../common), [`data_generators/`](../data_generators),
[`local/`](../local), [`scripts/`](../scripts), [`tests/`](../tests). Each already
carries a README from Phase 1.

## 6. Infrastructure (local only)

[`local/docker-compose.yml`](../local/docker-compose.yml) defines postgres,
mock-salesforce (built from [`local/mock_salesforce/`](../local/mock_salesforce)),
and sftp. Config comes from `local/.env` (copy from `.env.example`). Postgres
schema is created by [`local/postgres/init.sql`](../local/postgres/init.sql).

## 7. Implementation

- **`scb_common`** — see [common/scb_common/](../common/scb_common): `logging.py`
  (structured JSON + the metrics envelope), `context.py` (`batch_id`), `config.py`
  (`${ENV:default}` interpolation), `schema.py` (contracts + additive evolution),
  `dq.py` (declarative rules + quarantine + thresholds), `retry.py` (backoff),
  `metadata.py` (batch/file/DQ audit + watermark store, in-memory & JSONL).
- **Generators** — [data_generators/](../data_generators): shared `reference.py`
  keeps keys consistent across sources; each source module builds pure-Python rows;
  `generate.py` serializes to native formats.
- **Local services** — mock Salesforce API and WMS seed loader.

## 8. Testing

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e common -e data_generators
pytest -q
```

**Result in the authoring session: 46 passed** — 36 `common`, 7 generators,
3 integration (generate → schema-validate → DQ-quarantine). A real all-source
generation was run and produced every native-format file. The full local stack
bring-up is driven by `scripts/bootstrap_local.ps1` (needs Docker Desktop running).

## 9. Documentation

This document + updated folder READMEs + [PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

## 10. Code Review notes (self-review)

- Fixed a real logging bug: the stdout handler bound `sys.stdout` once, which
  breaks under `capsys`/redirected output — now resolved at emit time.
- Removed `__init__.py` from test dirs to avoid three colliding `tests` packages.
- `Unique` is dataset-level (not row-level) by design; DQ `evaluate` treats it
  specially. Business-key uniqueness for composite keys (PO number+line) is a
  Phase 6 concern once we compute a composite key column.

## 11. Interview Questions

- *Why generate dirty data on purpose?* To prove the DQ framework and error paths,
  not just the happy path — the difference between a demo and a platform.
- *Why is `batch_id` so central?* It correlates logs, audit tables, DQ results,
  and output partitions for one run; it's the key to observability and idempotency.
- *Why keep schema/DQ rules engine-agnostic?* Define the contract once, evaluate
  locally (fast tests) and in Spark (scale) — no logic duplication or drift.
- *Why Postgres in Docker instead of Cloud SQL?* Identical JDBC extraction
  experience at $0; Cloud SQL is the enterprise swap (cost doc §7).
- *How do you make re-running the seed safe?* `TRUNCATE` + `COPY` — idempotent.

## 12. Best Practices applied

Structured logging everywhere; config over code (no hard-coded secrets);
deterministic seeds for reproducibility; typed errors separating data vs infra
failures; dependency-light core; tests as first-class (46 before any cloud).

## 13. Common Mistakes (avoided)

- Treating SAP material numbers as ints (drops leading zeros) — kept as strings.
- `inferSchema`/implicit typing — we assert explicit contracts.
- Logging free-text — we log structured fields Cloud Logging can index.
- Blind re-runs — seed is idempotent; audit store dedups files by checksum.

## 14. Cost Considerations

**$0.** Everything is local (laptop + Docker Desktop). Postgres/mock-API/SFTP are
containers; the only "resource" is disk under `data/` (git-ignored). Cleanup:
`docker compose -f local/docker-compose.yml down -v`.

## 15. Next Steps

**Phase 3 — Terraform foundation (dev):** bootstrap remote state + CI deployer SA,
then `project_services`, `networking`, `iam`, `secret_manager`, `storage`, and a
$50 billing budget. First real (tiny) GCP spend; prove `apply`/`destroy` round-trips.

---

## Quickstart

```powershell
# one-time
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt; pip install -e common -e data_generators

# generate data + start the stack + seed WMS
powershell -File scripts\bootstrap_local.ps1 -Date 2026-07-19

# checks
curl http://localhost:8080/health
curl -H "Authorization: Bearer local-dev-token" "http://localhost:8080/api/Customer?limit=5"

# stop
docker compose -f local\docker-compose.yml down -v
```
