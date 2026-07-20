# Phase 5 — Ingestion: Land the Five Sources to Bronze

> The 15-step walkthrough for the metadata-driven ingestion layer: per-format
> extractors (SFTP/REST/JDBC/GCS) that land all five sources to Bronze Parquet
> with checksum dedup, watermark incremental, archive, and full audit.

---

## 1. Objectives

- **Config-driven** ingestion: `config/sources/*.yaml` declares each source and
  its entities (load type, keys, watermark) — onboarding a table is a config row.
- One uniform **Bronze contract** from five wildly different inputs.
- **Idempotent** landing (checksum dedup), **incremental** (watermarks),
  **archived** originals, **audited** runs (batch/file audit + metrics envelope).

## 2. Theory

- **Bronze = raw + lineage, schema-on-read.** Business columns are stored **as
  strings**, nulls preserved; typing/cleaning is Silver's job (Phase 6). This is
  what makes ingestion robust to a column that mixes numbers and text (Excel
  `' 310.9 '`) — it would otherwise break Parquet's one-type-per-column rule.
- **Idempotency via content checksum** (ADR-0007): a file already seen (by SHA-256)
  is skipped, so re-running a batch converges. For multi-sheet Excel the dedup key
  is `checksum:sheet`.
- **Watermarks** advance per entity for incremental loads (max of the watermark
  column across landed rows).
- **Archive**: originals are copied to an archive path (enterprise usually *moves*;
  we copy so the demo stays replayable).

## 3. Business Context

Five sources, five protocols/formats. Without a framework you'd write (and
maintain) a bespoke pipeline per entity. The metadata-driven approach converges
them into one Bronze contract and one audited code path, which is exactly how a
real platform onboards the 20th and 200th feed without new code.

## 4. Architecture

```
config/sources/<source>.yaml  ──►  Extractor.run_source(cfg, date)
                                        │
 LandingStore (local fs / GCS) ◄────────┤ discover files/rows
        │ checksum + is_file_seen? ─────┤ (skip duplicates → file_audit)
        ▼                               │ read (csv/json/parquet/xlsx/jdbc)
 read bytes ──► readers.read_entity ──► write_bronze (+ 7 audit cols)
                                        │  data/bronze/<src>/<entity>/ingest_date=<d>/<batch>.parquet
                                        ├─ archive original
                                        ├─ advance watermark (incremental)
                                        └─ batch_audit + metrics (rows read/written/rejected)
```

## 5. Folder Creation

[`ingestion/`](../ingestion) (landing, readers, bronze, jdbc, extractor, run) and
[`config/sources/`](../config/sources) (5 source configs).

## 6. Infrastructure

No new cloud infra. Locally the `LandingStore` is the filesystem and Bronze lands
under `data/bronze/`. In the cloud the *same code* uses `GcsLandingStore` and the
`landing`/`bronze` buckets from Phase 3, and `BigQueryMetadataStore` for audit —
swapped via config/flags, no logic change.

## 7. Implementation

| File | Role |
|---|---|
| `landing.py` | `LandingStore` (local + GCS), SHA-256 checksums, archive |
| `readers.py` | CSV (delimiter, leading zeros), JSON (records), Parquet, Excel (skip title row) |
| `jdbc.py` | PostgreSQL/WMS incremental reader (lazy psycopg2, injectable connect) |
| `bronze.py` | audit columns + `row_hash`, string-typed Bronze Parquet writer |
| `extractor.py` | orchestrator: discover → dedup → read → write → archive → audit → watermark |
| `run.py` | CLI (`--source`, `--entity`, `--date`, `--bq-project/-dataset`) |

## 8. Testing / Verification

- **Unit/e2e tests: 63 passing** (+11 ingestion: bronze, readers, extractor
  idempotency/watermark/missing-file).
- **Real run** against the Phase-2 data (`2026-07-19`), four file-based sources:

  | Source | Rows | Bronze files | Notes |
  |---|---|---|---|
  | sap_erp | 2701 | 5 | pipe-CSV; 15 `XXX`-currency rows carried through raw |
  | salesforce | 155 | 4 | JSON; per-entity watermark set |
  | tms | 600 | 1 | Parquet promoted |
  | supplier_portal | 1396 | 4 | messy Excel; `' 310.9 '` preserved as string |

  Re-running `sap_erp` → **0 processed / 5 skipped** (checksum idempotency).
  Audit: 5 `batch_audit`, 19 `file_audit`, 6 watermarks.
- **WMS (JDBC)** is implemented but needs the live Postgres from Phase 2
  (`docker compose up` + `scripts/seed_wms.py`); run
  `python -m ingestion.run --source wms --date <d>` once it's up.

## 9. Documentation

This doc + `ingestion/` & `config/` READMEs + PROJECT_PROGRESS.

## 10. Code Review notes

- **Bronze-as-strings** was a deliberate fix after the messy-Excel `unit_price`
  column (mixed float/text) broke Parquet's single-type rule. Documented as the
  Bronze contract, not a workaround.
- **Cross-run dedup is real**: because `file_audit` persists checksums, a source
  that partially processed in an earlier run correctly skips already-landed
  entities on the next run — surfaced during testing and kept (it's the feature).
- CSV nulls arrive as empty strings (CSV has no null); Bronze preserves `''`, and
  the DQ `NotNull` rule already treats `''` as a failure.

## 11. Interview Questions

- *Why store Bronze as strings?* Schema-on-read: raw fidelity + robustness to
  dirty/mixed columns; casting belongs in Silver where DQ can gate it.
- *How is re-running a batch safe?* SHA-256 file dedup + watermark + string-keyed
  output paths — the run converges (idempotency, ADR-0007).
- *How do you add a new source table?* Add an entity to the YAML — no code.
- *How does the same code run locally and on GCP?* `LandingStore` and
  `MetadataStore` are interfaces; swap filesystem→GCS and JSONL→BigQuery.
- *How do you handle multi-sheet Excel dedup?* Dedup key is `checksum:sheet`.

## 12. Best Practices applied

Config over code; interface-based storage (local↔cloud); content-hash idempotency;
per-entity watermarks; structured audit + metrics envelope; raw immutable Bronze;
lazy heavy deps (pandas/psycopg2 only where needed).

## 13. Common Mistakes (avoided)

Typing in Bronze (brittle); moving files out of landing before success; appending
without dedup (double counts); losing leading zeros on SAP SKUs; failing the whole
run on one missing file (we warn and continue).

## 14. Cost Considerations

**Local: $0.** In the cloud, ingestion is GCS object reads/writes + small
BigQuery streaming inserts for audit — **pennies**. No compute cluster involved
(extractors are plain Python; Spark starts in Phase 6).

## 15. Next Steps

**Phase 6 — Spark Bronze → Silver:** schema validation & evolution, typing,
dedup, the DQ framework as a Spark gate (quarantine), SCD1/SCD2 via Iceberg
`MERGE INTO`, idempotency — on local Spark and Dataproc Serverless.

---

## Run it

```bash
pip install -e common                 # once, so scb_common resolves for `-m`
python -m data_generators.generate --source all --date 2026-07-19
python -m ingestion.run --source all  --date 2026-07-19       # (wms needs live Postgres)
# audit lands in data/_audit/*.jsonl ; Bronze under data/bronze/
```
