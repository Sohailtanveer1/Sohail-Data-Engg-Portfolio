# config/

Metadata-driven pipeline configuration (YAML): per-source connection settings and
per-entity load type (full/incremental), schema contract, business keys, DQ
rules, and targets. This is what makes onboarding a new table a config change,
not a code change. See [ADR-0005](../docs/adr/0005-metadata-driven-framework.md).
**Populated in Phase 5.**
