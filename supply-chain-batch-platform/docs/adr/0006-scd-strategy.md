# ADR-0006 — Slowly Changing Dimension strategy

**Status:** Proposed · **Date:** 2026-07-19

## Context
Dimension attributes change over time (a material's standard cost, a customer's
credit limit, a vendor's payment terms). Some analyses need point-in-time
history ("what was the credit limit when this order shipped?"); others only need
the current value. We must choose per dimension.

## Options
1. **SCD1 everywhere (overwrite).** Simple, small tables. Loses history — wrong
   for facts that must reflect attributes *as of* their date.
2. **SCD2 everywhere (versioned rows).** Full history, but larger tables and more
   complex joins where history adds no value (e.g. carrier name).
3. **Per-dimension choice.** ✅ SCD2 where history matters, SCD1 where it doesn't.

## Decision
**Option 3.**
- **SCD2:** `dim_material`, `dim_vendor`/`dim_supplier`, `dim_customer` — history
  drives point-in-time correctness of facts.
- **SCD1:** `dim_warehouse`, `dim_carrier`, `dim_sales_rep` — corrections
  overwrite; no historical-attribute analysis required.

**SCD2 mechanics:** surrogate key per version; `effective_from`/`effective_to`;
`is_current`; a `row_hash` over tracked attributes for change detection; Iceberg
`MERGE INTO` closes the old row (`effective_to`, `is_current=false`) and inserts
the new one atomically.

## Consequences
- ➕ Correct point-in-time joins where needed; lean tables elsewhere.
- ➕ Hash-based detection avoids spurious new versions.
- ➖ SCD2 joins are date-ranged (fact date between effective_from/to).
- ➖ SCD2 is bug-prone (overlaps/duplicate current rows) → covered by unit tests.

## Enterprise vs Portfolio
- **Enterprise:** may add SCD3 (limited prior value) or mini-dimensions for
  fast-changing attributes; governed effective-dating standards.
- **Portfolio:** SCD1/SCD2 as above, thoroughly tested — the common interview set.
