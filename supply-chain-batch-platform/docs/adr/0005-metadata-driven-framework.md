# ADR-0005 — Metadata-driven pipeline framework

**Status:** Proposed · **Date:** 2026-07-19

## Context
Five sources with ~20+ entities, each needing extract → Bronze → Silver with
different load types, schemas, keys, and DQ rules. Hand-coding a bespoke pipeline
per entity does not scale and is a maintenance trap.

## Options
1. **One pipeline per entity (imperative).** Simple to start, explicit. But N
   near-duplicate scripts; adding a table = copy/paste; drift across pipelines.
2. **Fully generic single engine (config only).** Maximum reuse, but risks an
   over-abstracted "framework" that's hard to debug and hides edge cases.
3. **Metadata-driven with escape hatches.** ✅ Config (`config/*.yaml` + BigQuery
   control tables) drives the common path; per-entity overrides/custom transforms
   allowed where needed.

## Decision
**Option 3.** A config-driven framework: `pipeline_control` + `source_config`
(BigQuery) and YAML in `config/` declare *what* runs, *how* (full/incremental),
*schema*, *keys*, *DQ rules*, and *targets*. The engine reads config and executes;
unusual entities register a custom transform hook.

## Consequences
- ➕ Adding a table ≈ adding a config row, not a new pipeline.
- ➕ Central visibility of every pipeline's behavior; consistent audit/DQ.
- ➕ Enables dynamic Airflow DAG generation from the same metadata.
- ➖ Upfront framework investment; needs good logging to debug config-driven runs.
- ➖ Risk of over-generalization — mitigated by allowing per-entity overrides.

## Enterprise vs Portfolio
- **Enterprise:** metadata in a governed store (often the same control DB),
  UI/self-service onboarding of new feeds, lineage integration.
- **Portfolio:** YAML + BigQuery control tables, version-controlled in `config/`.
