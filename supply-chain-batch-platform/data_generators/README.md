# data_generators/

Local Python generators that emulate the five source systems with realistic —
and deliberately messy — data so the DQ framework has real problems to catch.
**Implemented in Phase 2.**

| Module | Source | Output format |
|---|---|---|
| `sap_erp.py` | SAP ERP | CSV (pipe-delimited) + `_SUCCESS` |
| `salesforce.py` | Salesforce CRM | JSON (served by mock API) |
| `wms.py` | Warehouse Mgmt System | CSV (loaded into Postgres) |
| `tms.py` | Transportation Mgmt System | Parquet (partitioned by `ship_date`) |
| `supplier_portal.py` | Supplier Portal | Excel `.xlsx` (deliberately messy) + `_SUCCESS` |

`reference.py` holds shared, seeded reference data so keys line up across sources.

```
python -m data_generators.generate --source all --date 2026-07-19 --out data/landing
python -m data_generators.generate --source sap_erp --dirty 0.1   # more bad rows
```
