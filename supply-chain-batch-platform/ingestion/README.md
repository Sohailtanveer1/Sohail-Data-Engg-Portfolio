# ingestion/

Metadata-driven land-to-Bronze layer. **Implemented in Phase 5.**

| File | Role |
|---|---|
| `landing.py` | `LandingStore` (local fs + GCS), SHA-256 checksums, archive |
| `readers.py` | Format readers: CSV, JSON, Parquet, Excel |
| `jdbc.py` | PostgreSQL/WMS incremental reader (lazy psycopg2) |
| `bronze.py` | Audit columns + `row_hash`; string-typed Bronze Parquet |
| `extractor.py` | Orchestrator: discover → dedup → read → write → archive → audit → watermark |
| `run.py` | CLI entry point |

```bash
pip install -e common
python -m ingestion.run --source all --date 2026-07-19   # wms needs live Postgres
```

Driven by [`config/sources/*.yaml`](../config/sources). Bronze contract, dedup,
and idempotency: [docs/phase-05-ingestion.md](../docs/phase-05-ingestion.md).
