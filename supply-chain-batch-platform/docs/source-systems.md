# Source System Analysis

Five enterprise sources, each with a distinct protocol and format — chosen
deliberately so the platform demonstrates every major batch ingestion pattern
(file pull, API pagination, database extraction, cloud-native handoff, and messy
office formats). For each we cover: what it provides, extraction pattern,
load type, format trade-offs, real-world gotchas, and the local emulation.

---

## Format trade-offs (reference)

| Format | Pros | Cons | Enterprise use case |
|---|---|---|---|
| **CSV** | Universal, human-readable, streamable | No schema/types, delimiter/quoting hell, no nesting | ERP/legacy exports, interchange |
| **JSON** | Nested, self-describing, API-native | Verbose, no enforced schema, slow to parse at scale | REST APIs, event/config payloads |
| **Parquet** | Columnar, compressed, typed, predicate pushdown | Not human-readable, poor for row-level updates | Analytical lake storage (Bronze/Silver) |
| **Excel (.xlsx)** | Business-user friendly, multi-sheet | Merged cells, formulas, hidden rows, type chaos, not stream-friendly | Supplier/vendor manual submissions |
| **JDBC table** | Live/consistent, typed, pushdown filters | Load on source DB, connection/security, drift | Operational DB extraction (WMS) |

**Design consequence:** we normalize *all* of these to **Parquet in Bronze**
immediately, so downstream Silver/Gold logic never has to care about the source
format again.

---

## Source 1 — SAP ERP (SFTP / CSV / daily)

- **Provides:** Purchase Orders, Material Master, Vendors, Goods Receipt,
  Inventory Valuation.
- **Extraction pattern:** SFTP pull of a dated drop folder
  (`/outbound/<entity>/<YYYYMMDD>/*.csv`). File-arrival **sensor** waits for a
  `_SUCCESS`/manifest marker before processing (avoids reading half-written files).
- **Load type:** Master data (Material, Vendor) → **full** snapshot → SCD.
  Transactions (PO, Goods Receipt) → **incremental** by document date.
- **Gotchas:** SAP CSVs use `|` or `;` delimiters, code-page/encoding issues,
  leading-zero material numbers (must stay strings), and "delta files" that are
  actually full dumps. Numeric fields sometimes carry trailing sign (`100-`).
- **Local emulation:** `data_generators/sap_erp.py` writes dated CSVs to a local
  SFTP volume (Docker) → an extractor lands them to GCS.

## Source 2 — Salesforce CRM (REST API / JSON / hourly incremental)

- **Provides:** Customers, Accounts, Sales Reps, Credit Information.
- **Extraction pattern:** Authenticated REST calls with **pagination** and an
  incremental filter (`SystemModstamp > watermark`). Token stored in Secret
  Manager. Handle **rate limits** (429 → backoff) and paginated cursors.
- **Load type:** **incremental** by `SystemModstamp`; watermark persisted per
  object in the `watermark` table.
- **Gotchas:** API limits, soft-deleted records (`IsDeleted`), field-level
  changes without a reliable delete feed (need periodic full reconcile),
  nested/related objects requiring multiple calls.
- **Local emulation:** a small Flask/FastAPI "mock Salesforce" in Docker that
  serves paginated JSON with `modstamp` filtering.

## Source 3 — Warehouse Management System (PostgreSQL / JDBC / every 4h)

- **Provides:** Inventory, Warehouse Locations, Stock Movement, Cycle Counts.
- **Extraction pattern:** Spark **JDBC** read with a **partition column**
  (`numPartitions`, `partitionColumn`, `lowerBound/upperBound`) to parallelize
  and avoid hammering the source. Incremental via `updated_at > watermark` or an
  append-only movement id.
- **Load type:** Inventory/Locations → **full-ish** snapshot every 4h;
  Stock Movement → **incremental append** by movement id.
- **Gotchas:** long-running queries locking the OLTP DB (use a read replica in
  prod), timezone columns, schema drift when the WMS is upgraded.
- **Local emulation:** real **PostgreSQL in Docker** seeded by a generator — this
  is genuinely representative (Spark JDBC against a live Postgres).

## Source 4 — Transportation Management System (GCS export / Parquet / daily)

- **Provides:** Shipments, Carrier Information, Delivery Status, Routes,
  Freight Cost.
- **Extraction pattern:** The TMS already **exports Parquet to a GCS bucket**;
  we simply detect the daily prefix and promote it to Bronze (cheapest possible
  ingestion — no reformatting). GCS-object **sensor** on the dated prefix.
- **Load type:** **incremental** by ship date / export partition.
- **Gotchas:** partial-day exports, schema evolution in the Parquet files
  (new columns), duplicate re-exports (dedup on shipment id + version).
- **Local emulation:** generator writes partitioned Parquet directly to the GCS
  landing bucket (or a local `local/gcs` folder in dev).

## Source 5 — Supplier Portal (SFTP / Excel .xlsx / daily)

- **Provides:** Supplier Catalog, Price Lists, Lead Time, Minimum Order Quantity.
- **Extraction pattern:** SFTP pull of `.xlsx` workbooks (often multi-sheet:
  one sheet per price region). Parsed with pandas/openpyxl in the extractor and
  normalized to Parquet in Bronze.
- **Load type:** **full** snapshot daily (catalog is a current-state document) →
  SCD on supplier/price.
- **Gotchas:** the classic Excel nightmares — merged header cells, a title row
  above the real header, formula cells, blank trailing rows, numbers stored as
  text, and sheets renamed by whoever uploaded them. Robust parsing + DQ is
  essential.
- **Local emulation:** generator writes `.xlsx` (with deliberately messy quirks
  so the DQ framework has something real to catch) to the SFTP volume.

---

## Why this mix is deliberate (interview framing)

Each source forces a different, genuinely enterprise skill:
- SAP → **file sensing, delimiter/encoding robustness, full-vs-incremental**.
- Salesforce → **API pagination, rate-limit backoff, watermarking, secrets**.
- WMS → **parallel JDBC extraction without hurting the OLTP source**.
- TMS → **cloud-native cheap handoff (Parquet already lake-ready)**.
- Supplier → **taming messy human-authored Excel with data quality gates**.

Together they justify a **metadata-driven** framework: five wildly different
inputs converging into one uniform Bronze contract via per-source connectors.
