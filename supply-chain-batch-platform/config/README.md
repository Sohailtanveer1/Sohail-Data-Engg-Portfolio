# config/

Metadata-driven pipeline configuration (YAML). This is what makes onboarding a
new table a config change, not a code change ([ADR-0005](../docs/adr/0005-metadata-driven-framework.md)).

**`sources/` (Phase 5):** one file per source (`sap_erp`, `salesforce`, `wms`,
`tms`, `supplier_portal`) declaring `source_type`, `format`, landing/archive
paths, and per-entity `load_type` (full/incremental), `watermark_column`, and
`business_keys`. Consumed by [`ingestion/`](../ingestion).

Silver-layer DQ rules and schema contracts join here in Phase 6.
