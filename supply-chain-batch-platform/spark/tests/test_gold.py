"""Unit tests for the pure Gold builders (no SparkSession needed)."""

from datetime import date

from spark.transforms.gold import (
    DimJoin,
    build_fact_select,
    generate_dim_date,
    pit_join_clause,
)


def test_generate_dim_date_range_and_fields():
    rows = generate_dim_date(date(2026, 1, 1), date(2026, 1, 31))
    assert len(rows) == 31
    jan1 = rows[0]
    assert jan1["date_key"] == 20260101
    assert jan1["quarter"] == 1 and jan1["month"] == 1
    assert jan1["day_of_week"] == 4          # 2026-01-01 is a Thursday
    assert jan1["is_weekend"] is False
    # a Saturday
    sat = next(r for r in rows if r["date"] == "2026-01-03")
    assert sat["is_weekend"] is True


def test_fiscal_year_respects_start_month():
    rows = generate_dim_date(date(2026, 1, 15), date(2026, 1, 15), fiscal_start_month=2)
    assert rows[0]["fiscal_year"] == 2025     # Jan is before the Feb fiscal start


def test_pit_join_scd2_uses_effective_dating():
    dim = DimJoin(name="dim_material", table="scb.silver.material",
                  business_key="material_id", sk_column="material_sk",
                  scd="scd2", fact_date="order_date")
    clause = pit_join_clause(dim)
    assert "dim_material.`material_id` = f.`material_id`" in clause
    assert "f.`order_date` >= dim_material.`effective_from`" in clause
    assert "f.`order_date` < dim_material.`effective_to`" in clause


def test_pit_join_scd1_is_key_only():
    dim = DimJoin(name="dim_warehouse", table="t", business_key="warehouse_id",
                  sk_column="warehouse_sk", scd="scd1")
    assert pit_join_clause(dim) == "dim_warehouse.`warehouse_id` = f.`warehouse_id`"


def test_build_fact_select_resolves_sks_and_measures():
    dims = [
        DimJoin(name="dim_material", table="scb.silver.material",
                business_key="material_id", sk_column="material_sk",
                scd="scd2", fact_date="order_date"),
    ]
    sql = build_fact_select(
        "scb.silver.purchase_order",
        surrogate_name="po_sk", surrogate_keys=["po_number", "po_line"],
        date_column="order_date", dims=dims,
        measures=[{"name": "order_qty"},
                  {"name": "line_amount", "expr": "order_qty * unit_price"}],
    )
    assert "AS `po_sk`" in sql
    assert "dim_material.`material_sk` AS `dim_material_sk`" in sql
    assert "(order_qty * unit_price) AS `line_amount`" in sql
    assert "LEFT JOIN scb.silver.material dim_material ON" in sql
    assert "FROM scb.silver.purchase_order f" in sql
